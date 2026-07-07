# SPDX-License-Identifier: MIT

"""Install dispatch and the run_install orchestration entrypoint."""

from __future__ import annotations

import contextlib
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any, Final

from apothem.harnesses._shared import install_driver
from apothem.lib import atomic_io, install_ledger
from apothem.lib.data_home import resolve_install_data_home
from apothem.lib.install_ledger import LedgerRecord
from apothem.lib.propagation import (
    HarnessRules,
    InstallEntry,
    resolve_target,
)

from .install_driver_apply import (
    _COHORT_DOC_FILES,
    apply_codex_agents,
    apply_command_skills,
    apply_gemini_agents,
    apply_gemini_commands,
    apply_markdown_commands,
    apply_merge_tree_entries,
    apply_opencode_agents,
    apply_qwen_agents,
    apply_replace_tree,
    apply_write_text,
)
from .install_driver_backup import _compensating_rollback, _install_lock_path
from .install_driver_converters import (
    _codex_agent_text,
    _gemini_agent_text,
    _gemini_command_text,
    _generated_skill_text,
    _native_markdown_command_text,
    _opencode_agent_text,
    _qwen_agent_text,
)
from .install_driver_merge import (
    _merged_json_text,
    _operator_owned_preview,
    apply_sentinel_merge,
    render_content_tokens,
)
from .install_driver_pathsafety import _allowed_write_root, _root_for
from .install_driver_planvalidation import (
    _projected_profile_body,
    _validate_install_plan,
    make_ignore,
)
from .install_driver_treeops import (
    _directory_contents_equal,
    _single_file_directory_matches,
    sweep_stale,
)
from .install_driver_types import (
    AuthorizeFn,
    IgnoreFn,
    MaterializationError,
    MaterializationOutcome,
    MaterializationResult,
    MaterializationRun,
    _is_excluded_path,
    _result,
    _with_detail,
    resolve_source,
)


def _capability_projection_results(harness_name: str) -> list[MaterializationResult]:
    """Return registry capability warnings for unsupported projection cells."""
    from apothem.lib.harness_registry import get_harness_entry

    try:
        entry = get_harness_entry(harness_name)
    except KeyError:
        return []
    results: list[MaterializationResult] = []
    for capability in sorted(entry.capability_status):
        status = entry.capability_status[capability]
        if status not in {"unsupported", "discovery-pending"}:
            continue
        rationale = entry.unsupported_rationale.get(
            capability,
            f"{capability} is not projected for {entry.public_id}.",
        )
        results.append(
            MaterializationResult(
                outcome="warning",
                operation="capability_projection",
                path=entry.capabilities_path,
                message=rationale,
                detail={"capability": capability, "status": status},
            )
        )
    return results


#: The uniform message every dry-run result carries. A dry run writes nothing,
#: so the message states only that; the prospective ``outcome`` word
#: (``created`` / ``updated`` / ``unchanged``) carries the would-this-change
#: distinction, exactly as the stale-sweep dry-run results already do.
_DRY_RUN_MESSAGE: Final[str] = "dry run: no filesystem changes made"

#: Per-file directory modes whose native target keeps the source basename and
#: whose body is a pure (source_path -> text) conversion. ``gemini_commands``
#: is excluded — it renames to a ``.toml`` target and is handled inline.
_NATIVE_FILE_CONVERTERS: Final[dict[str, Callable[[Path], str]]] = {
    "gemini_agents": _gemini_agent_text,
    "opencode_agents": _opencode_agent_text,
    "qwen_agents": _qwen_agent_text,
    "markdown_commands": _native_markdown_command_text,
}


def _prospective_file_outcome(target: Path, content: bytes) -> MaterializationOutcome:
    """Classify the no-write outcome of writing *content* to *target*.

    Mirrors the create / update / no-op decision
    :func:`install_driver_backup.write_bytes_safely` makes at write time —
    absent target → ``created``; on-disk bytes equal → ``unchanged``; on-disk
    bytes differ → ``updated`` — without touching the filesystem.
    """
    if not target.exists():
        return "created"
    try:
        return "unchanged" if target.read_bytes() == content else "updated"
    except OSError:
        # An unreadable existing target would be backed up and overwritten.
        return "updated"


