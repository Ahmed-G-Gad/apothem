# SPDX-License-Identifier: MIT

"""Path-escape / symlink / case-fold guards and write-root resolution."""

from __future__ import annotations

import contextlib
import os
import shutil
import sys
from collections.abc import Callable
from pathlib import Path, PosixPath, WindowsPath
from typing import NamedTuple

from apothem.lib.links import is_link
from apothem.lib.propagation import USER_LEVEL_PREFIXES, user_home

from .install_driver_types import (
    MaterializationResult,
    _handle_rm_error,
    _path_text,
    _result,
)


def _is_relative_to(path: Path, root: Path) -> bool:
    """Return True when *path* is inside *root* after normalization."""
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _normalized(path: Path) -> Path:
    """Return an absolute normalized path without requiring existence."""
    return path.expanduser().resolve(strict=False)


#: The ``lstat`` the case probe reads, kept apart so a test can replace it
#: without replacing ``os.lstat`` for the whole process.
_lstat = os.lstat


def _filesystem_is_case_insensitive(path: Path) -> bool:
    """Best-effort: does the filesystem holding *path* fold case?

    Probes the nearest existing ancestor by re-casing its name: on a volume
    that folds case the swapped-case name is the same entry, by file identity
    (device and inode, read without following a link). A swapped-case name
    that does not exist, or that is a different entry (a sibling folder that
    differs only in case on a case-sensitive volume), means the volume does
    not fold case. Falls back to the platform default (Windows and macOS fold
    case by default; other POSIX volumes do not) when no letter-bearing
    ancestor exists, or when the volume reports no inode numbers.

    Only that one folder is probed. A folder below it that sets its own case
    rule (Windows ``fsutil file setCaseSensitiveInfo``, as WSL sets) or a
    volume mounted below it can fold case differently, and the answer does
    not cover it.
    """
    base = path
    while not base.exists() and base.parent != base:
        base = base.parent
    name = base.name
    if base.exists() and name and name.swapcase() != name:
        try:
            original = _lstat(base)
            swapped = _lstat(base.with_name(name.swapcase()))
        except OSError:
            return False
        if original.st_ino and swapped.st_ino:
            return os.path.samestat(original, swapped)
    return sys.platform in ("win32", "darwin")


def _parts_within(path: Path, root: Path) -> bool:
    """Return True when *path* is *root* or below it, comparing names by case.

    ``PurePath.relative_to`` ignores case on Windows, which would put a
    sibling that differs only in case inside *root* on a folder where Windows
    keeps case (``fsutil file setCaseSensitiveInfo``, as WSL sets).
    """
    return path.parts[: len(root.parts)] == root.parts


def _within_allowed_root(target: Path, root: Path) -> bool:
    """Return True when *target* is inside *root*, case-fold-aware.

    An exact (case-sensitive, on every platform) containment is tried first.
    When it fails and the
    boundary filesystem folds case, the comparison is retried on case-normalized
    paths so a case variant that resolves to the same location (``~/.Claude`` vs
    ``~/.claude``) is correctly treated as inside the root — without widening the
    boundary on a case-sensitive filesystem, where such a variant is a genuinely
    different location. ``os.path.normcase`` folds case on Windows; the extra
    lower-casing covers macOS's case-insensitive default, where ``normcase`` is a
    POSIX no-op.
    """
    normalized_target = _normalized(target)
    normalized_root = _normalized(root)
    if _parts_within(normalized_target, normalized_root):
        return True
    if not _filesystem_is_case_insensitive(normalized_root):
        return False
    folded_target = Path(os.path.normcase(str(normalized_target)).lower())
    folded_root = Path(os.path.normcase(str(normalized_root)).lower())
    return _is_relative_to(folded_target, folded_root)


def _lexical_key(path: Path) -> str:
    """Return *path* normalized without resolving symlinks, case-folded where the OS is."""
    return os.path.normcase(os.path.normpath(str(path)))


def _is_lexically_within(path: Path, parent: Path) -> bool:
    """Return True when *path* is *parent* or below it, by name only."""
    key, base = _lexical_key(path), _lexical_key(parent)
    return key == base or key.startswith(base.rstrip(os.sep) + os.sep)


def _spelled(path: Path) -> Path:
    """Return *path* absolute and expanded, ``..`` folded by name, links kept."""
    return Path(os.path.normpath(path.expanduser().absolute()))


