# SPDX-License-Identifier: MIT

"""Propagation-plan construction, source/target/ownership validation, profile projection."""

from __future__ import annotations

import fnmatch
from pathlib import Path
from typing import Any

from apothem.lib.propagation import (
    HarnessRules,
    InstallEntry,
    load_manifest,
    resolve_target,
)

from .install_driver_apply import _COHORT_DOC_FILES
from .install_driver_pathsafety import _allowed_write_root, _validate_target_path
from .install_driver_types import (
    _INSTALL_ENTRY_MODES,
    _REFUSED_OWNERSHIP_CLASSES,
    IgnoreFn,
    MaterializationResult,
    _is_excluded_path,
    _result,
    resolve_source,
)


def load_rules(harness_name: str) -> HarnessRules:
    """Load *harness_name*'s propagation rules from the canonical manifest.

    Raises:
        RuntimeError: When the manifest has no entry for *harness_name*.
    """
    manifest = load_manifest()
    if harness_name not in manifest:
        raise RuntimeError(
            f"propagation manifest is missing the '{harness_name}' harness entry"
        )
    return manifest[harness_name]


def make_ignore(exclude: list[str], per_dir_filters: dict[str, list[str]]) -> IgnoreFn:
    """Return a ``shutil.copytree`` ignore-function bound to manifest filters.

    The returned function strips every ``exclude`` glob from any directory
    walked by ``shutil.copytree`` and additionally strips
    ``per_dir_filters[<basename>]`` filenames from a directory whose basename
    matches a key in ``per_dir_filters``. Manifest-driven; no hardcoded
    patterns.
    """

    def _ignore(directory: str, contents: list[str]) -> list[str]:
        excluded: list[str] = []
        for name in contents:
            if any(fnmatch.fnmatch(name, pattern) for pattern in exclude):
                excluded.append(name)
                continue
            dir_basename = Path(directory).name
            if (
                dir_basename in per_dir_filters
                and name in per_dir_filters[dir_basename]
            ):
                excluded.append(name)
        return excluded

    return _ignore


def _generated_targets_for_entry(
    entry: InstallEntry,
    *,
    harness_root: Path | None,
    project_root: Path | None,
    exclude: list[str],
) -> list[Path]:
    """Return concrete generated targets for non-single-file install modes."""
    src = resolve_source(entry.source)
    dst = resolve_target(
        entry.target,
        harness_root=harness_root,
        project_root=project_root,
    )
    if entry.mode == "replace_tree":
        return [dst]
    if not src.is_dir():
        return []
    if entry.mode in {"merge_tree_entries", "native_skills"}:
        return [
            dst / source_path.name
            for source_path in sorted(src.iterdir())
            if not _is_excluded_path(source_path, exclude)
        ]
    if entry.mode == "command_skills":
        return [
            dst / source_path.stem
            for source_path in sorted(src.glob("*.md"))
            if source_path.name not in _COHORT_DOC_FILES
        ]
    if entry.mode in {"codex_agents", "gemini_commands"}:
        suffix = ".toml"
        return [
            dst / f"{source_path.stem}{suffix}"
            for source_path in sorted(src.glob("*.md"))
            if source_path.name not in _COHORT_DOC_FILES
        ]
    if entry.mode in {
        "gemini_agents",
        "opencode_agents",
        "qwen_agents",
        "antigravity_agents",
    }:
        return [
            dst / source_path.name
            for source_path in sorted(src.glob("*.md"))
            if source_path.name not in _COHORT_DOC_FILES
        ]
    if entry.mode in {"markdown_commands", "claude_rules", "antigravity_rules"}:
        return [
            dst / source_path.name
            for source_path in sorted(src.glob("*.md"))
            if source_path.name not in _COHORT_DOC_FILES
        ]
    return []


def _validate_ownership_class(
    entry: InstallEntry, target: Path
) -> MaterializationResult | None:
    """Return an error when an entry targets a refused ownership class.

    A manifest entry whose ``ownership_class`` is ``vendor-reserved`` (a
    vendor-managed path) or ``immutable`` (an append-only record) is a defect:
    the propagation driver must never write such a path (model §5.F hard
    refusal). The guard fires before the first write.
    """
    if entry.ownership_class in _REFUSED_OWNERSHIP_CLASSES:
        return _result(
            "error",
            entry.mode,
            target,
            f"{entry.ownership_class} path is not a write target",
            source=resolve_source(entry.source),
            detail={"ownership_class": entry.ownership_class},
        )
    return None


def _validate_source(entry: InstallEntry, src: Path) -> MaterializationResult | None:
    """Return an error result when a manifest source does not match its mode."""
    if entry.mode in {"write_text", "sentinel_merge"}:
        if not src.is_file():
            return _result(
                "error",
                entry.mode,
                src,
                "manifest source must be an existing file",
                source=src,
            )
        return None
    if not src.is_dir():
        return _result(
            "error",
            entry.mode,
            src,
            "manifest source must be an existing directory",
            source=src,
        )
    return None


def _validate_install_plan(
    rules: HarnessRules,
    *,
    root: Path,
    harness_root: Path | None,
    project_root: Path | None,
) -> list[MaterializationResult]:
    """Validate all sources and targets before the first write starts."""
    errors: list[MaterializationResult] = []
    allowed_root = _allowed_write_root(harness_root, project_root)
    for legacy in rules.stale_sweep:
        target_error = _validate_target_path(
            root / legacy,
            allowed_root=allowed_root,
            operation="sweep_stale",
        )
        if target_error is not None:
            errors.append(target_error)
    for entry in rules.install:
        target = resolve_target(
            entry.target,
            harness_root=harness_root,
            project_root=project_root,
        )
        if entry.mode not in _INSTALL_ENTRY_MODES:
            errors.append(
                _result(
                    "error",
                    entry.mode,
                    target,
                    "unknown install entry mode",
                    source=resolve_source(entry.source),
                )
            )
            continue
        ownership_error = _validate_ownership_class(entry, target)
        if ownership_error is not None:
            errors.append(ownership_error)
            continue
        source_error = _validate_source(entry, resolve_source(entry.source))
        if source_error is not None:
            errors.append(source_error)
        target_error = _validate_target_path(
            target,
            allowed_root=allowed_root,
            operation=entry.mode,
        )
        if target_error is not None:
            errors.append(target_error)
    return errors


def _projected_profile_body(
    harness_name: str, profile: dict[str, Any] | None
) -> str | None:
    """Return the projected managed-block body for *profile*, or None.

    Resolves the manifest *harness_name* to its public adapter id, applies the
    per-harness override, and renders the shared profile's managed block. None
    when no profile is supplied (the static-only install path).
    """
    if not profile:
        return None
    from apothem.lib.harness_registry import get_harness_entry
    from apothem.lib.profile import coerce_profile
    from apothem.lib.profile_projection import project

    try:
        public_id = get_harness_entry(harness_name).public_id
    except KeyError:
        public_id = harness_name.replace("_", "-")
    for_harness = coerce_profile(profile).for_harness(public_id)
    return project(for_harness, public_id).managed_block_body
