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
file these helpers leave out is noted, and so is every folder they could not
list, so the report can list it (:func:`start_skip_log`,
:func:`take_skipped_paths`): a link or an unreadable folder never hides a
file or a tree without a trace. A second log holds every folder a walk left
out as a nested checkout (:func:`note_checkout`,
:func:`take_skipped_checkouts`); it is for information and never changes a
verdict.
"""

from __future__ import annotations

import os
import re
import stat
import string
from collections.abc import Callable
from pathlib import Path
from typing import Final, Literal

# Windows sets this bit in the tag of a reparse point that names another file or
# folder: a symbolic link, a junction or a WSL link. ``os.lstat`` reports a
# junction as a plain folder, so the tag is what shows it is a link.
NAME_SURROGATE_TAG_BIT: Final[int] = 0x20000000

# What a directory entry is, looked at without following it.
EntryKind = Literal["dir", "file", "link", "other", "skipped-folder", "skipped-file"]
DIR_ENTRY: Final[EntryKind] = "dir"
FILE_ENTRY: Final[EntryKind] = "file"
LINK_ENTRY: Final[EntryKind] = "link"
OTHER_ENTRY: Final[EntryKind] = "other"
# A folder or a regular file the helpers leave out: on Windows, one whose
# name Win32 rewrites. A skipped folder may hide files, so it is always
# noted; a skipped file is noted only where a caller would have read it.
SKIPPED_FOLDER_ENTRY: Final[EntryKind] = "skipped-folder"
SKIPPED_FILE_ENTRY: Final[EntryKind] = "skipped-file"

# Win32 drops a trailing dot or space from each path segment when a path is
# opened by name, so ``X.`` listed as a real folder would be reopened as ``X``,
# which can be a junction. Such a name is treated as a special entry there.
_WIN32_REWRITTEN_ENDINGS: Final[tuple[str, ...]] = (".", " ")


def _rewritten_by_win32(name: str) -> bool:
    """Return True on Windows for a name Win32 would change when it is reopened."""
    return os.name == "nt" and name.endswith(_WIN32_REWRITTEN_ENDINGS)


# Every Windows device or extended path prefix; only an extended drive path
# (``\\?\C:\...``) can name a file inside a project.
_DEVICE_PREFIXES: Final[tuple[str, ...]] = ("\\\\?\\", "\\\\.\\", "\\??\\")
_DRIVE_ROOT: Final[re.Pattern[str]] = re.compile(r"[A-Za-z]:\\")

# Every device prefix above has this length.
_EXTENDED_PREFIX: Final[str] = "\\\\?\\"
# The prefixes after which Windows takes the rest literally: ``.``, ``..``
# and ``/`` are not path syntax there.
_LITERAL_PREFIXES: Final[tuple[str, ...]] = ("\\\\?\\", "\\??\\")

# Upper-cases ASCII letters only: ``str.upper`` would also fold a sharp s to
# ``SS`` or a long s to ``S``, which name other drives, servers and shares.
_ASCII_UPPER: Final[dict[int, int]] = str.maketrans(
    string.ascii_lowercase, string.ascii_uppercase
)


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

# Keyed by the exact spelling (``os.fspath``), never by ``Path``: on Windows
# ``Path`` equality folds case with ``str.lower``, so ``checK.yml`` with a
# Kelvin sign would equal ``check.yml``, though NTFS keeps two entries. An
# ordered dict: a project can hold thousands of links.
_skipped: dict[str, Path] = {}
# Links the run read through (a fixed file that names a project file):
# a walk that passes one by is not leaving anything out.
_used: set[str] = set()
# Folders a walk left out as a nested checkout, keyed like ``_skipped``.
_checkouts: dict[str, Path] = {}
# Called each time a skip log starts or stops, such as the guarded open's
# release of the folders it keeps open during one run (``_safe_open``).
_log_bound_callbacks: list[Callable[[], None]] = []


def on_skip_log_bounds(callback: Callable[[], None]) -> None:
    """Call *callback* each time a skip log starts or stops."""
    if callback not in _log_bound_callbacks:
        _log_bound_callbacks.append(callback)


def skip_log_running() -> bool:
    """Return True while a command-line run notes what it skips."""
    return _skip_root is not None


def _log_bound() -> None:
    for callback in _log_bound_callbacks:
        callback()


def start_skip_log(root: Path) -> None:
    """Start noting the links and special files skipped below *root*.

    The command-line entry of a root validator calls this (through
    ``parse_root_args``) before its check runs; a check called on its own notes
    nothing.
    """
    global _skip_root
    _log_bound()
    _skip_root = root
    _skipped.clear()
    _used.clear()
    _checkouts.clear()


def note_skipped(path: Path) -> None:
    """Note that *path* was left out: a link, a special file, or a folder
    that could not be listed."""
    if _skip_root is not None and os.fspath(path) not in _used:
        _skipped.setdefault(os.fspath(path), path)


def note_checkout(folder: Path) -> None:
    """Note that a walk left out *folder* as a nested checkout."""
    if _skip_root is not None:
        _checkouts.setdefault(os.fspath(folder), folder)


def _note_used(path: Path) -> None:
    """Note that the run read through the link *path*: it hid nothing."""
    if _skip_root is not None:
        _used.add(os.fspath(path))
        _skipped.pop(os.fspath(path), None)


def note_root_spelling(typed: Path, resolved: Path) -> None:
    """Record that *typed*, an absolute path the operator gave, is *resolved*.

    The command-line entry calls this (through ``parse_root_args``) so that an
    absolute link written through the root as typed, before links above it
    were resolved, still counts as inside the project.
    """
    _root_spellings.clear()
    if typed != resolved:
        _root_spellings[typed] = resolved


def _shown(root: Path | None, noted: list[Path]) -> list[str]:
    """Return *noted* relative to *root* (or in full outside it), sorted once."""
    if root is None:
        return []
    shown: list[str] = []
    for path in noted:
        try:
            shown.append(path.relative_to(root).as_posix())
        except ValueError:
            shown.append(path.as_posix())
    return sorted(set(shown))


def take_skipped_checkouts() -> list[str]:
    """Return the folders left out as nested checkouts, and clear that log.

    The paths are relative to the root and sorted. The skip log itself keeps
    running: call this before :func:`take_skipped_paths`, which stops it.
    """
    noted = list(_checkouts.values())
    _checkouts.clear()
    return _shown(_skip_root, noted)


def take_skipped_paths() -> list[str]:
    """Return the noted paths, relative to the root and sorted, and stop the log."""
    global _skip_root
    root, noted = _skip_root, list(_skipped.values())
    _skip_root = None
    _log_bound()
    _skipped.clear()
    _used.clear()
    _checkouts.clear()
    return _shown(root, noted)


# ---------------------------------------------------------------------------
# Listing a folder without following links
# ---------------------------------------------------------------------------


def _entry_kind(entry: os.DirEntry[str]) -> EntryKind | None:
    """Return what *entry* is, without following a link; None if it vanished.

    On POSIX hosts the answer comes from the listing itself (``d_type``); on
    Windows from the listing's attributes and reparse tag. Neither stats the
    target of a link. A link is ``"link"`` whatever its name. On Windows a
    folder or a regular file whose name ends in a dot or a space is
    ``"skipped-folder"`` or ``"skipped-file"``, and any other such entry is
    ``"other"``: a caller reopens an entry by name, and Win32 would drop that
    ending and reach a different entry, such as a junction beside it.
    """
    try:
        if entry.is_symlink():
            return LINK_ENTRY
        if os.name == "nt" and is_link(entry.stat(follow_symlinks=False)):
            return LINK_ENTRY
        if _rewritten_by_win32(entry.name):
            if entry.is_dir(follow_symlinks=False):
                return SKIPPED_FOLDER_ENTRY
            if entry.is_file(follow_symlinks=False):
                return SKIPPED_FILE_ENTRY
            return OTHER_ENTRY
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


# The Windows errors that say a listed folder is not there: the file (2) or
# the path (3) is not found, or the name is not a folder (267).
_NOT_THERE_WINERRORS: Final[frozenset[int]] = frozenset({2, 3, 267})
# Windows without long paths turned on fails a folder path of this length or
# more with "path not found" (3), not "name too long" (206): a folder name
# may be at most 260 characters less the 12 a file name inside it needs.
_LONG_FOLDER_PATH: Final[int] = 260 - 12


def _too_long_for_win32(folder: Path) -> bool:
    r"""Return True when *folder*, on Windows, may be past the old path limit.

    A path with the ``\\?\`` prefix has no such limit. Elsewhere than
    Windows nothing is too long here.
    """
    if os.name != "nt":
        return False
    full = os.fspath(folder.absolute())
    return not full.startswith("\\\\?\\") and len(full) >= _LONG_FOLDER_PATH


def _listing_absent(exc: OSError, folder: Path) -> bool:
    """Return True when *exc*, from listing *folder*, means there is no folder.

    A folder that is gone, or a name that is not a folder, hides nothing. On
    Windows a path too long (206) and other failures also raise
    :class:`FileNotFoundError`; only the codes in
    :data:`_NOT_THERE_WINERRORS` mean nothing is there to list. A Windows
    host without long paths turned on reports a folder past the old path
    limit as "path not found" (3) even when its parent just listed it, so a
    3 on such a folder (:func:`_too_long_for_win32`) is not read as absence.
    """
    if isinstance(exc, NotADirectoryError):
        return True
    if not isinstance(exc, FileNotFoundError):
        return False
    code = getattr(exc, "winerror", None)
    if code == 3 and _too_long_for_win32(folder):
        return False
    return code is None or code in _NOT_THERE_WINERRORS


def scan_entries(folder: Path) -> list[tuple[Path, EntryKind]]:
    """Return every entry of *folder* with what it is, links included.

    Pre-conditions: the caller already trusts *folder* (see
    :func:`list_real_entries`). Post-conditions: no link is followed and no
    entry is noted; a folder that cannot be listed gives an empty list. When
    it is there but cannot be listed (no access, a path too long, an I/O
    error), *folder* itself is noted in the skip log, so the files it may
    hold are not left out without a trace (:func:`_listing_absent`). For a
    validator that checks names, such as a stray plans folder that is a link.
    """
    try:
        with os.scandir(folder) as listing:
            entries = list(listing)
    except OSError as exc:
        if not _listing_absent(exc, folder):
            note_skipped(folder)
        return []
    found: list[tuple[Path, EntryKind]] = []
    for entry in entries:
        kind = _entry_kind(entry)
        if kind is not None:
            found.append((folder / entry.name, kind))
    return found


def no_files(name: str) -> bool:
    """A ``wanted_files`` for a caller that looks at folders only."""
    return False


def as_opened(name: str) -> str:
    """Return *name* as Win32 would open it: without a trailing dot or space."""
    if os.name != "nt":
        return name
    return name.rstrip("".join(_WIN32_REWRITTEN_ENDINGS))


def list_real_entries(
    folder: Path, *, wanted_files: Callable[[str], bool] | None = None
) -> list[Path]:
    """Return the real folders and regular files directly inside *folder*.

    Pre-conditions: the caller already trusts *folder*: it is the root, or
    :func:`is_project_dir` or this function vouched for it.
    Post-conditions: links of any kind, named pipes, devices and sockets are
    left out, as if they were not there, and noted in the skip log, so a
    caller can test each entry with ``is_dir`` or ``is_file`` without
    following a link. On Windows a regular file whose name ends in a dot or
    a space is left out too; it is noted only when *wanted_files* accepts
    the name as Win32 would open it (:func:`as_opened`). The default,
    None, is a caller that looks at every file name, so each one is noted;
    a caller that wants folders only passes :func:`no_files`. The order is
    the host's listing order; callers sort. A folder that cannot be listed
    gives an empty list, and is noted when it is there (:func:`scan_entries`).
    """
    kept: list[Path] = []
    for path, kind in scan_entries(folder):
        if kind in (DIR_ENTRY, FILE_ENTRY):
            kept.append(path)
        elif kind != SKIPPED_FILE_ENTRY or (
            wanted_files is None or wanted_files(as_opened(path.name))
        ):
            note_skipped(path)
    return kept


# ---------------------------------------------------------------------------
# Fixed paths
# ---------------------------------------------------------------------------


def _last_level(root: Path, path: Path) -> os.stat_result | None:
    """Return ``os.lstat(path)`` when each level between *root* and it is a real folder.

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
        except (OSError, ValueError):
            return None
        if is_link(info):
            note_skipped(folder)
            return None
        if not stat.S_ISDIR(info.st_mode):
            return None
    try:
        return os.lstat(folder / parts[-1])
    except (OSError, ValueError):
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