def _aggregate_dir_outcome(
    child_outcomes: list[MaterializationOutcome], *, target_dir: Path
) -> MaterializationOutcome:
    """Fold a directory entry's per-child outcomes into one entry outcome.

    Every child unchanged (or an empty source directory) → the whole entry is
    ``unchanged``. Otherwise the entry reports ``created`` when its target
    directory does not yet exist (a fresh install) and ``updated`` when it
    exists but its contents would change.
    """
    if not child_outcomes or all(outcome == "unchanged" for outcome in child_outcomes):
        return "unchanged"
    return "created" if not target_dir.exists() else "updated"


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
) -> list[MaterializationOutcome]:
    """Classify each child of a per-file directory mode without writing.

    Each branch mirrors the matching ``apply_*`` function in
    :mod:`install_driver_apply` — the same source enumeration, the same
    cohort-doc exclusion, the same native-text conversion — so the no-write
    classification tracks what the real install would decide.
    """
    outcomes: list[MaterializationOutcome] = []
    if entry.mode == "merge_tree_entries":
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
                if b"${" in data:
                    with contextlib.suppress(UnicodeDecodeError):
                        data = render_content_tokens(
                            data.decode("utf-8"),
                            harness_root=harness_root,
                            project_root=project_root,
                        ).encode("utf-8")
                outcomes.append(_prospective_file_outcome(target, data))
        return outcomes
    for source_path in sorted(src.glob("*.md")):
        if source_path.name in _COHORT_DOC_FILES:
            continue
        if entry.mode == "command_skills":
            skill_dir = dst / source_path.stem
            content = _generated_skill_text(
                source_path, harness_name=harness_name, install_root=root
            )
            if _single_file_directory_matches(skill_dir, "SKILL.md", content):
                outcomes.append("unchanged")
            else:
                outcomes.append("updated" if skill_dir.exists() else "created")
            continue
        if entry.mode == "codex_agents":
            target = dst / f"{source_path.stem}.toml"
            outcome = _prospective_file_outcome(
                target, _codex_agent_text(source_path).encode("utf-8")
            )
            # A stale ``.md`` from a prior layout is removed before the ``.toml``
            # is written, so its presence makes the child a change even when the
            # rendered ``.toml`` already matches.
            if outcome == "unchanged" and (dst / source_path.name).exists():
                outcome = "updated"
            outcomes.append(outcome)
            continue
        if entry.mode == "gemini_commands":
            outcomes.append(
                _prospective_file_outcome(
                    dst / f"{source_path.stem}.toml",
                    _gemini_command_text(source_path).encode("utf-8"),
                )
            )
            continue
        converter = _NATIVE_FILE_CONVERTERS.get(entry.mode)
        if converter is not None:
            outcomes.append(
                _prospective_file_outcome(
                    dst / source_path.name, converter(source_path).encode("utf-8")
                )
            )
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
        ),
        target_dir=target,
    )


