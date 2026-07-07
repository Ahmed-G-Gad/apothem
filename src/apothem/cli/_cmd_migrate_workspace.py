# SPDX-License-Identifier: MIT

"""``apothem migrate-workspace`` — collapse a legacy layout into shared ``.apothem``."""

from __future__ import annotations

from pathlib import Path

import click
from rich.markup import escape

from apothem.cli import main
from apothem.cli._common_flags import (
    common_options,
    get_console,
    resolve_format,
)
from apothem.cli._epilogs import _EP_MIGRATE_WORKSPACE
from apothem.cli._helpers import (
    _CliUserError,
    _emit_expected_error,
    _project_option,
    _resolve_project_root,
)
from apothem.cli._json_formatter import emit_json
from apothem.lib.workspace_migration import (
    WorkspaceMigrationError,
    detect_legacy_layout,
    migrate_workspace,
)


@main.command(name="migrate-workspace", epilog=_EP_MIGRATE_WORKSPACE)
@_project_option
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Detect the legacy layout and report what would migrate without writing.",
)
@common_options
def migrate_workspace_command(
    project: str | None,
    dry_run: bool,
    quiet: bool,
    verbose: bool,
    output_format: str,
    no_color: bool,
    json_flag: bool,
) -> None:
    """Migrate a legacy per-harness workspace into the shared ``.apothem`` layout.

    The base is the resolved ``--project`` root when supplied, otherwise the
    current working directory (the project-local default). Per-harness
    memory/contexts/learning stores union-merge into the shared store; a
    conflicting record is skipped, never overwritten; a legacy ``.plans`` tree
    moves under ``.apothem/plans``; every consumed source is backed up first.
    The migration is idempotent.
    """
    fmt = resolve_format(output_format, json_flag)
    con = get_console(no_color=no_color, quiet=quiet)
    try:
        project_root = _resolve_project_root(project)
    except _CliUserError as exc:
        _emit_expected_error(
            command="migrate-workspace",
            fmt=fmt,
            harness=None,
            profile_path=None,
            error=exc.to_dict(),
        )
        return

    base = project_root if project_root is not None else Path.cwd()

    if dry_run:
        detected = detect_legacy_layout(base)
        if fmt == "json":
            emit_json(
                {
                    "command": "migrate-workspace",
                    "base": str(base),
                    "dry_run": True,
                    "legacy_layout_detected": detected,
                }
            )
            return
        if detected:
            con.print(
                f"[yellow]Legacy layout detected under {escape(str(base))}.[/] "
                "Run 'apothem migrate-workspace' to migrate it."
            )
        else:
            con.print(
                f"[green]No legacy layout under {escape(str(base))}; "
                "nothing to migrate.[/]"
            )
        return

    try:
        outcome = migrate_workspace(base)
    except WorkspaceMigrationError as exc:
        # The standard expected-error envelope, not an ad-hoc shape: JSON
        # consumers parse one error contract across every command.
        _emit_expected_error(
            command="migrate-workspace",
            fmt=fmt,
            harness=None,
            profile_path=None,
            error=_CliUserError(
                code="workspace.migration_failed",
                message="Apothem workspace migration failed.",
                field="project",
                reason=f"{base}: {exc}",
                fix="Inspect the reported path, then re-run "
                "'apothem migrate-workspace' (the migration is idempotent).",
            ).to_dict(),
        )
        return

    if fmt == "json":
        payload = outcome.to_dict()
        payload["command"] = "migrate-workspace"
        payload["status"] = "success"
        emit_json(payload)
        return

    if not outcome.migrated:
        con.print(
            f"[green]No legacy layout under {escape(str(base))}; nothing to migrate.[/]"
        )
        return

    con.print(f"[green]✓[/] Migrated the workspace under {escape(str(base))}.")
    con.print(
        f"  Merged: {outcome.memory_merged} memory, "
        f"{outcome.contexts_merged} contexts, "
        f"{outcome.learning_merged} learning records."
    )
    if outcome.plans_moved:
        con.print("  Moved: .plans/ -> .apothem/plans/")
    if outcome.backup_root is not None:
        con.print(f"  Backup: {escape(str(outcome.backup_root))}")
    if outcome.conflicts:
        con.print(
            f"  [yellow]Skipped {len(outcome.conflicts)} conflicting record(s) "
            "(same id, different body): "
            f"{escape(', '.join(outcome.conflicts))}[/]"
        )
    for note in outcome.notes:
        con.print(f"  [yellow]Note:[/] {escape(note)}")
