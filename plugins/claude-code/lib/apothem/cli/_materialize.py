# SPDX-License-Identifier: MIT

"""Shared install/update materialization orchestrators.

``_materialize`` drives a single-harness or batch install/update from the
shared profile (blast-radius preview, placeholder advisory, fail-fast batch
error handling — the first harness failure aborts the run and emits the
partial result accumulated so far, lifecycle envelope);
``_dry_run_materialization`` returns a
no-write plan run. Both are consumed by the install / update / quickstart
command modules. Patchable-helper call sites resolve through the
``apothem.cli`` package (``_pkg``)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

import click
from rich.console import Console
from rich.markup import escape

import apothem.cli as _pkg
from apothem.cli._common_flags import get_console
from apothem.cli._helpers import (
    _EXIT_EXPECTED,
    _EXIT_PARTIAL,
    _Adapter,
    _adapter_resolve_output_path,
    _CliUserError,
    _emit_expected_error,
    _invoke_with_project,
    _lifecycle_envelope,
    _load_profile,
    _materialization_error,
    _partition_blast_radius,
    _placeholder_advisory_entry,
    _placeholder_identity_fields,
    _profile_error,
    _profile_scaffold_text,
    _render_blast_radius,
    _resolve_profile_path,
    _resolve_project_root,
    _result_dicts,
    _warning_dicts,
    _write_profile_text_safely,
)
from apothem.cli._json_formatter import emit_json
from apothem.harnesses._shared.install_driver import (
    MaterializationError,
    MaterializationResult,
    MaterializationRun,
)
from apothem.lib.atomic_io import write_bytes_atomically
from apothem.lib.clean_slate import CleanSlateError, CleanSlateResult, run_clean_slate
from apothem.lib.install_advisories import (
    mcp_profile_advisories,
    shared_root_advisories,
)
from apothem.lib.profile import ProfileValidationError, validate_profile


@dataclass(frozen=True)
class _RunContext:
    """The fixed inputs of one install/update run, shared by its phases."""

    harness: str
    profile_path: Path
    verb_present: str
    verb_past: str
    fmt: str
    dry_run: bool
    quiet: bool
    verbose: bool
    con: Console

    @property
    def is_batch(self) -> bool:
        """Whether the selection is the ``all`` batch."""
        return self.harness.strip().lower() == "all"

    def fail(
        self,
        error: dict[str, object],
        *,
        project_root: Path | None = None,
        files_written: list[str] | None = None,
        results: list[dict[str, object]] | None = None,
        warnings: list[dict[str, object]] | None = None,
        exit_code: int = _EXIT_EXPECTED,
    ) -> None:
        """Emit an expected failure for this run (the emitter exits)."""
        _emit_expected_error(
            command=self.verb_present,
            fmt=self.fmt,
            harness=self.harness,
            profile_path=self.profile_path,
            project_root=project_root,
            error=error,
            files_written=files_written,
            results=results,
            warnings=warnings,
            exit_code=exit_code,
        )


@dataclass(frozen=True)
class _RunInputs:
    """What the load phase resolved: the project root, profile, and adapters."""

    project_root: Path | None
    shared_profile: dict[str, Any]
    adapters: list[tuple[str, _Adapter]]
    first_run_entry: dict[str, object] | None


@dataclass
class _RunTotals:
    """What the per-harness loop has accumulated so far."""

    files_written: list[str] = field(default_factory=list)
    results: list[dict[str, object]] = field(default_factory=list)
    warnings: list[dict[str, object]] = field(default_factory=list)
    last_output_path: Path | None = None
    last_materialization: MaterializationRun | None = None


def _materialize(
    harness: str,
    profile: str | None,
    dry_run: bool,
    verb_present: str,
    verb_past: str,
    *,
    fmt: str = "plain",
    quiet: bool = False,
    no_color: bool = False,
    project: str | None = None,
    clean: bool = False,
    assume_yes: bool = False,
    verbose: bool = False,
    payload_sink: list[dict[str, object]] | None = None,
    create_default_profile: bool = False,
) -> None:
    """Install or update a harness adapter from the shared profile.

    The command accepts a single harness id or ``all``. Profiles are
    validated before dry-runs and writes, and JSON output always uses the
    lifecycle envelope required by the product contract.

    With *create_default_profile* (``install``), a run that names no
    ``--profile`` and finds no profile at the default path scaffolds the
    starter profile first, so the first documented command succeeds on a
    clean machine. A dry run uses that scaffold in memory and writes nothing.

    The run proceeds in phases: load the profile and adapters, the opt-in
    clean-slate removal, the blast-radius disclosure, the run-wide advisories,
    one materialization per adapter, then the closing envelope or summary.
    """
    con = get_console(no_color=no_color, quiet=quiet)
    profile_path = _resolve_profile_path(profile)
    run = _RunContext(
        harness=harness,
        profile_path=profile_path,
        verb_present=verb_present,
        verb_past=verb_past,
        fmt=fmt,
        dry_run=dry_run,
        quiet=quiet,
        verbose=verbose,
        con=con,
    )
    first_run = (
        create_default_profile
        and profile is None
        and not profile_path.exists()
        and not profile_path.is_symlink()
    )
    inputs = _load_run_inputs(run, project, first_run=first_run)
    if inputs is None:
        return

    clean_result: CleanSlateResult | None = None
    if clean:
        proceed, clean_result = _clean_slate_phase(run, assume_yes=assume_yes)
        if not proceed:
            return

    _disclose_blast_radius(run, inputs, assume_yes=assume_yes)

    totals = _RunTotals()
    _record_run_advisories(run, inputs, totals)
    for harness_id, adapter in inputs.adapters:
        if not _materialize_harness(run, inputs, totals, harness_id, adapter):
            return

    _emit_run_outcome(
        run,
        inputs,
        totals,
        clean_result=clean_result,
        payload_sink=payload_sink,
    )
    if clean and not dry_run and fmt != "json" and not quiet:
        verify_harness = "all" if run.is_batch else harness
        con.print(
            "[bold]Next step:[/] confirm the fresh install with "
            f"[cyan]apothem verify --harness {escape(verify_harness)}[/]"
        )


def _load_run_inputs(
    run: _RunContext, project: str | None, *, first_run: bool
) -> _RunInputs | None:
    """Resolve the project root, the shared profile, and the selected adapters.

    Returns ``None`` after emitting the expected error when any of them fails.
    """
    first_run_entry: dict[str, object] | None = None
    try:
        project_root = _resolve_project_root(project)
        if first_run:
            shared_profile, first_run_entry = _first_run_profile(
                run.profile_path, dry_run=run.dry_run
            )
        else:
            shared_profile = _load_profile(run.profile_path)
        adapters = _pkg._select_and_load_adapters(
            run.harness,
            project_root,
            shared_profile=shared_profile,
            apply_excludes=run.is_batch,
        )
    except ProfileValidationError as exc:
        run.fail(_profile_error(exc))
        return None
    except _CliUserError as exc:
        run.fail(exc.to_dict())
        return None
    return _RunInputs(project_root, shared_profile, adapters, first_run_entry)


def _clean_slate_phase(
    run: _RunContext, *, assume_yes: bool
) -> tuple[bool, CleanSlateResult | None]:
    """Run the opt-in clean-slate removal, then restore the profile file.

    It runs after the profile is loaded into memory and before any fresh
    materialization. The profile file is one of the bounded removal targets,
    so its bytes are captured here and restored after removal: the shared
    profile is the operator's identity source of truth, not stale install
    state, and the timestamped backup preserves every removed target for
    recovery. Returns ``(proceed, result)``; *proceed* is false once an
    error has been emitted.
    """
    profile_path = run.profile_path
    profile_bytes = profile_path.read_bytes() if profile_path.is_file() else None
    try:
        clean_result = run_clean_slate(
            Path.home(),
            dry_run=run.dry_run,
            assume_yes=assume_yes,
            # Use the patchable seam (not raw sys.stdin.isatty()) so the
            # clean-slate interactivity gate is test-reachable, matching the
            # blast-radius confirmation.
            interactive=_pkg._stdin_is_interactive(),
            echo=(run.con.print if run.fmt != "json" else None),
        )
    except CleanSlateError as exc:
        run.fail(
            _CliUserError(
                code="clean_slate.refused",
                message="Clean-slate removal was refused.",
                field="clean",
                reason=str(exc),
                fix="Re-run interactively, pass --yes for non-interactive use, "
                "or correct the unsafe target before retrying.",
            ).to_dict()
        )
        return False, None
    if not run.dry_run and profile_bytes is not None:
        # This restore is the identity safety net, so it gets the same care
        # as every other write: clean-slate has just removed the profile,
        # and these in-memory bytes plus the timestamped backup are the only
        # copies left. A raw write would surface a disk-full or
        # permission failure as a traceback with the canonical path already
        # empty, and an interruption mid-write would leave it truncated.
        try:
            write_bytes_atomically(profile_path, profile_bytes)
        except OSError as exc:
            backup_dir = clean_result.backup_dir if clean_result else None
            run.fail(
                _CliUserError(
                    code="clean_slate.profile_restore_failed",
                    message="Clean-slate removal ran, but the profile could "
                    "not be written back.",
                    field="clean",
                    reason=str(exc),
                    fix=(
                        "Copy the profile back from the clean-slate backup "
                        f"at {backup_dir}."
                        if backup_dir is not None
                        else "Restore the profile from the clean-slate "
                        "backup directory reported above."
                    ),
                ).to_dict()
            )
            return False, clean_result
    # A clean dry run falls through to the materialization preview: the
    # operation previews both phases (removals, then fresh writes), and JSON
    # mode keeps its single-envelope contract — the removal preview rides the
    # envelope's "clean" key instead of truncating the run.
    return True, clean_result


def _disclose_blast_radius(
    run: _RunContext, inputs: _RunInputs, *, assume_yes: bool
) -> None:
    """Disclose where a multi-harness install writes; confirm home-rooted writes.

    An ``all`` install fans out into mixed scopes: project-scope adapters write
    under --project, but user-scope adapters write under the operator's real
    home directory, a surprise worth disclosing before any byte is written.
    The grouped preview prints in plain mode; when the selection writes
    outside the supplied project root, an interactive confirmation guards the
    home-rooted writes. --yes, a non-interactive context, --dry-run, and
    --format json each bypass the prompt (dry-run and json still print/return
    the preview data without mutating). Single-named installs and update are
    out of scope.
    """
    if not (run.is_batch and run.verb_present == "install" and run.fmt != "json"):
        return
    within, outside = _partition_blast_radius(inputs.adapters, inputs.project_root)
    _render_blast_radius(run.con, within, outside, inputs.project_root)
    if not run.dry_run and outside and not assume_yes and _pkg._stdin_is_interactive():
        click.confirm("Proceed and write these files?", abort=True)


def _record_run_advisories(
    run: _RunContext, inputs: _RunInputs, totals: _RunTotals
) -> None:
    """Record the run-wide advisories once, before any harness is written."""
    con = run.con
    first_run_entry = inputs.first_run_entry
    if first_run_entry is not None:
        totals.warnings.append(first_run_entry)
        if run.fmt != "json":
            if run.dry_run:
                con.print(f"[yellow]Note:[/] {escape(str(first_run_entry['message']))}")
            else:
                con.print(
                    f"[green]✓[/] Created a starter profile at "
                    f"[cyan]{escape(str(run.profile_path))}[/]"
                )

    # Placeholder-identity advisory (install + update). When the loaded profile
    # still carries the shipped scaffold identity, surface a single advisory so a
    # fake identity is not silently projected — advisory only, never blocking
    # (identity is never fabricated or coerced). It rides the JSON warnings array
    # and prints once in plain mode, regardless of the harness selection.
    placeholder_fields = _placeholder_identity_fields(inputs.shared_profile)
    if placeholder_fields:
        advisory = _placeholder_advisory_entry(run.profile_path, placeholder_fields)
        totals.warnings.append(advisory)
        if run.fmt != "json":
            con.print(f"[yellow]Note:[/] {escape(str(advisory['message']))}")
    # MCP advisories (install + update): a deprecated transport, plain http:// to
    # a remote host, or a literal credential in headers/env would be copied into
    # every harness config that takes MCP servers. Advisory only, printed once.
    for advisory in mcp_profile_advisories(inputs.shared_profile, run.profile_path):
        totals.warnings.append(advisory)
        if run.fmt != "json":
            con.print(f"[yellow]Note:[/] {escape(str(advisory['message']))}")


def _run_adapter(
    run: _RunContext,
    inputs: _RunInputs,
    harness_id: str,
    adapter: _Adapter,
    output_path: Path,
) -> MaterializationRun | None:
    """Preview, update, or install one adapter, per the run's verb and mode."""
    if run.dry_run:
        return _dry_run_materialization(
            harness_id,
            adapter,
            output_path,
            inputs.project_root,
            inputs.shared_profile,
        )
    action = adapter.update if run.verb_present == "update" else adapter.install
    maybe_run = _invoke_with_project(
        action, inputs.shared_profile, project=inputs.project_root
    )
    return maybe_run if isinstance(maybe_run, MaterializationRun) else None


