# SPDX-License-Identifier: MIT

"""``apothem harnesses`` group — list and inspect registered adapters."""

from __future__ import annotations

import sys

import click
from rich.markup import escape
from rich.table import Table

import apothem.cli as _pkg
from apothem.cli import main
from apothem.cli._common_flags import (
    common_options,
    get_console,
    resolve_format,
)
from apothem.cli._epilogs import (
    _EP_HARNESSES_LIST,
    _EP_HARNESSES_SHOW,
)
from apothem.cli._helpers import (
    _CONTEXT,
    _EXIT_EXPECTED,
    _EXIT_PARTIAL,
    AliasedGroup,
    _CliUserError,
    _emit_expected_error,
    _unknown_harness_error,
)
from apothem.cli._json_formatter import emit_json


@main.group(cls=AliasedGroup, context_settings=_CONTEXT)
def harnesses() -> None:
    """List and inspect registered harness adapters."""


@harnesses.command("list", epilog=_EP_HARNESSES_LIST)
@common_options
def harnesses_list(
    quiet: bool,
    verbose: bool,
    output_format: str,
    no_color: bool,
    json_flag: bool,
) -> None:
    """List all registered harness adapters."""
    fmt = resolve_format(output_format, json_flag)
    con = get_console(no_color=no_color, quiet=quiet)
    adapters, load_failures = _pkg._all_adapters()

    # One adapter raising while reporting its status must not abort the listing;
    # it becomes an error row and the command exits non-zero so the fault is
    # observable. Load failures take the same error-row shape.
    entries: list[dict[str, object]] = []
    errored = bool(load_failures)
    for failure in load_failures:
        entries.append(
            {
                "name": failure["name"],
                "outcome": "error",
                "message": failure["error"],
            }
        )
    for adapter in adapters:
        name = getattr(adapter, "name", type(adapter).__name__)
        try:
            entries.append(
                {
                    "name": name,
                    "installed": adapter.is_installed(),
                    "output_path": str(adapter.output_path),
                }
            )
        except Exception as exc:
            errored = True
            entries.append(
                {
                    "name": name,
                    "outcome": "error",
                    "message": f"{type(exc).__name__}: {exc}",
                }
            )

    listed_any = any("installed" in entry for entry in entries)
    exit_code = 0
    if errored:
        exit_code = _EXIT_PARTIAL if listed_any else _EXIT_EXPECTED

    if fmt == "json":
        emit_json(entries)
        if exit_code:
            sys.exit(exit_code)
        return

    table = Table(
        title="Registered Harness Adapters",
        show_header=True,
        header_style="bold cyan",
    )
    table.add_column("Name", style="cyan", no_wrap=True)
    table.add_column("Installed", justify="center")
    table.add_column("Output Path")

    for entry in entries:
        if entry.get("outcome") == "error":
            table.add_row(
                str(entry["name"]),
                "[red]error[/]",
                escape(str(entry.get("message", ""))),
            )
            continue
        table.add_row(
            str(entry["name"]),
            "[green]✓[/]" if entry["installed"] else "[red]✗[/]",
            escape(str(entry["output_path"])),
        )

    con.print(table)
    if exit_code:
        sys.exit(exit_code)


@harnesses.command("show", epilog=_EP_HARNESSES_SHOW)
@click.argument("name")
@common_options
def harnesses_show(
    name: str,
    quiet: bool,
    verbose: bool,
    output_format: str,
    no_color: bool,
    json_flag: bool,
) -> None:
    """Show details for a specific harness adapter."""
    fmt = resolve_format(output_format, json_flag)
    con = get_console(no_color=no_color, quiet=quiet)
    try:
        entry = _pkg.get_harness_entry(name)
        adapter = _pkg._load_adapter_for_entry(entry)
    except KeyError:
        error = _unknown_harness_error(name).to_dict()
        _emit_expected_error(
            command="harnesses show",
            fmt=fmt,
            harness=name,
            error=error,
        )
        return
    except _CliUserError as exc:
        _emit_expected_error(
            command="harnesses show",
            fmt=fmt,
            harness=name,
            error=exc.to_dict(),
        )
        return

    # Adapter lifecycle code is the untrusted edge (see _adapter_failure_result):
    # is_installed() may raise, so probe it once behind a structured error rather
    # than letting a broken adapter surface a bare traceback in either branch.
    try:
        installed = adapter.is_installed()
    except Exception as exc:
        _emit_expected_error(
            command="harnesses show",
            fmt=fmt,
            harness=name,
            error=_CliUserError(
                code="harness.load_failed",
                message="Apothem adapter probe failed.",
                field="harness",
                reason=f"{entry.public_id}: {type(exc).__name__}: {exc}",
                fix="Reinstall Apothem or inspect the adapter package import.",
            ).to_dict(),
        )
        return

    if fmt == "json":
        emit_json(
            {
                "name": adapter.name,
                "display_name": entry.display_name,
                "scope": entry.scope,
                "installed": installed,
                "output_path": str(adapter.output_path),
            }
        )
    else:
        con.print(f"  [bold]Name:[/]       {adapter.name}")
        con.print(f"  [bold]Display:[/]    {entry.display_name}")
        con.print(f"  [bold]Scope:[/]      {entry.scope}")
        con.print(f"  [bold]Installed:[/]  {installed}")
        con.print(f"  [bold]Output:[/]     {escape(str(adapter.output_path))}")
