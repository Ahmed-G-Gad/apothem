# SPDX-License-Identifier: MIT

"""Propagation-plan construction, validation, dry-run classification, profile projection."""

from __future__ import annotations

import contextlib
import fnmatch
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any, Final

from apothem.lib.propagation import (
    HarnessRules,
    InstallEntry,
    load_manifest,
    resolve_target,
)

from .install_driver_apply import _COHORT_DOC_FILES
from .install_driver_converters import (
    _antigravity_agent_text,
    _antigravity_rule_text,
    _claude_rule_text,
    _codex_agent_text,
    _command_skill_files,
    _gemini_agent_text,
    _gemini_command_text,
    _native_markdown_command_text,
    _opencode_agent_text,
    _qwen_agent_text,
)
from .install_driver_jsonmerge import CONFIG_UNPARSEABLE_CODE
from .install_driver_merge import (
    PROFILE_DOCUMENT_RELATIVE,
    _merged_json_text,
    _operator_owned_preview,
    render_content_tokens,
)
from .install_driver_pathsafety import (
    _allowed_write_root,
    _normalized,
    _validate_target_path,
)
from .install_driver_preview import (
    DRY_RUN_MESSAGE,
    preview_data_surfaces,
)
from .install_driver_preview import aggregate_dir_outcome as _aggregate_dir_outcome
from .install_driver_preview import (
    prospective_file_outcome as _prospective_file_outcome,
)
from .install_driver_shared import (
    SKILL_MODES,
    check_resolved_target,
    emission_name,
    entry_write_root,
)
from .install_driver_skillguard import SkillGuard, user_level_folders_ok
from .install_driver_treeops import (
    SkillFolderGuard,
    _directory_contents_equal,
    _generated_directory_matches,
    preview_native_skills,
    stale_needs_sweep,
)
from .install_driver_types import (
    _INSTALL_ENTRY_MODES,
    _REFUSED_OWNERSHIP_CLASSES,
    IgnoreFn,
    MaterializationOutcome,
    MaterializationResult,
    _is_excluded_path,
    _result,
    _with_detail,
    resolve_source,
    skills_sharing_command_target,
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


#: Public name of :func:`_generated_targets_for_entry` for callers outside the
#: driver (the user-level report lists the folders an entry should hold).
generated_targets_for_entry = _generated_targets_for_entry


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
        placeholder_error = check_resolved_target(entry, target)
        if placeholder_error is not None:
            errors.append(placeholder_error)
            continue
        source_error = _validate_source(entry, resolve_source(entry.source))
        if source_error is not None:
            errors.append(source_error)
        target_error = _validate_target_path(
            target,
            allowed_root=entry_write_root(entry, harness_root, project_root),
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


_DRY_RUN_MESSAGE: Final[str] = DRY_RUN_MESSAGE

#: Per-file directory modes whose native target keeps the source basename and
#: whose body is a pure (source_path -> text) conversion. ``gemini_commands``
#: is excluded — it renames to a ``.toml`` target and is handled inline.
_NATIVE_FILE_CONVERTERS: Final[dict[str, Callable[[Path], str]]] = {
    "gemini_agents": _gemini_agent_text,
    "opencode_agents": _opencode_agent_text,
    "qwen_agents": _qwen_agent_text,
    "markdown_commands": _native_markdown_command_text,
    "claude_rules": _claude_rule_text,
    "antigravity_rules": _antigravity_rule_text,
    "antigravity_agents": _antigravity_agent_text,
}


def _prospective_merge_tree_outcomes(
    *,
    src: Path,
    dst: Path,
    ignore: IgnoreFn,
    exclude: list[str],
    harness_root: Path | None,
    project_root: Path | None,
    render_tokens: bool = True,
) -> list[MaterializationOutcome]:
    """Classify each child of a ``merge_tree_entries`` entry without writing.

    Mirrors the merge-tree apply: excluded and ignored children are skipped, a
    child directory compares by contents, and a child file compares by its
    token-rendered bytes (its own bytes, for a user-level target).
    """
    outcomes: list[MaterializationOutcome] = []
    for source_path in sorted(src.iterdir()):
        if _is_excluded_path(source_path, exclude):
            continue
        if source_path.name in ignore(str(src), [source_path.name]):
            continue
        target = dst / source_path.name
        if source_path.is_dir():
            if _directory_contents_equal(source_path, target, ignore):
                outcomes.append("unchanged")
            else:
                outcomes.append("updated" if target.exists() else "created")
        elif source_path.is_file():
            data = source_path.read_bytes()
            if render_tokens and b"${" in data:
                with contextlib.suppress(UnicodeDecodeError):
                    data = render_content_tokens(
                        data.decode("utf-8"),
                        harness_root=harness_root,
                        project_root=project_root,
                    ).encode("utf-8")
            outcomes.append(_prospective_file_outcome(target, data))
    return outcomes


def _prospective_markdown_child_outcome(
    mode: str,
    source_path: Path,
    *,
    dst: Path,
    root: Path,
    harness_name: str,
    guard: SkillFolderGuard | None = None,
) -> MaterializationOutcome | None:
    """Classify one markdown source child of a per-file directory mode.

    Returns ``None`` for a mode with no per-file conversion, which contributes
    no child outcome. A *guard* that objects to a command-skill folder keeps it
    out of the changes: the install would leave that folder alone.
    """
    if mode == "command_skills":
        skill_dir = dst / source_path.stem
        files = _command_skill_files(
            source_path, harness_name=harness_name, install_root=root
        )
        matches = _generated_directory_matches(skill_dir, files)
        if matches or (guard is not None and guard(skill_dir, matches) is not None):
            return "unchanged"
        return "updated" if skill_dir.exists() else "created"
    if mode == "codex_agents":
        outcome = _prospective_file_outcome(
            dst / f"{source_path.stem}.toml",
            _codex_agent_text(source_path).encode("utf-8"),
        )
        # A stale ``.md`` from a prior layout is removed before the ``.toml``
        # is written, so its presence makes the child a change even when the
        # rendered ``.toml`` already matches.
        if outcome == "unchanged" and (dst / source_path.name).exists():
            outcome = "updated"
        return outcome
    if mode == "gemini_commands":
        return _prospective_file_outcome(
            dst / f"{source_path.stem}.toml",
            _gemini_command_text(source_path).encode("utf-8"),
        )
    converter = _NATIVE_FILE_CONVERTERS.get(mode)
    if converter is None:
        return None
    return _prospective_file_outcome(
        dst / source_path.name, converter(source_path).encode("utf-8")
    )


def _prospective_child_outcomes(
    entry: InstallEntry,
    *,
    src: Path,
    dst: Path,
    ignore: IgnoreFn,
    exclude: list[str],
    root: Path,
    harness_root: Path | None,
    project_root: Path | None,
    harness_name: str,
    skip: frozenset[str] = frozenset(),
    guard: SkillFolderGuard | None = None,
) -> list[MaterializationOutcome]:
    """Classify each child of a per-file directory mode without writing.

    Each branch mirrors the matching ``apply_*`` function in
    :mod:`install_driver_apply` — the same source enumeration, the same
    cohort-doc exclusion, the same native-text conversion — so the no-write
    classification tracks what the real install would decide. *skip* names
    the commands a same-named skill shadows (``command_skills`` only), and
    *guard* the user-level skill folders the install would leave alone.
    """
    emission = emission_name(entry, harness_name)
    if entry.mode == "native_skills":
        return preview_native_skills(
            src=src,
            dst=dst,
            ignore=ignore,
            exclude=exclude,
            harness_name=emission,
            guard=guard,
        )
    if entry.mode == "merge_tree_entries":
        return _prospective_merge_tree_outcomes(
            src=src,
            dst=dst,
            ignore=ignore,
            exclude=exclude,
            harness_root=harness_root,
            project_root=project_root,
            render_tokens=not entry.user_level,
        )
    outcomes: list[MaterializationOutcome] = []
    for source_path in sorted(src.glob("*.md")):
        if source_path.name in _COHORT_DOC_FILES:
            continue
        if entry.mode == "command_skills" and source_path.stem in skip:
            continue
        outcome = _prospective_markdown_child_outcome(
            entry.mode,
            source_path,
            dst=dst,
            root=root,
            harness_name=emission,
            guard=guard,
        )
        if outcome is not None:
            outcomes.append(outcome)
    return outcomes


def _prospective_entry_outcome(
    entry: InstallEntry,
    *,
    target: Path,
    src: Path,
    ignore: IgnoreFn,
    exclude: list[str],
    root: Path,
    harness_root: Path | None,
    project_root: Path | None,
    harness_name: str,
    skip: frozenset[str] = frozenset(),
    guard: SkillFolderGuard | None = None,
) -> MaterializationOutcome:
    """Classify an Apothem-owned ``write_text`` or any tree entry, no writes.

    Operator-owned ``write_text`` / ``sentinel_merge`` entries route through
    :func:`_operator_owned_preview` instead (it also yields the unified diff);
    this covers the Apothem-owned ``write_text`` direct copy and every directory
    mode. The plan validator guarantees each source exists.
    """
    if entry.mode == "write_text":
        content = render_content_tokens(
            src.read_text(encoding="utf-8"),
            harness_root=harness_root,
            project_root=project_root,
        )
        if target.suffix.lower() == ".json" and target.exists():
            with contextlib.suppress(json.JSONDecodeError, OSError):
                content = _merged_json_text(target, content, prefer_existing=True)
        return _prospective_file_outcome(target, content.encode("utf-8"))
    if entry.mode == "replace_tree":
        if target.exists() and _directory_contents_equal(src, target, ignore):
            return "unchanged"
        return "updated" if target.exists() else "created"
    return _aggregate_dir_outcome(
        _prospective_child_outcomes(
            entry,
            src=src,
            dst=target,
            ignore=ignore,
            exclude=exclude,
            root=root,
            harness_root=harness_root,
            project_root=project_root,
            harness_name=harness_name,
            skip=skip,
            guard=guard,
        ),
        target_dir=target,
    )


def user_level_entry_ok(
    entry: InstallEntry,
    rules: HarnessRules,
    *,
    root: Path,
    harness_root: Path | None,
    project_root: Path | None,
    harness_name: str,
) -> bool:
    """Return True when a user-level *entry*'s folders are all in place and Apothem's.

    Every folder must exist (a skill folder with a ``SKILL.md``), whichever
    harness wrote it. A skill folder that differs from what would be written and
    that no install record lists belongs to someone else, so it fails: the name
    is held. A folder an install lists but whose bytes differ (an older engine
    wrote it) passes; ``update`` rewrites it. An unreadable ledger skips the
    second test.
    """
    folders = _generated_targets_for_entry(
        entry,
        harness_root=harness_root,
        project_root=project_root,
        exclude=rules.exclude,
    )
    if not user_level_folders_ok(entry, folders):
        return False
    if entry.mode not in SKILL_MODES:
        return True
    guard = SkillGuard.load()
    _prospective_child_outcomes(
        entry,
        src=resolve_source(entry.source),
        dst=resolve_target(
            entry.target, harness_root=harness_root, project_root=project_root
        ),
        ignore=make_ignore(rules.exclude, rules.per_directory_filters),
        exclude=rules.exclude,
        root=root,
        harness_root=harness_root,
        project_root=project_root,
        harness_name=harness_name,
        skip=skills_sharing_command_target(entry, rules),
        guard=guard.check,
    )
    return not guard.readable or not guard.conflicts


def _dry_run_results(
    rules: HarnessRules,
    *,
    root: Path,
    harness_root: Path | None,
    project_root: Path | None,
    harness_name: str,
    profile_body: str | None,
    profile: dict[str, Any] | None = None,
) -> list[MaterializationResult]:
    """Return prospective no-write results for the validated plan.

    Each install entry is classified against its current on-disk target —
    ``created`` (target absent), ``updated`` (target present and differing), or
    ``unchanged`` (target present and already matching) — by mirroring what the
    matching ``apply_*`` function would decide, without touching the filesystem.
    A re-preview after install therefore reports the unchanged targets as no-ops
    instead of phantom writes. The plan validator has already run, so every
    entry's source exists; *profile_body* is folded into ``sentinel_merge``
    anchors so their classification matches the projected managed block. The
    shared data stores the install seeds are previewed last, as the install
    writes them.
    """
    ignore = make_ignore(rules.exclude, rules.per_directory_filters)
    results: list[MaterializationResult] = []
    preserve = _preserved_paths(root)
    for legacy in rules.stale_sweep:
        stale = root / legacy
        results.append(
            _result(
                "skipped" if stale_needs_sweep(stale, preserve) else "unchanged",
                "sweep_stale",
                stale,
                _DRY_RUN_MESSAGE,
            )
        )
    for entry in rules.install:
        target = resolve_target(
            entry.target,
            harness_root=harness_root,
            project_root=project_root,
        )
        src = resolve_source(entry.source)
        detail: dict[str, str] = {"ownership_class": entry.ownership_class}
        conflicts: list[MaterializationResult] = []
        outcome: MaterializationOutcome
        message = _DRY_RUN_MESSAGE
        operator_owned_write = entry.mode == "sentinel_merge" or (
            entry.mode == "write_text" and entry.ownership_class == "operator-owned"
        )
        if operator_owned_write:
            preview = _operator_owned_preview(
                entry,
                harness_root=harness_root,
                project_root=project_root,
                profile_body=profile_body,
                harness_name=harness_name,
            )
            if preview is None:
                outcome = "skipped"
            elif preview.refusal is not None:
                target, outcome = preview.target, "error"
                message = preview.refusal.reason
                detail["code"] = CONFIG_UNPARSEABLE_CODE
                detail["fix"] = preview.refusal.fix
            else:
                target, outcome = preview.target, preview.outcome
                if entry.ownership_class == "operator-owned":
                    if preview.diff:
                        detail["diff"] = preview.diff
                    if preview.gate_required:
                        detail["destructive_gate"] = "required"
        else:
            skill_guard = SkillGuard.load() if entry.user_level else None
            outcome = _prospective_entry_outcome(
                entry,
                target=target,
                src=src,
                ignore=ignore,
                exclude=rules.exclude,
                root=root,
                harness_root=harness_root,
                project_root=project_root,
                harness_name=harness_name,
                skip=skills_sharing_command_target(entry, rules),
                guard=skill_guard.check if skill_guard is not None else None,
            )
            if skill_guard is not None:
                conflicts = skill_guard.conflicts
        results.append(
            _with_detail(
                _result(outcome, entry.mode, target, message, source=src),
                detail,
            )
        )
        results.extend(conflicts)
    results.extend(preview_data_surfaces(root, profile=profile))
    return results


def _preserved_paths(root: Path) -> frozenset[Path]:
    """Return the current files a stale-sweep entry must not remove.

    The single-file-config adapters project the profile document into
    ``apothem/rules/``, a directory earlier layouts used for copied rules.
    """
    return frozenset({_normalized(root / PROFILE_DOCUMENT_RELATIVE)})
