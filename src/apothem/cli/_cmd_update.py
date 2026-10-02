# SPDX-License-Identifier: MIT

"""``apothem update`` + ``rollback`` + the update continuous-form aliases."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import cast

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
from apothem.cli._epilogs import (
    _EP_ROLLBACK,
    _EP_UPDATE,
)
from apothem.cli._helpers import (
    _EXIT_EXPECTED,
    _EXIT_PARTIAL,
    _adapter_resolve_output_path,
    _CliUserError,
    _confirmation_required_error,
    _emit_expected_error,
    _harness_option,
    _lifecycle_envelope,
    _profile_option,
    _project_option,
    _resolve_project_root,
)
from apothem.cli._json_formatter import emit_json
from apothem.cli._materialize import _materialize
from apothem.harnesses._shared import install_driver
from apothem.harnesses._shared.install_driver import MaterializationResult
from apothem.lib import install_ledger
from apothem.lib.install_ledger import LedgerRecord


@main.command(epilog=_EP_UPDATE)
@_harness_option
@_profile_option
@click.option("--dry-run", is_flag=True, help="Preview update without writing files.")
@_project_option
@common_options
def update(
    harness: str,
    profile: str | None,
    dry_run: bool,
    project: str | None,
    quiet: bool,
    verbose: bool,
    output_format: str,
    no_color: bool,
    json_flag: bool,
) -> None:
    """Re-install a harness adapter configuration from the current profile."""
    _materialize(
        harness,
        profile,
        dry_run,
        "update",
        "Updated",
        fmt=resolve_format(output_format, json_flag),
        quiet=quiet,
        no_color=no_color,
        project=project,
        verbose=verbose,
    )


def _make_updating_alias(name: str) -> click.Command:
    """Build the ``Updating`` / ``updating`` continuous-form alias."""

    @click.command(name=name, epilog=_EP_UPDATE, hidden=True)
    @_harness_option
    @_profile_option
    @click.option(
        "--dry-run",
        is_flag=True,
        help="Preview update without writing files.",
    )
    @_project_option
    @common_options
    def _alias(
        harness: str,
        profile: str | None,
        dry_run: bool,
        project: str | None,
        quiet: bool,
        verbose: bool,
        output_format: str,
        no_color: bool,
        json_flag: bool,
    ) -> None:
        """Alias for update (continuous form). Identical behavior."""
        _materialize(
            harness,
            profile,
            dry_run,
            "update",
            "Updated",
            fmt=resolve_format(output_format, json_flag),
            quiet=quiet,
            no_color=no_color,
            project=project,
            verbose=verbose,
        )

    return _alias


def _record_harness_error(
    error: _CliUserError,
    *,
    solo: bool,
    harness_id: str,
    output_path: Path,
    fmt: str,
    harness: str,
    no_color: bool,
    plain_line: str,
    results: list[dict[str, object]],
) -> bool:
    """Dispatch a per-harness rollback error, solo or as a batch member.

    When only one harness was selected (*solo*), the error is the whole
    command's outcome: emit the structured expected-error envelope and return
    ``True`` so the caller stops. Otherwise the failure is one batch row: append
    an ``error`` result for *harness_id*, print *plain_line* to the error console
    outside JSON mode (so the failure is visible in plain mode, not only as a
    JSON row), and return ``False`` so the caller marks the batch errored and
    continues. *plain_line* is Rich markup, printed verbatim by the caller-chosen
    console.
    """
    if solo:
        _emit_expected_error(
            command="rollback",
            fmt=fmt,
            harness=harness,
            error=error.to_dict(),
        )
        return True
    results.append(
        {
            "harness": harness_id,
            "outcome": "error",
            "operation": "rollback",
            "path": str(output_path),
            "message": error.message,
        }
    )
    if fmt != "json":
        get_error_console(no_color=no_color).print(plain_line)
    return False


def _rollback_impl(
    harness: str,
    *,
    install_id: str | None,
    yes: bool,
    fmt: str,
    quiet: bool,
    no_color: bool,
    project: str | None,
) -> None:
    """Shared body for the ``rollback`` command.

    Resolves the recorded install (the latest, or the supplied ``--install-id``)
    for each selected harness, then reverses it through
    :func:`install_driver.rollback_install`: every recorded backup is restored
    to its recorded path, every file and directory the install created is
    removed. Emits the standard lifecycle envelope.
    """
    con = get_console(no_color=no_color, quiet=quiet)
    try:
        project_root = _resolve_project_root(project)
        selected = _pkg._selected_harness_ids(
            harness, shared_profile=None, apply_excludes=False
        )
        _pkg._require_project_for_selection(selected, project_root)
    except _CliUserError as exc:
        _emit_expected_error(
            command="rollback", fmt=fmt, harness=harness, error=exc.to_dict()
        )
        return

    # Destructive-confirmation gate: mirror uninstall — refuse up front with
    # a structured error when no prompt is possible (JSON mode or no
    # interactive terminal) and --yes was not given.
    if not yes and (fmt == "json" or not _pkg._stdin_is_interactive()):
        _emit_expected_error(
            command="rollback",
            fmt=fmt,
            harness=harness,
            error=_confirmation_required_error("rollback").to_dict(),
        )
        return

    results: list[dict[str, object]] = []
    restored_any = False
    errored = False
    last_output_path: Path | None = None
    for harness_id in selected:
        entry = _pkg.get_harness_entry(harness_id)
        try:
            adapter = _pkg._load_adapter_for_entry(entry)
        except _CliUserError as exc:
            _emit_expected_error(
                command="rollback", fmt=fmt, harness=harness, error=exc.to_dict()
            )
            return
        output_path = _adapter_resolve_output_path(adapter, project_root)
        last_output_path = output_path
        if entry.scope == "user":
            install_root = output_path.parent
            root_kwargs: dict[str, Path] = {"harness_root": install_root}
        else:
            install_root = cast(Path, project_root)
            root_kwargs = {"project_root": install_root}

        try:
            if install_id is not None:
                record = install_ledger.find_record(
                    entry.package_key, install_id, root=install_root
                )
            else:
                record = install_ledger.latest_record(
                    entry.package_key, root=install_root
                )
        except install_ledger.LedgerError as exc:
            # The ledger is the source of truth for what to restore; a corrupted
            # record cannot be silently skipped without risking a wrong or
            # partial rollback, so surface it as a structured error rather than
            # letting the raw parse failure escape as a traceback.
            corrupt = _CliUserError(
                code="rollback.ledger_corrupt",
                message="The install ledger is corrupted.",
                field="harness",
                reason=f"{harness_id}: {exc}.",
                fix="Inspect the harness ledger for a hand-edited or truncated "
                "record; rollback cannot proceed against a corrupted ledger.",
            )
            if _record_harness_error(
                corrupt,
                solo=len(selected) == 1,
                harness_id=harness_id,
                output_path=output_path,
                fmt=fmt,
                harness=harness,
                no_color=no_color,
                plain_line=f"[red]✗[/] {harness_id} rollback failed: ledger corrupt.",
                results=results,
            ):
                return
            errored = True
            continue

        if record is None:
            reason = (
                f"no install record with id {install_id!r}"
                if install_id is not None
                else "no recorded install to roll back"
            )
            no_record = _CliUserError(
                code="rollback.no_record",
                message="Nothing to roll back.",
                field="install-id" if install_id is not None else "harness",
                reason=f"{harness_id}: {reason}.",
                fix="Run 'apothem install' first, or pass an --install-id that "
                "appears in the harness ledger.",
            )
            # Mirror uninstall: a batch member's failure is visible in plain
            # mode, not only as a JSON result row.
            if _record_harness_error(
                no_record,
                solo=len(selected) == 1,
                harness_id=harness_id,
                output_path=output_path,
                fmt=fmt,
                harness=harness,
                no_color=no_color,
                plain_line=f"[red]✗[/] {harness_id} rollback failed: {escape(reason)}.",
                results=results,
            ):
                return
            errored = True
            continue

        if not record.targets and not record.created_dirs:
            results.append(
                {
                    "harness": harness_id,
                    "outcome": "skipped",
                    "operation": "rollback",
                    "path": str(output_path),
                    "message": "the install recorded no changes; nothing to roll back",
                }
            )
            if fmt != "json":
                con.print(
                    f"[dim]{harness_id}: install {escape(str(record.install_id))} "
                    "recorded no changes; nothing to roll back.[/]"
                )
            continue

        if not yes:
            click.confirm(
                f"Roll back {harness_id} to the state before install "
                f"{record.install_id}?",
                abort=True,
            )

        # Reverse the record target by target: restore each recorded backup
        # to its recorded path, remove what the install created, and remove
        # the directories it created once empty.
        target_results: list[MaterializationResult] = install_driver.rollback_install(
            record, harness_name=entry.package_key, **root_kwargs
        )
        install_ledger.append_record(
            LedgerRecord.create(
                harness=entry.package_key,
                root=install_root,
                kind="rollback",
                install_id=record.install_id,
            )
        )
        harness_failures: list[MaterializationResult] = []
        for result in target_results:
            if result.outcome in {"created", "updated"}:
                restored_any = True
            elif result.outcome == "error":
                errored = True
                harness_failures.append(result)
            entry_dict: dict[str, object] = {
                "harness": harness_id,
                "outcome": result.outcome,
                "operation": "rollback",
                "path": result.path,
                "message": result.message,
            }
            if result.backup_path is not None:
                entry_dict["backup_path"] = result.backup_path
            results.append(entry_dict)
        if fmt != "json":
            # A restore failure is visible in plain mode, not only as a JSON
            # result row — and never behind an unconditional success line.
            if harness_failures:
                err_con = get_error_console(no_color=no_color)
                for failed in harness_failures:
                    err_con.print(
                        f"[red]✗[/] {harness_id} restore failed: "
                        f"{escape(str(failed.path))} — {escape(str(failed.message))}"
                    )
            else:
                con.print(
                    f"[green]✓[/] Rolled back [cyan]{harness_id}[/] to install "
                    f"[dim]{escape(str(record.install_id))}[/]"
                )

    exit_code = 0
    if errored:
        exit_code = _EXIT_PARTIAL if restored_any else _EXIT_EXPECTED
    if fmt == "json":
        status = _pkg._status_for_exit_code(exit_code)
        emit_json(
            _lifecycle_envelope(
                status=status,
                command="rollback",
                action="rolled_back",
                harness=harness,
                profile_path=None,
                project_root=project_root,
                files_written=[
                    str(item["path"])
                    for item in results
                    if item.get("outcome") in {"created", "updated"}
                ],
                results=results,
                warnings=[],
                output_path=last_output_path if len(selected) == 1 else None,
            )
        )
    if exit_code:
        sys.exit(exit_code)


@main.command(epilog=_EP_ROLLBACK)
@_harness_option
@click.option(
    "--install-id",
    default=None,
    metavar="ULID",
    help=(
        "Roll back the install pass with this ULID, taken from the harness "
        "install ledger (default: the latest recorded install)."
    ),
)
@click.option(
    "--last",
    is_flag=True,
    help="Roll back the latest recorded install (the default; explicit form).",
)
@click.option("--yes", is_flag=True, help="Skip confirmation prompt.")
@_project_option
@common_options
def rollback(
    harness: str,
    install_id: str | None,
    last: bool,
    yes: bool,
    project: str | None,
    quiet: bool,
    verbose: bool,
    output_format: str,
    no_color: bool,
    json_flag: bool,
) -> None:
    """Restore a harness to the state before its recorded install."""
    if install_id is not None and last:
        _emit_expected_error(
            command="rollback",
            fmt=resolve_format(output_format, json_flag),
            harness=harness,
            error=_CliUserError(
                code="rollback.conflicting_selectors",
                message="Pass at most one of --install-id and --last.",
                field="install-id",
                reason="--install-id selects a specific install; --last selects "
                "the most recent. They are mutually exclusive.",
                fix="Drop --last to roll back the given id, or drop --install-id "
                "to roll back the latest.",
            ).to_dict(),
        )
        return
    _rollback_impl(
        harness,
        install_id=install_id,
        yes=yes,
        fmt=resolve_format(output_format, json_flag),
        quiet=quiet,
        no_color=no_color,
        project=project,
    )


main.add_command(_make_updating_alias("Updating"))


main.add_command(_make_updating_alias("updating"))