def _existing_chain(path: Path, floor: Path, named: Path | None = None) -> list[Path]:
    """Return existing path components from *path* upward to *floor*.

    With *named* (a project root as the operator spelled it, see
    :func:`_named_floor`) and *path* spelled inside it, the walk stops at
    *named* by name, so every folder between them is returned even when a
    link inside the project leads one of them back to the floor. Otherwise
    the walk stops at the first component that resolves to *floor*.
    """
    expanded = path.expanduser()
    # ``lexists`` (an ``lstat``) also sees a link or junction whose target is
    # gone; ``_is_link`` covers a junction ``lstat`` may not report.
    probe = (
        expanded if os.path.lexists(expanded) or _is_link(expanded) else expanded.parent
    )
    named_key = None
    if named is not None and _is_lexically_within(_spelled(probe), named):
        named_key = _lexical_key(named)
    floor_resolved = _normalized(floor)
    chain: list[Path] = []
    while True:
        if os.path.lexists(probe) or _is_link(probe):
            chain.append(probe)
        if named_key is not None:
            if _lexical_key(_spelled(probe)) == named_key:
                break
        elif _normalized(probe) == floor_resolved:
            break
        parent = probe.parent
        if parent == probe:
            break
        probe = parent
    return chain


def _linkable_ancestors(path: Path, floor: Path) -> list[Path]:
    """Return the folders a link at or above which *path* may cross.

    Dotfile managers link ``~/.config`` or ``~/.agents`` into a dotfiles
    folder. When *floor* is the user home, a link at or above one of the
    manifest's closed user-level folders (``~/.agents/skills``,
    ``~/.config/apothem/rules``, ...) is allowed: the write guard has already
    confirmed the resolved path stays in the home. When the install root is
    below ``~/.config`` (OpenCode's folder, or a ``CODEX_HOME`` there), *floor*
    is at or below the folder ``~/.config`` leads to, and a link at
    ``~/.config`` is allowed when that folder is inside the home. A link below
    either folder (a skill folder, the install root, a file in it) is still
    refused. The walk stops at *floor*, so a link above it is not examined.
    """
    home = user_home()
    bases: list[Path] = []
    normalized_floor = _normalized(floor)
    if normalized_floor == _normalized(home):
        bases = [
            base
            for base in (home / prefix for prefix in USER_LEVEL_PREFIXES)
            if _is_lexically_within(path, base)
        ]
    config = home / ".config"
    if (
        _is_lexically_within(path, config)
        and _is_relative_to(normalized_floor, _normalized(config))
        and _within_allowed_root(config, home)
    ):
        bases.append(config)
    return bases


#: The one link test the write guard, the sweeps and the reversal share (see
#: :func:`apothem.lib.links.is_link`); the clean-slate routine uses it too.
_is_link = is_link


class _Walk(NamedTuple):
    """What :func:`_walk_without_links` found below a folder."""

    files: list[Path]
    folders: list[Path]
    links: list[Path]
    unreadable: list[Path]


def _walk_without_links(top: Path) -> _Walk:
    """Return the files, folders and links below *top*, never entering a link.

    ``Path.rglob`` enters a Windows junction (``is_symlink()`` is False for
    one), so a walk that deletes what it finds would delete through it. A
    folder the walk cannot list (*top* included) is returned in
    ``unreadable`` so the caller can report it.
    """
    files: list[Path] = []
    folders: list[Path] = []
    links: list[Path] = []
    unreadable: list[Path] = []
    pending = [top]
    while pending:
        folder = pending.pop()
        try:
            with os.scandir(folder) as scan:
                entries = sorted(scan, key=lambda e: e.name)
        except OSError:
            unreadable.append(folder)
            continue
        for entry in entries:
            path = Path(entry.path)
            if _is_link(path):
                links.append(path)
            elif entry.is_dir(follow_symlinks=False):
                folders.append(path)
                pending.append(path)
            else:
                files.append(path)
    return _Walk(files, folders, links, unreadable)


def _lexical_set(paths: list[Path]) -> set[str]:
    return {_lexical_key(path) for path in paths}


def _skip_links_into(
    source: Path, dest: Path, links: list[Path]
) -> Callable[[str, list[str]], set[str]]:
    """Return a ``copytree`` ignore hook that skips each of *links* in *dest*.

    Copying a tree over a folder that still holds a link would write through
    the link. Paths are compared by name, never resolved, so a link is matched
    as the entry it is rather than the folder it points to.
    """
    kept = _lexical_set(links)

    def skip(folder: str, names: list[str]) -> set[str]:
        here = dest / Path(folder).relative_to(source)
        return {name for name in names if _lexical_key(here / name) in kept}

    return skip


