# SPDX-License-Identifier: MIT

"""``apothem uninstall`` + the continuous-form aliases."""

from __future__ import annotations

import sys
from pathlib import Path

import click
from rich.markup import escape

import apothem.cli as _pkg
from apothem.cli import main
from apothem.cli._common_flags import (
    common_options,
    get_console,
    get_error_console,
    resolve_format,
)
from apothem.cli._epilogs import _EP_UNINSTALL
from apothem.cli._helpers import (
    _EXIT_EXPECTED,
    _EXIT_PARTIAL,
    _adapter_failure_result,
    _adapter_resolve_output_path,
    _CliUserError,
    _confirmation_required_error,
    _emit_expected_error,
    _harness_option,
    _invoke_with_project,
    _lifecycle_envelope,
    _project_option,
    _resolve_project_root,
)
from apothem.cli._json_formatter import emit_json


def _uninstall_impl(
    harness: str,
    yes: bool,
    fmt: str,
    quiet: bool,
    no_color: bool,
    project: str | None = None,
) -> None:
    """Shared body for ``uninstall`` and its continuous-form aliases."""
    con = get_console(no_color=no_color, quiet=quiet)
    try:
        project_root = _resolve_project_root(project)
        adapters = _pkg._select_and_load_adapters(
            harness, project_root, shared_profile=None, apply_excludes=False
        )
    except _CliUserError as exc:
        _emit_expected_error(
            command="uninstall",
            fmt=fmt,
            harness=harness,
            error=exc.to_dict(),
        )
        return

    # Destructive-confirmation gate: when no prompt is possible (JSON mode
    # would corrupt the single-document contract; a non-interactive run has
    # no terminal), refuse up front with a structured error instead of dying
    # mid-batch on a bare Abort. Resolved through the patchable ``_pkg`` seam
    # so the interactivity check is test-reachable.
    if not yes and (fmt == "json" or not _pkg._stdin_is_interactive()):
        _emit_expected_error(
            command="uninstall",
            fmt=fmt,
            harness=harness,
            error=_confirmation_required_error("uninstall").to_dict(),
        )
        return

    results: list[dict[str, object]] = []
    last_output_path: Path | None = None
    errored = False
    removed_any = False
    for harness_id, adapter in adapters:
        output_path = _adapter_resolve_output_path(adapter, project_root)
        last_output_path = output_path
        # A bad adapter degrades to a per-harness error result rather than
        # aborting the batch (the confirm prompt's Abort still propagates).
        try:
            installed = bool(
                _invoke_with_project(adapter.is_installed, project=project_root)
            )
            if not installed:
                results.append(
                    {
                        "harness": harness_id,
                        "outcome": "skipped",
                        "operation": "uninstall",
                        "path": str(output_path),
                        "message": "not installed; no files removed",
                    }
                )
                if fmt != "json":
                    con.print(
                        f"[dim]{harness_id} is not installed; nothing to remove.[/]"
                    )
                continue
            if not yes:
                click.confirm(
                    f"Remove {harness_id} configuration at {output_path}?",
                    abort=True,
                )
            _invoke_with_project(adapter.uninstall, project=project_root)
        except click.Abort:
            raise
        except Exception as exc:
            errored = True
            results.append(
                _adapter_failure_result(harness_id, "uninstall", output_path, exc)
            )
            if fmt != "json":
                get_error_console(no_color=no_color).print(
                    f"[red]✗[/] {harness_id} uninstall failed: {escape(str(exc))}"
                )
            continue
        removed_any = True
        results.append(
            {
                "harness": harness_id,
                "outcome": "updated",
                "operation": "uninstall",
                "path": str(output_path),
                "message": "managed files removed",
            }
        )
        if fmt != "json":
            con.print(f"[green]✓[/] Uninstalled [cyan]{harness_id}[/]")

    exit_code = 0
    if errored:
        exit_code = _EXIT_PARTIAL if removed_any else _EXIT_EXPECTED
    if fmt == "json":
        status = _pkg._status_for_exit_code(exit_code)
        emit_json(
            _lifecycle_envelope(
                status=status,
                command="uninstall",
                action="uninstalled",
                harness=harness,
                profile_path=None,
                project_root=project_root,
                files_written=[],
                results=results,
                warnings=[],
                output_path=last_output_path if len(adapters) == 1 else None,
            )
        )
    if exit_code:
        sys.exit(exit_code)


@main.command(epilog=_EP_UNINSTALL)
@_harness_option
@click.option("--yes", is_flag=True, help="Skip confirmation prompt.")
@_project_option
@common_options
def uninstall(
    harness: str,
    yes: bool,
    project: str | None,
    quiet: bool,
    verbose: bool,
    output_format: str,
    no_color: bool,
    json_flag: bool,
) -> None:
    """Remove a harness adapter configuration."""
    _uninstall_impl(
        harness,
        yes,
        resolve_format(output_format, json_flag),
        quiet,
        no_color,
        project=project,
    )


def _make_uninstalling_alias(name: str) -> click.Command:
    """Build the ``Uninstalling`` / ``uninstalling`` continuous-form alias."""

    @click.command(name=name, epilog=_EP_UNINSTALL, hidden=True)
    @_harness_option
    @click.option("--yes", is_flag=True, help="Skip confirmation prompt.")
    @_project_option
    @common_options
    def _alias(
        harness: str,
        yes: bool,
        project: str | None,
        quiet: bool,
        verbose: bool,
        output_format: str,
        no_color: bool,
        json_flag: bool,
    ) -> None:
        """Alias for uninstall (continuous form). Identical behavior."""
        _uninstall_impl(
            harness,
            yes,
            resolve_format(output_format, json_flag),
            quiet,
            no_color,
            project=project,
        )

    return _alias


main.add_command(_make_uninstalling_alias("Uninstalling"))


main.add_command(_make_uninstalling_alias("uninstalling"))