def _materialize_harness(
    run: _RunContext,
    inputs: _RunInputs,
    totals: _RunTotals,
    harness_id: str,
    adapter: _Adapter,
) -> bool:
    """Materialize one harness and fold its outcome into *totals*.

    The first harness failure aborts the batch: it emits the partial result
    accumulated so far and returns ``False``.
    """
    project_root = inputs.project_root
    output_path = _adapter_resolve_output_path(adapter, project_root)
    totals.last_output_path = output_path
    try:
        materialization = _run_adapter(run, inputs, harness_id, adapter, output_path)
    except MaterializationError as exc:
        files_written = [*totals.files_written, *exc.run.files_written]
        run.fail(
            _materialization_error(exc, files_written=exc.run.files_written),
            project_root=project_root,
            files_written=files_written,
            results=[*totals.results, *_result_dicts(harness_id, exc.run)],
            warnings=[*totals.warnings, *_warning_dicts(harness_id, exc.run)],
            exit_code=_EXIT_PARTIAL if files_written else _EXIT_EXPECTED,
        )
        return False
    except NotImplementedError:
        error = _CliUserError(
            code="harness.not_implemented",
            message="Apothem adapter is not implemented.",
            field="harness",
            reason=f"{harness_id} does not implement {run.verb_present}.",
            fix="Choose another harness or update the adapter package.",
        )
        _fail_with_totals(run, totals, error.to_dict(), project_root)
        return False
    except _CliUserError as exc:
        _fail_with_totals(run, totals, exc.to_dict(), project_root)
        return False

    totals.last_materialization = materialization
    if materialization is not None:
        totals.files_written.extend(materialization.files_written)
    totals.results.extend(_result_dicts(harness_id, materialization))
    totals.warnings.extend(_warning_dicts(harness_id, materialization))
    # Shared-root advisories: a path this harness writes that other
    # harnesses also load, or a path it loads that already holds another
    # install's Apothem content. Advisory only; the install is unchanged.
    shared_advisories = shared_root_advisories(
        harness_id, home=Path.home(), project=project_root
    )
    totals.warnings.extend(shared_advisories)
    if run.fmt != "json":
        _print_harness_outcome(
            run, harness_id, materialization, shared_advisories, output_path
        )
    return True


