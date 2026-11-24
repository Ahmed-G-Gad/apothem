# SPDX-License-Identifier: MIT

"""Look at a project's files without following a link out of it.

Why this module exists. A project can arrive with its files from someone else,
in an archive or a shared folder, and the conformity validators read it. A
symbolic link, or on Windows a junction, can lead from the project to a file or
a whole tree anywhere on the disk or on a network share, and a named pipe or a
link to a device such as ``/dev/zero`` makes a read wait or never end.
``Path.is_file``, ``Path.is_dir``, ``Path.glob`` and ``os.walk`` all follow
links (``os.walk`` even stats the target of each symbolic link it lists), so
the helpers here look at each level with ``os.lstat`` or a ``DirEntry``
without following, and treat a link, a named pipe, a device or a socket as if
it were not there.

Two exceptions keep a project's own links useful. A fixed file that is a link
to a regular file inside the project, such as ``CLAUDE.md`` pointing at
``AGENTS.md``, is read at the file it points to (:func:`project_file_target`).
And a validator that checks a name, not content, still sees a link by that
name (:func:`scan_entries`).

Skip log. While a validator runs from the command line, every link and special
file these helpers leave out is noted, so the report can list it
(:func:`start_skip_log`, :func:`take_skipped_paths`): a link never hides a
file or a tree without a trace.
"""

from __future__ import annotations

import os
import stat
from pathlib import Path
from typing import Final, Literal

# Windows sets this bit in the tag of a reparse point that names another file or
# folder: a symbolic link, a junction or a WSL link. ``os.lstat`` reports a
# junction as a plain folder, so the tag is what shows it is a link.
NAME_SURROGATE_TAG_BIT: Final[int] = 0x20000000

# What a directory entry is, looked at without following it.
EntryKind = Literal["dir", "file", "link", "other"]
DIR_ENTRY: Final[EntryKind] = "dir"
FILE_ENTRY: Final[EntryKind] = "file"
LINK_ENTRY: Final[EntryKind] = "link"
OTHER_ENTRY: Final[EntryKind] = "other"

# Win32 drops a trailing dot or space from each path segment when a path is
# opened by name, so ``X.`` listed as a real folder would be reopened as ``X``,
# which can be a junction. Such a name is treated as a special entry there.
_WIN32_REWRITTEN_ENDINGS: Final[tuple[str, ...]] = (".", " ")


def rewritten_by_win32(name: str) -> bool:
    """Return True on Windows for a name Win32 would change when it is reopened."""
    return _rewritten_by_win32(name)


def _rewritten_by_win32(name: str) -> bool:
    """Return True on Windows for a name Win32 would change when it is reopened."""
    return os.name == "nt" and name.endswith(_WIN32_REWRITTEN_ENDINGS)


# The prefix Windows puts on the target os.readlink returns for an absolute
# link target, and the form it takes for a network path.
_EXTENDED_PREFIX: Final[str] = "\\\\?\\"
_EXTENDED_UNC_PREFIX: Final[str] = "UNC\\"


def is_link(info: os.stat_result) -> bool:
    """Return True when *info*, from ``os.lstat``, describes a link of any kind."""
    if stat.S_ISLNK(info.st_mode):
        return True
    return bool(getattr(info, "st_reparse_tag", 0) & NAME_SURROGATE_TAG_BIT)


# ---------------------------------------------------------------------------
# Skip log
# ---------------------------------------------------------------------------

_skip_root: Path | None = None
# Other spellings of a root, such as the path the operator typed before it was
# resolved, mapped to the resolved root; see :func:`note_root_spelling`.
_root_spellings: dict[Path, Path] = {}

# A dict used as an ordered set: a project can hold thousands of links.
_skipped: dict[Path, None] = {}


def start_skip_log(root: Path) -> None:
    """Start noting the links and special files skipped below *root*.

    The command-line entry of a root validator calls this (through
    ``parse_root_args``) before its check runs; a check called on its own notes
    nothing.
    """
    global _skip_root
    _skip_root = root
    _skipped.clear()


def note_skipped(path: Path) -> None:
    """Note that *path*, a link or a special file, was left out."""
    if _skip_root is not None:
        _skipped.setdefault(path, None)


def note_root_spelling(typed: Path, resolved: Path) -> None:
    """Record that *typed*, an absolute path the operator gave, is *resolved*.

    The command-line entry calls this (through ``parse_root_args``) so that an
    absolute link written through the root as typed, before links above it
    were resolved, still counts as inside the project.
    """
    _root_spellings.clear()
    if typed != resolved:
        _root_spellings[typed] = resolved


def take_skipped_paths() -> list[str]:
    """Return the noted paths, relative to the root and sorted, and stop the log."""
    global _skip_root
    root, noted = _skip_root, list(_skipped)
    _skip_root = None
    _skipped.clear()
    if root is None:
        return []
    shown: list[str] = []
    for path in noted:
        try:
            shown.append(path.relative_to(root).as_posix())
        except ValueError:
            shown.append(path.as_posix())
    return sorted(set(shown))


