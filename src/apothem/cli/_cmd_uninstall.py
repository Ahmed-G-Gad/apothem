# SPDX-License-Identifier: MIT

"""``apothem uninstall`` + the continuous-form aliases."""

from __future__ import annotations

import re
import shlex
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
    existing_user_level_dirs,
    is_project_scope,
    preview_uninstall,
    uninstall_advisories,
)
from apothem.harnesses._shared import install_driver_homelink
from apothem.harnesses._shared.install_driver import (
    MaterializationResult,
    MaterializationRun,
)
from apothem.harnesses._shared.install_driver_backup import REMOVED_APOTHEM_ONLY_FILE
from apothem.lib.harness_registry import package_key_for_public_id
from apothem.lib.install_ledger import recorded_root


def _retention_advisories(
    harness_id: str,
    adapter: object,
    project_root: Path | None,
    output_path: Path,
) -> list[dict[str, object]]:
    """Return the retained and released advisories for uninstalling *adapter*.

    Empty when the harness writes no user-home folder or has no install record.
    The ledger root is the project for a project-scope adapter, spelled as its
    install record spells it (an install made through the Python API can keep
    the folder as typed), and the harness folder for a user-scope one. A
    report that cannot be built never blocks the uninstall.
    """
    root = project_root if is_project_scope(adapter) else output_path.parent
    if root is None:
        return []
    try:
        if is_project_scope(adapter):
            root = recorded_root(package_key_for_public_id(harness_id), root)
        return uninstall_advisories(harness_id, preview_uninstall(harness_id, root))
    except (OSError, ValueError):
        return []