def _fail_with_totals(
    run: _RunContext,
    totals: _RunTotals,
    error: dict[str, object],
    project_root: Path | None,
) -> None:
    """Emit a harness failure carrying everything the batch wrote before it."""
    run.fail(
        error,
        project_root=project_root,
        files_written=totals.files_written,
        results=totals.results,
        warnings=totals.warnings,
        exit_code=_EXIT_PARTIAL if totals.files_written else _EXIT_EXPECTED,
    )


def _print_harness_outcome(
    run: _RunContext,
    harness_id: str,
    materialization: MaterializationRun | None,
    shared_advisories: list[dict[str, object]],
    output_path: Path,
) -> None:
    """Print one harness's advisories, warnings, and result line (plain mode)."""
    con = run.con
    for advisory in shared_advisories:
        con.print(f"[yellow]Note:[/] {harness_id} - {escape(str(advisory['message']))}")
    # Paths and adapter-produced messages are operator/user data, not
    # trusted markup: a bracketed path segment would otherwise crash
    # or restyle the Rich rendering.
    if materialization is not None and materialization.warnings:
        _print_adapter_warnings(run, harness_id, materialization)
    if run.dry_run:
        con.print(
            f"[bold yellow]DRY RUN[/] would {run.verb_present} "
            f"[cyan]{harness_id}[/] -> {escape(str(output_path))}"
        )
    else:
        con.print(
            f"[green]✓[/] {run.verb_past} [cyan]{harness_id}[/] -> "
            f"{escape(str(output_path))}"
        )


