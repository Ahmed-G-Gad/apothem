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

What it does not cover. The checks see the tree as it is when they run. Each
file's levels are checked right before it is read, and the file opened must
be the one that check found, so a file swapped in between is not read; but a
folder above it that a program swaps for a link in between is followed. A hard
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
import errno
import os
import stat
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Final

from apothem.conformity._git import run_git, split_names
from apothem.conformity._grep_base import (
    GIT_LS_FILES_TIMEOUT_SECONDS,
    GitFailedError,
    GitTimeoutError,
    linked_git_message,
    nearest_linked_git_entry,
)
from apothem.conformity._project_paths import (
    NAME_SURROGATE_TAG_BIT,
    is_link,
)

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
# The share modes read, write and delete, so the gate's own open of a file on
# Windows conflicts only with a holder that does not share reading.
_SHARE_ALL: Final[int] = 0x7
# Opens a link or junction itself on Windows, never the file it names.
_FILE_FLAG_OPEN_REPARSE_POINT: Final[int] = 0x00200000
# The FILE_INFO_BY_HANDLE_CLASS value of a file's attributes and reparse tag.
_FILE_ATTRIBUTE_TAG_INFO: Final[int] = 9
# The Windows errors a file system gives for an information class it does
# not have: invalid function, not supported, invalid parameter.
_QUERY_NOT_SUPPORTED: Final[frozenset[int]] = frozenset({1, 50, 87})
# How many leading bytes of a file over the limit decide whether it is
# binary: the span git looks at for the same question.
_BINARY_SNIFF_BYTES: Final[int] = 8000
# A file over the limit is binary when at least this share of those bytes
# are NUL, as in a zero-filled image (nearly all) or UTF-16 text (half). A
# text file with a stray NUL stays text, so its findings are not hidden.
_BINARY_NUL_SHARE: Final[float] = 0.25

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


class CorpusListError(Exception):
    """The tracked-file list cannot be read: git was not run, or did not start.

    git is not run when the ``.git`` entry it would use is a link (see
    :func:`~apothem.conformity._grep_base.nearest_linked_git_entry`), and
    does not start when it is missing. The message is a fixed sentence, like
    those of the git-check errors in :mod:`apothem.conformity._grep_base`:
    git's own error text is left out, because it can quote the repository's
    settings and name files outside the project.
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
    off the repository's settings that start a program and gives git no input.
    The output is read as file names, so a name keeps every byte it holds (a
    carriage return, a byte that is not UTF-8) and names the file on disk; a
    name that names no file there is skipped on its own instead of failing the
    run. The call gives up after
    :data:`GIT_LS_FILES_TIMEOUT_SECONDS`. A file with a merge conflict, which
    the index lists once per stage, is kept once, and counts as a link or a
    submodule when any of its stages does. Each name is judged as git writes
    it (see :func:`name_skip`); no path is resolved and no link is followed.

    Raises :class:`CorpusListError` when git is not run or cannot be started
    (the ``.git`` entry git would use, in *root* or a folder above it, is a
    link, so git would read another repository's index; or git did not
    start),
    :class:`~apothem.conformity._grep_base.GitFailedError` when git exits
    with an error (for example, *root* is not inside a git work tree), and
    :class:`~apothem.conformity._grep_base.GitTimeoutError` when git runs
    past the time limit: the same errors, in the same words, as the
    standalone validators' own git commands.
    """
    linked = nearest_linked_git_entry(root)
    if linked is not None:
        raise CorpusListError(linked_git_message(root, linked))
    try:
        completed = run_git(
            ["ls-files", "-s", "-z"],
            cwd=root,
            timeout=GIT_LS_FILES_TIMEOUT_SECONDS,
            file_names=True,
        )
    except subprocess.TimeoutExpired as exc:
        raise GitTimeoutError("git ls-files", GIT_LS_FILES_TIMEOUT_SECONDS) from exc
    except OSError as exc:
        raise CorpusListError("git did not start") from exc
    if completed.returncode != 0:
        raise GitFailedError("git ls-files", completed.returncode)
    modes: dict[str, str] = {}
    for record in split_names(completed.stdout):
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


def _held_by_another_program(exc: OSError) -> bool:
    """Return True when the refused open (*exc*) is worth one retry: another
    program holds the file for now.

    On Windows that is a program that has the file open without sharing it,
    which the Windows API reports as a sharing violation. Elsewhere it is a
    write lease (a Samba oplock, an NFS delegation, ``F_SETLEASE``): the
    non-blocking open reports ``EAGAIN`` and starts the lease break, which
    usually ends within the wait. A refusal for lack of permission, or a file
    being deleted, is not worth a retry.
    """
    if sys.platform == "win32":
        return getattr(exc, "winerror", None) == _SHARING_VIOLATION
    return exc.errno in (errno.EAGAIN, errno.EWOULDBLOCK)


