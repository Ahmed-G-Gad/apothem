# SPDX-License-Identifier: MIT

"""What an uninstall pass left behind, whether it finished, and its ledger record.

After the removals, :func:`left_behind` names each path the pass kept (files
of the operator's, links, a BEGIN marker left alone), :func:`left_unfinished`
tells whether what stays leaves the uninstall unfinished, and
:func:`record_uninstall` appends the record that says which: ``uninstall`` or
``uninstall-incomplete``. A finished uninstall also ends the harness's install
under each other spelling of the same folder (:func:`end_other_spellings`).
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from apothem.lib import install_ledger
from apothem.lib.install_ledger import LedgerRecord

from .install_driver_blocks import ANOTHER_BLOCK, stray_begin_warnings
from .install_driver_digests import backup_ledger_targets
from .install_driver_pathsafety import _is_link
from .install_driver_retention import unrecorded_warning
from .install_driver_sweep import _link_kept as link_kept
from .install_driver_sweep import kept_link_warnings, links_left_in
from .install_driver_types import (
    KEPT_REASON,
    MaterializationResult,
    _path_text,
    _result,
)
from .install_driver_written import UNPROVEN_REASONS, kept_file_warnings

#: Kept reasons that leave the uninstall unfinished: the ones ``apothem
#: update`` settles (:data:`install_driver_written.UNPROVEN_REASONS`), and a
#: file that holds another block between Apothem's markers (``another-block``),
#: which the operator deletes by hand before a second uninstall.
UNFINISHED_REASONS: frozenset[str] = UNPROVEN_REASONS | {ANOTHER_BLOCK}


def left_behind(
    results: list[MaterializationResult],
    active: list[LedgerRecord],
    *,
    floor: Path,
    prior: tuple[MaterializationResult, ...] = (),
) -> list[MaterializationResult]:
    """Return a warning for each path the uninstall kept: links and the user's files.

    A link a *prior* result (the caller's own removal) already names is not
    named again. A file the uninstall rewrote that still holds a BEGIN marker
    with no END after it is named too (see :func:`stray_begin_warnings`).
    """
    kept = [*kept_link_warnings(results), *kept_file_warnings(results)]
    created = {Path(path) for install in active for path in install.created_dirs}
    named = {result.detail.get("symlink") for result in (*prior, *results)}
    kept += [
        warning
        for warning in links_left_in(created, known=kept)
        if warning.path not in named
    ]
    recorded = (target.path for install in active for target in install.targets)
    return [
        *kept,
        *links_on_the_way(recorded, floor, known=[*prior, *results, *kept]),
        *stray_begin_warnings([*prior, *results]),
    ]


def links_on_the_way(
    paths: Iterable[str],
    floor: Path,
    *,
    known: list[MaterializationResult],
) -> list[MaterializationResult]:
    """Return one warning per link between *floor* and a recorded path.

    An uninstall leaves a link and what it points to in place; when nothing
    of Apothem's is left behind it, nothing else would name it. A link a
    result in *known* already names is skipped.
    """
    seen = {result.path for result in known} | {
        result.detail["symlink"] for result in known if "symlink" in result.detail
    }
    notes = []
    for text in paths:
        for ancestor in Path(text).parents:
            if ancestor == floor or floor not in ancestor.parents:
                break
            if _path_text(ancestor) not in seen and _is_link(ancestor):
                seen.add(_path_text(ancestor))
                notes.append(link_kept(ancestor))
    return notes


def left_unfinished(results: list[MaterializationResult]) -> bool:
    """Return True when Apothem's files stay where the uninstall could not finish.

    A removal failed, Apothem's files stay behind a link, files stay because
    this release cannot show whether they are Apothem's (an earlier release
    recorded them without digests, or no install record is left; ``apothem
    update`` records them, then a second uninstall finishes), or a file holds
    another block between Apothem's markers (deleted by hand, then a second
    uninstall finishes). See :data:`UNFINISHED_REASONS`.
    """
    return any(
        result.outcome == "error"
        or result.detail.get("blocked")
        or result.detail.get(KEPT_REASON) in UNFINISHED_REASONS
        for result in results
    )


def last_uninstall_finished(harness_name: str, root: Path) -> bool:
    """Return True when *root*'s latest ledger record is a finished uninstall.

    The unfinished uninstalls after it, and a failed install's own rollback,
    are passed over (see :func:`install_ledger.last_uninstall_finished`), so
    the next run works the same way. With no install in place, only then does
    what stays never stop the uninstall (``kept_reason`` ``no-active-install``);
    any other history (a rollback, unfinished uninstalls only, none) leaves it
    unfinished. See :func:`install_driver_written.remove_written`. A ledger
    that cannot be read shows no such record.
    """
    try:
        return install_ledger.last_uninstall_finished(harness_name, root=root)
    except (OSError, install_ledger.LedgerError):
        return False


def _latest_record(harness_name: str, root: Path | str) -> LedgerRecord | None:
    """Return *root*'s latest ledger record (``None`` also when it cannot be read)."""
    try:
        return install_ledger.latest_record(harness_name, root=root, kind=None)
    except (OSError, install_ledger.LedgerError):
        return None