def _print_adapter_warnings(
    run: _RunContext, harness_id: str, materialization: MaterializationRun
) -> None:
    """Print an adapter's warnings: each one under --verbose, else grouped.

    Without --verbose only capability-projection cells collapse into the
    grouped count; any other adapter warning (an instruction file an install
    hides, a data surface it could not create) prints on its own line, because
    the grouped Note would misreport it as a capability.
    """
    capability_count = 0
    for warning in materialization.warnings:
        if not run.verbose and warning.operation == "capability_projection":
            capability_count += 1
            continue
        run.con.print(f"[yellow]Warning:[/] {harness_id} - {escape(warning.message)}")
    if capability_count:
        noun = "capability" if capability_count == 1 else "capabilities"
        run.con.print(
            f"[dim]Note:[/] {harness_id} - {capability_count} {noun} "
            "not projected; pass --verbose for detail"
        )


def _emit_run_outcome(
    run: _RunContext,
    inputs: _RunInputs,
    totals: _RunTotals,
    *,
    clean_result: CleanSlateResult | None,
    payload_sink: list[dict[str, object]] | None,
) -> None:
    """Emit the JSON lifecycle envelope, or the plain multi-harness summary."""
    solo = len(inputs.adapters) == 1
    if run.fmt == "json":
        payload = _lifecycle_envelope(
            status="dry_run" if run.dry_run else "success",
            command=run.verb_present,
            action="dry_run" if run.dry_run else run.verb_past.lower(),
            harness=run.harness,
            profile_path=run.profile_path,
            project_root=inputs.project_root,
            files_written=totals.files_written,
            results=totals.results,
            warnings=totals.warnings,
            output_path=totals.last_output_path if solo else None,
            materialization=totals.last_materialization if solo else None,
        )
        if clean_result is not None:
            payload["clean"] = _clean_slate_dict(clean_result)
        # When a caller supplies a sink (the guided ``quickstart`` flow), hand it
        # the success envelope instead of emitting, so the caller can fold it into
        # one combined JSON summary rather than printing two documents.
        if payload_sink is not None:
            payload_sink.append(payload)
        else:
            emit_json(payload)
    elif len(inputs.adapters) > 1 and not run.quiet:
        run.con.print(
            f"[green]✓[/] {run.verb_past} {len(inputs.adapters)} harnesses "
            f"({len(totals.files_written)} files written)."
        )


