# SPDX-License-Identifier: MIT

"""Directory tree replace / sweep / generated-directory write primitives.

Also holds the skill-directory emission helpers the ``native_skills`` install
mode and its dry-run preview share.
"""

from __future__ import annotations

import os
import shutil
from collections.abc import Callable, Iterable
from pathlib import Path

from .install_driver_backup import _replace_path, backup_existing, write_bytes_safely
from .install_driver_converters import _native_skill_emission
from .install_driver_pathsafety import (
    _remove_tree_keeping_links,
    _skip_links_into,
    _validate_target_path,
)
from .install_driver_types import (
    STAGING_SUFFIX,
    IgnoreFn,
    MaterializationOutcome,
    MaterializationResult,
    _handle_rm_error,
    _is_excluded_path,
    _result,
)

#: Decides whether a user-level skill folder must be left alone: called with the
#: folder and whether it already holds exactly what would be written, it returns
#: the result that explains why, or ``None`` to go ahead (``SkillGuard.check``).
SkillFolderGuard = Callable[[Path, bool], MaterializationResult | None]


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
    kept: list[Path] = []
    if existed:
        backup = backup_existing(
            dst,
            install_root=root,
            harness_name=harness_name,
            allowed_root=allowed_root or root,
        )
        # A link inside the old tree is the operator's: it stays, and the copy
        # goes around it.
        kept = _remove_tree_keeping_links(dst)
    shutil.copytree(
        src, dst, ignore=_with_links_skipped(src, dst, kept, ignore), dirs_exist_ok=True
    )
    return _result(
        "updated" if existed else "created",
        "replace_tree",
        dst,
        "copied directory tree"
        + (f"; left {len(kept)} link(s) in it in place" if kept else ""),
        source=src,
        backup_path=backup,
    )


def _with_links_skipped(
    src: Path,
    dst: Path,
    links: list[Path],
    ignore: Callable[[str, list[str]], Iterable[str]] | None,
) -> Callable[[str, list[str]], Iterable[str]] | None:
    """Return *ignore* extended to skip each of *links* in *dst*."""
    if not links:
        return ignore
    skip_links = _skip_links_into(src, dst, links)
    if ignore is None:
        return skip_links
    return lambda folder, names: set(ignore(folder, names)) | skip_links(folder, names)


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


def _generated_directory_matches(
    directory: Path,
    files: dict[str, bytes],
    ignore: IgnoreFn | None = None,
) -> bool:
    """Return True when *directory* holds exactly *files* (relative POSIX paths).

    *ignore* filters the on-disk side, so interpreter artifacts that collect
    beside installed scripts do not read as drift.
    """
    if not directory.is_dir():
        return False
    on_disk = {path.as_posix() for path in _iter_relative_files(directory, ignore)}
    if on_disk != set(files):
        return False
    return all((directory / name).read_bytes() == data for name, data in files.items())