def _dry_run_results(
    rules: HarnessRules,
    *,
    root: Path,
    harness_root: Path | None,
    project_root: Path | None,
    harness_name: str,
    profile_body: str | None,
) -> list[MaterializationResult]:
    """Return prospective no-write results for the validated plan.

    Each install entry is classified against its current on-disk target —
    ``created`` (target absent), ``updated`` (target present and differing), or
    ``unchanged`` (target present and already matching) — by mirroring what the
    matching ``apply_*`` function would decide, without touching the filesystem.
    A re-preview after install therefore reports the unchanged targets as no-ops
    instead of phantom writes. The plan validator has already run, so every
    entry's source exists; *profile_body* is folded into ``sentinel_merge``
    anchors so their classification matches the projected managed block.
    """
    ignore = make_ignore(rules.exclude, rules.per_directory_filters)
    results: list[MaterializationResult] = []
    for legacy in rules.stale_sweep:
        stale = root / legacy
        results.append(
            _result(
                "skipped" if stale.exists() else "unchanged",
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
        outcome: MaterializationOutcome
        operator_owned_write = entry.mode == "sentinel_merge" or (
            entry.mode == "write_text" and entry.ownership_class == "operator-owned"
        )
        if operator_owned_write:
            preview = _operator_owned_preview(
                entry,
                harness_root=harness_root,
                project_root=project_root,
                profile_body=profile_body,
            )
            if preview is None:
                outcome = "skipped"
            else:
                target, outcome, diff, gate_required = preview
                if entry.ownership_class == "operator-owned":
                    if diff:
                        detail["diff"] = diff
                    if gate_required:
                        detail["destructive_gate"] = "required"
        else:
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
            )
        results.append(
            _with_detail(
                _result(outcome, entry.mode, target, _DRY_RUN_MESSAGE, source=src),
                detail,
            )
        )
    return results


def _dispatch_install_entry(
    entry: InstallEntry,
    ignore: IgnoreFn,
    rules: HarnessRules,
    *,
    harness_root: Path | None,
    project_root: Path | None,
    harness_name: str,
    authorize: AuthorizeFn | None = None,
    profile_body: str | None = None,
) -> list[MaterializationResult]:
    """Apply one validated install entry and return structured results."""
    if entry.mode == "write_text":
        return apply_write_text(
            entry,
            harness_root=harness_root,
            project_root=project_root,
            harness_name=harness_name,
            authorize=authorize,
        )
    if entry.mode == "sentinel_merge":
        return apply_sentinel_merge(
            entry,
            harness_root=harness_root,
            project_root=project_root,
            harness_name=harness_name,
            authorize=authorize,
            profile_body=profile_body,
        )
    if entry.mode == "replace_tree":
        return apply_replace_tree(
            entry,
            ignore,
            harness_root=harness_root,
            project_root=project_root,
            harness_name=harness_name,
        )
    if entry.mode == "merge_tree_entries":
        return apply_merge_tree_entries(
            entry,
            ignore,
            rules.exclude,
            harness_root=harness_root,
            project_root=project_root,
            harness_name=harness_name,
        )
    if entry.mode == "command_skills":
        return apply_command_skills(
            entry,
            harness_root=harness_root,
            project_root=project_root,
            harness_name=harness_name,
        )
    if entry.mode == "codex_agents":
        return apply_codex_agents(
            entry,
            harness_root=harness_root,
            project_root=project_root,
            harness_name=harness_name,
        )
    if entry.mode == "gemini_agents":
        return apply_gemini_agents(
            entry,
            harness_root=harness_root,
            project_root=project_root,
            harness_name=harness_name,
        )
    if entry.mode == "opencode_agents":
        return apply_opencode_agents(
            entry,
            harness_root=harness_root,
            project_root=project_root,
            harness_name=harness_name,
        )
    if entry.mode == "qwen_agents":
        return apply_qwen_agents(
            entry,
            harness_root=harness_root,
            project_root=project_root,
            harness_name=harness_name,
        )
    if entry.mode == "gemini_commands":
        return apply_gemini_commands(
            entry,
            harness_root=harness_root,
            project_root=project_root,
            harness_name=harness_name,
        )
    if entry.mode == "markdown_commands":
        return apply_markdown_commands(
            entry,
            harness_root=harness_root,
            project_root=project_root,
            harness_name=harness_name,
        )
    raise ValueError(
        f"unknown install entry mode '{entry.mode}' for source '{entry.source}'"
    )


def _materialize_data_surfaces(
    harness_name: str, root: Path, *, profile: dict[str, Any] | None = None
) -> list[MaterializationResult]:
    """Materialize the shared memory, contexts, and learning data surfaces.

    Every target sharing *root* resolves to the SAME Apothem-owned working
    directory (``<base>/.apothem/``, where *base* is derived from the profile's
    ``workspace`` block) — seeded with an empty memory store, an empty contexts
    store, and an empty learning store so the surfaces exist as concrete
    artifacts after install. The seed is idempotent and non-destructive: an
    operator's accumulated records, fragments, and captured learning signals are
    never overwritten, so a re-install — or a second harness installing into the
    same base — preserves them and reports ``unchanged``. Because the home is
    shared, a write under one target is visible to every other target sharing
    the base.

    Seeding the learning surface captures nothing — it only creates the empty
    store. Continuous-learning capture stays default-off: it activates only
    when the operator sets ``enforcement.learning_loop`` and is gated at
    :func:`apothem.lib.learning.capture`.

    Args:
        harness_name: The harness identifier whose install pass triggered the
            materialization. Retained for the result message only — the home is
            shared, not keyed by this identifier.
        root: The install root (harness root or project root) the shared
            working directory is anchored to under project-local scope.
        profile: The install profile dict carrying the ``workspace`` block, or
            ``None`` for the non-interactive path (project-local ``.apothem``).

    Returns:
        One materialization result per data surface (memory, contexts,
        learning). An OS-level failure is reported as a ``warning`` result
        rather than aborting the surrounding install pass.
    """
    from apothem.lib.contexts import ContextStore
    from apothem.lib.learning import LearningStore
    from apothem.lib.memory import MemoryStore

    home_spec = resolve_install_data_home(root, profile=profile)
    preexisting = home_spec.root.exists()
    outcome: MaterializationOutcome = "unchanged" if preexisting else "created"
    try:
        home = home_spec.ensure()
        memory_path = MemoryStore(home).ensure_initialized()
        contexts_path = ContextStore(home).ensure_initialized()
        learning_path = LearningStore(home).ensure_initialized()
    except OSError as exc:
        return [
            _result(
                "warning",
                "data_surface",
                home_spec.root,
                f"could not materialize memory/contexts/learning data surfaces: {exc}",
            )
        ]
    return [
        _result(
            outcome,
            "data_surface",
            memory_path,
            "materialized memory surface data home",
        ),
        _result(
            outcome,
            "data_surface",
            contexts_path,
            "materialized contexts surface data home",
        ),
        _result(
            outcome,
            "data_surface",
            learning_path,
            "materialized learning surface data home",
        ),
    ]


def run_install(
    harness_name: str,
    *,
    harness_root: Path | None = None,
    project_root: Path | None = None,
    dry_run: bool = False,
    authorize: AuthorizeFn | None = None,
    profile: dict[str, Any] | None = None,
) -> MaterializationRun:
    """Propagate *harness_name*'s convention surface to its install root.

    User-scope callers pass ``harness_root`` (created if absent); project-scope
    callers pass ``project_root`` (assumed to exist). The manifest's
    stale-sweep entries are removed first, then each install entry is applied
    in declaration order. Destructive replacements are reversible: existing
    targets are copied to ``~/.apothem/backups/`` before replacement or
    stale-sweep deletion.

    When *profile* is supplied, its projected managed block is folded into every
    ``sentinel_merge`` instruction anchor (alongside the template governance),
    so the shared profile reaches the harness's instruction surface.

    When *authorize* is supplied, every non-additive overwrite of an
    operator-owned target is gated through it: returning ``False`` skips that
    write and leaves the operator's file untouched. ``None`` (the default) is
    the non-interactive path — operator content is merge-preserved and backed
    up, never silently lost.
    """
    rules = install_driver.load_rules(harness_name)
    profile_body = _projected_profile_body(harness_name, profile)
    root = _root_for(harness_root, project_root)
    results = _capability_projection_results(harness_name)
    errors = _validate_install_plan(
        rules,
        root=root,
        harness_root=harness_root,
        project_root=project_root,
    )
    if errors:
        run = MaterializationRun(
            harness=harness_name,
            dry_run=dry_run,
            results=(*results, *errors),
        )
        first_error = errors[0]
        raise MaterializationError(
            f"materialization validation failed: {first_error.message}",
            run,
        )
    if dry_run:
        return MaterializationRun(
            harness=harness_name,
            dry_run=True,
            results=(
                *results,
                *_dry_run_results(
                    rules,
                    root=root,
                    harness_root=harness_root,
                    project_root=project_root,
                    harness_name=harness_name,
                    profile_body=profile_body,
                ),
            ),
        )
    if harness_root is not None:
        harness_root.mkdir(parents=True, exist_ok=True)
    ignore = make_ignore(rules.exclude, rules.per_directory_filters)
    write_root = _allowed_write_root(harness_root, project_root)

    # Transactional pass: serialize concurrent installs into the same
    # (harness, root) behind one advisory lock (a different root keys a different
    # lock and is not blocked), and on a mid-pass failure restore every target
    # written so far from its just-captured backup before re-raising — a partial
    # install never leaves a half-materialized tree. The lock is released on
    # success and on exception (context-manager exit).
    with atomic_io.advisory_lock(_install_lock_path(harness_name, root)):
        try:
            results.extend(
                sweep_stale(
                    rules.stale_sweep,
                    root,
                    harness_name=harness_name,
                    allowed_root=write_root,
                )
            )
            for entry in rules.install:
                entry_results = install_driver._dispatch_install_entry(
                    entry,
                    ignore,
                    rules,
                    harness_root=harness_root,
                    project_root=project_root,
                    harness_name=harness_name,
                    authorize=authorize,
                    profile_body=profile_body,
                )
                results.extend(entry_results)
                entry_errors = [
                    result for result in entry_results if result.outcome == "error"
                ]
                if entry_errors:
                    raise MaterializationError(
                        f"materialization write failed: {entry_errors[0].message}",
                        MaterializationRun(
                            harness=harness_name,
                            dry_run=False,
                            results=tuple(results),
                        ),
                    )
            results.extend(
                _materialize_data_surfaces(harness_name, root, profile=profile)
            )
        except BaseException:
            _compensating_rollback(results, allowed_root=write_root)
            with contextlib.suppress(Exception):
                install_ledger.append_record(
                    LedgerRecord.create(
                        harness=harness_name, root=root, kind="rollback"
                    )
                )
            raise
    return MaterializationRun(
        harness=harness_name,
        dry_run=False,
        results=tuple(results),
    )