def _respelled(root: Path, named: Path) -> Path:
    """Return *named* spelled through *root* when it uses another spelling of it."""
    for typed, resolved in _root_spellings.items():
        if resolved == root and _exactly_inside(typed, named):
            return root.joinpath(*named.parts[len(typed.parts) :])
    return named


def _exactly_inside(root: Path, path: Path) -> bool:
    """Return True when *path* starts with *root*'s own parts, compared exactly.

    ``Path.relative_to`` compares names without case on Windows, and a Kelvin
    sign folds to ``K``, so a sibling such as ``desK`` would pass it. Only
    the ASCII letters of the first part (the drive, or a network server and
    share) are compared without case; :func:`_names_the_root` accepts
    another spelling of the root's own folder.
    """
    count = len(root.parts)
    if len(path.parts) < count:
        return False
    head, rest = path.parts[0], path.parts[1:count]
    return (
        head.translate(_ASCII_UPPER) == root.parts[0].translate(_ASCII_UPPER)
        and rest == root.parts[1:]
    )


def _names_the_root(root: Path, candidate: Path) -> bool:
    """Return True when *candidate*, another spelling, is *root*'s own folder.

    On Windows a folder opens under another letter case of its name, so a
    link written as ``c:\\work\\proj`` reaches the root ``C:\\Work\\Proj``.
    The host's own case rule (``os.path.normcase``) must first make
    *candidate* the root's name; it keeps a Kelvin sign apart from ``K``,
    so ``desK`` with one is refused without being looked at. Then each
    level spelled differently is decided by identity, from the top down:
    it must be a real folder (``os.lstat``, not a link) and
    ``os.path.samestat`` with the root's folder at that level. That
    ``os.lstat`` reads the metadata of an entry outside the project (never
    its content), and only of an entry whose name differs from the root's
    folder at that level by letter case. So a case-sensitive folder whose
    other-case child is a junction, or another folder, is refused at that
    level, and nothing below it is looked at.
    """
    if os.path.normcase(str(candidate)) != os.path.normcase(str(root)):
        return False
    theirs, ours = candidate.parts, root.parts
    if len(theirs) != len(ours):
        return False
    if theirs[0].translate(_ASCII_UPPER) != ours[0].translate(_ASCII_UPPER):
        return False
    for level in range(1, len(ours)):
        if theirs[level] == ours[level]:
            # The same name in a folder already shown to be the same.
            continue
        try:
            found = os.lstat(Path(*theirs[: level + 1]))
            own = os.lstat(Path(*ours[: level + 1]))
        except (OSError, ValueError):
            return False
        if is_link(found) or not stat.S_ISDIR(found.st_mode):
            return False
        if not os.path.samestat(found, own):
            return False
    return True


