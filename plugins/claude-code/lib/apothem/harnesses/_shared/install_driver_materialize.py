# SPDX-License-Identifier: MIT

"""Install dispatch and the run_install orchestration entrypoint."""

from __future__ import annotations

import contextlib
from pathlib import Path
from typing import Any

from apothem.harnesses._shared import install_driver
from apothem.lib import atomic_io, install_ledger
from apothem.lib.data_home import resolve_install_data_home
from apothem.lib.install_ledger import LedgerRecord
from apothem.lib.propagation import (
    HarnessRules,
    InstallEntry,
)

from .install_driver_apply import (
    HARNESS_EMISSION_APPLIERS,
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
from .install_driver_merge import (
    apply_sentinel_merge,
)
from .install_driver_pathsafety import _allowed_write_root, _root_for
from .install_driver_planvalidation import (
    _dry_run_results,
    _preserved_paths,
    _projected_profile_body,
    _validate_install_plan,
    make_ignore,
)
from .install_driver_treeops import (
    sweep_stale,
)
from .install_driver_types import (
    AuthorizeFn,
    IgnoreFn,
    MaterializationError,
    MaterializationOutcome,
    MaterializationResult,
    MaterializationRun,
    _result,
    backup_session,
    skills_sharing_command_target,
)


def capability_projection_results(harness_name: str) -> list[MaterializationResult]:
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
            skip=skills_sharing_command_target(entry, rules),
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
    applier = HARNESS_EMISSION_APPLIERS.get(entry.mode)
    if applier is not None:
        return applier(
            entry,
            ignore=ignore,
            exclude=rules.exclude,
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


@backup_session()
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
    results = capability_projection_results(harness_name)
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
                    profile=profile,
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
                    preserve=_preserved_paths(root),
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