def _open_binary(path: Path) -> BinaryIO:
    """Open *path* to read bytes, never through a link at its last level.

    On Windows see :func:`_open_windows_handle`. Elsewhere the open neither
    follows a link (``O_NOFOLLOW``) nor waits for a named pipe to get a writer
    or a lease to break (``O_NONBLOCK``, cleared once the file is open).
    """
    if sys.platform == "win32":
        import msvcrt  # Windows only, so imported here.

        handle = _open_windows_handle(path)
        try:
            fd = msvcrt.open_osfhandle(handle, os.O_RDONLY)
        except BaseException:
            _close_handle(handle)
            raise
    else:
        flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_NOCTTY
        fd = os.open(path, flags | os.O_CLOEXEC)
    try:
        if sys.platform != "win32":
            os.set_blocking(fd, True)
        return os.fdopen(fd, "rb")
    except BaseException:
        os.close(fd)
        raise


if sys.platform == "win32":
    import _winapi
    import ctypes
    import functools
    from ctypes import wintypes

    class _AttributeTagInfo(ctypes.Structure):
        """``FILE_ATTRIBUTE_TAG_INFO``: a file's attributes and reparse tag."""

        _fields_ = (("attributes", wintypes.DWORD), ("tag", wintypes.DWORD))

    class _ByHandleFileInformation(ctypes.Structure):
        """``BY_HANDLE_FILE_INFORMATION``, of which the file ID is used."""

        _fields_ = tuple(
            (name, wintypes.DWORD)
            for name in (
                "attributes",
                "created_low",
                "created_high",
                "accessed_low",
                "accessed_high",
                "written_low",
                "written_high",
                "volume_serial",
                "size_high",
                "size_low",
                "links",
                "index_high",
                "index_low",
            )
        )

    @functools.cache
    def _kernel32() -> ctypes.WinDLL:
        """Return ``kernel32`` with the two queries used here typed, built once."""
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        by_class = kernel32.GetFileInformationByHandleEx
        by_class.argtypes = (
            wintypes.HANDLE,
            ctypes.c_int,
            ctypes.c_void_p,
            wintypes.DWORD,
        )
        by_class.restype = wintypes.BOOL
        basic = kernel32.GetFileInformationByHandle
        basic.argtypes = (wintypes.HANDLE, ctypes.c_void_p)
        basic.restype = wintypes.BOOL
        return kernel32

    def _create_file(path: Path, flags: int) -> int:
        """Open *path* to read through the Windows API, sharing everything."""
        return int(
            _winapi.CreateFile(
                str(path),
                _winapi.GENERIC_READ,
                _SHARE_ALL,
                0,
                _winapi.OPEN_EXISTING,
                flags,
                0,
            )
        )

    def _close_handle(handle: int) -> None:
        _winapi.CloseHandle(handle)

    def _reparse_tag(handle: int) -> int | None:
        """Return the reparse tag of the open file *handle*: 0 for none, or None
        when the file system does not give one.

        ``os.fstat`` reports no tag on Windows, so the attribute and tag record
        (``FileAttributeTagInfo``) is read from the handle. Any other failure
        raises ``OSError``, so the file is not read.
        """
        info = _AttributeTagInfo()
        query = _kernel32().GetFileInformationByHandleEx
        if not query(
            handle, _FILE_ATTRIBUTE_TAG_INFO, ctypes.byref(info), ctypes.sizeof(info)
        ):
            error = ctypes.get_last_error()
            if error in _QUERY_NOT_SUPPORTED:
                return None
            raise ctypes.WinError(error)
        if not info.attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT:
            return 0
        return int(info.tag)

    def _file_id(handle: int) -> tuple[int, int]:
        """Return the volume and file index of the open file *handle*."""
        info = _ByHandleFileInformation()
        if not _kernel32().GetFileInformationByHandle(handle, ctypes.byref(info)):
            raise ctypes.WinError(ctypes.get_last_error())
        return info.volume_serial, (info.index_high << 32) | info.index_low

    def _open_windows_handle(path: Path) -> int:
        """Open *path* on Windows and return a handle to read its content from.

        The first open uses ``FILE_FLAG_OPEN_REPARSE_POINT``, so a reparse
        point at *path* is opened itself. One whose tag names another file or
        folder (a link or junction, see :func:`is_link`) raises ``ELOOP``, as
        ``O_NOFOLLOW`` does elsewhere. A plain file is read through that
        handle. Any other reparse point, such as a file Data Deduplication or
        a cloud sync program keeps behind one, is opened again without the
        flag, so its filter gives the real content, and the second handle must
        name the same file; when no filter claims the tag (its program is
        stopped), that open fails and the file is unreadable rather than read
        as its empty stub. A file system that gives no tag takes the same
        second open. The API also reports a sharing violation as such, which
        Python's ``open`` does not.
        """
        first = _create_file(path, _FILE_FLAG_OPEN_REPARSE_POINT)
        try:
            tag = _reparse_tag(first)
            if tag is not None and tag & NAME_SURROGATE_TAG_BIT:
                raise OSError(errno.ELOOP, "a link is in the file's place", str(path))
            if tag == 0:
                return first
            second = _create_file(path, 0)
            try:
                if _file_id(second) != _file_id(first):
                    raise OSError(
                        errno.ELOOP, "the file changed between opens", str(path)
                    )
            except BaseException:
                _close_handle(second)
                raise
        except BaseException:
            _close_handle(first)
            raise
        _close_handle(first)
        return second