# ---------------------------------------------------------------------------
# Listing a folder without following links
# ---------------------------------------------------------------------------


def _entry_kind(entry: os.DirEntry[str]) -> EntryKind | None:
    """Return what *entry* is, without following a link; None if it vanished.

    On POSIX hosts the answer comes from the listing itself (``d_type``); on
    Windows from the listing's attributes and reparse tag. Neither stats the
    target of a link. On Windows a name that ends in a dot or a space is
    ``"other"``: a caller reopens an entry by name, and Win32 would drop that
    ending and reach a different entry, such as a junction beside it.
    """
    if _rewritten_by_win32(entry.name):
        return OTHER_ENTRY
    try:
        if entry.is_symlink():
            return LINK_ENTRY
        if os.name == "nt" and is_link(entry.stat(follow_symlinks=False)):
            return LINK_ENTRY
        if entry.is_dir(follow_symlinks=False):
            return DIR_ENTRY
        if entry.is_file(follow_symlinks=False):
            return FILE_ENTRY
    except OSError:
        return None
    return OTHER_ENTRY


def path_kind(path: Path) -> EntryKind | None:
    """Return what *path* is, looked at with ``os.lstat``; None when it is missing.

    The last level is never followed, so a link reports as ``"link"`` whatever
    it points to. The caller vouches for the folders above it.
    """
    try:
        info = os.lstat(path)
    except OSError:
        return None
    if is_link(info):
        return LINK_ENTRY
    if stat.S_ISDIR(info.st_mode):
        return DIR_ENTRY
    if stat.S_ISREG(info.st_mode):
        return FILE_ENTRY
    return OTHER_ENTRY


def scan_entries(folder: Path) -> list[tuple[Path, EntryKind]]:
    """Return every entry of *folder* with what it is, links included.

    Pre-conditions: the caller already trusts *folder* (see
    :func:`list_real_entries`). Post-conditions: no link is followed and
    nothing is noted; a folder that cannot be listed gives an empty list. For
    a validator that checks names, such as a stray plans folder that is a link.
    """
    try:
        with os.scandir(folder) as listing:
            entries = list(listing)
    except OSError:
        return []
    found: list[tuple[Path, EntryKind]] = []
    for entry in entries:
        kind = _entry_kind(entry)
        if kind is not None:
            found.append((folder / entry.name, kind))
    return found


def list_real_entries(folder: Path) -> list[Path]:
    """Return the real folders and regular files directly inside *folder*.

    Pre-conditions: the caller already trusts *folder*: it is the root, or
    :func:`is_project_dir` or this function vouched for it.
    Post-conditions: links of any kind, named pipes, devices and sockets are
    left out, as if they were not there, and noted in the skip log, so a
    caller can test each entry with ``is_dir`` or ``is_file`` without
    following a link. The order is the host's listing order; callers sort. A
    folder that cannot be listed gives an empty list.
    """
    kept: list[Path] = []
    for path, kind in scan_entries(folder):
        if kind in (DIR_ENTRY, FILE_ENTRY):
            kept.append(path)
        else:
            note_skipped(path)
    return kept


# ---------------------------------------------------------------------------
# Fixed paths
# ---------------------------------------------------------------------------


def _last_level(root: Path, path: Path) -> os.stat_result | None:
    """Return ``os.lstat(path)`` when every level above it below *root* is a real folder.

    Pre-conditions: *path* was built from *root*, with the same spelling, so
    the test is by name: a path that does not start with *root*, or that has a
    ``..`` part, is outside it.
    Post-conditions: None when *path* is outside *root*, is *root* itself or
    does not exist, or when a level between *root* and *path* is not a real
    folder; a link found there is noted. The last level itself may be
    anything, a link included; callers decide.
    """
    try:
        parts = path.relative_to(root).parts
    except ValueError:
        return None
    if not parts or ".." in parts:
        return None
    # A level Win32 would rewrite (a trailing dot or space) is not looked up:
    # its lstat and a later open could reach a different entry.
    if any(_rewritten_by_win32(part) for part in parts):
        return None
    folder = root
    for part in parts[:-1]:
        folder = folder / part
        try:
            info = os.lstat(folder)
        except OSError:
            return None
        if is_link(info):
            note_skipped(folder)
            return None
        if not stat.S_ISDIR(info.st_mode):
            return None
    try:
        return os.lstat(folder / parts[-1])
    except OSError:
        return None


def _is_regular(info: os.stat_result | None) -> bool:
    return info is not None and not is_link(info) and stat.S_ISREG(info.st_mode)


def is_project_file(root: Path, path: Path) -> bool:
    """Return True iff *path* is a regular file reached through real folders.

    Pre-conditions: *path* was built from *root* (see :func:`_last_level`).
    Post-conditions: False for a path outside *root*, a link at any level, a
    named pipe, a device, a socket, a folder or a missing path; a link or a
    special file is noted in the skip log. For a fixed file that may be a link
    to another file in the project, use :func:`project_file_target`.
    """
    info = _last_level(root, path)
    if info is None:
        return False
    if _is_regular(info):
        return True
    if is_link(info) or not stat.S_ISDIR(info.st_mode):
        note_skipped(path)
    return False


