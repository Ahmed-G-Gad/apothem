# SPDX-License-Identifier: MIT

"""Directory tree replace / sweep / single-file-directory write primitives."""

from __future__ import annotations

import contextlib
import os
import shutil
from pathlib import Path

from .install_driver_backup import _replace_path, backup_existing, write_bytes_safely
from .install_driver_pathsafety import _validate_target_path
from .install_driver_types import (
    IgnoreFn,
    MaterializationResult,
    _handle_rm_error,
    _result,
)


def _iter_relative_files(root: Path, ignore: IgnoreFn | None) -> list[Path]:
    """Return relative file paths under *root* after applying ignore filters."""
    relative_files: list[Path] = []
    for directory, dirs, files in os.walk(root):
        directory_path = Path(directory)
        ignored = set(ignore(directory, dirs + files)) if ignore else set()
        dirs[:] = sorted(name for name in dirs if name not in ignored)
        for name in sorted(files):
            if name not in ignored:
                relative_files.append((directory_path / name).relative_to(root))
    return relative_files


def _directory_contents_equal(src: Path, dst: Path, ignore: IgnoreFn) -> bool:
    """Return True when two directories have identical emitted file bytes.

    The ignore filter applies to BOTH sides: the installed tree accumulates
    interpreter artifacts (``__pycache__`` beside the hook scripts that run
    in place at the harness root), and those generated entries must not
    defeat the comparison — otherwise every update re-copies an unchanged
    directory.
    """
    if not src.is_dir() or not dst.is_dir():
        return False
    source_files = _iter_relative_files(src, ignore)
    target_files = _iter_relative_files(dst, ignore)
    if source_files != target_files:
        return False
    for relative in source_files:
        if (src / relative).read_bytes() != (dst / relative).read_bytes():
            return False
    return True


def replace_tree(
    src: Path,
    dst: Path,
    ignore: IgnoreFn,
    *,
    install_root: Path | None = None,
    harness_name: str = "manual",
    allowed_root: Path | None = None,
) -> MaterializationResult:
    """Replace ``dst/`` with a fresh copy of ``src/``, eliminating stale files."""
    if not src.is_dir():
        return _result(
            "skipped",
            "replace_tree",
            dst,
            "source directory does not exist",
            source=src,
        )
    root = install_root or dst.parent
    target_error = _validate_target_path(
        dst,
        allowed_root=allowed_root or root,
        operation="replace_tree",
    )
    if target_error is not None:
        return target_error
    if dst.exists() and _directory_contents_equal(src, dst, ignore):
        return _result(
            "unchanged",
            "replace_tree",
            dst,
            "directory already matches",
            source=src,
        )
    existed = dst.exists()
    backup: Path | None = None
    if existed:
        backup = backup_existing(
            dst,
            install_root=root,
            harness_name=harness_name,
            allowed_root=allowed_root or root,
        )
        shutil.rmtree(dst, onerror=_handle_rm_error)
    shutil.copytree(src, dst, ignore=ignore)
    return _result(
        "updated" if existed else "created",
        "replace_tree",
        dst,
        "copied directory tree",
        source=src,
        backup_path=backup,
    )


def sweep_stale(
    stale_sweep: list[str],
    root: Path,
    *,
    harness_name: str = "manual",
    allowed_root: Path | None = None,
) -> list[MaterializationResult]:
    """Remove each stale top-level path under *root* from earlier layouts.

    Directories are removed recursively via ``shutil.rmtree``; files are
    removed via ``Path.unlink``. Missing paths are silently skipped so a
    re-install is idempotent.
    """
    results: list[MaterializationResult] = []
    for legacy in stale_sweep:
        stale = root / legacy
        target_error = _validate_target_path(
            stale,
            allowed_root=allowed_root or root,
            operation="sweep_stale",
        )
        if target_error is not None:
            results.append(target_error)
            continue
        if stale.is_dir():
            backup = backup_existing(
                stale,
                install_root=root,
                harness_name=harness_name,
                allowed_root=allowed_root or root,
            )
            shutil.rmtree(stale, onerror=_handle_rm_error)
            results.append(
                _result(
                    "updated",
                    "sweep_stale",
                    stale,
                    "removed stale directory",
                    backup_path=backup,
                )
            )
        elif stale.is_file():
            backup = backup_existing(
                stale,
                install_root=root,
                harness_name=harness_name,
                allowed_root=allowed_root or root,
            )
            with contextlib.suppress(OSError):  # pragma: no cover
                stale.unlink()
            results.append(
                _result(
                    "updated",
                    "sweep_stale",
                    stale,
                    "removed stale file",
                    backup_path=backup,
                )
            )
        else:
            results.append(
                _result("unchanged", "sweep_stale", stale, "stale path absent")
            )
    return results


def _single_file_directory_matches(
    directory: Path,
    filename: str,
    content: str,
) -> bool:
    """Return True when *directory* contains exactly one matching file."""
    if not directory.is_dir():
        return False
    children = sorted(child.name for child in directory.iterdir())
    return (
        children == [filename]
        and (directory / filename).read_text(encoding="utf-8") == content
    )


def _write_single_file_directory(
    directory: Path,
    filename: str,
    content: str,
    *,
    root: Path,
    harness_name: str,
    operation: str,
    source: Path,
    allowed_root: Path,
) -> MaterializationResult:
    """Replace or create a generated directory containing one text file."""
    target_error = _validate_target_path(
        directory,
        allowed_root=allowed_root,
        operation=operation,
    )
    if target_error is not None:
        return target_error
    if _single_file_directory_matches(directory, filename, content):
        return _result(
            "unchanged",
            operation,
            directory,
            "generated directory already matches",
            source=source,
        )
    removed = _replace_path(
        directory,
        install_root=root,
        harness_name=harness_name,
        allowed_root=allowed_root,
    )
    if removed is not None and removed.outcome == "error":
        return removed
    directory.mkdir(parents=True, exist_ok=True)
    write_result = write_bytes_safely(
        directory / filename,
        content.encode("utf-8"),
        install_root=root,
        harness_name=harness_name,
        operation=operation,
        source=source,
        allowed_root=allowed_root,
    )
    if write_result.outcome == "error":
        return write_result
    return _result(
        "updated" if removed else "created",
        operation,
        directory,
        "wrote generated directory",
        source=source,
        backup_path=Path(removed.backup_path)
        if removed and removed.backup_path
        else None,
    )
