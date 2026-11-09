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
    MaterializationError,
    MaterializationResult,
    MaterializationRun,
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
    # ``lexists`` (an ``lstat``) also sees a link or junction whose target is
    # gone; ``_is_link`` covers a junction ``lstat`` may not report.
    probe = (
        expanded if os.path.lexists(expanded) or _is_link(expanded) else expanded.parent
    )
    floor_expanded = floor.expanduser()
    chain: list[Path] = []
    while True:
        if os.path.lexists(probe) or _is_link(probe):
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
    if _normalized(floor) == _normalized(home):
        bases = [
            base
            for base in (home / prefix for prefix in USER_LEVEL_PREFIXES)
            if _is_lexically_within(path, base)
        ]
    config = home / ".config"
    if (
        _is_lexically_within(path, config)
        and _is_relative_to(_normalized(floor), _normalized(config))
        and _within_allowed_root(config, home)
    ):
        bases.append(config)
    return bases


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


def _unsafe_symlink(path: Path, floor: Path) -> Path | None:
    """Return the first symlink or junction in the write path, if any.

    A link at or above a user-level folder, or at ``~/.config`` for an install
    root below it (see :func:`_linkable_ancestors`), does not count. Nor does
    the home folder itself or a folder above it, as the home is spelled (a
    profile moved to another drive behind a junction): the caller has already
    checked that the resolved path stays inside the resolved allowed root, so
    such a link cannot lead the write out of the home.
    """
    home = user_home()
    bases = _linkable_ancestors(path, floor)
    for candidate in _existing_chain(path, floor):
        if _is_lexically_within(home, candidate):
            continue
        if _is_link(candidate) and not any(
            _is_lexically_within(base, candidate) for base in bases
        ):
            return candidate
    return None


def _names_same_folder(first: Path, second: Path) -> bool:
    """Return True when *first* and *second* name one folder.

    When both exist they are compared by file identity, which also matches a
    change of case on a case-insensitive volume, a short (8.3) name, a bind
    mount, a link or a junction. Otherwise, or when the filesystem reports no
    inode numbers (some network and FUSE mounts do), their resolved paths are
    compared.
    """
    try:
        stats = [first.stat(), second.stat()]
    except OSError:
        stats = []
    if stats and all(item.st_ino for item in stats):
        return os.path.samestat(stats[0], stats[1])
    return _normalized(first) == _normalized(second)


def _spelled_inside_home(path: Path) -> bool:
    """Return True when *path*, as spelled, passes through the home folder.

    One of its spelled ancestors (or *path* itself) is the home folder, by
    file identity: the home as it is spelled, resolved, in another case or by
    its short name.
    """
    home = user_home()
    return any(_names_same_folder(folder, home) for folder in (path, *path.parents))


def _link_leaving_home(root: Path) -> Path | None:
    """Return the link that leads *root*, spelled inside the home, out of it.

    ``None`` when *root* is spelled outside the home (the operator named that
    folder, through ``XDG_CONFIG_HOME`` or ``CODEX_HOME``), when it stays
    inside the home once resolved, or when no link sits between it and the
    home (a bind mount or a macOS firmlink naming the home another way leads
    nowhere else). The write guard stops its walk at the folder above the
    install root, so a link higher up (``CODEX_HOME=~/a/b/codex`` with ``~/a``
    leading out of the home) is found here. Of the links on the way up, the
    one named is the highest that leads out of the home itself, not a link
    below it that stays inside (``~/a`` leading to ``~/c`` while ``~/a/b``
    leads out names ``~/a/b``).
    """
    home = user_home()
    if not _spelled_inside_home(root) or _within_allowed_root(root, home):
        return None
    first: Path | None = None
    leading_out: Path | None = None
    for folder in (root, *root.parents):
        if _names_same_folder(folder, home):
            break
        if not _is_link(folder):
            continue
        first = first or folder
        if not _within_allowed_root(folder, home):
            leading_out = folder
    return leading_out or first


def _first_link(root: Path) -> Path | None:
    """Return the first link at or above *root*, read without resolving any."""
    for folder in (root, *root.parents):
        try:
            if _is_link(folder):
                return folder
        except OSError:
            return None
    return None


def link_leaving_home_refusal(
    root: Path, *, operation: str
) -> MaterializationResult | None:
    """Return the error result for a link that leads *root* out of the home.

    ``None`` when there is no such link (see :func:`_link_leaving_home`) or a
    folder on the way cannot be read; the result's ``detail["symlink"]``
    names the link. A link loop counts as such a link where resolving it
    raises :class:`RuntimeError` (Python 3.10 to 3.12): the first link found
    is named. From Python 3.13 resolving a loop does not raise, so this check
    names no link for it; the write that follows cannot pass through the loop
    and stops there.
    """
    try:
        link = _link_leaving_home(root)
    except RuntimeError:
        link = _first_link(root) or root
    except (OSError, ValueError):
        return None
    if link is None:
        return None
    return _result(
        "error",
        operation,
        root,
        "target path crosses a symlink",
        detail={"symlink": _path_text(link)},
    )


def refuse_link_leaving_home(
    harness_name: str,
    root: Path,
    *,
    operation: str,
    uninstall: bool = False,
    dry_run: bool = False,
) -> None:
    """Raise when a link leads the install root *root* out of the home.

    Run before an install, update or uninstall of a harness whose root an
    environment variable moves (see :func:`_link_leaving_home`); nothing is
    written or removed. A link loop on the way up (Python 3.10 to 3.12 raise
    :class:`RuntimeError` resolving one) is refused too, naming the first link
    found. A folder that cannot be read is left to the write guard, which
    still checks every target. Read-only commands never call this.

    Raises:
        MaterializationError: When there is such a link, or a link loop.
    """
    refusal = link_leaving_home_refusal(root, operation=operation)
    if refusal is None:
        return
    link = refusal.detail.get("symlink", str(root))
    message = (
        f"uninstall refused: {refusal.message} ({link} leads outside the home folder)"
        if uninstall
        else f"materialization write failed: {refusal.message}"
    )
    raise MaterializationError(
        message,
        MaterializationRun(harness=harness_name, dry_run=dry_run, results=(refusal,)),
    )


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
        kind = (
            "a symlink" if symlink.is_symlink() else "a junction or other reparse point"
        )
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
