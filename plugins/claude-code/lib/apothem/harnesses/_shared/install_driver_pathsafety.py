# SPDX-License-Identifier: MIT

"""Path-escape / symlink / case-fold guards and write-root resolution."""

from __future__ import annotations

import os
import sys
from pathlib import Path

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


def _unsafe_symlink(path: Path, floor: Path) -> Path | None:
    """Return the first symlink in the write path, if any."""
    for candidate in _existing_chain(path, floor):
        if candidate.is_symlink():
            return candidate
    return None


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
