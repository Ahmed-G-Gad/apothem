# SPDX-License-Identifier: MIT

"""``apothem uninstall`` + the continuous-form aliases."""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

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
from apothem.harnesses._shared.install_driver import (
    MaterializationResult,
    MaterializationRun,
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


#: The grouped line for paths an uninstall kept, by ``kept_reason``.
_KEPT_GROUP_LINES = {
    "unrecorded": "{count} paths were kept: the install record does not list them",
    "no-record": "{count} paths were kept: no install record shows Apothem wrote them",
    "no-digests": (
        "{count} paths were kept: the install record does not show which files "
        "Apothem wrote (it was made by an earlier release); move any file of "
        "your own out of those folders (an update replaces them), then run "
        "apothem update, then apothem uninstall again"
    ),
    "changed": "{count} paths were kept: they are not what Apothem wrote (changed or yours)",
}


def _warning_groups(run: MaterializationRun) -> list[dict[str, object]]:
    """Group a run's warnings the way they are reported.

    Paths kept for the same link (all the files under a linked folder), and
    paths kept for the same reason, form one group with their count; any
    other warning is a group of one. Each group is the first warning's
    dictionary with the grouped ``message``, ``count`` and ``paths``.
    """
    groups: dict[tuple[str, str], list[MaterializationResult]] = {}
    for warning in run.warnings:
        link = warning.detail.get("symlink")
        reason = warning.detail.get("kept_reason", "")
        if link:
            key = ("blocked" if warning.detail.get("blocked") else "link", link)
        elif reason in _KEPT_GROUP_LINES:
            key = ("kept", reason)
        else:
            key = ("message", warning.message)
        groups.setdefault(key, []).append(warning)
    return [_group(key, members) for key, members in groups.items()]


def _group(
    key: tuple[str, str], members: list[MaterializationResult]
) -> dict[str, object]:
    """Return one reported warning for the *members* grouped under *key*."""
    group = members[0].to_dict()
    count = len(members)
    kind, value = key
    if count > 1 and kind in {"link", "blocked"}:
        group["message"] = (
            f"{count} paths reached through the link {value} were left in "
            "place: Apothem does not remove anything through a link"
        )
    elif count > 1 and kind == "kept":
        group["message"] = _KEPT_GROUP_LINES[value].format(count=count)
    group["count"] = count
    group["paths"] = [member.path for member in members]
    return group


def _warning_lines(run: MaterializationRun) -> list[str]:
    """Return the warnings to print, one line per group (see :func:`_warning_groups`).

    A link that keeps Apothem's own files is reported as a failure instead.
    """
    return [
        str(group["message"])
        for group in _warning_groups(run)
        if not _is_blocked(group)
    ]


def _is_blocked(group: dict[str, object]) -> bool:
    """Return True for a group of Apothem's files left behind a link."""
    detail = group.get("detail")
    return isinstance(detail, dict) and bool(detail.get("blocked"))


def _blocked_by_link(run: MaterializationRun) -> Counter[str]:
    """Count the installed paths an uninstall left because a link leads to them."""
    return Counter(
        warning.detail.get("symlink", "")
        for warning in run.warnings
        if warning.detail.get("blocked")
    )


def _unloaded_links(run: MaterializationRun) -> set[str]:
    """Return the blocking links whose files the tool no longer loads.

    A warning says so with ``loaded: "0"`` (open-claw's rules file, whose hook
    entry the uninstall has already removed); a link counts only when every
    blocked warning for it says so.
    """
    loaded = {
        warning.detail.get("symlink", "")
        for warning in run.warnings
        if warning.detail.get("blocked") and warning.detail.get("loaded") != "0"
    }
    return set(_blocked_by_link(run)) - loaded


def _earlier_release_paths(run: MaterializationRun) -> int:
    """Count the paths kept because an earlier release recorded them without digests."""
    return sum(
        1
        for warning in run.warnings
        if warning.detail.get("kept_reason") == "no-digests"
    )


def _report_run(
    harness_id: str,
    outcome: object,
    output_path: Path,
    warnings: list[dict[str, object]],
    *,
    fmt: str,
    con: Console,
    no_color: bool,
) -> tuple[list[dict[str, object]], bool]:
    """Report an adapter's uninstall results; return the failure rows and partial flag.

    A link the uninstall left in place, or a step that failed (such as removing
    a leftover folder), is reported rather than hidden behind the success line.
    Each warning is added to *warnings*; the printed lines are grouped. A
    failure returns one ``uninstall`` error row for the harness, then one row
    per failed step. The uninstall is partial when it removed files before the
    failure, or when installed files stay because they are reached through a
    link (most tools still load them).
    """
    run = outcome if isinstance(outcome, MaterializationRun) else None
    if run is None:
        return [], False
    warnings.extend(
        {"harness": harness_id, **group}
        for group in _warning_groups(run)
        if not _is_blocked(group)
    )
    counts = Counter(error.message for error in run.errors)
    blocked = _blocked_by_link(run)
    unloaded = _unloaded_links(run)
    earlier = _earlier_release_paths(run)
    problems = [
        f"{count} installed path(s) stay because they are reached through the "
        f"link {link}"
        + ("" if link in unloaded else f", and {harness_id} still loads them")
        + "; replace the link with a real folder that holds the same files, "
        "then run the command again"
        for link, count in blocked.items()
    ] + [
        f"{message} ({count} paths)" if count > 1 else message
        for message, count in counts.items()
    ]
    if earlier:
        problems.append(
            f"{earlier} path(s) an earlier release installed stay because its "
            "install record does not show which files Apothem wrote and they "
            "differ from what this release writes; move any file of your own "
            "out of those folders (an update replaces them), then run apothem "
            "update, then apothem uninstall again"
        )
    another = sum(
        1 for w in run.warnings if w.detail.get("kept_reason") == "another-block"
    )
    if another:
        problems.append(
            f"{another} file(s) hold another block between Apothem's markers that "
            "is not a copy of Apothem's own, so Apothem left them as they are; "
            "delete it by hand (or the marker pair you quoted), then run apothem "
            "uninstall again"
        )
    if fmt != "json":
        for line in _warning_lines(run):
            con.print(f"[yellow]Warning:[/] {harness_id} - {escape(line)}")
        for line in problems:
            get_error_console(no_color=no_color).print(
                f"[red]✗[/] {harness_id} uninstall did not finish: {escape(line)}"
            )
    if not problems:
        return [], False
    summary: dict[str, object] = {
        "harness": harness_id,
        "outcome": "error",
        "operation": "uninstall",
        "path": str(output_path),
        "message": "; ".join(problems),
    }
    steps = [{"harness": harness_id, **error.to_dict()} for error in run.errors]
    removed = any(result.outcome == "updated" for result in run.results)
    return [summary, *steps], bool(blocked) or bool(earlier) or removed


def _failed_adapter(
    harness_id: str,
    exc: Exception,
    output_path: Path,
    warnings: list[dict[str, object]],
    *,
    fmt: str,
    no_color: bool,
) -> tuple[list[dict[str, object]], bool]:
    """Report an uninstall that raised; return its rows and whether it removed files.

    An uninstall that stops after removing files carries the run so far (a
    :class:`~apothem.harnesses._shared.install_driver.MaterializationError`
    with ``run``): its warnings and failed steps are reported, and the files
    it removed make the uninstall partial.
    """
    run = getattr(exc, "run", None)
    run = run if isinstance(run, MaterializationRun) else None
    removed = run is not None and any(
        result.outcome == "updated" for result in run.results
    )
    if run is not None:
        warnings.extend(
            {"harness": harness_id, **group}
            for group in _warning_groups(run)
            if not _is_blocked(group)
        )
    if fmt != "json":
        verb = "stopped after removing files" if removed else "failed"
        get_error_console(no_color=no_color).print(
            f"[red]✗[/] {harness_id} uninstall {verb}: {escape(str(exc))}"
        )
    steps = (
        [{"harness": harness_id, **error.to_dict()} for error in run.errors]
        if run is not None
        else []
    )
    row = _adapter_failure_result(harness_id, "uninstall", output_path, exc)
    return [row, *steps], removed


def _finished_row(
    harness_id: str, outcome: object, output_path: Path
) -> dict[str, object]:
    """Return the ``results`` row of an uninstall that finished.

    ``updated`` when it removed files; ``unchanged`` when everything it found
    stayed (each kept path is a warning), so a batch is not reported partial
    on the strength of a harness that removed nothing.
    """
    run = outcome if isinstance(outcome, MaterializationRun) else None
    removed = run is not None and any(
        result.outcome == "updated" for result in run.results
    )
    return {
        "harness": harness_id,
        "outcome": "updated" if removed else "unchanged",
        "operation": "uninstall",
        "path": str(output_path),
        "message": "managed files removed" if removed else "no files removed",
    }


def _settled(retention: list[dict[str, object]]) -> list[dict[str, object]]:
    """Return the retention notes as they stand after the uninstall ran.

    A note is built before the uninstall (from the ledger it then replaces),
    so a folder it says was removed may still be there, holding files Apothem
    did not write; that note is reworded to say so.
    """
    settled = []
    for advisory in retention:
        path = Path(str(advisory.get("path", "")))
        if advisory.get("role") == "released" and path.is_dir():
            advisory = {
                **advisory,
                "message": (
                    f"{advisory['path']} was kept: no other Apothem install uses "
                    "it, but it holds files Apothem did not write."
                ),
            }
        settled.append(advisory)
    return settled


def _print_removed(
    harness_id: str,
    retention: list[dict[str, object]],
    *,
    fmt: str,
    con: Console,
) -> None:
    """Print the success line and each retention note (plain output only)."""
    if fmt == "json":
        return
    con.print(f"[green]✓[/] Uninstalled [cyan]{harness_id}[/]")
    for advisory in retention:
        con.print(f"[yellow]Note:[/] {harness_id} - {escape(str(advisory['message']))}")


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
            if not yes:
                click.confirm(
                    f"Remove {harness_id} configuration at {output_path}?",
                    abort=True,
                )
            # What the uninstall keeps in the user home because another install
            # still uses it is read from the ledger before the install's own
            # record is replaced.
            retention = _retention_advisories(
                harness_id, adapter, project_root, output_path
            )
            outcome = _invoke_with_project(adapter.uninstall, project=project_root)
        except click.Abort:
            raise
        except Exception as exc:
            errored = True
            rows, removed = _failed_adapter(
                harness_id, exc, output_path, warnings, fmt=fmt, no_color=no_color
            )
            results.extend(rows)
            removed_any |= removed
            continue
        failures, partial = _report_run(
            harness_id,
            outcome,
            output_path,
            warnings,
            fmt=fmt,
            con=con,
            no_color=no_color,
        )
        # A partial uninstall removed files, so a batch of one exits as partial.
        removed_any |= partial
        if failures:
            errored = True
            results.extend(failures)
            continue
        row = _finished_row(harness_id, outcome, output_path)
        removed_any |= row["outcome"] == "updated"
        results.append(row)
        retention = _settled(retention)
        warnings.extend(retention)
        _print_removed(harness_id, retention, fmt=fmt, con=con)

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