def _write_generated_directory(
    directory: Path,
    files: dict[str, bytes],
    *,
    root: Path,
    harness_name: str,
    operation: str,
    source: Path,
    allowed_root: Path,
    ignore: IgnoreFn | None = None,
    staged: bool = False,
) -> MaterializationResult:
    """Replace or create a generated directory holding exactly *files*.

    The multi-file form of :func:`_write_single_file_directory`: an unchanged
    directory is left alone; otherwise the old one is backed up and removed,
    and every file is written through the safe-write primitive.

    With *staged* the files are written into a hidden sibling folder first and
    the finished folder is renamed into place, so a failed or interrupted write
    never leaves a half-written folder under the final name (a shared folder
    that an interrupted write left partial would read as someone else's).
    """
    target_error = _validate_target_path(
        directory,
        allowed_root=allowed_root,
        operation=operation,
    )
    if target_error is not None:
        return target_error
    if _generated_directory_matches(directory, files, ignore):
        return _result(
            "unchanged",
            operation,
            directory,
            "generated directory already matches",
            source=source,
        )
    if staged:
        return _write_staged_directory(
            directory,
            files,
            root=root,
            harness_name=harness_name,
            operation=operation,
            source=source,
            allowed_root=allowed_root,
        )
    removed = _replace_path(
        directory,
        install_root=root,
        harness_name=harness_name,
        allowed_root=allowed_root,
    )
    if removed is not None and removed.outcome == "error":
        return removed
    for name in sorted(files):
        target = directory / name
        target.parent.mkdir(parents=True, exist_ok=True)
        write_result = write_bytes_safely(
            target,
            files[name],
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


def _write_staged_directory(
    directory: Path,
    files: dict[str, bytes],
    *,
    root: Path,
    harness_name: str,
    operation: str,
    source: Path,
    allowed_root: Path,
) -> MaterializationResult:
    """Write *files* beside *directory*, then swap the finished folder into place."""
    stage = directory.with_name(f".{directory.name}{STAGING_SUFFIX}")
    shutil.rmtree(stage, onerror=_handle_rm_error)
    try:
        for name in sorted(files):
            written = write_bytes_safely(
                stage / name,
                files[name],
                install_root=root,
                harness_name=harness_name,
                operation=operation,
                source=source,
                allowed_root=allowed_root,
            )
            if written.outcome == "error":
                return written
        removed = _replace_path(
            directory,
            install_root=root,
            harness_name=harness_name,
            allowed_root=allowed_root,
        )
        if removed is not None and removed.outcome == "error":
            return removed
        try:
            stage.replace(directory)
        except OSError as exc:
            return _result(
                "error",
                operation,
                directory,
                f"could not move the finished folder into place: {exc}",
                source=source,
                backup_path=Path(removed.backup_path)
                if removed and removed.backup_path
                else None,
            )
    finally:
        shutil.rmtree(stage, onerror=_handle_rm_error)
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


def _skill_children(
    src: Path, ignore: IgnoreFn | None, exclude: list[str] | None
) -> list[Path]:
    """Return the direct children of a skills cohort that propagate.

    The same selection ``merge_tree_entries`` makes: manifest ``exclude``
    globs and per-directory filters both drop a child.
    """
    children: list[Path] = []
    for source_path in sorted(src.iterdir()):
        if _is_excluded_path(source_path, exclude or []):
            continue
        if ignore is not None and source_path.name in ignore(
            str(src), [source_path.name]
        ):
            continue
        children.append(source_path)
    return children


def _native_skill_dir_files(
    skill_dir: Path, *, harness_name: str, ignore: IgnoreFn | None
) -> dict[str, bytes]:
    """Return a skill directory's emitted files for *harness_name*.

    Every source file is carried byte-for-byte except ``SKILL.md``, which goes
    through the harness's skill emission; the emission's sidecar files are
    added unless the source already ships a file at that path.
    """
    files = {
        rel.as_posix(): (skill_dir / rel).read_bytes()
        for rel in _iter_relative_files(skill_dir, ignore)
    }
    skill_md = skill_dir / "SKILL.md"
    if skill_md.is_file():
        text, sidecars = _native_skill_emission(
            harness_name, skill_md.read_text(encoding="utf-8")
        )
        files["SKILL.md"] = text.encode("utf-8")
        for name, body in sidecars.items():
            files.setdefault(name, body.encode("utf-8"))
    return files


def preview_native_skills(
    *,
    src: Path,
    dst: Path,
    ignore: IgnoreFn | None,
    exclude: list[str] | None,
    harness_name: str,
    guard: SkillFolderGuard | None = None,
) -> list[MaterializationOutcome]:
    """Classify each child a ``native_skills`` install would write, no writes.

    A *guard* that objects to a folder keeps it out of the changes: the install
    would leave that folder alone.
    """
    outcomes: list[MaterializationOutcome] = []
    for source_path in _skill_children(src, ignore, exclude):
        target = dst / source_path.name
        if source_path.is_dir():
            files = _native_skill_dir_files(
                source_path, harness_name=harness_name, ignore=ignore
            )
            matches = _generated_directory_matches(target, files, ignore)
            if guard is not None and guard(target, matches) is not None:
                outcomes.append("unchanged")
                continue
        elif source_path.is_file():
            matches = target.is_file() and (
                target.read_bytes() == source_path.read_bytes()
            )
        else:
            continue
        if matches:
            outcomes.append("unchanged")
        else:
            outcomes.append("updated" if target.exists() else "created")
    return outcomes


def remove_created_dirs(
    directories: Iterable[Path], *, allowed_root: Path
) -> list[MaterializationResult]:
    """Remove the *directories* an install created, now that they are empty.

    Deepest first, so a created parent goes once its created children have. A
    directory that still holds anything (operator content, or data another
    harness keeps) is left in place; so is one outside *allowed_root* or behind
    a symlink. Returns one ``updated`` result per directory removed.
    """
    results: list[MaterializationResult] = []
    ordered = sorted(
        {Path(directory) for directory in directories},
        key=lambda path: len(path.parts),
        reverse=True,
    )
    for directory in ordered:
        if not directory.is_dir() or directory.is_symlink():
            continue
        if (
            _validate_target_path(
                directory, allowed_root=allowed_root, operation="remove_directory"
            )
            is not None
        ):
            continue
        try:
            directory.rmdir()
        except OSError:
            continue
        results.append(
            _result(
                "updated",
                "remove_directory",
                directory,
                "removed an empty directory the install created",
            )
        )
    return results