#: ``detail`` key naming the links a removal left in place, one per line.
KEPT_LINKS = "kept_links"


def kept_links_detail(links: list[Path]) -> dict[str, str]:
    """Return the ``detail`` entry that records the paths a removal left in place."""
    return {KEPT_LINKS: "\n".join(_path_text(link) for link in links)} if links else {}


def _remove_tree_keeping_links(top: Path) -> list[Path]:
    """Remove the folder *top* and what it holds, except links; return what stayed.

    ``shutil.rmtree`` does not delete through a Windows junction, but it does
    remove the junction itself, and a link below *top* is the operator's. Each
    link stays, with the folders that hold it; everything else is removed. The
    result lists each link, each file that could not be removed and each
    folder that could not be read, so the caller can report them.
    """
    walk = _walk_without_links(top)
    if not walk.links and not walk.unreadable:
        shutil.rmtree(top, onerror=_handle_rm_error)
        return [path for path in walk.files if path.exists()]
    for path in walk.files:
        # Checked again just before the removal: the walk ran earlier.
        if not _is_link(path):
            with contextlib.suppress(OSError):
                path.unlink()
    for folder in sorted(
        [*walk.folders, top], key=lambda path: len(path.parts), reverse=True
    ):
        # rmdir removes only an empty folder, so one that holds a link stays.
        if not _is_link(folder):
            with contextlib.suppress(OSError):
                folder.rmdir()
    left = [path for path in walk.files if not _is_link(path) and path.exists()]
    return [*walk.links, *left, *walk.unreadable]


def _unsafe_symlink(
    path: Path,
    floor: Path,
    *,
    project_floor: bool = False,
    named: Path | None = None,
) -> Path | None:
    """Return the first symlink or junction in the write path, if any.

    A link at or above a user-level folder, or at ``~/.config`` for an install
    root below it (see :func:`_linkable_ancestors`), does not count. Nor does
    the home folder itself or a folder above it, as the home is spelled (a
    profile moved to another drive behind a junction): the caller has already
    checked that the resolved path stays inside the resolved allowed root, so
    such a link cannot lead the write out of the home.

    *project_floor* says *floor* is a project root (see :class:`_ProjectFloor`):
    then neither exemption applies, and every link inside the project is
    refused. *named* is the project root as the operator spelled it: a link
    there, the folder the operator named, is followed wherever it leads, as
    the CLI follows ``--project``. Only that spelling is exempt; a link inside
    the project that leads back to the floor is still refused. A *floor*
    that is a :class:`_ProjectFloor` sets both itself, so a caller that
    passes the boundary object gets the write guard's answer.
    """
    if isinstance(floor, _ProjectFloor):
        project_floor = True
        named = _named_floor(floor) if named is None else named
    home = user_home()
    bases = [] if project_floor else _linkable_ancestors(path, floor)
    named_key = None if named is None else _lexical_key(named)
    for candidate in _existing_chain(path, floor, named):
        if _is_lexically_within(home, candidate):
            continue
        if named_key is not None and _lexical_key(_spelled(candidate)) == named_key:
            continue
        if _is_link(candidate) and not any(
            _is_lexically_within(base, candidate) for base in bases
        ):
            return candidate
    return None


def _link_below_floor(path: Path, floor: Path) -> Path | None:
    """Return the first link or junction from *path* up to *floor*, if any.

    No link is exempt, except a :class:`_ProjectFloor`'s project folder as
    the operator spelled it, which is followed wherever it leads (see
    :func:`_unsafe_symlink`).
    """
    named = _named_floor(floor)
    named_key = None if named is None else _lexical_key(named)
    for candidate in _existing_chain(path, floor, named):
        if named_key is not None and _lexical_key(_spelled(candidate)) == named_key:
            continue
        if _is_link(candidate):
            return candidate
    return None


def _leads_to(link: Path) -> str:
    """Return where *link* leads, as display text; the link itself for a loop."""
    try:
        return _path_text(_normalized(link))
    except (OSError, RuntimeError, ValueError):
        return _path_text(link)


