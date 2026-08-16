# SPDX-License-Identifier: MIT

"""``apothem status`` — install/verify/drift sweep across every harness."""

from __future__ import annotations

import sys

from rich.markup import escape

import apothem.cli as _pkg
from apothem.cli import main
from apothem.cli._common_flags import (
    common_options,
    get_console,
    get_error_console,
    resolve_format,
)
from apothem.cli._epilogs import _EP_STATUS
from apothem.cli._helpers import (
    _EXIT_PARTIAL,
    _adapter_failure_result,
    _baseline_unavailable_entry,
    _CliUserError,
    _drift_state,
    _emit_expected_error,
    _invoke_with_project,
    _lifecycle_envelope,
    _load_profile,
    _profile_error,
    _profile_option,
    _project_option,
    _resolve_profile_path,
    _resolve_project_root,
)
from apothem.cli._json_formatter import emit_json
from apothem.lib.harness_registry import iter_harness_entries
from apothem.lib.profile import ProfileValidationError


@main.command(epilog=_EP_STATUS)
@_profile_option
@_project_option
@common_options
def status(
    profile: str | None,
    project: str | None,
    quiet: bool,
    verbose: bool,
    output_format: str,
    no_color: bool,
    json_flag: bool,
) -> None:
    """Report install, verify, and drift state for every registered harness."""
    fmt = resolve_format(output_format, json_flag)
    con = get_console(no_color=no_color, quiet=quiet)
    try:
        project_root = _resolve_project_root(project)
    except _CliUserError as exc:
        _emit_expected_error(command="status", fmt=fmt, error=exc.to_dict())
        return
    profile_path = _resolve_profile_path(profile)
    baseline_warning: dict[str, object] | None = None
    try:
        shared_profile = _load_profile(profile_path)
    except ProfileValidationError as exc:
        # An explicit --profile names the drift baseline the operator wants
        # compared against; an unreadable one is a user error surfaced like
        # diff/install/update rather than silently degraded.
        if profile is not None:
            _emit_expected_error(
                command="status",
                fmt=fmt,
                profile_path=profile_path,
                error=_profile_error(exc),
            )
            return
        # The default profile is the drift baseline but not a status
        # precondition: an unreadable one degrades drift to "unknown" rather
        # than aborting the read-only sweep (installed/verified stay reportable).
        shared_profile = {}
        baseline_warning = _baseline_unavailable_entry(profile_path, exc)

    # The degradation is deliberate but must never be silent: report it once,
    # up front, so the rows below are read as degraded rather than clean.
    if baseline_warning is not None and fmt != "json":
        con.print(f"[yellow]![/] {escape(str(baseline_warning['message']))}")

    results: list[dict[str, object]] = []
    errored = False
    for entry in iter_harness_entries():
        harness_id = entry.public_id
        try:
            adapter = _pkg._load_adapter_for_entry(entry)
        except Exception as exc:
            # Adapter loading is the untrusted edge: one adapter raising (a
            # structured load error or any uncaught import-time fault) becomes a
            # recorded error row, never an aborted sweep.
            errored = True
            results.append(_adapter_failure_result(harness_id, "status", None, exc))
            if fmt != "json":
                get_error_console(no_color=no_color).print(
                    f"[red]✗[/] [cyan]{harness_id}[/] failed to load: {escape(str(exc))}"
                )
            continue

        # Project-scope harnesses without a --project cannot resolve their target;
        # surface a skipped row rather than crashing (mirrors verify's gate).
        if entry.scope == "project" and project_root is None:
            results.append(
                {
                    "harness": harness_id,
                    "installed": False,
                    "verified": False,
                    "drift": "needs-project",
                }
            )
            if fmt != "json":
                con.print(
                    f"[yellow]-[/] [cyan]{harness_id}[/] needs --project "
                    "(project-scope harness)"
                )
            continue

        try:
            installed = bool(
                _invoke_with_project(adapter.is_installed, project=project_root)
            )
            verified = bool(_invoke_with_project(adapter.verify, project=project_root))
            # Without a readable baseline there is nothing to compare an
            # installed harness against — comparing to an empty profile would
            # misreport every install as drifted.
            if baseline_warning is not None:
                drift = "unknown" if installed else "absent"
            else:
                drift = _drift_state(
                    entry, adapter, installed, project_root, shared_profile
                )
        except Exception as exc:
            errored = True
            failure = _adapter_failure_result(harness_id, "status", None, exc)
            failure["installed"] = False
            failure["verified"] = False
            failure["drift"] = "error"
            results.append(failure)
            if fmt != "json":
                get_error_console(no_color=no_color).print(
                    f"[red]✗[/] [cyan]{harness_id}[/] status failed: {escape(str(exc))}"
                )
            continue

        results.append(
            {
                "harness": harness_id,
                "installed": installed,
                "verified": verified,
                "drift": drift,
            }
        )
        if fmt != "json":
            inst_glyph = "[green]✓[/]" if installed else "[red]✗[/]"
            ver_glyph = "[green]✓[/]" if verified else "[red]✗[/]"
            drift_styled = {
                "in-sync": "[green]in-sync[/]",
                "drift": "[yellow]drift[/]",
                "absent": "[dim]absent[/]",
                "unknown": "[dim]unknown[/]",
            }.get(drift, drift)
            con.print(
                f"{inst_glyph} [cyan]{harness_id}[/]  "
                f"installed={installed!s:<5} verified={verified!s:<5} "
                f"{drift_styled}  ({ver_glyph})"
            )

    exit_code = _EXIT_PARTIAL if errored else 0

    if fmt == "json":
        payload = _lifecycle_envelope(
            status=_pkg._status_for_exit_code(exit_code),
            command="status",
            action="status",
            harness="all",
            profile_path=profile_path,
            project_root=project_root,
            files_written=[],
            results=results,
            warnings=[baseline_warning] if baseline_warning is not None else [],
        )
        emit_json(payload)
        if exit_code:
            sys.exit(exit_code)
        return

    if not results:
        con.print("[yellow]No harness adapters registered.[/]")
    if exit_code:
        sys.exit(exit_code)
