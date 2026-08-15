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

from pathlib import Path
from typing import cast

import click
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
    _render_blast_radius,
    _resolve_profile_path,
    _resolve_project_root,
    _result_dicts,
    _warning_dicts,
)
from apothem.cli._json_formatter import emit_json
from apothem.harnesses._shared.install_driver import (
    MaterializationError,
    MaterializationResult,
    MaterializationRun,
)
from apothem.lib.atomic_io import write_bytes_atomically
from apothem.lib.clean_slate import CleanSlateError, CleanSlateResult, run_clean_slate
from apothem.lib.profile import ProfileValidationError


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
) -> None:
    """Install or update a harness adapter from the shared profile.

    The command accepts a single harness id or ``all``. Profiles are
    validated before dry-runs and writes, and JSON output always uses the
    lifecycle envelope required by the product contract.
    """
    con = get_console(no_color=no_color, quiet=quiet)
    profile_path = _resolve_profile_path(profile)
    try:
        project_root = _resolve_project_root(project)
        shared_profile = _load_profile(profile_path)
        adapters = _pkg._select_and_load_adapters(
            harness,
            project_root,
            shared_profile=shared_profile,
            apply_excludes=harness.strip().lower() == "all",
        )
    except ProfileValidationError as exc:
        _emit_expected_error(
            command=verb_present,
            fmt=fmt,
            harness=harness,
            profile_path=profile_path,
            error=_profile_error(exc),
        )
        return
    except _CliUserError as exc:
        _emit_expected_error(
            command=verb_present,
            fmt=fmt,
            harness=harness,
            profile_path=profile_path,
            error=exc.to_dict(),
        )
        return

    # Opt-in clean-slate removal runs after the profile is loaded into memory
    # (above) and before any fresh materialization below. The profile file is
    # one of the bounded removal targets, so its bytes are captured here and
    # restored after removal — the shared profile is the operator's identity
    # source of truth, not stale install state, and the timestamped backup
    # preserves every removed target for recovery.
    clean_result: CleanSlateResult | None = None
    if clean:
        profile_bytes = profile_path.read_bytes() if profile_path.is_file() else None
        try:
            clean_result = run_clean_slate(
                Path.home(),
                dry_run=dry_run,
                assume_yes=assume_yes,
                # Use the patchable seam (not raw sys.stdin.isatty()) so the
                # clean-slate interactivity gate is test-reachable, matching the
                # blast-radius confirmation below.
                interactive=_pkg._stdin_is_interactive(),
                echo=(con.print if fmt != "json" else None),
            )
        except CleanSlateError as exc:
            _emit_expected_error(
                command=verb_present,
                fmt=fmt,
                harness=harness,
                profile_path=profile_path,
                error=_CliUserError(
                    code="clean_slate.refused",
                    message="Clean-slate removal was refused.",
                    field="clean",
                    reason=str(exc),
                    fix="Re-run interactively, pass --yes for non-interactive use, "
                    "or correct the unsafe target before retrying.",
                ).to_dict(),
            )
            return
        if not dry_run and profile_bytes is not None:
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
                _emit_expected_error(
                    command=verb_present,
                    fmt=fmt,
                    harness=harness,
                    profile_path=profile_path,
                    error=_CliUserError(
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
                    ).to_dict(),
                )
                return
        # A clean dry run falls through to the materialization preview below:
        # the operation previews both phases (removals, then fresh writes), and
        # JSON mode keeps its single-envelope contract — the removal preview
        # rides the envelope's "clean" key instead of truncating the run.

    # Blast-radius disclosure (multi-harness install only). An ``all`` install
    # fans out into mixed scopes: project-scope adapters write under --project,
    # but user-scope adapters write under the operator's real home directory —
    # a surprise worth disclosing before any byte is written. The grouped
    # preview prints in plain mode; when the selection writes outside the
    # supplied project root, an interactive confirmation guards the home-rooted
    # writes. --yes, a non-interactive context, --dry-run, and --format json
    # each bypass the prompt (dry-run and json still print/return the preview
    # data without mutating). Single-named installs and update are out of scope.
    if harness.strip().lower() == "all" and verb_present == "install" and fmt != "json":
        within, outside = _partition_blast_radius(adapters, project_root)
        _render_blast_radius(con, within, outside, project_root)
        if not dry_run and outside and not assume_yes and _pkg._stdin_is_interactive():
            click.confirm("Proceed and write these files?", abort=True)

    all_files_written: list[str] = []
    all_results: list[dict[str, object]] = []
    all_warnings: list[dict[str, object]] = []

    # Placeholder-identity advisory (install + update). When the loaded profile
    # still carries the shipped scaffold identity, surface a single advisory so a
    # fake identity is not silently projected — advisory only, never blocking
    # (identity is never fabricated or coerced). It rides the JSON warnings array
    # and prints once in plain mode, regardless of the harness selection.
    placeholder_fields = _placeholder_identity_fields(shared_profile)
    if placeholder_fields:
        advisory = _placeholder_advisory_entry(profile_path, placeholder_fields)
        all_warnings.append(advisory)
        if fmt != "json":
            con.print(f"[yellow]Note:[/] {escape(str(advisory['message']))}")
    last_output_path: Path | None = None
    last_materialization: MaterializationRun | None = None

    for harness_id, adapter in adapters:
        output_path = _adapter_resolve_output_path(adapter, project_root)
        last_output_path = output_path
        materialization: MaterializationRun | None

        try:
            if dry_run:
                materialization = _dry_run_materialization(
                    harness_id,
                    adapter,
                    output_path,
                    project_root,
                )
            elif verb_present == "update":
                maybe_run = _invoke_with_project(
                    adapter.update,
                    shared_profile,
                    project=project_root,
                )
                materialization = (
                    maybe_run if isinstance(maybe_run, MaterializationRun) else None
                )
            else:
                maybe_run = _invoke_with_project(
                    adapter.install,
                    shared_profile,
                    project=project_root,
                )
                materialization = (
                    maybe_run if isinstance(maybe_run, MaterializationRun) else None
                )
        except MaterializationError as exc:
            error = _materialization_error(exc, files_written=exc.run.files_written)
            results = [*all_results, *_result_dicts(harness_id, exc.run)]
            warnings = [*all_warnings, *_warning_dicts(harness_id, exc.run)]
            files_written = [*all_files_written, *exc.run.files_written]
            exit_code = _EXIT_PARTIAL if files_written else _EXIT_EXPECTED
            _emit_expected_error(
                command=verb_present,
                fmt=fmt,
                harness=harness,
                profile_path=profile_path,
                project_root=project_root,
                error=error,
                files_written=files_written,
                results=results,
                warnings=warnings,
                exit_code=exit_code,
            )
            return
        except NotImplementedError:
            error = _CliUserError(
                code="harness.not_implemented",
                message="Apothem adapter is not implemented.",
                field="harness",
                reason=f"{harness_id} does not implement {verb_present}.",
                fix="Choose another harness or update the adapter package.",
            ).to_dict()
            _emit_expected_error(
                command=verb_present,
                fmt=fmt,
                harness=harness,
                profile_path=profile_path,
                project_root=project_root,
                error=error,
                files_written=all_files_written,
                results=all_results,
                warnings=all_warnings,
                exit_code=_EXIT_PARTIAL if all_files_written else _EXIT_EXPECTED,
            )
            return
        except _CliUserError as exc:
            _emit_expected_error(
                command=verb_present,
                fmt=fmt,
                harness=harness,
                profile_path=profile_path,
                project_root=project_root,
                error=exc.to_dict(),
                files_written=all_files_written,
                results=all_results,
                warnings=all_warnings,
                exit_code=_EXIT_PARTIAL if all_files_written else _EXIT_EXPECTED,
            )
            return

        last_materialization = materialization
        if materialization is not None:
            all_files_written.extend(materialization.files_written)
        all_results.extend(_result_dicts(harness_id, materialization))
        all_warnings.extend(_warning_dicts(harness_id, materialization))

        if fmt != "json":
            # Paths and adapter-produced messages are operator/user data, not
            # trusted markup: a bracketed path segment would otherwise crash
            # or restyle the Rich rendering.
            if materialization is not None and materialization.warnings:
                if verbose:
                    for warning in materialization.warnings:
                        con.print(
                            f"[yellow]Warning:[/] {harness_id} - "
                            f"{escape(warning.message)}"
                        )
                else:
                    count = len(materialization.warnings)
                    noun = "capability" if count == 1 else "capabilities"
                    con.print(
                        f"[dim]Note:[/] {harness_id} - {count} {noun} not "
                        "projected; pass --verbose for detail"
                    )
            if dry_run:
                con.print(
                    f"[bold yellow]DRY RUN[/] would {verb_present} "
                    f"[cyan]{harness_id}[/] -> {escape(str(output_path))}"
                )
            else:
                con.print(
                    f"[green]✓[/] {verb_past} [cyan]{harness_id}[/] -> "
                    f"{escape(str(output_path))}"
                )

    if fmt == "json":
        status = "dry_run" if dry_run else "success"
        action = "dry_run" if dry_run else verb_past.lower()
        payload = _lifecycle_envelope(
            status=status,
            command=verb_present,
            action=action,
            harness=harness,
            profile_path=profile_path,
            project_root=project_root,
            files_written=all_files_written,
            results=all_results,
            warnings=all_warnings,
            output_path=last_output_path if len(adapters) == 1 else None,
            materialization=last_materialization if len(adapters) == 1 else None,
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
    elif len(adapters) > 1 and not quiet:
        con.print(
            f"[green]✓[/] {verb_past} {len(adapters)} harnesses "
            f"({len(all_files_written)} files written)."
        )

    if clean and not dry_run and fmt != "json" and not quiet:
        verify_harness = harness if harness.strip().lower() != "all" else "all"
        con.print(
            "[bold]Next step:[/] confirm the fresh install with "
            f"[cyan]apothem verify --harness {escape(verify_harness)}[/]"
        )


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
) -> MaterializationRun:
    """Return a no-write materialization run using the adapter plan surface."""
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
