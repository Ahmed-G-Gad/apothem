# SPDX-License-Identifier: MIT

"""Path-escape / symlink / case-fold guards and write-root resolution."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from apothem.lib.propagation import USER_LEVEL_PREFIXES, user_home

from .install_driver_types import MaterializationResult, _path_text, _result


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
    probe = expanded if expanded.exists() or expanded.is_symlink() else expanded.parent
    floor_expanded = floor.expanduser()
    chain: list[Path] = []
    while True:
        if probe.exists() or probe.is_symlink():
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


def _unsafe_symlink(path: Path, floor: Path) -> Path | None:
    """Return the first symlink in the write path, if any.

    A link at or above a user-level folder (see :func:`_linkable_ancestors`)
    does not count.
    """
    bases = _linkable_ancestors(path, floor)
    for candidate in _existing_chain(path, floor):
        if candidate.is_symlink() and not any(
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
        return _result(
            "error",
            operation,
            target,
            "target path crosses a symlink",
            detail={"symlink": _path_text(symlink)},
        )
    return None
