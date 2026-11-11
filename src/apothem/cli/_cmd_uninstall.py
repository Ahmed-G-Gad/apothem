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
    detail_paths,
    kept_listing,
    kept_paths,
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
from apothem.harnesses._shared.install_driver_blocks import ANOTHER_BLOCK, MARKER_LEFT
from apothem.harnesses._shared.install_driver_datahome import shell_quoted
from apothem.harnesses._shared.install_driver_types import KEPT_REASON
from apothem.harnesses._shared.install_driver_written import UNPROVEN_REASONS
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
    "no-record": (
        "{count} paths were kept: no install record shows whether Apothem wrote them"
    ),
    "no-active-install": (
        "{count} paths were kept: no install record lists them, and they do not "
        "match what this release writes; remove them by hand if you no longer "
        "want them"
    ),
    "no-digests": (
        "{count} paths were kept: the install record (made by an earlier "
        "release) cannot show they are Apothem's, and they differ from what "
        "this release writes"
    ),
    "changed": (
        "{count} paths were kept: they are not what Apothem wrote (changed or yours)"
    ),
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
    if kind == "kept":
        group["files"] = [path for member in members for path in kept_paths(member)]
        detail = group.get("detail")
        if isinstance(detail, dict):
            # The complete list is ``files``; member 0's own would repeat part.
            detail.pop("kept_files", None)
    return group


def _warning_lines(run: MaterializationRun) -> list[str]:
    """Return the warnings to print, one per group (see :func:`_warning_groups`).

    A group of kept paths lists every file under its line, so the advice that
    names them ("copy any you edited") points at files the reader can see. A
    link that keeps Apothem's own files is reported as a failure instead.
    """
    return [
        _with_files(group) for group in _warning_groups(run) if not _is_blocked(group)
    ]


def _with_files(group: dict[str, object]) -> str:
    """Return *group*'s message, followed by the paths it kept, one per line.

    Only a group of one whose sole kept path is its own (which its message
    names) prints no list.
    """
    files = group.get("files")
    if not isinstance(files, list):
        return str(group["message"])
    own = str(group.get("path")) if group.get("count") == 1 else None
    return kept_listing(str(group["message"]), files, own)


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
    """Count the paths kept because no record shows whether Apothem wrote them.

    The install was recorded by an earlier release without digests, or not
    recorded at all; either leaves the uninstall unfinished, as its ledger
    record says (the same kept reasons). Each kept path counts once, a folder
    with its files listed under it included, as the grouped line counts them.
    """
    return sum(
        1
        for warning in run.warnings
        if warning.detail.get("kept_reason") in UNPROVEN_REASONS
    )


def _error_groups(
    run: MaterializationRun,
) -> list[tuple[MaterializationResult, list[MaterializationResult]]]:
    """Group a run's failed steps by message and by the link they name.

    Returns the first step of each group with the group's members, so the
    steps refused at one link form one line, and steps refused at two links
    form two.
    """
    groups: dict[tuple[str, str], list[MaterializationResult]] = {}
    for error in run.errors:
        key = (error.message, error.detail.get("symlink", ""))
        groups.setdefault(key, []).append(error)
    return [(members[0], members) for members in groups.values()]


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


#: The failure line for the paths :func:`_earlier_release_paths` counts;
#: ``{fix}`` is :data:`_FIX_MARKED` when a warning names a file with an Apothem
#: marker the uninstall left, otherwise empty.
_UNPROVEN_PATHS = (
    "{count} path(s) stay because no record shows whether Apothem wrote them "
    "(the install was recorded by an earlier release, or not at all). apothem "
    "update writes this release's files over them and replaces each Apothem "
    "folder entry it writes whole (backing both up first), so first copy any "
    "listed file you edited or added{fix}; then run apothem update, then "
    "apothem uninstall again"
)

#: Why a file a warning names for an Apothem marker the uninstall left (a BEGIN
#: marker with no END after it, or another block between the markers) is
#: fixed before an update.
_MARKER_RISK = (
    "until a later release, an update rewrites a managed block from a BEGIN "
    "marker with no END marker to the end of the file, cutting your text after it"
)

#: What :data:`_UNPROVEN_PATHS` adds for those files.
_FIX_MARKED = (
    ", and fix the {count} file(s) whose warnings name an Apothem marker: "
    + _MARKER_RISK
)

#: The same for an uninstall that stopped, whose warnings may say to run
#: apothem update (see :func:`_stopped_caveat`).
_FIX_MARKED_FIRST = (
    ". Before you run apothem update, fix the {count} file(s) whose warnings "
    "name an Apothem marker: " + _MARKER_RISK
)