def _first_run_profile(
    profile_path: Path, *, dry_run: bool
) -> tuple[dict[str, Any], dict[str, object]]:
    """Scaffold the default profile for a first ``install``; return it and its advisory.

    A real run writes the starter profile through the shared atomic boundary
    and loads it back. A dry run validates the same scaffold in memory and
    writes nothing. Either way the returned advisory rides the envelope's
    ``warnings`` array so a JSON caller learns the profile was (or would be)
    created; the placeholder-identity advisory follows separately.
    """
    import yaml

    text = _profile_scaffold_text()
    if dry_run:
        loaded = validate_profile(yaml.safe_load(text), profile_path=profile_path)
        return loaded.to_dict(), {
            "harness": None,
            "outcome": "advisory",
            "operation": "profile_scaffold_preview",
            "path": str(profile_path),
            "message": (
                f"No profile at {profile_path}; this dry run uses the starter "
                "profile in memory. A real install creates it."
            ),
        }
    try:
        _write_profile_text_safely(profile_path, text, operation="install_profile_init")
    except OSError as exc:
        raise _CliUserError(
            code="profile.write_failed",
            message="Apothem could not create the starter profile.",
            field="profile",
            reason=str(exc),
            fix="Check the profile path and directory permissions, or pass "
            "an existing profile with --profile PATH.",
        ) from exc
    return _load_profile(profile_path), {
        "harness": None,
        "outcome": "advisory",
        "operation": "profile_created",
        "path": str(profile_path),
        "message": (
            f"Created a starter profile at {profile_path}. Its identity fields "
            "are placeholders; personalize them, then run update to apply."
        ),
    }