def _refuse_or_confirm(
    harness_id: str, adapter: object, output_path: Path, *, yes: bool
) -> None:
    """Refuse an uninstall a link would lead out of the home, else confirm it.

    Such an uninstall changes nothing, so it is refused before the question,
    as rollback is (see
    :func:`~apothem.harnesses._shared.install_driver_homelink.refuse_link_leaving_home`).
    A project-scope install root is the ``--project`` folder, already
    resolved, so only a user-scope one is checked.

    Raises:
        MaterializationError: When a link leads the install root out of the home.
        click.Abort: When the operator declines the confirmation.
    """
    if not is_project_scope(adapter):
        install_driver_homelink.refuse_link_leaving_home(
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


def _warning_lines(run: MaterializationRun, *, no_record: bool = False) -> list[str]:
    """Return the warnings to print, one line per group (see :func:`_warning_groups`).

    A link that keeps Apothem's own files is reported as a failure instead.
    With *no_record*, the paths kept because no install record matched are
    left out: the outcome line that follows counts them.
    """
    return [
        str(group["message"])
        for group in _warning_groups(run)
        if not _is_blocked(group)
        and not (no_record and _kept_reason(group) == "no-record")
    ]


def _kept_reason(group: dict[str, object]) -> object:
    """Return the ``kept_reason`` of a reported warning group, if any."""
    detail = group.get("detail")
    return detail.get("kept_reason") if isinstance(detail, dict) else None


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


def _earlier_release_paths(run: MaterializationRun) -> int:
    """Count the paths kept because an earlier release recorded them without digests."""
    return sum(
        1
        for warning in run.warnings
        if warning.detail.get("kept_reason") == "no-digests"
    )


def _error_groups(run: MaterializationRun) -> list[tuple[MaterializationResult, int]]:
    """Group a run's failed steps by message and by the link they name.

    Returns the first step of each group with the group's size, so the
    steps refused at one link form one line, and steps refused at two links
    form two.
    """
    groups: dict[tuple[str, str], list[MaterializationResult]] = {}
    for error in run.errors:
        key = (error.message, error.detail.get("symlink", ""))
        groups.setdefault(key, []).append(error)
    return [(members[0], len(members)) for members in groups.values()]


def _error_line(error: MaterializationResult, count: int) -> str:
    """Return the line reporting *count* failed steps like *error*.

    A step refused because a link leads it out of the allowed folder has a
    message that does not name the link; the line adds the link, where it
    leads and the fix.
    """
    line = f"{error.message} ({count} paths)" if count > 1 else error.message
    named = install_driver_homelink.unnamed_link_text(error)
    return f"{line}: {named}" if named else line


def _one_named_link(run: MaterializationRun, blocked: Counter[str]) -> dict[str, str]:
    """Return ``symlink`` and ``leads_to`` when the problems name one link only.

    The link is one a failed step names, or one that keeps installed paths
    behind it. Empty when the problems name no link, or more than one.
    """
    links: dict[str, str] = {}
    for error in run.errors:
        link = error.detail.get("symlink")
        if link:
            links.setdefault(link, error.detail.get("leads_to", ""))
    for link in blocked:
        if link:
            links.setdefault(link, "")
    if len(links) != 1:
        return {}
    ((link, leads_to),) = links.items()
    return {
        "symlink": link,
        "leads_to": leads_to or install_driver_homelink.leads_to_text(link),
    }


def _report_run(
    harness_id: str,
    outcome: object,
    output_path: Path,
    warnings: list[dict[str, object]],
    *,
    fmt: str,
    con: Console,
    no_color: bool,
    project: Path | None,
) -> tuple[list[dict[str, object]], bool]:
    """Report an adapter's uninstall results; return the failure rows and partial flag.

    A link the uninstall left in place, or a step that failed (such as removing
    a leftover folder), is reported rather than hidden behind the success line.
    Each warning is added to *warnings*; the printed lines are grouped. A
    failure returns one ``uninstall`` error row for the harness, then one row
    per failed step. The uninstall is partial when it removed files before the
    failure, or when installed files stay because they are reached through a
    link: the tool still loads them. When no install record matched, the
    line counting the kept paths is left to the outcome line that follows;
    with a failure, the error row and a ``Note:`` line carry that outcome.
    """
    run = outcome if isinstance(outcome, MaterializationRun) else None
    if run is None:
        return [], False
    warnings.extend(
        {"harness": harness_id, **group}
        for group in _warning_groups(run)
        if not _is_blocked(group)
    )
    blocked = _blocked_by_link(run)
    earlier = _earlier_release_paths(run)
    problems = [
        f"{count} installed path(s) stay because they are reached through the "
        f"link {link}, and {harness_id} still loads them; replace the link with a "
        "real folder that holds the same files, then run the command again"
        for link, count in blocked.items()
    ] + [_error_line(error, count) for error, count in _error_groups(run)]
    if earlier:
        problems.append(
            f"{earlier} path(s) an earlier release installed stay because its "
            "install record does not show which files Apothem wrote and they "
            "differ from what this release writes; move any file of your own "
            "out of those folders (an update replaces them), then run apothem "
            "update, then apothem uninstall again"
        )
    no_record = _no_record(run)
    if fmt != "json":
        for line in _warning_lines(run, no_record=no_record):
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
    detail = dict(_one_named_link(run, blocked))
    if no_record:
        found = _no_record_message(run, harness_id, project=project)
        summary["message"] = f"{summary['message']}; {found}"
        detail[_KEPT_REASON] = _NO_RECORD
        if fmt != "json":
            # Under --quiet the error stream still carries it, as the outcome
            # line of a run that finished does.
            out = get_error_console(no_color=no_color) if con.quiet else con
            out.print(f"[yellow]Note:[/] {harness_id} - {escape(found)}.")
    if detail:
        summary["detail"] = detail
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
    harness_id: str, outcome: object, output_path: Path, *, project: Path | None
) -> dict[str, object]:
    """Return the ``results`` row of an uninstall that finished.

    ``updated`` when it removed files; ``unchanged`` when everything it found
    stayed (each kept path is a warning), so a batch is not reported partial
    on the strength of a harness that removed nothing. When no install record
    matched, the row's ``detail`` carries ``kept_reason`` ``no-record`` and
    the message says what was kept, what was still removed and what to do.
    *project* is the ``--project`` folder of a project-scope harness, else
    ``None``.
    """
    run = outcome if isinstance(outcome, MaterializationRun) else None
    removed = run is not None and any(
        result.outcome == "updated" for result in run.results
    )
    row: dict[str, object] = {
        "harness": harness_id,
        "outcome": "updated" if removed else "unchanged",
        "operation": "uninstall",
        "path": str(output_path),
        "message": "managed files removed" if removed else "no files removed",
    }
    if run is not None and _no_record(run):
        row["message"] = _no_record_message(run, harness_id, project=project)
        row["detail"] = {_KEPT_REASON: _NO_RECORD}
    return row


#: The ``kept_reason`` of a path kept because no install record matched.
_KEPT_REASON, _NO_RECORD = "kept_reason", "no-record"


def _no_record(run: MaterializationRun) -> bool:
    """Return True when the uninstall kept files because no install record matched."""
    return any(
        warning.detail.get(_KEPT_REASON) == _NO_RECORD for warning in run.warnings
    )