def is_project_dir(root: Path, path: Path) -> bool:
    """Return True iff *path* is *root* or a real folder reached through real folders.

    Pre-conditions: *path* was built from *root* (see :func:`_last_level`).
    Post-conditions: False for a path outside *root*, a link to a folder or a
    junction at any level (noted in the skip log), a file or a missing path,
    so a caller never lists a folder outside the project. *root* itself is the
    folder the caller was pointed at and counts when it is a folder.
    """
    if path == root:
        return root.is_dir()
    info = _last_level(root, path)
    if info is None:
        return False
    if is_link(info):
        note_skipped(path)
        return False
    return stat.S_ISDIR(info.st_mode)


def _inside(root: Path, path: Path) -> bool:
    """Return True when *path* is *root* or below it, by name."""
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _respelled(root: Path, named: Path) -> Path:
    """Return *named* spelled through *root* when it uses another spelling of it."""
    for typed, resolved in _root_spellings.items():
        if resolved == root and _inside(typed, named):
            return root / named.relative_to(typed)
    return named


def _link_target(root: Path, link: Path) -> Path | None:
    """Return the file a link inside *root* names, found level by level, or None.

    ``os.readlink`` reads the link itself and never touches its target. The
    text is then walked one level at a time from the link's folder, as the
    system would: ``..`` steps up from a folder already shown to be real, and
    each named folder must be a real folder inside *root* (``os.lstat``), so
    a ``..`` after a link is never tidied away as text. A level outside
    *root* stops the walk before anything there is looked at. A network
    path, a drive without a root (``C:name``), a rooted path without a drive
    and an absolute path outside *root* give None.
    """
    try:
        text = str(link.readlink())
    except (OSError, ValueError):
        return None
    if text.startswith(_EXTENDED_PREFIX):
        text = text[len(_EXTENDED_PREFIX) :]
        if text.startswith(_EXTENDED_UNC_PREFIX):
            return None
    if os.name != "nt" and text.startswith("//") and not text.startswith("///"):
        text = text[1:]  # POSIX allows a doubled leading slash for the root
    named = Path(text)
    if named.is_absolute():
        named = _respelled(root, named)
        if not _inside(root, named):
            return None
        folder, parts = root, named.relative_to(root).parts
    elif named.anchor:
        return None
    else:
        folder, parts = link.parent, named.parts
    if not parts or parts[-1] == "..":
        return None
    for part in parts[:-1]:
        if part == "..":
            # Never step above the root: a name compared without case
            # (Windows, or a Kelvin sign) could re-enter a sibling folder.
            if folder == root:
                return None
            folder = folder.parent
            continue
        folder = folder / part
        if not _inside(root, folder):
            return None
        try:
            info = os.lstat(folder)
        except OSError:
            return None
        if is_link(info) or not stat.S_ISDIR(info.st_mode):
            return None
    return folder / parts[-1]


def project_file_target(root: Path, path: Path) -> Path | None:
    """Return the regular file to read for the fixed *path*, or None.

    That is *path* itself when it is a regular file reached through real
    folders, or, when *path* is a link, the file it names when that is a
    regular file inside *root* reached through real folders (one level: a link
    to a link is refused). So a project's ``CLAUDE.md`` that points at its
    ``AGENTS.md`` counts, while a link that leads out of the project, to a
    folder, a named pipe or a device does not. Pre-conditions: *path* was built
    from *root*. Post-conditions: None for anything else; a link or special
    file that is refused is noted in the skip log.
    """
    info = _last_level(root, path)
    if info is None:
        return None
    if _is_regular(info):
        return path
    if not is_link(info):
        if not stat.S_ISDIR(info.st_mode):
            note_skipped(path)
        return None
    # Only a symbolic link names a file; a junction or another reparse point
    # that leads to a file cannot be opened as one, so it is refused.
    target = _link_target(root, path) if stat.S_ISLNK(info.st_mode) else None
    if target is not None and _is_regular(_last_level(root, target)):
        # Rebuilt from the root's own spelling, so the file opened is the
        # one just checked, not a differently spelled twin.
        return root.joinpath(*target.relative_to(root).parts)
    note_skipped(path)
    return None


def child_folder_files(root: Path, folder: Path, name: str) -> list[Path]:
    """Return ``folder/<child>/<name>`` for each real child folder that holds it.

    Use it in place of ``folder.glob("*/" + name)``: on Python 3.12,
    ``Path.glob`` matches the *name* part by listing every child folder, a
    linked one included, so the glob would list a folder outside the project.
    This lists *folder* alone and looks *name* up in each real child folder
    with :func:`is_project_file`.
    Pre-conditions: *folder* was built from *root* (see :func:`_last_level`).
    Post-conditions: empty when *folder* is not a real folder inside *root*;
    otherwise the regular files only, in the host's listing order (callers
    sort).
    """
    if not is_project_dir(root, folder):
        return []
    return [
        child / name
        for child in list_real_entries(folder)
        if child.is_dir() and is_project_file(root, child / name)
    ]