def _ensure_directory(path: Path, *, operation: str) -> MaterializationResult | None:
    """Create *path* and its parents; return an error result when that is impossible.

    The result names the existing path that is not a folder (``~/.agents``
    left as a file, say) when that is what blocks the install, so the operator
    sees which path to move.
    """
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        blocker = next(
            (
                item
                for item in (path, *path.parents)
                if item.exists() and not item.is_dir()
            ),
            None,
        )
        reason = (
            f"{blocker} exists and is not a folder; move it, then run the command again"
            if blocker is not None
            else str(exc)
        )
        return _result(
            "error",
            operation,
            path,
            f"could not create {path}: {reason}",
            detail={"blocking_path": _path_text(blocker)} if blocker else None,
        )
    return None


def _prepare_target_directory(
    path: Path, *, allowed_root: Path, operation: str
) -> MaterializationResult | None:
    """Validate *path* against *allowed_root*, then create it; an error result if either fails."""
    return _validate_target_path(
        path, allowed_root=allowed_root, operation=operation
    ) or _ensure_directory(path, operation=operation)


def _root_for(harness_root: Path | None, project_root: Path | None) -> Path:
    """Return the active install root, preferring the user-scope harness root."""
    root = harness_root if harness_root is not None else project_root
    if root is None:
        raise ValueError("install driver requires either harness_root or project_root")
    return root


if sys.platform == "win32":
    _ConcretePath = WindowsPath
else:
    _ConcretePath = PosixPath


class _ProjectFloor(_ConcretePath):
    """A write boundary that is a project root, not the folder above one.

    A harness root's boundary is the folder above it; a project root's
    boundary is the project root itself, the folder the operator named with
    ``--project``. The two cannot be told apart by path, so the boundary
    carries its kind: inside a project floor every link is refused, with no
    user-level or ``~/.config`` exemption (see :func:`_unsafe_symlink`).

    The kind carries to the paths derived from the floor (``resolve()``,
    ``/``, ``parent``), which only makes them stricter. The project root as
    the operator spelled it, whose own link is followed, is kept only on the
    object :func:`_allowed_write_root` returns (see :func:`_named_floor`), so
    a boundary built from the floor (``floor / "sub"``) never follows a link
    at the folder it was built for.
    """

    #: Set on the instance by :func:`_allowed_write_root` only; read through
    #: :func:`_named_floor`, since a derived path has no instance value.
    _named: Path


def _named_floor(allowed_root: Path) -> Path | None:
    """Return the project root as spelled, for a floor from :func:`_allowed_write_root`.

    ``None`` for any other boundary, a path derived from such a floor
    included: a derived path is a new object and has no spelling of its own.
    """
    if not isinstance(allowed_root, _ProjectFloor):
        return None
    named = vars(allowed_root).get("_named")
    return named if isinstance(named, Path) else None


def _write_boundary(allowed_root: Path | None, install_root: Path) -> Path:
    """Return the write boundary for a writer given *allowed_root* or not.

    *allowed_root* when given, as the same object, so a :class:`_ProjectFloor`
    keeps its kind and its spelling. Without one the boundary is
    *install_root* as it was passed, checked as a harness boundary when it is
    a plain path: a link at the boundary itself is refused, and the
    user-level and ``~/.config`` exemptions apply. Every project-scope writer
    passes the floor from :func:`_allowed_write_root` as *allowed_root*, so a
    project write never takes this fallback.
    """
    return install_root if allowed_root is None else allowed_root


def _allowed_write_root(harness_root: Path | None, project_root: Path | None) -> Path:
    """Return the filesystem boundary allowed for resolved install targets.

    A project root's boundary is returned as a :class:`_ProjectFloor` that
    also keeps the project root as the operator spelled it, so the write
    guard knows it is a project root and which folder was named (see
    :func:`_validate_target_path`).
    """
    if project_root is not None:
        floor = _ProjectFloor(_normalized(project_root))
        floor._named = _spelled(project_root)
        return floor
    if harness_root is None:
        raise ValueError("install driver requires either harness_root or project_root")
    return _normalized(harness_root).parent


#: Where the write guard's link refusal turns from what happened to what to
#: do: the CLI shows the part before it as the reason and gives the fix on
#: its own line (see :func:`.install_driver_homelink.link_refusal_reason_and_fix`).
LINK_FIX_LEAD = ". To fix it, "


def _link_fix(link: Path, *, named: bool = False) -> str:
    """Return what to do about *link*, refused by the write guard.

    A link to a file is replaced by a copy of that file; any other link (to
    a folder, or one whose target is gone) by a real folder. *named* puts the
    link's path in the text. The text has no final full stop.
    """
    which = f"the link {link}" if named else "the link"
    if link.is_file():
        return (
            f"replace {which} with a copy of the file it leads to, then run the "
            "command again"
        )
    return (
        f"replace {which} with a real folder that holds the same files, then "
        "run the command again"
    )


