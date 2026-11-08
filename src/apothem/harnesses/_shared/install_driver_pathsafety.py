# SPDX-License-Identifier: MIT

"""Path-escape / symlink / case-fold guards and write-root resolution."""

from __future__ import annotations

import contextlib
import os
import shutil
import stat
import sys
from collections.abc import Callable
from pathlib import Path
from typing import NamedTuple

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


def _filesystem_is_case_insensitive(path: Path) -> bool:
    """Best-effort: does the filesystem holding *path* fold case?

    Probes the nearest existing ancestor by re-casing its name and testing
    existence — a case-insensitive volume still resolves the swapped-case name.
    Falls back to the platform default (Windows and macOS fold case by default;
    other POSIX volumes do not) when no letter-bearing ancestor exists.
    """
    base = path
    while not base.exists() and base.parent != base:
        base = base.parent
    name = base.name
    if base.exists() and name and name.swapcase() != name:
        return base.with_name(name.swapcase()).exists()
    return sys.platform in ("win32", "darwin")


def _within_allowed_root(target: Path, root: Path) -> bool:
    """Return True when *target* is inside *root*, case-fold-aware.

    An exact (case-sensitive) containment is tried first. When it fails and the
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
    if _is_relative_to(normalized_target, normalized_root):
        return True
    if not _filesystem_is_case_insensitive(normalized_root):
        return False
    folded_target = Path(os.path.normcase(str(normalized_target)).lower())
    folded_root = Path(os.path.normcase(str(normalized_root)).lower())
    return _is_relative_to(folded_target, folded_root)


def _existing_chain(path: Path, floor: Path) -> list[Path]:
    """Return existing path components from *path* upward to *floor*."""
    expanded = path.expanduser()
    # ``_is_link`` also sees a junction whose target folder is gone, for which
    # ``exists()`` and ``is_symlink()`` are both False.
    probe = expanded if expanded.exists() or _is_link(expanded) else expanded.parent
    floor_expanded = floor.expanduser()
    chain: list[Path] = []
    while True:
        if probe.exists() or _is_link(probe):
            chain.append(probe)
        if _normalized(probe) == _normalized(floor_expanded):
            break
        parent = probe.parent
        if parent == probe:
            break
        probe = parent
    return chain


def _lexical_key(path: Path) -> str:
    """Return *path* normalized without resolving symlinks, case-folded where the OS is."""
    return os.path.normcase(os.path.normpath(str(path)))


def _is_lexically_within(path: Path, parent: Path) -> bool:
    """Return True when *path* is *parent* or below it, by name only."""
    key, base = _lexical_key(path), _lexical_key(parent)
    return key == base or key.startswith(base.rstrip(os.sep) + os.sep)


def _linkable_ancestors(path: Path, floor: Path) -> list[Path]:
    """Return the user-level folders *path* sits in, when *floor* is the user home.

    Dotfile managers link ``~/.config`` or ``~/.agents`` into a dotfiles
    folder, so a link at or above one of the manifest's closed user-level
    folders (``~/.agents/skills``, ``~/.config/apothem/rules``, ...) is
    allowed. The write guard has already confirmed the resolved path stays in
    the home, and a link below the folder (a skill folder or a file in it) is
    still refused.
    """
    if _normalized(floor) != _normalized(user_home()):
        return []
    return [
        base
        for base in (user_home() / prefix for prefix in USER_LEVEL_PREFIXES)
        if _is_lexically_within(path, base)
    ]


#: Bit set in the reparse tag of a Windows reparse point that names another
#: location: junctions, symbolic links and other name surrogates.
_NAME_SURROGATE_BIT = 0x20000000


def _is_link(path: Path) -> bool:
    """Return True when *path* itself is a symbolic link or a Windows junction.

    A junction is a directory reparse point: ``is_symlink()`` is False for it
    and ``is_dir()`` is True. Any reparse point whose tag carries the
    name-surrogate bit names another location and counts too.
    ``Path.is_junction`` exists from Python 3.12; this reads the tag from
    ``lstat`` so it also works on 3.10 and 3.11.
    """
    if path.is_symlink():
        return True
    if sys.platform != "win32":
        return False
    try:
        tag = getattr(os.lstat(path), "st_reparse_tag", 0)
    except OSError:
        return False
    return bool(tag & _NAME_SURROGATE_BIT) or tag == stat.IO_REPARSE_TAG_MOUNT_POINT


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


def _remove_tree_keeping_links(top: Path) -> list[Path]:
    """Remove the folder *top* and what it holds, except links; return those links.

    ``shutil.rmtree`` does not delete through a Windows junction, but it does
    remove the junction itself, and a link below *top* is the operator's. Each
    link stays, with the folders that hold it; everything else is removed.
    """
    walk = _walk_without_links(top)
    if not walk.links and not walk.unreadable:
        shutil.rmtree(top, onerror=_handle_rm_error)
        return []
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
    return walk.links


def _unsafe_symlink(path: Path, floor: Path) -> Path | None:
    """Return the first symlink in the write path, if any.

    A link at or above a user-level folder (see :func:`_linkable_ancestors`)
    does not count.
    """
    bases = _linkable_ancestors(path, floor)
    for candidate in _existing_chain(path, floor):
        if _is_link(candidate) and not any(
            _is_lexically_within(base, candidate) for base in bases
        ):
            return candidate
    return None


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


def _allowed_write_root(harness_root: Path | None, project_root: Path | None) -> Path:
    """Return the filesystem boundary allowed for resolved install targets."""
    if project_root is not None:
        return _normalized(project_root)
    if harness_root is None:
        raise ValueError("install driver requires either harness_root or project_root")
    return _normalized(harness_root).parent


def _validate_target_path(
    target: Path,
    *,
    allowed_root: Path,
    operation: str,
) -> MaterializationResult | None:
    """Return an error result when a resolved target is unsafe."""
    normalized_target = _normalized(target)
    normalized_root = _normalized(allowed_root)
    if not _within_allowed_root(normalized_target, normalized_root):
        return _result(
            "error",
            operation,
            target,
            "target escapes the allowed materialization root",
            detail={"allowed_root": _path_text(normalized_root)},
        )
    symlink = _unsafe_symlink(target, normalized_root)
    if symlink is not None:
        kind = "a symlink" if symlink.is_symlink() else "a Windows junction"
        return _result(
            "error",
            operation,
            target,
            f"target path crosses a link ({kind}) at {symlink}; Apothem does not write "
            "through a link. To fix it, replace the link with a real folder that "
            "holds the same files, then run the command again",
            detail={"symlink": _path_text(symlink)},
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
