# SPDX-License-Identifier: MIT

"""List a checked project's tracked files and read only those inside it.

Why this module exists. ``gate --all-perwrite`` lists the tracked files with
``git ls-files`` and reads each one, and the project may come with its ``.git``
folder from someone else, in an archive or a shared folder. git lists an index
entry exactly as the index holds it, and the working tree is whatever arrived,
so the list can point anywhere: an entry such as ``../x`` or an absolute path,
a symbolic link or Windows junction to a file or folder elsewhere, a named pipe
whose read waits for ever, a device, or a huge file. This module lists
the entries and reads only the regular files inside the project, and for every
other entry it says why it was not read, so the report can count them.
:func:`lstat_inside` also keeps ``link_check`` from looking up a link target
outside the project during a corpus run.

What it does not cover. The checks see the tree as it is when they run; a
program that swaps a folder for a link while the gate runs is out of their
reach, though each file's levels are checked right before it is read. A hard
link reads as an ordinary file, because nothing in it tells where the other
names of its data are; git and archive tools do not create one to a file
outside the project. And ``git ls-files`` itself reads the repository's own git
configuration: :func:`run_git` turns off the settings in it that start a
program, but others, such as an ``include.path`` that names a named pipe or a
network share, still apply (see ``_git.py``); the time limit bounds a wait one
of them causes.
"""

from __future__ import annotations

import codecs
import os
import stat
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Final

from apothem.conformity._git import run_git
from apothem.conformity._grep_base import GIT_LS_FILES_TIMEOUT_SECONDS

# The largest file the corpus run reads, in bytes. It is well above any text a
# project tracks, lockfiles and notebooks included; a larger tracked file is
# skipped and counted, so a huge file cannot use up the machine's memory.
MAX_FILE_BYTES: Final[int] = 64 * 1024 * 1024
# The block size for judging whether a file over the limit is text.
_SNIFF_BLOCK_BYTES: Final[int] = 1024 * 1024
# How long to wait before the one retry of an open refused because another
# program holds the file: such a hold is usually over by then.
_RETRY_DELAY_SECONDS: Final[float] = 0.2
# Windows' error for a file another program has open without sharing it.
_SHARING_VIOLATION: Final[int] = 32
# The share modes read, write and delete, so a probe open of a file conflicts
# only with a program that shares nothing.
_SHARE_ALL: Final[int] = 0x7
# How many leading bytes of a file over the limit may hold a NUL before it
# counts as binary: the span git looks at for the same question.
_BINARY_SNIFF_BYTES: Final[int] = 8000

# The index modes git gives a symbolic link and a submodule.
_LINK_MODE: Final[str] = "120000"
_SUBMODULE_MODE: Final[str] = "160000"

# Why a listed path was not read. The corpus report counts each one.
SKIP_OUTSIDE: Final[str] = "outside_project"
SKIP_UNSUPPORTED: Final[str] = "unsupported_name"
SKIP_LINK: Final[str] = "link"
SKIP_SUBMODULE: Final[str] = "submodule"
SKIP_NOT_REGULAR: Final[str] = "not_regular_file"
SKIP_MISSING: Final[str] = "missing"
SKIP_TOO_LARGE: Final[str] = "too_large"
SKIP_NOT_TEXT: Final[str] = "not_utf8_text"
SKIP_UNREADABLE: Final[str] = "unreadable"
SKIP_EXEMPT: Final[str] = "exempt"
SKIP_REASONS: Final[tuple[str, ...]] = (
    SKIP_OUTSIDE,
    SKIP_UNSUPPORTED,
    SKIP_LINK,
    SKIP_SUBMODULE,
    SKIP_NOT_REGULAR,
    SKIP_MISSING,
    SKIP_TOO_LARGE,
    SKIP_NOT_TEXT,
    SKIP_UNREADABLE,
    SKIP_EXEMPT,
)
# Reasons that fail the run: a path that leaves the project means the index
# was written by hand, and a file too large or impossible to read may hold a
# finding the run cannot see.
FAILING_SKIPS: Final[tuple[str, ...]] = (
    SKIP_OUTSIDE,
    SKIP_TOO_LARGE,
    SKIP_UNREADABLE,
)