def _same_file(seen: os.stat_result, opened: os.stat_result) -> bool:
    """Return True when the *opened* file is the regular file ``os.lstat`` *seen*.

    It must be a regular file. The file ID (device and inode) is compared
    when the system gives one; on a file system that gives none (an inode of
    0), the open never followed a link at the last level (see
    :func:`_open_binary`), so a swap to another regular file is the one
    change left unseen.
    """
    if not stat.S_ISREG(opened.st_mode):
        return False
    if not seen.st_ino or not opened.st_ino:
        return True
    return (seen.st_dev, seen.st_ino) == (opened.st_dev, opened.st_ino)


def _read_file(path: Path, seen: os.stat_result) -> bytes | str | None:
    """Return the bytes of the regular file *path*, or why it was not read.

    *seen* is what ``os.lstat`` found at *path*. The opened file must be that
    same regular file; when it is not (it was swapped for another file, a link
    or a named pipe since), the result is None and nothing is read. The file
    is opened once per attempt, and each attempt starts afresh. An open
    refused because another program holds the file (see
    :func:`_held_by_another_program`) is tried once more after
    :data:`_RETRY_DELAY_SECONDS`, since such a hold is often brief. A refusal
    for lack of permission is not retried, and neither is an error while
    reading, such as a range of the file another program has locked.
    """
    for attempt in range(2):
        try:
            handle = _open_binary(path)
        except OSError as exc:
            if exc.errno == errno.ELOOP:
                # O_NOFOLLOW met a link that took the file's place.
                return None
            if attempt == 0 and _held_by_another_program(exc):
                time.sleep(_RETRY_DELAY_SECONDS)
                continue
            return _read_failure(exc)
        try:
            with handle:
                opened = os.fstat(handle.fileno())
                if not _same_file(seen, opened):
                    return None
                return _read_open_file(handle, opened.st_size)
        except OSError as exc:
            return _read_failure(exc)
    return SKIP_UNREADABLE  # pragma: no cover - the loop always returns


def _read_open_file(handle: BinaryIO, size: int) -> bytes | str:
    """Return the bytes of the open file *handle*, or why they are not read.

    *size* is the file's size when it was opened. A file over
    :data:`MAX_FILE_BYTES` is judged by :func:`_oversized_reason`. Otherwise
    the first read asks for *size* plus one byte, so a small file costs a
    small read, and a file that grew since is read on in blocks; one that grew
    past the limit while it was read is :data:`SKIP_TOO_LARGE`, whatever its
    bytes.
    """
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

    The file is binary, :data:`SKIP_NOT_TEXT`, when at least
    :data:`_BINARY_NUL_SHARE` of its first :data:`_BINARY_SNIFF_BYTES` are NUL
    (a zero-filled image, or UTF-16 text), or when its first
    :data:`MAX_FILE_BYTES` bytes, read in blocks, do not decode as UTF-8. Any
    other file is text the run cannot read, :data:`SKIP_TOO_LARGE`, which fails
    the run since a finding in it would go unseen: a stray NUL does not change
    that, and a character cut at the limit still counts as text.
    """
    decoder = codecs.getincrementaldecoder("utf-8")()
    head = handle.read(min(_BINARY_SNIFF_BYTES, MAX_FILE_BYTES))
    if head and head.count(0) >= _BINARY_NUL_SHARE * len(head):
        return SKIP_NOT_TEXT
    left = MAX_FILE_BYTES - len(head)
    try:
        decoder.decode(head)
        while left > 0:
            block = handle.read(min(_SNIFF_BLOCK_BYTES, left))
            if not block:
                # The file ended before the limit: a cut character is not text.
                decoder.decode(b"", final=True)
                break
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
    A file swapped for another, a link or a named pipe between the look and
    the open is looked up once more; swapped again, it is unreadable.
    """
    if entry.skip is not None:
        return None, entry.skip
    if leaves_root(root, entry.path):
        return None, SKIP_OUTSIDE
    if entry.mode == _LINK_MODE:
        return None, SKIP_LINK
    if entry.mode == _SUBMODULE_MODE:
        return None, SKIP_SUBMODULE
    data: bytes | str | None = None
    for _attempt in range(2):
        info = lstat_inside(root, entry.path)
        if isinstance(info, str):
            return None, info
        if not stat.S_ISREG(info.st_mode):
            return None, SKIP_NOT_REGULAR
        data = _read_file(entry.path, info)
        if data is not None:
            break
    if data is None:
        # Swapped again on the second look.
        return None, SKIP_UNREADABLE
    if isinstance(data, str):
        return None, data
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return None, SKIP_NOT_TEXT
    return text.replace("\r\n", "\n").replace("\r", "\n"), None