def _link_leading_out(target: Path, root: Path) -> Path | None:
    """Return the link that leads *target* out of *root*, if one does.

    Walks up from *target* as spelled (``..`` folded by name) and returns the
    first link that sits inside *root* and leads outside it: the link that
    made the write escape. No user-level or ``~/.config`` link is exempt here,
    since this only names the cause of a refusal. A link above *root*, the
    project folder the operator named included (it leads to *root* itself),
    and an escape spelled with ``..`` or a case variant name no link.
    """
    probe = _spelled(target)
    while probe.parent != probe:
        if (
            _is_link(probe)
            and _within_allowed_root(probe.parent, root)
            and not _within_allowed_root(probe, root)
        ):
            return probe
        probe = probe.parent
    return None


def _validate_target_path(
    target: Path,
    *,
    allowed_root: Path,
    operation: str,
) -> MaterializationResult | None:
    """Return an error result when a resolved target is unsafe.

    An *allowed_root* from :func:`_allowed_write_root` for a project root is
    a :class:`_ProjectFloor`: a link at the project root as the operator
    spelled it is followed wherever it leads, and a link inside it is refused.
    """
    project_floor = isinstance(allowed_root, _ProjectFloor)
    named = _named_floor(allowed_root)
    normalized_target = _normalized(target)
    normalized_root = _normalized(allowed_root)
    if not _within_allowed_root(normalized_target, normalized_root):
        detail = {"allowed_root": _path_text(normalized_root)}
        exit_link = _link_leading_out(target, normalized_root)
        if exit_link is not None:
            detail.update(symlink=_path_text(exit_link), leads_to=_leads_to(exit_link))
        return _result(
            "error",
            operation,
            target,
            "target escapes the allowed materialization root",
            detail=detail,
        )
    symlink = _unsafe_symlink(
        target, normalized_root, project_floor=project_floor, named=named
    )
    if symlink is not None:
        kind = (
            "a symlink" if symlink.is_symlink() else "a junction or other reparse point"
        )
        leads_to = _leads_to(symlink)
        where = (
            f", which leads to {leads_to}" if leads_to != _path_text(symlink) else ""
        )
        return _result(
            "error",
            operation,
            target,
            f"target path crosses a link ({kind}) at {symlink}{where}; Apothem does "
            f"not write through a link{LINK_FIX_LEAD}{_link_fix(symlink)}",
            detail={"symlink": _path_text(symlink), "leads_to": leads_to},
        )
    return None


#: Path segment naming Apothem's own working subtree beneath a harness or
#: project root (mirrors ``_APOTHEM_SUBTREE`` in :mod:`apothem.lib.data_home`,
#: and the ``.apothem/`` segment the manifest's target templates hardcode). No
#: vendor creates this directory, so a target inside it exists only because an
#: Apothem install put it there.
_APOTHEM_SUBTREE: str = ".apothem"


def _holds_content(target: Path) -> bool:
    """Return True when *target* is a file, or a directory holding some file.

    An empty directory is NOT content. Uninstall reverses tree targets
    child-by-child (so operator-authored siblings survive) and leaves the
    directory itself in place, so every Apothem tree target outlives an
    uninstall as an empty shell. Testing mere existence would report a fully
    uninstalled harness as still installed.
    """
    if _is_link(target):
        return False
    if target.is_file():
        return True
    if not target.is_dir():
        return False
    walk = _walk_without_links(target)
    # A folder the walk cannot read may hold files, so it counts as content.
    return bool(walk.files or walk.unreadable)


def _stale_path_proves_install(stale: Path) -> bool:
    """Return True when an earlier layout's folder still holds Apothem's files.

    The manifest's ``stale-sweep`` list names paths earlier releases wrote. One
    that holds content under the Apothem-owned ``.apothem/`` subtree (or sits
    inside it) is the same kind of evidence as a current target there: an
    install exists in the earlier layout, and an uninstall or update has work
    to do on it, even when the current layout's targets are gone. A stale
    path that is a link (a junction on Windows) is the operator's, not
    Apothem's, and is not followed.
    """
    if _is_link(stale):
        return False
    if _APOTHEM_SUBTREE in stale.parts:
        return _holds_content(stale)
    return _holds_content(stale / _APOTHEM_SUBTREE)