# Windows device names. Current Windows reads them as a device only when
# they stand alone (``CON``, ``nul``); older versions also read them with an
# extension (``nul.yml``), and the regular-file check refuses those there.
_WINDOWS_DEVICE_NAMES: Final[frozenset[str]] = frozenset(
    {"con", "prn", "aux", "nul", "conin$", "conout$"}
    | {f"com{digit}" for digit in "123456789\u00b9\u00b2\u00b3"}
    | {f"lpt{digit}" for digit in "123456789\u00b9\u00b2\u00b3"}
)

# Characters no Windows file name can hold as written: a colon (a drive, as in
# ``a:b.md``, or a file stream), the folder separator, the characters Windows
# reserves, and the control characters.
_WINDOWS_UNHELD: Final[frozenset[str]] = frozenset(
    ':\\<>"|?*' + "".join(chr(code) for code in range(1, 32))
)

# Windows sets this bit in the tag of a reparse point that names another file or
# folder: a symbolic link, a junction or a WSL link. ``os.lstat`` reports a
# junction as a plain folder, so the tag is what shows it is a link.
_NAME_SURROGATE_TAG_BIT: Final[int] = 0x20000000


class CorpusListError(Exception):
    """The tracked-file list cannot be read; the message says why.

    The message is a fixed sentence with git's exit code at most. git's own
    error text is left out, because it can quote the repository's settings and
    name files outside the project.
    """


@dataclass(frozen=True)
class TrackedEntry:
    """One index entry: its path inside the root, its mode, and any name skip.

    *skip* is set when the name itself rules the entry out (see
    :func:`name_skip`); *path* is then the root, never read. *name* is the
    entry as git lists it, for a report that names the file.
    """

    path: Path
    mode: str
    skip: str | None = None
    name: str = ""


