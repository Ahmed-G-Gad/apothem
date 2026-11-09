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
from apothem.cli._user_level_report import (
    is_project_scope,
    preview_uninstall,
    uninstall_advisories,
)

# Import order matters here. ``install_driver_pathsafety`` imports
# ``install_driver_types``, which imports ``install_driver``; that loads its
# concern modules, and ``install_driver_backup`` among them imports names from
# ``install_driver_pathsafety`` while it is still half loaded, which raises
# ImportError. Importing ``install_driver`` first loads the whole cycle in the
# order it expects. The one ``from`` statement keeps the order (names import
# left to right, and the sorter keeps them in this order), and ``noqa: F401``
# keeps the otherwise unused ``install_driver`` import.
from apothem.harnesses._shared import (
    install_driver,  # noqa: F401
    install_driver_pathsafety,
)


def _retention_advisories(
    harness_id: str,
    adapter: object,
    project_root: Path | None,
    output_path: Path,
) -> list[dict[str, object]]:
    """Return the retained and released advisories for uninstalling *adapter*.

    Empty when the harness writes no user-home folder or has no install record.
    The ledger root is the project for a project-scope adapter and the harness
    folder for a user-scope one. A report that cannot be built never blocks the
    uninstall.
    """
    root = project_root if is_project_scope(adapter) else output_path.parent
    if root is None:
        return []
    try:
        return uninstall_advisories(harness_id, preview_uninstall(harness_id, root))
    except (OSError, ValueError):
        return []


def _refuse_or_confirm(
    harness_id: str, adapter: object, output_path: Path, *, yes: bool
) -> None:
    """Refuse an uninstall a link would lead out of the home, else confirm it.

    Such an uninstall changes nothing, so it is refused before the question,
    as rollback is (see
    :func:`~apothem.harnesses._shared.install_driver_pathsafety.refuse_link_leaving_home`).
    A project-scope install root is the ``--project`` folder, already
    resolved, so only a user-scope one is checked.

    Raises:
        MaterializationError: When a link leads the install root out of the home.
        click.Abort: When the operator declines the confirmation.
    """
    if not is_project_scope(adapter):
        install_driver_pathsafety.refuse_link_leaving_home(
            harness_id,
            output_path.parent,
            operation="uninstall_refused",
            uninstall=True,
        )
    if not yes:
        click.confirm(
            f"Remove {harness_id} configuration at {output_path}?",
            abort=True,
        )


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
    warnings: list[dict[str, object]] = []
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
            _refuse_or_confirm(harness_id, adapter, output_path, yes=yes)
            # What the uninstall keeps in the user home because another install
            # still uses it is read from the ledger before the install's own
            # record is replaced.
            retention = _retention_advisories(
                harness_id, adapter, project_root, output_path
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
        warnings.extend(retention)
        if fmt != "json":
            con.print(f"[green]✓[/] Uninstalled [cyan]{harness_id}[/]")
            for advisory in retention:
                con.print(
                    f"[yellow]Note:[/] {harness_id} - {escape(str(advisory['message']))}"
                )

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
                warnings=warnings,
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
