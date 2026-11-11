# SPDX-License-Identifier: MIT

"""What a managed-block file shows, and the warnings for the markers left in one.

A managed-block file (``sentinel_merge``) holds the operator's text beside
Apothem's block, which runs from a BEGIN marker to the next END marker. This
module reads such a file as install evidence (a whole block counts; a BEGIN
marker without its END counts only while the install may be open) and builds
the warnings an uninstall gives when it leaves a file because of its markers:
a block that lost its END marker, another whole block that is not a copy of
Apothem's own, and a BEGIN marker of the operator's left alone once Apothem's
block is out. Each of those warnings carries :data:`MARKER_LEFT`.
"""

from __future__ import annotations

from pathlib import Path

from apothem.lib import install_ledger
from apothem.lib.harness_materializer import (
    APOTHEM_BLOCK_END,
    complete_managed_block,
    extract_managed_block,
    remove_managed_block,
)
from apothem.lib.install_ledger import LedgerTarget

from .install_driver_types import (
    KEPT_REASON,
    MaterializationResult,
    _path_text,
    _result,
)

#: ``detail`` key (``"1"``) of a warning that names a file the uninstall left
#: as it is because of its markers: a BEGIN marker with no END marker after it
#: (:func:`endless_block_warning`, :func:`stray_begin_warnings`), or another
#: whole block (:func:`another_block_warning`). An install or update that writes
#: such a file again can take the operator's text with the block it rewrites:
#: from a BEGIN marker with no END, everything to the end of the file. So an
#: uninstall whose next step is ``apothem update`` names such a file first.
MARKER_LEFT = "marker_left"

#: ``kept_reason`` of a file that holds another whole block besides Apothem's
#: own (see :func:`another_block_warning`); it leaves the uninstall unfinished.
ANOTHER_BLOCK = "another-block"


def _endless(path: Path) -> bool:
    """Return True when *path* holds a BEGIN marker with no END marker after it."""
    try:
        text = path.read_bytes().decode("utf-8", errors="replace")
    except OSError:
        return False
    return extract_managed_block(text) is not None and not complete_managed_block(text)


def whole_block_left(entry: LedgerTarget) -> bool:
    """Return True when the managed-block file *entry* records holds a whole block.

    The block, both markers, is what Apothem wrote there, whatever the operator
    wrote around it (see :func:`install_driver_written.still_written`). A BEGIN
    marker left without its END does not count: the uninstall leaves that file
    as it is.
    """
    try:
        text = Path(entry.path).read_bytes().decode("utf-8", errors="replace")
    except OSError:
        return False
    return complete_managed_block(text) is not None


def endless_block_left(entry: LedgerTarget) -> bool:
    """Return True when *entry*, a managed-block file, lost its block's END marker.

    After an unfinished uninstall such a file keeps the install open, so the
    next uninstall runs, names the file and finishes (see :func:`whole_block_left`,
    which does not count it as Apothem's).
    """
    return entry.mode == "sentinel_merge" and _endless(Path(entry.path))


def install_may_be_open(harness_name: str, root: Path) -> bool:
    """Return False only when the ledger shows the install at *root* was closed.

    Closed means the latest record there is an ``uninstall``, or a rollback of
    a known install.

    An install still in effect, and a root the ledger knows nothing about (an
    install from before the ledger, a ledger lost or unreadable), may be open:
    the evidence that depends on it keeps counting there.
    """
    try:
        if install_ledger.current_install_record(harness_name, root=root):
            return True
        here = [
            record
            for record in install_ledger.read_records(harness_name)
            if record.root == str(root)
        ]
    except (OSError, install_ledger.LedgerError):
        return True
    if not here:
        return True
    # Closed: an uninstall, or a rollback of an install recorded here. An
    # unfinished uninstall or a rollback of no known install leaves it open.
    latest = here[-1]
    installs = {record.install_id for record in here if record.kind == "install"}
    return not (
        latest.kind == "uninstall"
        or (latest.kind == "rollback" and latest.install_id in installs)
    )


def endless_block_warning(target: Path, operation: str) -> MaterializationResult | None:
    """Return a warning when *target*'s managed block lost its END marker.

    A BEGIN marker with no END after it: the text below it may be the
    operator's, so nothing is removed, and the file no longer counts as
    Apothem's (see :func:`whole_block_left`). ``None`` when the file holds a
    whole block, holds no marker, or cannot be read.
    """
    try:
        text = target.read_bytes().decode("utf-8", errors="replace")
    except OSError:
        return None
    if extract_managed_block(text) is None or complete_managed_block(text):
        return None
    return _result(
        "warning",
        operation,
        target,
        f"{_path_text(target)} has the Apothem BEGIN marker but no END marker "
        f"({APOTHEM_BLOCK_END}) after it, so Apothem cannot tell where its block "
        "ends and left the file as it is. Delete that marker line, and what is "
        "left of the block, by hand, "
        "keeping your own text.",
        detail={MARKER_LEFT: "1"},
    )


def sentinel_refusal(target: Path) -> MaterializationResult | None:
    """Return why an uninstall leaves the managed-block file *target* as it is.

    Its block lost its END marker (:func:`endless_block_warning`), or another
    whole block stays once Apothem's own and its copies are out
    (:func:`another_block_warning`). ``None`` when the strip may go ahead.
    """
    endless = endless_block_warning(target, "surgical_uninstall")
    if endless is not None:
        return endless
    try:
        text = target.read_bytes().decode("utf-8", errors="replace")
    except OSError:
        return None
    if complete_managed_block(remove_managed_block(text)):
        return another_block_warning(target)
    return None


def another_block_warning(target: Path) -> MaterializationResult:
    """Name a file that holds another whole block besides Apothem's own.

    It is not a copy of Apothem's block, so it may be the operator's (a marker
    pair they quote): nothing changes, and the uninstall stays unfinished.
    """
    return _result(
        "warning",
        "surgical_uninstall",
        target,
        f"{_path_text(target)} holds another block between Apothem's markers that "
        "is not a copy of Apothem's own, so Apothem left the file as it is. Delete "
        "it by hand (or the marker pair you quoted), then run the uninstall again.",
        detail={KEPT_REASON: ANOTHER_BLOCK, MARKER_LEFT: "1"},
    )


def stray_begin_warnings(
    results: list[MaterializationResult],
) -> list[MaterializationResult]:
    """Name each file the uninstall rewrote that still holds a BEGIN marker alone.

    Taking Apothem's whole block out can leave such a line above where it was
    (a stray line of the operator's, say). An install or update that writes
    the file again replaces everything from that line to the end of the file.
    """
    rewritten = {
        result.path: result.operation
        for result in results
        if result.outcome == "updated"
        and result.operation in {"surgical_uninstall", "retire_anchor"}
    }
    return [
        _result(
            "warning",
            operation,
            Path(path),
            f"{path} still holds a line that reads as the Apothem BEGIN marker, "
            f"with no END marker ({APOTHEM_BLOCK_END}) after it, now that "
            "Apothem's block is out. Delete that line by hand: an install or "
            "update that writes this file again replaces everything from it to "
            "the end of the file.",
            detail={MARKER_LEFT: "1"},
        )
        for path, operation in rewritten.items()
        if _endless(Path(path))
    ]