def tracked_entries(root: Path) -> list[TrackedEntry]:
    """Return the index entries under *root*, each path built from its git name.

    Runs ``git ls-files -s -z`` in *root* through :func:`run_git`, which turns
    off the repository's settings that start a program, gives git no input and
    decodes its output as UTF-8 with any other byte replaced, so a file name
    that is not UTF-8 names no file on disk and is skipped on its own instead
    of failing the run. The call gives up after
    :data:`GIT_LS_FILES_TIMEOUT_SECONDS`. A file with a merge conflict, which
    the index lists once per stage, is kept once, and counts as a link or a
    submodule when any of its stages does. Each name is judged as git writes
    it (see :func:`name_skip`); no path is resolved and no link is followed.

    Raises :class:`CorpusListError` when the list cannot be read: git cannot be
    started, git exits with an error (for example, *root* is not inside a git
    work tree), or git runs past the time limit.
    """
    try:
        completed = run_git(
            ["ls-files", "-s", "-z"],
            cwd=root,
            timeout=GIT_LS_FILES_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        raise CorpusListError(
            f"git ls-files did not finish within {GIT_LS_FILES_TIMEOUT_SECONDS} seconds"
        ) from exc
    except OSError as exc:
        raise CorpusListError("git did not start") from exc
    if completed.returncode != 0:
        raise CorpusListError(
            f"git ls-files failed with exit code {completed.returncode}"
        )
    modes: dict[str, str] = {}
    for record in completed.stdout.split("\0"):
        # Each record is "<mode> <object> <stage>\t<path>".
        details, tab, name = record.partition("\t")
        if not tab or not name:
            continue
        mode = details.split(" ", 1)[0]
        if name not in modes or mode in (_LINK_MODE, _SUBMODULE_MODE):
            modes[name] = mode
    entries: list[TrackedEntry] = []
    for name, mode in modes.items():
        skip = name_skip(name)
        if skip is None:
            path = root.joinpath(*name.split("/"))
            entries.append(TrackedEntry(path, mode, name=name))
        else:
            entries.append(TrackedEntry(root, mode, skip, name))
    return entries


def name_skip(name: str) -> str | None:
    """Return why a git *name* is not read on this system, or None to read it.

    git writes a name as parts joined by ``/``, and never an empty, ``.`` or
    ``..`` part, so a name with one (a leading ``/`` is an empty first part)
    was written by hand to reach outside the project: :data:`SKIP_OUTSIDE`.
    So is a part that names ``.git`` on Windows (see :func:`_names_git`),
    which git never writes either.
    On Windows, a part with a colon (``a:b.md`` reads as drive ``a:``, and a
    colon later in a part names a file stream), a backslash (a folder
    separator there), one of ``<>"|?*``, a control character, or a trailing
    dot or space (which Windows drops) cannot be held as written, and a device
    name such as ``CON`` or ``NUL``, or a short name such as ``GIT~2``, names
    something other than a project file. git on another system can write
    such a name, so it is skipped as :data:`SKIP_UNSUPPORTED`, which does not
    fail the run.
    """
    parts = name.split("/")
    if any(part in ("", ".", "..") or _names_git(part) for part in parts):
        return SKIP_OUTSIDE
    if os.name == "nt" and any(_windows_cannot_hold(part) for part in parts):
        return SKIP_UNSUPPORTED
    return None


def _names_git(part: str) -> bool:
    """Return True when *part* names the ``.git`` folder on Windows (NTFS).

    That is ``.git`` in any case, followed by nothing but dots and spaces
    (which Windows drops) or by a colon (a file stream), and ``GIT~1``, its
    usual Windows short name. git refuses all of these on every system by
    default (``core.protectNTFS``), so an index that holds one was written
    by hand.
    """
    base = part.split(":", 1)[0].rstrip(". ").casefold()
    return base in (".git", "git~1")


def _windows_cannot_hold(part: str) -> bool:
    """Return True when Windows cannot hold *part* as written, or reads it as
    something else: a device such as ``CON`` or ``NUL``, or a short name
    such as ``GIT~2``, which can stand for ``.git``."""
    if not _WINDOWS_UNHELD.isdisjoint(part) or part.endswith((".", " ")):
        return True
    bare = part.casefold()
    if bare in _WINDOWS_DEVICE_NAMES:
        return True
    digits = bare[4:]
    return bare.startswith("git~") and digits.isascii() and digits.isdigit()


def is_link(info: os.stat_result) -> bool:
    """Return True when *info*, from ``os.lstat``, describes a link of any kind."""
    if stat.S_ISLNK(info.st_mode):
        return True
    return bool(getattr(info, "st_reparse_tag", 0) & _NAME_SURROGATE_TAG_BIT)


def leaves_root(root: Path, path: Path) -> bool:
    """Return True when *path* is not inside *root* by its name alone.

    True for a path that is not below *root* (an absolute index entry replaces
    the root it is joined to) and for one with a ``..`` part. Nothing on disk is
    looked at.
    """
    try:
        parts = path.relative_to(root).parts
    except ValueError:
        return True
    return not parts or ".." in parts


def lstat_inside(root: Path, path: Path) -> os.stat_result | str:
    """Return ``os.lstat`` of *path*, or the reason it is out of reach.

    *path* is in reach only when it stays inside *root* and every level below
    *root*, *path* itself included, is reached without a symbolic link or a
    Windows junction. Each level is checked with ``os.lstat``, which never
    follows a link, so nothing outside *root* is looked up: the walk stops at
    the first link. The reasons are :data:`SKIP_OUTSIDE`, :data:`SKIP_LINK`,
    :data:`SKIP_MISSING` (a level does not exist, or one on the way is not a
    folder) and :data:`SKIP_UNREADABLE` (a level exists but cannot be looked
    at, for example for lack of permission). What the returned result
    describes (a regular file, a folder, a named pipe) is for the caller to
    judge.
    """
    if leaves_root(root, path):
        return SKIP_OUTSIDE
    parts = path.relative_to(root).parts
    current = root
    info: os.stat_result | None = None
    for depth, part in enumerate(parts, start=1):
        if info is not None and not stat.S_ISDIR(info.st_mode):
            return SKIP_MISSING
        current = current / part
        try:
            info = os.lstat(current)
        except (OSError, ValueError) as exc:
            # ValueError: a NUL in the name, which no file can have.
            return _missing_or_unreadable(exc)
        if is_link(info):
            return SKIP_LINK
        if depth == len(parts):
            return info
    return SKIP_MISSING


def _missing_or_unreadable(exc: BaseException) -> str:
    """Return the skip reason for an error looking at a path with ``os.lstat``.

    Only a refusal (``PermissionError``: no permission) means the path is there
    but cannot be looked at: :data:`SKIP_UNREADABLE`, which fails the run. Any
    other error, a name the system rejects or one too long for it included,
    means there is no such file here: :data:`SKIP_MISSING`.
    """
    if isinstance(exc, PermissionError):
        return SKIP_UNREADABLE
    return SKIP_MISSING


def _read_failure(exc: OSError) -> str:
    """Return the skip reason for an error opening or reading a regular file.

    ``os.lstat`` has just found the file, so only an error saying it is gone
    now (deleted, or a folder on the way replaced) means :data:`SKIP_MISSING`.
    Any other error, a refusal or a file the system cannot open (such as an
    online-only placeholder whose sync program is stopped), means the file is
    there but cannot be read: :data:`SKIP_UNREADABLE`, which fails the run.
    """
    if isinstance(exc, (FileNotFoundError, NotADirectoryError)):
        return SKIP_MISSING
    return SKIP_UNREADABLE


def _held_by_another_program(path: Path, exc: OSError) -> bool:
    """Return True when the refused open of *path* (*exc*) is worth one retry:
    another program has the file open without sharing it.

    Windows reports that as a refusal (``PermissionError``), but Python's
    ``open`` keeps only the C library's error number, not the Windows error,
    so the file is opened once more through the Windows API, which reports
    it. A refusal for lack of permission, or a file being deleted, is not
    worth a retry. Elsewhere, no program can hold a file this way.
    """
    if getattr(exc, "winerror", None) == _SHARING_VIOLATION:
        return True
    if sys.platform != "win32" or not isinstance(exc, PermissionError):
        return False
    import _winapi  # Windows only, so imported here.

    try:
        handle = _winapi.CreateFile(
            str(path), _winapi.GENERIC_READ, _SHARE_ALL, 0, _winapi.OPEN_EXISTING, 0, 0
        )
    except OSError as probe:
        return getattr(probe, "winerror", None) == _SHARING_VIOLATION
    # The file opens now: whatever held it has let go.
    _winapi.CloseHandle(handle)
    return True


def _read_file(path: Path) -> bytes | str:
    """Return the bytes of the regular file *path*, or why it was not read.

    The file is opened once per attempt, and each attempt starts afresh. An
    open refused because another program holds the file is tried once more
    after :data:`_RETRY_DELAY_SECONDS`, since such a hold is often brief. A
    refusal for lack of permission is not retried, and neither is an error
    while reading, such as a range of the file another program has locked.
    """
    for attempt in range(2):
        try:
            handle = path.open("rb")
        except OSError as exc:
            if attempt == 0 and _held_by_another_program(path, exc):
                time.sleep(_RETRY_DELAY_SECONDS)
                continue
            return _read_failure(exc)
        try:
            with handle:
                return _read_open_file(handle)
        except OSError as exc:
            return _read_failure(exc)
    return SKIP_UNREADABLE  # pragma: no cover - the loop always returns


def _read_open_file(handle: BinaryIO) -> bytes | str:
    """Return the bytes of the open file *handle*, or why they are not read.

    A file over :data:`MAX_FILE_BYTES` is judged by :func:`_oversized_reason`.
    Otherwise the first read asks for the file's size plus one byte, so a small
    file costs a small read, and a file that grew since is read on in blocks;
    one that grew past the limit is :data:`SKIP_TOO_LARGE`.
    """
    size = os.fstat(handle.fileno()).st_size
    if size > MAX_FILE_BYTES:
        return _oversized_reason(handle)
    blocks: list[bytes] = []
    total = 0
    wanted = size + 1
    while True:
        block = handle.read(wanted)
        blocks.append(block)
        total += len(block)
        if total > MAX_FILE_BYTES:
            return SKIP_TOO_LARGE
        if len(block) < wanted:
            return b"".join(blocks)
        wanted = min(_SNIFF_BLOCK_BYTES, MAX_FILE_BYTES + 1 - total)


def _oversized_reason(handle: BinaryIO) -> str:
    """Return the skip reason for an open file over :data:`MAX_FILE_BYTES`.

    The file is judged on all of its first :data:`MAX_FILE_BYTES` bytes, read
    in blocks. When they decode as UTF-8, the file is text the run cannot read,
    :data:`SKIP_TOO_LARGE`, which fails the run since a finding in it would go
    unseen; a character cut at the limit still counts as text. A NUL in the
    first :data:`_BINARY_SNIFF_BYTES` marks a binary file, as it does for git,
    so a large zero-filled image or UTF-16 file does not fail the run: like
    bytes that do not decode, it is :data:`SKIP_NOT_TEXT`. A NUL further on
    is text, as in a smaller file.
    """
    decoder = codecs.getincrementaldecoder("utf-8")()
    left = MAX_FILE_BYTES
    try:
        while left > 0:
            block = handle.read(min(_SNIFF_BLOCK_BYTES, left))
            if not block:
                # The file ended before the limit: a cut character is not text.
                decoder.decode(b"", final=True)
                break
            sniffed = MAX_FILE_BYTES - left
            if b"\0" in block[: max(0, _BINARY_SNIFF_BYTES - sniffed)]:
                return SKIP_NOT_TEXT
            left -= len(block)
            decoder.decode(block)
    except UnicodeDecodeError:
        return SKIP_NOT_TEXT
    return SKIP_TOO_LARGE


def read_entry(root: Path, entry: TrackedEntry) -> tuple[str | None, str | None]:
    """Return ``(text, None)`` for an entry the run reads, else ``(None, reason)``.

    An entry is read only when it stays inside *root*, its index mode is not a
    link or a submodule, every level below *root* is reached without a link
    (see :func:`lstat_inside`), it is a regular file, it holds at most
    :data:`MAX_FILE_BYTES`, and its bytes are UTF-8 text. A link is skipped even
    when it points inside *root*: git tracks a link as the path it holds, and a
    tracked file it points to is read under its own path. With
    ``core.symlinks=false``, git writes a tracked link as a small regular file
    that holds that path, so the index mode is checked as well. The text is read
    the way ``Path.read_text`` reads it, line endings turned into ``\\n``.
    """
    if entry.skip is not None:
        return None, entry.skip
    if leaves_root(root, entry.path):
        return None, SKIP_OUTSIDE
    if entry.mode == _LINK_MODE:
        return None, SKIP_LINK
    if entry.mode == _SUBMODULE_MODE:
        return None, SKIP_SUBMODULE
    info = lstat_inside(root, entry.path)
    if isinstance(info, str):
        return None, info
    if not stat.S_ISREG(info.st_mode):
        return None, SKIP_NOT_REGULAR
    data = _read_file(entry.path)
    if isinstance(data, str):
        return None, data
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return None, SKIP_NOT_TEXT
    return text.replace("\r\n", "\n").replace("\r", "\n"), None
