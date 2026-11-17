# SPDX-License-Identifier: MIT

"""List a checked project's tracked files and read only those inside it.

Why this module exists. ``gate --all-perwrite`` lists the tracked files with
``git ls-files`` and reads each one, and the project may come with its ``.git``
folder from someone else, in an archive or a shared folder. git lists an index
entry exactly as the index holds it, and the working tree is whatever arrived,
so the list can point anywhere: an entry such as ``../x`` or an absolute path,
a symbolic link or Windows junction to a file or folder elsewhere, a named pipe
whose read waits for ever, a device, or a huge sparse file. This module lists
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
configuration, which the gate's git options govern, not this module.
"""

from __future__ import annotations

import os
import stat
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from apothem.conformity._grep_base import GIT_LS_FILES_TIMEOUT_SECONDS

# The largest file the corpus run reads, in bytes. Files the matchers check are
# far smaller; a larger tracked file is skipped and counted, so a huge or sparse
# file cannot use up the machine's memory.
MAX_FILE_BYTES: Final[int] = 8 * 1024 * 1024

# The index modes git gives a symbolic link and a submodule.
_LINK_MODE: Final[str] = "120000"
_SUBMODULE_MODE: Final[str] = "160000"

# Why a listed path was not read. The corpus report counts each one.
SKIP_OUTSIDE: Final[str] = "outside_project"
SKIP_LINK: Final[str] = "link"
SKIP_SUBMODULE: Final[str] = "submodule"
SKIP_NOT_REGULAR: Final[str] = "not_regular_file"
SKIP_MISSING: Final[str] = "missing"
SKIP_TOO_LARGE: Final[str] = "too_large"
SKIP_NOT_TEXT: Final[str] = "not_utf8_text"
SKIP_REASONS: Final[tuple[str, ...]] = (
    SKIP_OUTSIDE,
    SKIP_LINK,
    SKIP_SUBMODULE,
    SKIP_NOT_REGULAR,
    SKIP_MISSING,
    SKIP_TOO_LARGE,
    SKIP_NOT_TEXT,
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
    """One index entry: its path joined to the root as git lists it, its mode."""

    path: Path
    mode: str


def tracked_entries(root: Path) -> list[TrackedEntry]:
    """Return the index entries under *root*, each path joined as git lists it.

    Runs ``git ls-files -s -z`` in *root* with no input and gives up after
    :data:`GIT_LS_FILES_TIMEOUT_SECONDS`. Output is decoded as UTF-8 with any
    other byte replaced, so a file name that is not UTF-8 names no file on disk
    and is skipped on its own instead of failing the run. An entry git lists
    more than once (a file with a merge conflict) is kept once. No path is
    resolved and no link is followed.

    Raises :class:`CorpusListError` when the list cannot be read: git cannot be
    started, git exits with an error (for example, *root* is not inside a git
    work tree), or git runs past the time limit.
    """
    try:
        completed = subprocess.run(
            ["git", "ls-files", "-s", "-z"],  # noqa: S607 — read-only invocation; argv list (never shell); `git` resolved from PATH is the standard cross-platform invocation, mirroring the repo's other git subprocess call sites
            cwd=str(root),
            stdin=subprocess.DEVNULL,
            capture_output=True,
            check=False,
            encoding="utf-8",
            errors="replace",
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
    entries: list[TrackedEntry] = []
    seen: set[str] = set()
    for record in completed.stdout.split("\0"):
        # Each record is "<mode> <object> <stage>\t<path>".
        details, tab, name = record.partition("\t")
        if not tab or not name or name in seen:
            continue
        seen.add(name)
        entries.append(TrackedEntry(root / name, details.split(" ", 1)[0]))
    return entries


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
    the first link. The reasons are :data:`SKIP_OUTSIDE`, :data:`SKIP_LINK` and
    :data:`SKIP_MISSING` (a level does not exist, or one on the way is not a
    folder). What the returned result describes (a regular file, a folder, a
    named pipe) is for the caller to judge.
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
        except OSError:
            return SKIP_MISSING
        if is_link(info):
            return SKIP_LINK
        if depth == len(parts):
            return info
    return SKIP_MISSING


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
    if info.st_size > MAX_FILE_BYTES:
        return None, SKIP_TOO_LARGE
    try:
        with entry.path.open(encoding="utf-8") as handle:
            text = handle.read(MAX_FILE_BYTES + 1)
    except UnicodeDecodeError:
        return None, SKIP_NOT_TEXT
    except OSError:
        return None, SKIP_MISSING
    if len(text) > MAX_FILE_BYTES:
        # The file grew past the limit after it was checked.
        return None, SKIP_TOO_LARGE
    return text, None