#: The failure line for files that hold another block between Apothem's
#: markers (``kept_reason`` ``another-block``).
_ANOTHER_BLOCK_LINE = (
    "{count} file(s) hold another block between Apothem's markers that is not "
    "a copy of Apothem's own, so Apothem left them as they are; delete it by "
    "hand (or the marker pair you quoted), then run apothem uninstall again"
)


def _marked_files(run: MaterializationRun) -> list[str]:
    """Return each file a warning names for an Apothem marker the uninstall left.

    A BEGIN marker with no END marker after it, or another block between
    Apothem's markers: the warning's ``detail`` carries ``marker_left`` (see
    :data:`~apothem.harnesses._shared.install_driver_blocks.MARKER_LEFT`).
    """
    marked = (w.path for w in run.warnings if w.detail.get(MARKER_LEFT))
    return list(dict.fromkeys(marked))


def _link_problems(
    harness_id: str, run: MaterializationRun, blocked: Counter[str]
) -> dict[str, list[str]]:
    """Return the failure line for each link that keeps Apothem's files in place.

    A link whose files the tool no longer loads (see :func:`_unloaded_links`)
    does not say it still loads them.
    """
    unloaded = _unloaded_links(run)
    return {
        f"{count} installed path(s) stay because they are reached through the "
        f"link {link}"
        + ("" if link in unloaded else f", and {harness_id} still loads them")
        + "; replace the link with a real folder that holds the same files, "
        "then run the command again": []
        for link, count in blocked.items()
    }


def _problems(
    harness_id: str, run: MaterializationRun, blocked: Counter[str], earlier: int
) -> dict[str, list[str]]:
    """Return each reason an uninstall did not finish, with the paths it names.

    Failed steps are grouped by message and by the link they name (see
    :func:`_error_groups`). A failed step that could not remove files Apothem
    wrote names them, so the advice to close what holds them points at files
    the reader can see. When the next step is to run apothem update and a
    warning names a file with an Apothem marker the uninstall left, the step
    says to fix that file first (:data:`_FIX_MARKED`).
    """
    problems = _link_problems(harness_id, run, blocked)
    for first, members in _error_groups(run):
        problems[_error_line(first, len(members))] = [
            path for member in members for path in detail_paths(member, "stuck_files")
        ]
    if earlier:
        marked = len(_marked_files(run))
        fix = _FIX_MARKED.format(count=marked) if marked else ""
        problems[_UNPROVEN_PATHS.format(count=earlier, fix=fix)] = []
    another = sum(
        1 for w in run.warnings if w.detail.get("kept_reason") == ANOTHER_BLOCK
    )
    if another:
        problems[_ANOTHER_BLOCK_LINE.format(count=another)] = []
    return problems


def _stopped_caveat(run: MaterializationRun | None) -> str:
    """Return what the failure line of an uninstall that stopped adds, or ``""``.

    Its warnings may say to run apothem update (paths no record shows are
    Apothem's, see :func:`_earlier_release_paths`); when another warning names
    a file with an Apothem marker the uninstall left, that file comes first
    (:data:`_FIX_MARKED_FIRST`).
    """
    if run is None or not _earlier_release_paths(run):
        return ""
    marked = len(_marked_files(run))
    return _FIX_MARKED_FIRST.format(count=marked) if marked else ""


#: The ``detail`` keys that join the files a removal kept.
_KEPT_KEYS = ("kept_files", "kept_differing")