def _is_latest(entry: LedgerRecord) -> bool:
    """Return True when *entry* is the latest record at its root (by id, time, kind)."""
    latest = _latest_record(entry.harness, entry.root)
    key = (entry.install_id, entry.timestamp, entry.kind)
    return (
        latest is not None and (latest.install_id, latest.timestamp, latest.kind) == key
    )


def record_uninstall(
    harness_name: str,
    root: Path,
    record: LedgerRecord | None,
    results: list[MaterializationResult],
    *,
    finished: bool,
    own: list[LedgerRecord],
    same: Iterable[str] = (),
) -> list[MaterializationResult]:
    """Append the uninstall record, ``uninstall-incomplete`` unless *finished*.

    Either record references every backup the pass took, and goes into *own*
    (this pass's records) before it is appended, as an append interrupted
    after the record landed returns nothing. A finished uninstall ends the
    install; a failure to write it raises, so the caller can record the
    uninstall as unfinished instead, unless the root's latest record is a
    finished uninstall all the same (this one, left in after the error, or an
    earlier pass's): it then stands, with a warning. A finished uninstall that
    stands also ends the install still in place under each root in *same*, the
    harness's other spellings of this folder, whose files this pass removed
    (see :func:`end_other_spellings`). An unfinished one keeps the install
    active for a second run; it is written even when the pass raised, unless
    the root's latest record is this pass's own (the last in *own*); an
    earlier pass's finished uninstall does not count. A failure to write it
    returns a warning naming the ledger, so it does not hide the pass's own
    error. Retention is the caller's to run.
    """
    if not finished and own and _is_latest(own[-1]):
        return []
    entry = LedgerRecord.create(
        harness=harness_name,
        root=root,
        kind="uninstall" if finished else "uninstall-incomplete",
        targets=backup_ledger_targets(results),
        install_id=record.install_id if record is not None else None,
    )
    own.append(entry)
    warnings: list[MaterializationResult] = []
    try:
        install_ledger.append_record(entry)
    except (OSError, install_ledger.LedgerError) as exc:
        latest = _latest_record(harness_name, root)
        if finished and (latest is None or latest.kind != "uninstall"):
            raise
        warnings.append(unrecorded_warning(entry, exc, finished=finished))
    if finished:
        warnings += end_other_spellings(harness_name, same)
    return warnings


def end_other_spellings(
    harness_name: str, same: Iterable[str]
) -> list[MaterializationResult]:
    """End the install still in place under each root in *same*.

    The roots are the harness's other spellings of the folder a finished
    uninstall cleaned; it removed what their records list, so none of them
    holds the shared folders afterwards. The uninstall stands when one cannot
    be recorded, whatever the error: that one returns a warning naming the
    ledger and the spelling whose install stays active instead.
    """
    warnings: list[MaterializationResult] = []
    for other in same:
        try:
            current = install_ledger.current_install_record(harness_name, root=other)
            if current is None:
                continue
            install_ledger.append_record(
                LedgerRecord.create(
                    harness=harness_name,
                    root=other,
                    kind="uninstall",
                    targets=(),
                    install_id=current.install_id,
                )
            )
        except Exception as exc:  # the finished uninstall stands either way
            ledger = install_ledger.ledger_path(harness_name)
            message = (
                f"{ledger}: the uninstall removed what the install under {other} "
                f"wrote, but could not record that install's end ({exc}). Status "
                "and verify still count it, and it keeps the shared folders, "
                f"until an uninstall runs for {other}"
            )
            warnings.append(_result("warning", "record_uninstall", ledger, message))
    return warnings
