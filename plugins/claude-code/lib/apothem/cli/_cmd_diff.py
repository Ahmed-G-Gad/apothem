# SPDX-License-Identifier: MIT

"""``apothem diff`` — preview pending configuration changes for a harness."""

from __future__ import annotations

import click
from rich.console import Console
from rich.markup import escape

import apothem.cli as _pkg
from apothem.cli import main
from apothem.cli._common_flags import (
    common_options,
    get_console,
    resolve_format,
)
from apothem.cli._epilogs import _EP_DIFF
from apothem.cli._helpers import (
    _CliUserError,
    _complete_harness,
    _dry_run_plan,
    _emit_expected_error,
    _lifecycle_envelope,
    _load_profile,
    _materialization_error,
    _profile_error,
    _profile_option,
    _project_option,
    _resolve_profile_path,
    _resolve_project_root,
    _result_dicts,
    _unknown_harness_error,
    _warning_dicts,
)
from apothem.cli._json_formatter import emit_json
from apothem.harnesses._shared.install_driver import (
    MaterializationError,
    MaterializationRun,
    operation_label,
    preview_status,
)
from apothem.lib.profile import ProfileValidationError


@main.command(epilog=_EP_DIFF)
@click.option(
    "--harness",
    required=True,
    metavar="NAME",
    help="Harness adapter name to preview pending changes for.",
    shell_complete=_complete_harness,
)
@_profile_option
@_project_option
@common_options
def diff(
    harness: str,
    profile: str | None,
    project: str | None,
    quiet: bool,
    verbose: bool,
    output_format: str,
    no_color: bool,
    json_flag: bool,
) -> None:
    """Preview the pending configuration changes for a single harness."""
    fmt = resolve_format(output_format, json_flag)
    con = get_console(no_color=no_color, quiet=quiet)
    profile_path = _resolve_profile_path(profile)
    try:
        if harness.strip().lower() == "all":
            raise _unknown_harness_error(harness)
        project_root = _resolve_project_root(project)
        shared_profile = _load_profile(profile_path)
        selected = _pkg._selected_harness_ids(
            harness, shared_profile=None, apply_excludes=False
        )
        _pkg._require_project_for_selection(selected, project_root)
        harness_id = selected[0]
        entry = _pkg.get_harness_entry(harness_id)
        adapter = _pkg._load_adapter_for_entry(entry)
    except ProfileValidationError as exc:
        _emit_expected_error(
            command="diff",
            fmt=fmt,
            harness=harness,
            profile_path=profile_path,
            error=_profile_error(exc),
        )
        return
    except _CliUserError as exc:
        _emit_expected_error(
            command="diff",
            fmt=fmt,
            harness=harness,
            profile_path=profile_path,
            error=exc.to_dict(),
        )
        return

    try:
        run = _dry_run_plan(entry, adapter, project_root, shared_profile)
    except MaterializationError as exc:
        _emit_expected_error(
            command="diff",
            fmt=fmt,
            harness=harness,
            profile_path=profile_path,
            project_root=project_root,
            error=_materialization_error(exc, files_written=[]),
        )
        return
    except _CliUserError as exc:
        _emit_expected_error(
            command="diff",
            fmt=fmt,
            harness=harness,
            profile_path=profile_path,
            project_root=project_root,
            error=exc.to_dict(),
        )
        return

    if fmt == "json":
        payload = _lifecycle_envelope(
            status="dry_run",
            command="diff",
            action="dry_run",
            harness=harness,
            profile_path=profile_path,
            project_root=project_root,
            files_written=[],
            results=_result_dicts(harness_id, run),
            warnings=_warning_dicts(harness_id, run),
            materialization=run,
        )
        emit_json(payload)
        return

    _render_plain_preview(con, harness_id, run, verbose=verbose)


def _render_plain_preview(
    con: Console, harness_id: str, run: MaterializationRun, *, verbose: bool
) -> None:
    """Print the plain-mode preview: one line per pending change, plus diffs."""
    con.print(f"[bold]Pending changes for[/] [cyan]{harness_id}[/]:")
    if verbose:
        con.print(
            "[dim]Preview only — nothing is written. Showing the full plan, "
            "including unchanged targets and the raw operation kind and "
            "outcome.[/]"
        )
    else:
        con.print(
            "[dim]Preview only — nothing is written. Each line is what "
            "'apothem install' would do.[/]"
        )
    rendered = 0
    for result in run.results:
        # Warnings are surfaced elsewhere; a no-op target (e.g. nothing stale
        # to prune) is not a pending change. Both are omitted from the default
        # preview and restored under --verbose for the full plan.
        if result.outcome in {"warning", "unchanged"} and not verbose:
            continue
        rendered += 1
        label = operation_label(result.operation)
        status = preview_status(result.operation, result.outcome, dry_run=run.dry_run)
        raw = f" [dim]\\[{result.operation}/{result.outcome}][/]" if verbose else ""
        con.print(f"  [cyan]{label}[/] {escape(result.path)} [dim]({status})[/]{raw}")
        diff_text = result.detail.get("diff")
        if diff_text:
            _print_diff_lines(con, diff_text)
    if rendered == 0:
        if run.results:
            con.print(
                "  [dim]No pending changes. Re-run with --verbose for the full plan.[/]"
            )
        else:
            con.print("  [dim]No planned targets.[/]")


def _print_diff_lines(con: Console, diff_text: str) -> None:
    """Print a unified diff with added lines green and removed lines red."""
    for line in diff_text.splitlines():
        if line.startswith("+") and not line.startswith("+++"):
            con.print(f"    [green]{escape(line)}[/]")
        elif line.startswith("-") and not line.startswith("---"):
            con.print(f"    [red]{escape(line)}[/]")
        else:
            con.print(f"    [dim]{escape(line)}[/]")