def _step_rows(
    harness_id: str, run: MaterializationRun | None
) -> list[dict[str, object]]:
    """Return one ``results`` row per failed step of *run*.

    The files a step kept are a ``files`` list, as in the warnings, and the
    files Apothem wrote that it could not remove a ``stuck`` list, in place of
    the ``detail`` strings that join them.
    """
    rows = []
    for error in run.errors if run is not None else ():
        row: dict[str, object] = {"harness": harness_id, **error.to_dict()}
        detail = row.get("detail")
        if isinstance(detail, dict):
            files = [path for key in _KEPT_KEYS for path in detail_paths(error, key)]
            stuck = detail_paths(error, "stuck_files")
            for key in (*_KEPT_KEYS, "stuck_files"):
                detail.pop(key, None)
            if files:
                row["files"] = files
            if stuck:
                row["stuck"] = stuck
            if not detail:
                del row["detail"]
        rows.append(row)
    return rows


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
    link (most tools still load them). An install with no record is unfinished
    too (see :func:`_earlier_release_paths`): its error row carries
    ``kept_reason`` ``no-record``, and a ``Note:`` line says what was kept and
    what was still removed.
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
    problems = _problems(harness_id, run, blocked, earlier)
    if fmt != "json":
        # Under --quiet the warnings are not printed, so an unfinished
        # uninstall prints the paths its advice is about with the failure.
        listing = (
            get_error_console(no_color=no_color) if con.quiet and problems else con
        )
        for line in _warning_lines(run):
            listing.print(f"[yellow]Warning:[/] {harness_id} - {escape(line)}")
        for line, paths in problems.items():
            listed = kept_listing(line, paths, None)
            get_error_console(no_color=no_color).print(
                f"[red]✗[/] {harness_id} uninstall did not finish: {escape(listed)}"
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
    if _no_record(run):
        found = _no_record_message(run, harness_id, project=project)
        summary["message"] = f"{summary['message']}; {found}"
        detail[KEPT_REASON] = _NO_RECORD
        if fmt != "json":
            # Under --quiet the error stream carries it, with the failure line.
            out = get_error_console(no_color=no_color) if con.quiet else con
            out.print(f"[yellow]Note:[/] {harness_id} - {escape(found)}.")
    if detail:
        summary["detail"] = detail
    removed = any(result.outcome == "updated" for result in run.results)
    partial = bool(blocked) or bool(earlier) or removed
    return [summary, *_step_rows(harness_id, run)], partial


def _failed_adapter(
    harness_id: str,
    exc: Exception,
    output_path: Path,
    warnings: list[dict[str, object]],
    *,
    fmt: str,
    con: Console,
    no_color: bool,
) -> tuple[list[dict[str, object]], bool]:
    """Report an uninstall that raised; return its rows and whether it removed files.

    An uninstall that stops after removing files carries the run so far (a
    :class:`~apothem.harnesses._shared.install_driver.MaterializationError`
    with ``run``): its warnings and failed steps are reported, and the files
    it removed make the uninstall partial. The warnings print where
    :func:`_report_run` prints them: on *con*, or with the failure on
    standard error under ``--quiet``.
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
    caveat = _stopped_caveat(run)
    if fmt != "json":
        err = get_error_console(no_color=no_color)
        listing = err if con.quiet else con
        for line in _warning_lines(run) if run is not None else []:
            listing.print(f"[yellow]Warning:[/] {harness_id} - {escape(line)}")
        verb = "stopped after removing files" if removed else "failed"
        # Files Apothem wrote that it could not remove are named here, as in
        # an uninstall that finished its steps (see _problems).
        stuck = [
            path
            for error in (run.errors if run is not None else ())
            for path in detail_paths(error, "stuck_files")
        ]
        message = kept_listing(f"{exc}{caveat}", stuck, None)
        err.print(f"[red]✗[/] {harness_id} uninstall {verb}: {escape(message)}")
    row = _adapter_failure_result(harness_id, "uninstall", output_path, exc)
    if caveat:
        row["message"] = f"{row['message']}{caveat}"
    return [row, *_step_rows(harness_id, run)], removed


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


#: The ``kept_reason`` of a path kept because no install record matched.
_NO_RECORD = "no-record"


def _no_record(run: MaterializationRun) -> bool:
    """Return True when the uninstall kept files because no install record matched."""
    return any(
        warning.detail.get(KEPT_REASON) == _NO_RECORD for warning in run.warnings
    )


def _no_record_message(
    run: MaterializationRun, harness_id: str, *, project: Path | None
) -> str:
    """Return the ``Note:`` of an uninstall that matched no install record.

    It names the shared home folders left as they were and what the run
    still removed; the grouped warning line and the failure line already
    count the paths kept. The next step (update, then uninstall again) is on
    the failure line, with the files to fix first when a warning names an
    Apothem marker the uninstall left (see :data:`_FIX_MARKED`); for a
    project-scope harness (*project* is its ``--project`` folder) this adds
    the check that ``--project`` names the folder installed into, since an
    update in the wrong folder installs there, and repeats that those files
    come first.
    """
    message = "no install record matched"
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
    if project is not None:
        # Quoted as every printed command quotes a folder; one the quotes
        # cannot carry is named as it is.
        quoted = shell_quoted(str(project))
        named = f"--project {quoted}" if quoted else f"the --project folder {project}"
        message += (
            f"; before you run apothem update, check that {named} is the "
            "folder you installed into"
        )
        marked = len(_marked_files(run))
        if marked:
            message += (
                f", and fix the {marked} file(s) whose warnings name an Apothem marker"
            )
    return message


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
                harness_id,
                exc,
                output_path,
                warnings,
                fmt=fmt,
                con=con,
                no_color=no_color,
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
