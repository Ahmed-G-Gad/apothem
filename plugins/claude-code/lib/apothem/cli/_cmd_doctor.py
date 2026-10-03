# SPDX-License-Identifier: MIT

"""``apothem doctor`` — health checks for the installed harnesses.

doctor judges what is installed, not what could be. An uninstalled harness is
informational. An installed harness must pass its adapter's ``verify``, and
every hook command its install registered must start with a no-op payload
(see :mod:`apothem.cli._doctor_hooks`). A present profile must validate. Any
failed check exits 1; a machine with one healthy harness exits 0.
"""

from __future__ import annotations

import platform
import sys
from pathlib import Path

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
from apothem.cli._doctor_hooks import probe_hooks, registered_hook_argvs
from apothem.cli._epilogs import _EP_DOCTOR
from apothem.cli._helpers import (
    _EXIT_EXPECTED,
    _CliUserError,
    _emit_expected_error,
    _invoke_with_project,
    _project_option,
    _resolve_profile_path,
    _resolve_project_root,
)
from apothem.cli._json_formatter import emit_json
from apothem.lib.harness_registry import HarnessRegistryEntry
from apothem.lib.install_ledger import LedgerError
from apothem.lib.profile import ProfileValidationError, load_profile_file

_STATUS_STYLE = {
    "ok": "[green]ok[/]",
    "not_installed": "[dim]not installed[/]",
    "needs_project": "[dim]needs --project[/]",
    "verify_failed": "[red]verify failed[/]",
    "hook_failed": "[red]hook failed[/]",
    "error": "[red]error[/]",
}


def _check(
    code: str,
    status: str,
    message: str,
    *,
    harness: str | None = None,
    fix: str | None = None,
) -> dict[str, object]:
    """Return one doctor check record (``status`` is pass, fail, or info)."""
    return {
        "code": code,
        "status": status,
        "harness": harness,
        "message": message,
        "fix": fix,
    }


def _update_fix(harness: str) -> str:
    return (
        f"Run 'update --harness {harness}' with the same command prefix you "
        "installed with, then run doctor again."
    )


def _probe_harness(
    entry: HarnessRegistryEntry,
    project_root: Path | None,
    checks: list[dict[str, object]],
) -> dict[str, object]:
    """Check one harness, append its check records, and return its report row."""
    name = entry.public_id
    row: dict[str, object] = {"name": name, "installed": False, "verified": None}
    try:
        adapter = _pkg._load_adapter_for_entry(entry)
    except Exception as exc:
        row.update(status="error", error=f"{type(exc).__name__}: {exc}")
        checks.append(
            _check(
                "harness.load_failed",
                "fail",
                f"{name}: the adapter could not be loaded ({row['error']}).",
                harness=name,
                fix="Reinstall Apothem or inspect the adapter package import.",
            )
        )
        return row
    if entry.scope == "project" and project_root is None:
        row["status"] = "needs_project"
        return row
    try:
        installed = bool(
            _invoke_with_project(adapter.is_installed, project=project_root)
        )
        row["installed"] = installed
        if not installed:
            row["status"] = "not_installed"
            return row
        verified = bool(_invoke_with_project(adapter.verify, project=project_root))
    except Exception as exc:
        row.update(status="error", error=f"{type(exc).__name__}: {exc}")
        checks.append(
            _check(
                "harness.probe_failed",
                "fail",
                f"{name}: the install probe raised ({row['error']}).",
                harness=name,
                fix=_update_fix(name),
            )
        )
        return row
    row["verified"] = verified
    if not verified:
        row["status"] = "verify_failed"
        checks.append(
            _check(
                "harness.verify_failed",
                "fail",
                f"{name} is installed but does not verify: managed files are "
                "missing or changed.",
                harness=name,
                fix=_update_fix(name),
            )
        )
        return row
    checks.append(_check("harness.verified", "pass", f"{name} verifies.", harness=name))
    row["status"] = "ok"
    _probe_registered_hooks(entry, project_root, row, checks)
    return row


def _probe_registered_hooks(
    entry: HarnessRegistryEntry,
    project_root: Path | None,
    row: dict[str, object],
    checks: list[dict[str, object]],
) -> None:
    """Start the hooks a verified harness registered; record the outcome on *row*."""
    name = entry.public_id
    try:
        argvs = registered_hook_argvs(
            entry.package_key,
            within=project_root if entry.scope == "project" else None,
        )
    except LedgerError as exc:
        row.update(status="error", hooks=None)
        checks.append(
            _check(
                "ledger.unreadable",
                "fail",
                f"{name}: the install ledger cannot be read ({exc}).",
                harness=name,
                fix="Move the damaged ledger file aside, then re-run "
                f"'update --harness {name}' to record a fresh install.",
            )
        )
        return
    if argvs is None:
        row["hooks"] = None
        checks.append(
            _check(
                "hook.unchecked",
                "info",
                f"{name}: no install record, so its hook commands were not checked.",
                harness=name,
                fix=f"Run 'update --harness {name}' to record the install.",
            )
        )
        return
    probes = probe_hooks(argvs)
    failed = [probe for probe in probes if not probe.ok]
    row["hooks"] = {
        "probed": len(probes),
        "failed": [{"command": p.command, "detail": p.detail} for p in failed],
    }
    for probe in failed:
        checks.append(
            _check(
                "hook.start_failed",
                "fail",
                f"{name}: a registered hook command cannot start: {probe.command} "
                f"({probe.detail}).",
                harness=name,
                fix="Check that the interpreter in the hook command exists and "
                f"runs, then {_update_fix(name)[0].lower()}{_update_fix(name)[1:]}",
            )
        )
    if failed:
        row["status"] = "hook_failed"
    elif probes:
        checks.append(
            _check(
                "hook.started",
                "pass",
                f"{name}: {len(probes)} hook command(s) start.",
                harness=name,
            )
        )