def _no_record_message(
    run: MaterializationRun, harness_id: str, *, project: Path | None
) -> str:
    """Return the message of an uninstall that matched no install record.

    It counts the paths kept, names the shared home folders left as they
    were, names what the run still removed and ends with the next step:
    install and uninstall again, which removes the rest, or remove the kept
    paths by hand.
    """
    kept = sum(
        1 for warning in run.warnings if warning.detail.get(_KEPT_REASON) == _NO_RECORD
    )
    message = f"no install record matched, so {_count(kept, 'path')} {_was(kept)} kept"
    shared = existing_user_level_dirs(harness_id)
    if shared:
        folders = "the shared folder" if len(shared) == 1 else "the shared folders"
        was = _was(len(shared))
        message += f", and {folders} {', '.join(shared)} {was} left in your home"
    parts = _removed_parts(run)
    if parts:
        one = len(parts) == 1 and parts[0][1]
        names = " and ".join(part for part, _ in parts)
        message += f"; {names} {_was(1 if one else 2)} removed"
    where = f" --project {_quoted(project)}" if project is not None else ""
    command = f"apothem uninstall --harness {harness_id}{where}"
    step = (
        f"run apothem install --harness {harness_id}{where}, then {command}, to "
        "remove the rest, or remove the kept paths by hand (running the same "
        "uninstall again with --yes --format json lists them in its warnings)"
    )
    if project is not None:
        step = f"check that --project names the folder you installed into; if it does, {step}"
    return f"{message}; {step}"


#: The characters a folder can hold and still paste into a shell unquoted.
_PLAIN = re.compile(r"[A-Za-z0-9_./:~-]+")


def _quoted(folder: Path) -> str:
    """Return *folder* as a shell argument: quoted unless it is plain.

    Double quotes on Windows, where no file name holds one and a backslash
    is plain; POSIX quoting elsewhere.
    """
    text = str(folder)
    windows = sys.platform == "win32"
    if _PLAIN.fullmatch(text.replace("\\", "/") if windows else text):
        return text
    return f'"{text}"' if windows else shlex.quote(text)


def _removed_parts(run: MaterializationRun) -> list[tuple[str, bool]]:
    """Name what an uninstall that matched no install record still removed.

    Apothem-only files deleted whole, Apothem's lines taken out of a shared
    file, the data stores, and anything else, each with its count and
    whether it is one thing (``was removed``) or more (``were removed``).
    """
    removed = [result for result in run.results if result.outcome == "updated"]
    whole = sum(1 for r in removed if r.message == REMOVED_APOTHEM_ONLY_FILE)
    surgical = sum(1 for r in removed if r.operation == "surgical_uninstall")
    stores = sum(1 for r in removed if r.operation == "remove_data_home")
    other = len(removed) - surgical - stores
    homes = "its data folder" if stores == 1 else f"its {stores} data folders"
    lines = surgical - whole
    stored = f"the memory, contexts and learning stores in {homes} (backed up)"
    return [
        *([(_count(whole, "Apothem-only file"), whole == 1)] if whole else []),
        *(
            [(f"Apothem's own lines in {_count(lines, 'file')}", False)]
            if lines
            else []
        ),
        *([(stored, False)] if stores else []),
        *([(_count(other, "other path"), other == 1)] if other else []),
    ]


def _count(number: int, noun: str) -> str:
    """Return *number* and *noun*, with the noun plural unless *number* is 1."""
    return f"{number} {noun}" if number == 1 else f"{number} {noun}s"


def _was(number: int) -> str:
    """Return ``was`` for 1, else ``were``."""
    return "was" if number == 1 else "were"


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
    row: dict[str, object],
) -> None:
    """Print the outcome line and each retention note (plain output only).

    An uninstall that matched no install record (the row's ``detail`` says
    so) kept the files the install copied into place, so it says ``Partly
    uninstalled`` when it removed something and ``Not uninstalled`` when it
    removed nothing, instead of ``Uninstalled``. That line is printed under
    ``--quiet`` too, to the error stream, so the kept paths are never
    unreported.
    """
    if fmt == "json":
        return
    detail = row.get("detail")
    if isinstance(detail, dict) and detail.get(_KEPT_REASON) == _NO_RECORD:
        heading = (
            "Partly uninstalled" if row["outcome"] == "updated" else "Not uninstalled"
        )
        out = get_error_console(no_color=con.no_color) if con.quiet else con
        out.print(
            f"[yellow]{heading}:[/] {harness_id} - {escape(str(row['message']))}."
        )
    else:
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
            _refuse_or_confirm(harness_id, adapter, output_path, yes=yes)
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
        scoped = project_root if is_project_scope(adapter) else None
        failures, partial = _report_run(
            harness_id,
            outcome,
            output_path,
            warnings,
            fmt=fmt,
            con=con,
            no_color=no_color,
            project=scoped,
        )
        # A partial uninstall removed files, so a batch of one exits as partial.
        removed_any |= partial
        if failures:
            errored = True
            results.extend(failures)
            continue
        row = _finished_row(harness_id, outcome, output_path, project=scoped)
        removed_any |= row["outcome"] == "updated"
        results.append(row)
        retention = _settled(retention)
        warnings.extend(retention)
        _print_removed(harness_id, retention, fmt=fmt, con=con, row=row)

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
