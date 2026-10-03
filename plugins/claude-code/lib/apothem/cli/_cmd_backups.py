# SPDX-License-Identifier: MIT

"""``apothem backups`` group — prune the install backups and ledger history.

Every install, uninstall and rollback already keeps each harness to the newest
``BACKUP_KEEP`` backup sets and install records. ``backups prune`` runs that
same retention on demand, with its own bound and an optional dry run, so an
operator can reclaim ``~/.apothem/`` without deleting it by hand and without
losing the ability to roll back the latest install.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field

import click
from rich.console import Console
from rich.markup import escape

import apothem.cli as _pkg
from apothem.cli import main
from apothem.cli._common_flags import (
    common_options,
    get_console,
    get_error_console,
    resolve_format,
)
from apothem.cli._epilogs import _EP_BACKUPS_PRUNE
from apothem.cli._helpers import (
    _CONTEXT,
    _EXIT_EXPECTED,
    _EXIT_PARTIAL,
    AliasedGroup,
    _CliUserError,
    _complete_harness,
    _emit_expected_error,
    _lifecycle_envelope,
)
from apothem.cli._json_formatter import emit_json
from apothem.harnesses._shared import install_driver
from apothem.harnesses._shared.install_driver import BACKUP_KEEP, RetentionReport
from apothem.lib import install_ledger


@main.group(cls=AliasedGroup, context_settings=_CONTEXT)
def backups() -> None:
    """Manage the install backups and ledger history Apothem keeps."""


@dataclass
class _PruneTally:
    """Result rows and outcome flags accumulated across the selected harnesses.

    *pruned* records that some harness had something to prune (or, for a dry
    run, would have); *errored* that some harness failed.
    """

    dry_run: bool
    results: list[dict[str, object]] = field(default_factory=list)
    pruned: bool = False
    errored: bool = False

    def exit_code(self) -> int:
        """0 when clean; partial when a real run pruned something; else 1."""
        if not self.errored:
            return 0
        return _EXIT_PARTIAL if self.pruned and not self.dry_run else _EXIT_EXPECTED


@backups.command("prune", epilog=_EP_BACKUPS_PRUNE)
@click.option(
    "--keep",
    type=click.IntRange(min=1),
    default=BACKUP_KEEP,
    show_default=True,
    metavar="N",
    help="Backup sets per harness, and install records per install root, to keep.",
)
@click.option(
    "--harness",
    default="all",
    show_default=True,
    metavar="NAME",
    help="Harness adapter name, or 'all' for every registered harness.",
    shell_complete=_complete_harness,
)
@click.option(
    "--dry-run", is_flag=True, help="Report what would be pruned; delete nothing."
)
@common_options
def backups_prune(
    keep: int,
    harness: str,
    dry_run: bool,
    quiet: bool,
    verbose: bool,
    output_format: str,
    no_color: bool,
    json_flag: bool,
) -> None:
    """Delete backup sets and install records beyond the newest N per harness.

    Keeps the newest N backup sets under ~/.apothem/backups/ for each selected
    harness, and the newest N install records per install root in its ledger
    under ~/.apothem/state/. A backup set that a kept record, or the latest
    install record of any install root, still references is never deleted, so
    rollback of the latest install still restores.
    """
    fmt = resolve_format(output_format, json_flag)
    con = get_console(no_color=no_color, quiet=quiet)
    try:
        selected = _pkg._selected_harness_ids(
            harness, shared_profile=None, apply_excludes=False
        )
    except _CliUserError as exc:
        _emit_expected_error(
            command="backups prune", fmt=fmt, harness=harness, error=exc.to_dict()
        )
        return

    tally = _PruneTally(dry_run=dry_run)
    for harness_id in selected:
        package_key = _pkg.get_harness_entry(harness_id).package_key
        try:
            report = install_driver.prune_history(
                package_key, keep=keep, dry_run=dry_run
            )
        except (install_ledger.LedgerError, OSError) as exc:
            tally.errored = True
            tally.results.append(
                _row(
                    harness_id,
                    "error",
                    install_ledger.ledger_path(package_key),
                    f"nothing pruned: {exc}",
                )
            )
            if fmt != "json":
                get_error_console(no_color=no_color).print(
                    f"[red]✗[/] [cyan]{harness_id}[/] nothing pruned: "
                    f"{escape(str(exc))}"
                )
            continue
        _record_report(tally, harness_id, report)
        if fmt != "json":
            _print_report(con, harness_id, report, verbose=verbose, no_color=no_color)

    exit_code = tally.exit_code()
    if fmt == "json":
        status = _pkg._status_for_exit_code(exit_code)
        emit_json(
            _lifecycle_envelope(
                status="dry_run" if dry_run and exit_code == 0 else status,
                command="backups prune",
                action="dry_run" if dry_run else "pruned",
                harness=harness,
                profile_path=None,
                project_root=None,
                files_written=[],
                results=tally.results,
                warnings=[],
            )
        )
    elif not tally.pruned and not tally.errored:
        verb = "would be pruned" if dry_run else "to prune"
        con.print(f"Nothing {verb} (keeping the newest {keep} per harness).")
    if exit_code:
        sys.exit(exit_code)


def _row(
    harness_id: str, outcome: str, path: object, message: str
) -> dict[str, object]:
    """Return one ``prune`` result row."""
    return {
        "harness": harness_id,
        "outcome": outcome,
        "operation": "prune",
        "path": str(path),
        "message": message,
    }


def _record_report(
    tally: _PruneTally, harness_id: str, report: RetentionReport
) -> None:
    """Fold one harness's retention report into result rows on *tally*."""
    remove, drop = (
        ("would remove", "would drop") if report.dry_run else ("removed", "dropped")
    )
    backup_root = install_driver.BACKUP_ROOT
    for stamp in report.pruned:
        path = backup_root / stamp / report.harness
        if stamp in report.failed:
            tally.errored = True
            tally.results.append(
                _row(harness_id, "error", path, "backup set could not be fully removed")
            )
            continue
        tally.results.append(
            _row(harness_id, "updated", path, f"{remove} backup set {stamp}")
        )
    for stamp in report.protected:
        tally.results.append(
            _row(
                harness_id,
                "skipped",
                backup_root / stamp / report.harness,
                f"kept backup set {stamp}: an install record still references it",
            )
        )
    if report.records_dropped:
        tally.results.append(
            _row(
                harness_id,
                "updated",
                install_ledger.ledger_path(report.harness),
                f"{drop} {report.records_dropped} of "
                f"{report.records_before} install ledger records",
            )
        )
    removed = len(report.pruned) - len(report.failed)
    if removed or report.records_dropped:
        tally.pruned = True
    elif not report.failed:
        tally.results.append(
            _row(
                harness_id,
                "unchanged",
                backup_root,
                f"nothing to prune: {len(report.kept)} backup sets, "
                f"{report.records_after} install ledger records",
            )
        )


def _print_report(
    con: Console,
    harness_id: str,
    report: RetentionReport,
    *,
    verbose: bool,
    no_color: bool,
) -> None:
    """Print one harness's prune outcome (plain mode)."""
    for stamp in report.failed:
        get_error_console(no_color=no_color).print(
            f"[red]✗[/] [cyan]{harness_id}[/] backup set "
            f"{escape(str(install_driver.BACKUP_ROOT / stamp / report.harness))} "
            "could not be fully removed"
        )
    removed = len(report.pruned) - len(report.failed)
    if removed or report.records_dropped:
        lead = (
            "[bold yellow]DRY RUN[/] would remove"
            if report.dry_run
            else "[green]✓[/] Removed"
        )
        con.print(
            f"{lead} {removed} backup set(s) and {report.records_dropped} "
            f"ledger record(s) for [cyan]{harness_id}[/]; "
            f"{len(report.kept)} backup set(s) kept"
        )
    if not verbose:
        return
    for stamp in report.pruned:
        if stamp not in report.failed:
            con.print(
                f"  [dim]{'would remove' if report.dry_run else 'removed'}[/] {stamp}"
            )
    for stamp in report.protected:
        con.print(f"  [dim]kept (still referenced)[/] {stamp}")
