# SPDX-License-Identifier: MIT

"""``apothem doctor`` — system diagnostics for the Apothem installation."""

from __future__ import annotations

import sys

from rich.markup import escape
from rich.table import Table

import apothem.cli as _pkg
from apothem.cli import (
    _VERSION,
    main,
)
from apothem.cli._common_flags import (
    common_options,
    get_console,
    resolve_format,
)
from apothem.cli._epilogs import _EP_DOCTOR
from apothem.cli._helpers import (
    _EXIT_EXPECTED,
    _resolve_profile_path,
)
from apothem.cli._json_formatter import emit_json
from apothem.lib.profile import ProfileValidationError, load_profile_file


@main.command(epilog=_EP_DOCTOR)
@common_options
def doctor(
    quiet: bool,
    verbose: bool,
    output_format: str,
    no_color: bool,
    json_flag: bool,
) -> None:
    """Report Apothem environment and installation health, exiting non-zero on any failure.

    Prints the engine version, Python, and platform, validates the shared
    profile against the packaged schema — a present-but-malformed profile is a
    failure, not a green "found" — and probes every registered adapter's
    install state. An adapter that raises degrades to an error row rather than
    aborting the sweep. Any failed check — an invalid profile, or a harness that
    is uninstalled or could not be probed — forces a non-zero exit so a CI or
    setup step can gate on it.
    """
    import platform

    fmt = resolve_format(output_format, json_flag)
    con = get_console(no_color=no_color, quiet=quiet)
    adapters, load_failures = _pkg._all_adapters()
    # One adapter raising in is_installed() must not abort the diagnostic; it
    # degrades to an error row and forces a non-zero exit. Load failures take
    # the same shape — data in the report, never a stray styled warning that
    # would ignore --quiet/--no-color or corrupt JSON stdout.
    harness_status: list[dict[str, object]] = []
    errored = bool(load_failures)
    for failure in load_failures:
        harness_status.append(
            {"name": failure["name"], "installed": False, "error": failure["error"]}
        )
    for adapter in adapters:
        name = getattr(adapter, "name", type(adapter).__name__)
        try:
            harness_status.append({"name": name, "installed": adapter.is_installed()})
        except Exception as exc:
            errored = True
            harness_status.append(
                {
                    "name": name,
                    "installed": False,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )

    profile_path = _resolve_profile_path(None)
    profile_exists = profile_path.exists()
    # An existence check alone passes a present-but-malformed profile. Validate a
    # present profile against the packaged schema with the same loader the
    # `profile set` and install paths use, so a broken profile surfaces as a
    # diagnostic failure (and a non-zero exit) instead of a green "found".
    profile_valid: bool | None = None
    profile_error: str | None = None
    if profile_exists:
        try:
            load_profile_file(profile_path)
            profile_valid = True
        except ProfileValidationError as exc:
            profile_valid = False
            profile_error = str(exc)

    profile_ok = not (profile_exists and profile_valid is False)
    all_ok = (
        (not errored) and profile_ok and all(s["installed"] for s in harness_status)
    )

    if fmt == "json":
        payload: dict[str, object] = {
            "version": _VERSION,
            "python": sys.version.split()[0],
            "platform": f"{platform.system()} {platform.release()}",
            "profile_path": str(profile_path),
            "profile_exists": profile_exists,
            "profile_valid": profile_valid,
            "harnesses": harness_status,
            "all_ok": all_ok,
        }
        if profile_error is not None:
            payload["profile_error"] = profile_error
        emit_json(payload)
        if not all_ok:
            sys.exit(_EXIT_EXPECTED)
        return

    con.print("[bold]Apothem Doctor[/]")
    con.print(f"  Version:   Apothem v{_VERSION}")
    con.print(f"  Python:    {sys.version.split()[0]}")
    con.print(f"  Platform:  {platform.system()} {platform.release()}")

    if not profile_exists:
        profile_note = "[yellow]missing[/]"
    elif profile_valid:
        profile_note = "[green]found, valid[/]"
    else:
        profile_note = "[red]found, invalid[/]"
    con.print(f"  Profile:   {escape(str(profile_path))} [{profile_note}]")
    if profile_valid is False and profile_error:
        con.print(f"             [red]{escape(str(profile_error))}[/]")

    table = Table(title="Harness Status", show_header=True, header_style="bold cyan")
    table.add_column("Harness", style="cyan")
    table.add_column("Installed", justify="center")

    for status in harness_status:
        if status.get("error"):
            table.add_row(str(status["name"]), "[red]error[/]")
            continue
        installed = bool(status["installed"])
        table.add_row(str(status["name"]), "[green]✓[/]" if installed else "[dim]-[/]")

    con.print(table)

    if all_ok:
        con.print("[green]All checks passed.[/]")
    elif not profile_ok:
        con.print(
            "[yellow]The shared profile is present but failed schema validation. "
            "Fix the reported error, or re-scaffold it with 'apothem profile init'.[/]"
        )
        sys.exit(_EXIT_EXPECTED)
    else:
        con.print(
            "[yellow]Some harnesses are not installed or could not be checked. "
            "Run 'apothem install --harness <name>'.[/]"
        )
        sys.exit(_EXIT_EXPECTED)