@main.command(epilog=_EP_DOCTOR)
@_project_option
@common_options
def doctor(
    project: str | None,
    quiet: bool,
    verbose: bool,
    output_format: str,
    no_color: bool,
    json_flag: bool,
) -> None:
    """Check the installed harnesses and the shared profile; exit 1 on any failure.

    Reports the engine version, Python, and platform; validates a present
    shared profile against the packaged schema; and, for every installed
    harness, runs the adapter's verify and starts each hook command the
    install registered with a no-op payload. A harness that is not installed
    is reported but is not a failure, so a machine with one healthy harness
    passes. Project-scope harnesses are checked when --project names their
    root.
    """
    fmt = resolve_format(output_format, json_flag)
    con = get_console(no_color=no_color, quiet=quiet)
    try:
        project_root = _resolve_project_root(project)
    except _CliUserError as exc:
        _emit_expected_error(command="doctor", fmt=fmt, error=exc.to_dict())
        return

    checks: list[dict[str, object]] = []
    profile_path = _resolve_profile_path(None)
    profile_exists = profile_path.exists()
    profile_valid: bool | None = None
    profile_error: str | None = None
    profile_error_code: str | None = None
    if profile_exists:
        try:
            load_profile_file(profile_path)
            profile_valid = True
            checks.append(
                _check("profile.valid", "pass", "The shared profile validates.")
            )
        except ProfileValidationError as exc:
            profile_valid = False
            profile_error = str(exc)
            profile_error_code = exc.diagnostic.code
            checks.append(
                _check(
                    exc.diagnostic.code,
                    "fail",
                    f"The shared profile does not validate: {exc.diagnostic.reason}",
                    fix=exc.diagnostic.fix,
                )
            )
    else:
        checks.append(
            _check(
                "profile.missing",
                "info",
                f"No shared profile at {profile_path}; install creates one.",
            )
        )

    # Entries and adapters resolve through the apothem.cli package so the test
    # seams (patching apothem.cli.iter_harness_entries / _load_adapter_for_entry)
    # land here as they do for the other sweeps.
    harness_rows = [
        _probe_harness(entry, project_root, checks)
        for entry in _pkg.iter_harness_entries()
    ]
    all_ok = not any(check["status"] == "fail" for check in checks)
    installed_count = sum(1 for row in harness_rows if row["installed"])

    if fmt == "json":
        payload: dict[str, object] = {
            "version": _VERSION,
            "python": sys.version.split()[0],
            "platform": f"{platform.system()} {platform.release()}",
            "profile_path": str(profile_path),
            "profile_exists": profile_exists,
            "profile_valid": profile_valid,
            "project": str(project_root) if project_root is not None else None,
            "harnesses": harness_rows,
            "checks": checks,
            "all_ok": all_ok,
        }
        if profile_error is not None:
            payload["profile_error"] = profile_error
            payload["profile_error_code"] = profile_error_code
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
        con.print(f"             [red]{escape(profile_error)}[/]")

    table = Table(title="Harness Status", show_header=True, header_style="bold cyan")
    table.add_column("Harness", style="cyan")
    table.add_column("Status")
    table.add_column("Hooks", justify="right")
    for row in harness_rows:
        hooks = row.get("hooks")
        hook_cell = ""
        if isinstance(hooks, dict):
            failed = hooks.get("failed")
            failed_count = len(failed) if isinstance(failed, list) else 0
            hook_cell = f"{hooks.get('probed', 0)} started"
            if failed_count:
                hook_cell = f"[red]{failed_count} failed[/]"
        table.add_row(
            str(row["name"]), _STATUS_STYLE.get(str(row["status"]), ""), hook_cell
        )
    con.print(table)

    for check in checks:
        if check["status"] != "fail":
            continue
        con.print(f"[red]✗[/] {escape(str(check['message']))}")
        if check["fix"]:
            con.print(f"  Fix: {escape(str(check['fix']))}")

    if all_ok:
        if installed_count:
            con.print(f"[green]All checks passed[/] ({installed_count} installed).")
        else:
            con.print(
                "[green]All checks passed.[/] No harness is installed yet; "
                "install one with 'install --harness <name>'."
            )
        return
    sys.exit(_EXIT_EXPECTED)