def _clean_slate_dict(result: CleanSlateResult) -> dict[str, object]:
    """Return the clean-slate outcome as JSON-envelope data."""
    return {
        "dry_run": result.dry_run,
        "backup_dir": str(result.backup_dir) if result.backup_dir else None,
        "targets": [
            {
                "path": str(disposition.path),
                "present": disposition.present,
                "removed": disposition.removed,
                "skipped_reason": disposition.skipped_reason,
            }
            for disposition in result.dispositions
        ],
    }


def _dry_run_materialization(
    harness_id: str,
    adapter: _Adapter,
    output_path: Path,
    project_root: Path | None,
    shared_profile: dict[str, Any] | None = None,
) -> MaterializationRun:
    """Return a no-write materialization run for one harness.

    An adapter with ``preview`` (every registered adapter) reports what its
    install would do to each path, with diffs: the same plan ``diff`` shows.
    Otherwise the adapter's static ``plan`` entries are listed.
    """
    preview = getattr(adapter, "preview", None)
    if shared_profile is not None and callable(preview):
        previewed = _invoke_with_project(preview, shared_profile, project=project_root)
        if isinstance(previewed, MaterializationRun):
            return previewed
    plan_entries: list[dict[str, str]] = []
    plan_fn = getattr(adapter, "plan", None)
    if callable(plan_fn):
        try:
            candidate = _invoke_with_project(plan_fn, output_path, project=project_root)
        except Exception as exc:
            raise _CliUserError(
                code="materialization.plan_failed",
                message="Apothem dry-run planning failed.",
                field="harness",
                reason=str(exc),
                fix="Check the harness adapter and project path before retrying.",
            ) from exc
        if isinstance(candidate, list):
            plan_entries = cast("list[dict[str, str]]", candidate)
    results = tuple(
        MaterializationResult(
            outcome="skipped",
            operation=entry.get("mode", "plan"),
            path=entry.get("target", str(output_path)),
            source=entry.get("source"),
            message="dry run: no filesystem changes made",
        )
        for entry in plan_entries
    )
    return MaterializationRun(
        harness=_pkg.get_harness_entry(harness_id).package_key,
        dry_run=True,
        results=results,
    )