def _link_target(root: Path, link: Path) -> Path | None:
    """Return the file a link inside *root* names, found level by level, or None.

    ``os.readlink`` reads the link itself and never touches its target. The
    text is then walked one level at a time from the link's folder, as the
    system would. ``..`` steps up from a folder already shown to be real; it
    may climb to the root's parent only to come straight back in under the
    root's own folder (:func:`_names_the_root`). Each named folder must be a
    real folder inside *root* (``os.lstat``), so a ``..`` after a link is
    never tidied away as text. Outside *root* only the metadata of an entry
    that differs from one of the root's own folders by letter case is looked
    at (:func:`_names_the_root`); no content there is read. A device or
    extended path other than a drive path (``\\?\\C:\\``), an extended path
    that holds ``.``, ``..``, an empty part or ``/`` (Windows takes those
    literally there), a drive without a root (``C:name``), on Windows a part
    holding a colon
    (another drive, or a stream), a rooted path without a drive, a NUL, and
    an absolute path outside *root* give None.
    """
    try:
        # The raw text: a Path would drop ``.`` parts and turn ``/`` into ``\``
        # on Windows before the checks below could see them.
        text = os.readlink(link)  # noqa: PTH115 - Path.readlink rewrites the text
    except (OSError, ValueError):
        return None
    if "\0" in text:
        return None
    # On POSIX a backslash is an ordinary name character, not a prefix.
    if os.name == "nt" and text.startswith(_DEVICE_PREFIXES):
        literal = text.startswith(_LITERAL_PREFIXES)
        text = text[len(_EXTENDED_PREFIX) :]
        if _DRIVE_ROOT.match(text) is None:
            return None
        if literal and ("/" in text or {"", ".", ".."} & set(text.split("\\"))):
            return None
    if os.name != "nt" and text.startswith("//") and not text.startswith("///"):
        text = text[1:]  # POSIX allows a doubled leading slash for the root
    named = Path(text)
    if named.is_absolute():
        named = _respelled(root, named)
        count = len(root.parts)
        if not _exactly_inside(root, named) and not (
            len(named.parts) >= count
            and _names_the_root(root, Path(*named.parts[:count]))
        ):
            return None
        folder, parts = root, named.parts[count:]
    elif named.anchor:
        return None
    else:
        folder, parts = link.parent, named.parts
    if not parts or parts[-1] == "..":
        return None
    # A part with a colon would replace the folder with another drive's
    # current folder, or name a stream; neither is looked at.
    if os.name == "nt" and any(":" in part for part in parts):
        return None
    above = False
    for part in parts[:-1]:
        if above:
            # Only the root's own folder leads back in.
            if part != root.name and not _names_the_root(root, root.parent / part):
                return None
            folder, above = root, False
            continue
        if part == "..":
            if folder == root:
                folder, above = root.parent, True
            else:
                folder = folder.parent
            continue
        folder = folder / part
        try:
            info = os.lstat(folder)
        except (OSError, ValueError):
            return None
        if is_link(info) or not stat.S_ISDIR(info.st_mode):
            return None
    if above:
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
        _note_used(path)
        return target
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
        for child in list_real_entries(folder, wanted_files=no_files)
        if child.is_dir() and is_project_file(root, child / name)
    ]


def linked_git_entry(root: Path) -> bool:
    """Return True, and note it, when *root*'s ``.git`` entry is a link.

    git follows such a link to another repository, or climbs past it to an
    enclosing one when it dangles. A check that runs git calls
    ``nearest_linked_git_entry`` in ``_grep_base``, which asks this for
    *root* and then looks at the ``.git`` entries above it.
    """
    entry = root / ".git"
    if path_kind(entry) == LINK_ENTRY:
        note_skipped(entry)
        return True
    return False
