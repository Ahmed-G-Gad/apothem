# SPDX-License-Identifier: MIT

"""What a managed-block file shows, and the warnings for the markers left in one.

A managed-block file (``sentinel_merge``) holds the operator's text beside
Apothem's block, which runs from a BEGIN marker to the next END marker. This
module reads such a file as install evidence (a whole block counts; a BEGIN
marker without its END counts only while the install may be open) and builds
the warnings an uninstall gives when it leaves a file because of its markers:
a block that lost its END marker, another whole block that is not a copy of
Apothem's own, a marker pair no rule can place, and a BEGIN marker of the
operator's left alone once Apothem's block is out. Each of those warnings
carries :data:`MARKER_LEFT`; the second and third leave the uninstall
unfinished. It also finds the files whose markers verify reports
(:func:`stray_begin_files`): a BEGIN marker that starts no whole block, which
install and update keep as they are; two or more whole blocks
(:func:`whole_blocks_at`), which install and update leave as they are; and
marker pairs no rule can place (:func:`unclear_pairs_at`), which install and
update leave as they are while an install record lists the file; with no
record, only when rule 3 fired (a BEGIN marker outside code whose END marker
reads as code, with another pair after it) or a pair holds exactly the block
being written. The text for those (:mod:`install_driver_blocktext`) names each
pair or block, where its marker lines read, each BEGIN marker outside code
that starts no pair (:func:`lone_begins_at`), and a fix for each case with
what follows from it.
"""

from __future__ import annotations

from pathlib import Path

from apothem.lib import install_ledger
from apothem.lib.harness_materializer import (
    APOTHEM_BLOCK_BEGIN,
    APOTHEM_BLOCK_END,
    MarkerLine,
    UncertainPair,
    complete_managed_block,
    extract_managed_block,
    has_stray_begin,
    lone_begins,
    remove_managed_block,
    uncertain_block,
    uncertain_pairs,
    whole_blocks,
)
from apothem.lib.install_ledger import LedgerTarget
from apothem.lib.propagation import resolve_target

from .install_driver_blocktext import two_blocks_report, unclear_block_report
from .install_driver_layout import _load_rules
from .install_driver_pathsafety import _root_for
from .install_driver_shared import path_key
from .install_driver_types import (
    KEPT_REASON,
    MaterializationResult,
    _path_text,
    _result,
)

#: ``detail`` key (``"1"``) of a warning that names a file the uninstall left
#: as it is because of its markers: a BEGIN marker with no END marker after it
#: (:func:`endless_block_warning`, :func:`stray_begin_warnings`), another
#: whole block (:func:`another_block_warning`), or a marker pair no rule can
#: place (:func:`unclear_block_warning`). An install or update keeps a BEGIN
#: marker with no END and writes Apothem's block apart from it, and verify
#: fails until the operator deletes it; a file with two whole blocks or an
#: unclear pair it leaves as it is. So an uninstall whose next step is
#: ``apothem update`` says to fix such a file first.
MARKER_LEFT = "marker_left"

#: ``kept_reason`` of a file that holds another whole block besides Apothem's
#: own (see :func:`another_block_warning`); it leaves the uninstall unfinished.
ANOTHER_BLOCK = "another-block"

#: ``kept_reason`` of a file whose marker pairs no rule can place (see
#: :func:`unclear_block_warning`): a recorded one, or one where rule 3 fired.
#: It leaves the uninstall unfinished, as another block does: one of those
#: pairs may be Apothem's block, so the install record stays until the
#: operator fixes the marker lines, and a second uninstall then finishes.
UNCLEAR_BLOCK = "unclear-block"


def stray_begin_at(path: Path) -> bool:
    """Return True when *path* holds a BEGIN marker that starts no whole block."""
    try:
        text = path.read_bytes().decode("utf-8", errors="replace")
    except OSError:
        return False
    return has_stray_begin(text)


def unclear_block_at(path: Path) -> tuple[int, int | None] | None:
    """Return where *path* holds a marker pair no rule can place, if it does.

    See :func:`apothem.lib.harness_materializer.uncertain_block`: the line of
    the first pair's BEGIN marker, and the line of the fence that opens the
    code block holding that marker or, when rule 3 fired on the pair, its END
    marker (``None`` when no fence does: the line is indented code or goes on
    a paragraph). ``None`` when the file holds a whole block, no such pair, or
    cannot be read.
    """
    try:
        text = path.read_bytes().decode("utf-8", errors="replace")
    except OSError:
        return None
    return uncertain_block(text)


def unclear_pairs_at(path: Path) -> list[UncertainPair]:
    """Return each marker pair no rule can place in *path*, in order.

    See :func:`apothem.lib.harness_materializer.uncertain_pairs`. Empty when
    the file holds a whole block, no such pair, or cannot be read.
    """
    try:
        text = path.read_bytes().decode("utf-8", errors="replace")
    except OSError:
        return []
    return uncertain_pairs(text)


def lone_begins_at(path: Path) -> list[int]:
    """Return the lines of *path*'s BEGIN markers outside code that start no pair.

    See :func:`apothem.lib.harness_materializer.lone_begins`. Empty when the
    file cannot be read.
    """
    try:
        text = path.read_bytes().decode("utf-8", errors="replace")
    except OSError:
        return []
    return lone_begins(text)


def whole_blocks_at(path: Path) -> list[tuple[int, int]]:
    """Return the lines of each whole block's BEGIN and END marker in *path*.

    See :func:`apothem.lib.harness_materializer.whole_blocks`. Empty when the
    file cannot be read.
    """
    try:
        text = path.read_bytes().decode("utf-8", errors="replace")
    except OSError:
        return []
    return whole_blocks(text)


def markers_to_fix_at(path: Path) -> bool:
    """Return True when *path* holds Apothem markers only the operator can fix.

    A BEGIN marker that starts no whole block (:func:`stray_begin_at`), a
    marker pair no rule can place (:func:`unclear_block_at`), or two or more
    whole blocks (:func:`whole_blocks_at`). ``False`` when the file cannot be
    read.
    """
    try:
        text = path.read_bytes().decode("utf-8", errors="replace")
    except OSError:
        return False
    return (
        has_stray_begin(text)
        or uncertain_block(text) is not None
        or len(whole_blocks(text)) > 1
    )


def stray_begin_files(
    harness_name: str,
    *,
    harness_root: Path | None,
    project_root: Path | None,
) -> list[Path]:
    """Return the managed-block files of *harness_name* that hold markers to fix.

    The files looked at are the ones this tool's install keeps a managed block
    in: the manifest's ``sentinel_merge`` targets, resolved against the root as
    ``verify_install`` resolves them, and the ``sentinel_merge`` targets of the
    install records still in effect at that root, newest first (the anchors
    written outside the manifest, such as a profile document or an OpenClaw
    workspace's rules file; an earlier record lists a rules file a later
    install no longer writes, which an install or update keeps naming until
    it can take Apothem's block out). Without a readable record only the
    manifest targets count: nothing then shows which other file the install
    wrote, and a file of the project's own, such as its ``CLAUDE.md``, must not
    fail this tool's verify. Each existing file :func:`markers_to_fix_at`
    flags is returned once, manifest targets first, then the records', in
    their own order.
    """
    rules = _load_rules(harness_name)
    candidates = [
        resolve_target(
            entry.target, harness_root=harness_root, project_root=project_root
        )
        for entry in rules.install
        if entry.mode == "sentinel_merge"
    ]
    root = _root_for(harness_root, project_root)
    try:
        records = install_ledger.active_install_records(harness_name, root=root)
    except (OSError, install_ledger.LedgerError):
        records = []
    candidates.extend(
        Path(target.path)
        for record in reversed(records)
        for target in record.targets
        if target.mode == "sentinel_merge"
    )
    unique: dict[str, Path] = {}
    for path in candidates:
        unique.setdefault(path_key(path), path)
    return [
        path for path in unique.values() if path.is_file() and markers_to_fix_at(path)
    ]


#: What follows an install or update's warning for a file it cannot place
#: Apothem's block in.
_UPDATE_AGAIN = (
    " Then run apothem update again. apothem verify fails for this tool until "
    "you fix the file."
)


def stray_begin_install_warnings(
    results: list[MaterializationResult], *, dry_run: bool = False
) -> list[MaterializationResult]:
    """Name each managed-block file an install or update keeps Apothem markers in.

    The text after a BEGIN marker with no END is kept as it is, and Apothem's
    own block is written apart from it, so the text an old block left below
    the marker repeats Apothem's rules. The marker stays until the operator
    deletes it, with that old text; verify reports the file until then. A file
    the merge left as it is (outcome ``unchanged``, a dry run's preview
    included) whose marker pairs no rule can place (:func:`unclear_pairs_at`)
    gets its own warning, which names each pair and how to fix it, and so
    does a file the merge wrote that holds such pairs and no whole block (a
    code block of the operator's left open above the block, which a line in
    the block closes, or the pair rule 3 fired on, whose END marker a code
    block in Apothem's block hides); that warning does not say the file was
    left as it is. A file with two or more whole blocks
    (:func:`whole_blocks_at`), which the merge leaves as it is, gets a warning
    that names each block. A preview of a write whose pairs are all quoted (a
    first install appends its block after a pair the operator quotes) gets no
    such warning. With *dry_run* (a preview), a warning says Apothem would
    leave the file as it is.
    """
    held: dict[str, bool] = {}
    for result in results:
        if result.operation == "sentinel_merge" and result.outcome != "error":
            unchanged = result.outcome == "unchanged"
            held[result.path] = held.get(result.path, False) or unchanged
    warnings: list[MaterializationResult] = []
    for path, unchanged in held.items():
        message = _install_warning(path, unchanged=unchanged, dry_run=dry_run)
        if message is not None:
            warnings.append(_result("warning", "stray_begin", Path(path), message))
    return warnings


def _install_warning(path: str, *, unchanged: bool, dry_run: bool) -> str | None:
    """Return the install or update warning for the managed-block file *path*.

    See :func:`stray_begin_install_warnings`; ``None`` when it needs none.
    """
    target = Path(path)
    blocks = whole_blocks_at(target)
    if len(blocks) > 1:
        report = two_blocks_report(path, blocks, left=unchanged, dry_run=dry_run)
        return f"{report}{_UPDATE_AGAIN}"
    pairs = unclear_pairs_at(target)
    # A write that leaves no whole block gets the same text, without the claim
    # that the file was left as it is: a code block of the operator's left
    # open above the block, which a line in the block closes, or the pair rule
    # 3 fired on (a code block in Apothem's block hides its END marker). A
    # preview reads the file as it was before the write, so there only the
    # rule 3 pair counts.
    if pairs and (unchanged or not dry_run or any(pair.split for pair in pairs)):
        lone = lone_begins_at(target)
        report = unclear_block_report(
            path, pairs, left=unchanged, lone=lone, dry_run=dry_run
        )
        return f"{report}{_UPDATE_AGAIN}"
    if not stray_begin_at(target):
        return None
    # With no whole block yet (a preview reads the file before the write),
    # nothing is written apart from the marker: putting the END marker back
    # right below the old text then leaves one whole block, a fix that works,
    # but below a line of the operator's it makes that line Apothem's.
    block, back = (
        ("a whole block", "Do not add the END marker back below that text")
        if blocks
        else (
            "a block",
            "Do not add the END marker back with a line of yours between the two "
            "markers: the next run would replace or take out every line between "
            "them. Once an install or update has written Apothem's block apart "
            "from it, do not add the END marker back at all",
        )
    )
    return (
        f"{path} has an Apothem BEGIN marker that starts no whole block of its "
        f"own (its END marker {APOTHEM_BLOCK_END} is gone, or the marker is "
        "yours). Apothem never cuts the text after it: install and update keep "
        f"that text as it is and write {block} of their own apart from it. "
        "Delete that marker line by hand, with the old Apothem text below it "
        "that repeats the rules in Apothem's whole block, and keep your own "
        f"lines; apothem verify fails for this tool until you do. {back}: the "
        "file would then hold two Apothem blocks, which install and update leave "
        "as they are."
    )


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


def markers_left(entry: LedgerTarget) -> bool:
    """Return True when *entry*, a managed-block file, holds markers to fix by hand.

    A BEGIN marker that lost its END marker, or a marker pair no rule can
    place (:func:`unclear_block_at`); :func:`whole_block_left` counts neither
    as Apothem's. After an unfinished uninstall such a file keeps the install
    open, so the next uninstall runs and names the file: it finishes past a
    BEGIN marker that lost its END marker, and stays unfinished while a
    marker pair no rule can place is there (see :data:`UNCLEAR_BLOCK`).
    """
    if entry.mode != "sentinel_merge":
        return False
    path = Path(entry.path)
    return stray_begin_at(path) or unclear_block_at(path) is not None


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


def endless_block_warning(
    target: Path, operation: str, *, dry_run: bool = False
) -> MaterializationResult | None:
    """Return a warning when *target*'s managed block lost its END marker.

    A BEGIN marker with no END after it: the text below it may be the
    operator's, so nothing is removed, and the file no longer counts as
    Apothem's (see :func:`whole_block_left`). A BEGIN marker outside code
    whose END marker reads as code, with another marker pair after it, did
    not lose its END marker: it gets the warning that names each pair (see
    :func:`unclear_block_warning`), install record or not. With *dry_run* (a
    preview), the warning says Apothem would leave the file as it is.
    ``None`` when the file holds a whole block, holds no marker, or cannot be
    read.
    """
    try:
        text = target.read_bytes().decode("utf-8", errors="replace")
    except OSError:
        return None
    if extract_managed_block(text) is None or complete_managed_block(text):
        return None
    if any(pair.split for pair in uncertain_pairs(text)):
        return unclear_block_warning(target, operation, dry_run=dry_run)
    left = "would leave" if dry_run else "left"
    return _result(
        "warning",
        operation,
        target,
        f"{_path_text(target)} has the Apothem BEGIN marker but no END marker "
        f"({APOTHEM_BLOCK_END}) after it, so Apothem cannot tell where its block "
        f"ends and {left} the file as it is. Delete that marker line, and what "
        "is left of the block, by hand, keeping your own text.",
        detail={MARKER_LEFT: "1"},
    )


def another_block_at(path: Path) -> bool:
    """Return True when a whole block stays in *path* once Apothem's own is out.

    Apothem's block is the first whole block, and its exact copies go with it
    (see :func:`apothem.lib.harness_materializer.remove_managed_block`); any
    other whole block may be the operator's. ``False`` when the file cannot be
    read.
    """
    try:
        text = path.read_bytes().decode("utf-8", errors="replace")
    except OSError:
        return False
    return complete_managed_block(remove_managed_block(text)) is not None


def sentinel_refusal(
    target: Path, *, recorded: bool = False
) -> MaterializationResult | None:
    """Return why an uninstall leaves the managed-block file *target* as it is.

    When *recorded* (an install record lists the file), its marker pairs no
    rule can place (:func:`unclear_block_warning`). Its block lost its END
    marker, or a BEGIN marker outside code has its END marker in code with
    another pair after it, record or not (:func:`endless_block_warning`), or
    another whole block stays once Apothem's own and its copies are out
    (:func:`another_block_warning`). ``None`` when the strip may go ahead, or
    when the file holds no block.
    """
    unclear = unclear_block_warning(target, "surgical_uninstall") if recorded else None
    if unclear is not None:
        return unclear
    endless = endless_block_warning(target, "surgical_uninstall")
    if endless is not None:
        return endless
    if another_block_at(target):
        return another_block_warning(target)
    return None


#: The next step :func:`another_block_warning` gives an uninstall.
UNINSTALL_AGAIN = "then run the uninstall again"


def unclear_block_warning(
    target: Path, operation: str, *, outcome: str | None = None, dry_run: bool = False
) -> MaterializationResult | None:
    """Return a warning when *target*, a recorded file, holds an unclear block.

    Marker pairs no rule can place (:func:`unclear_pairs_at`): one may be
    Apothem's block, or text the operator quotes, so nothing is changed, and
    an uninstall stays unfinished until the operator fixes the marker lines
    (see :data:`UNCLEAR_BLOCK`). Each pair is named (see
    :func:`unclear_block_report`). *outcome* is what the next
    run does once the operator makes a pair read outside code, such as
    :data:`TAKES_OUT`; without it, as for an uninstall, the warning says to
    delete Apothem's block by hand. With *dry_run* (a preview), it says
    Apothem would leave the file as it is. ``None`` when the file holds a
    whole block or no such pair. The caller checks that an install record
    lists the file: a file Apothem never wrote may quote a pair, and that is
    not Apothem's to report (rule 3 aside, see :func:`endless_block_warning`).
    """
    pairs = unclear_pairs_at(target)
    if not pairs:
        return None
    return _result(
        "warning",
        operation,
        target,
        unclear_block_report(
            _path_text(target),
            pairs,
            outcome=outcome,
            lone=lone_begins_at(target),
            dry_run=dry_run,
        ),
        detail={KEPT_REASON: UNCLEAR_BLOCK, MARKER_LEFT: "1"},
    )


def another_block_warning(
    target: Path,
    *,
    operation: str = "surgical_uninstall",
    then: str = UNINSTALL_AGAIN,
    dry_run: bool = False,
) -> MaterializationResult:
    """Name a file that holds another whole block besides Apothem's own.

    It is not a copy of Apothem's block, so it may be the operator's (a marker
    pair they quote), an older Apothem block, or one pasted in a second time:
    nothing changes, and the uninstall stays unfinished. The text is the one
    install and update give (see :func:`two_blocks_report`): it names each
    whole block by its lines, and the operator changes the marker lines of
    each pair of theirs (never deleting Apothem's block to keep one: the
    strip would then take that pair out) and deletes each other Apothem
    block whole; then the strip takes out the one block left. A second block
    that shows only once Apothem's is out is named by its marker lines (see
    :func:`another_block_report`). *then* is the step after the fix (an
    install or update that retires the file gives its own). With *dry_run* (a
    preview), it says Apothem would leave the file as it is.
    """
    return _result(
        "warning",
        operation,
        target,
        another_block_report(target, then=then, dry_run=dry_run),
        detail={KEPT_REASON: ANOTHER_BLOCK, MARKER_LEFT: "1"},
    )


def another_block_report(
    target: Path, *, then: str | None, dry_run: bool = False
) -> str:
    """Return the text that names the blocks of *target*, which holds another one.

    Each whole block by its lines, or, when a second block shows only once
    Apothem's is out (see :func:`_revealed_block`), Apothem's block and the
    marker lines around it, with how to fix the file (see
    :func:`two_blocks_report`). :func:`another_block_warning` gives it, and
    so does the warning, with no ``detail``, that an uninstall with no
    install record gives for a bolt-on anchor (see
    :func:`install_driver_retention.unlisted_block_warnings`).
    """
    found = whole_blocks_at(target)
    revealed = _revealed_block(target, found[0]) if len(found) == 1 else None
    return two_blocks_report(
        _path_text(target),
        found,
        dry_run=dry_run,
        then=then,
        revealed=None if revealed is None else revealed[0],
        quoted=None if revealed is None else revealed[1],
    )


def _revealed_block(
    path: Path, block: tuple[int, int]
) -> tuple[tuple[int, int], MarkerLine | None] | None:
    """Return the whole block *path* shows once *block* is out, and its END line.

    The lines of *block* are blanked, not cut, so every other line keeps its
    number. The END marker line is given when it reads as code or as text
    (one the operator quotes in a code block, say): with no pair after them,
    such a pair still reads as a whole block, and a pair added after the text
    shows it, since rule 3 then fires on that pair (see
    :func:`apothem.lib.harness_materializer.uncertain_pairs`). Only the BEGIN
    marker of such a block needs to go. ``None`` when no whole block shows
    then, or the file cannot be read.
    """
    try:
        lines = path.read_bytes().decode("utf-8", errors="replace").split("\n")
    except OSError:
        return None
    begin, end = block
    lines[begin - 1 : end] = [""] * (end - begin + 1)
    text = "\n".join(lines)
    found = whole_blocks(text)
    if not found:
        return None
    probe = f"{text}\n\n{APOTHEM_BLOCK_BEGIN}\n{APOTHEM_BLOCK_END}\n"
    quoted = next(
        (
            pair.end
            for pair in uncertain_pairs(probe)
            if pair.split and pair.begin.line == found[0][0]
        ),
        None,
    )
    return found[0], quoted


#: Why the operator deletes a BEGIN marker an uninstall leaves alone.
_STILL_READ = "the tool still reads that text, and an install keeps it as it is"

#: The same for a rules file an update took Apothem's block out of because
#: the install no longer writes it: no install writes there, and verify names
#: the file while an install record lists it.
RETIRED_WHY = "apothem verify fails for this tool until you do"


def stray_begin_warnings(
    results: list[MaterializationResult], *, why: str = _STILL_READ
) -> list[MaterializationResult]:
    """Name each file the uninstall rewrote that still holds a BEGIN marker alone.

    Taking Apothem's whole block out can leave such a line above where it was
    (a stray line of the operator's, or what is left of an older block that
    lost its END marker, with that block's text below it). An install keeps
    it as it is, so the operator deletes it by hand, with any old Apothem
    text below it. *why* is the reason the text gives (:data:`RETIRED_WHY`
    for a rules file an update took Apothem's block out of).
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
            "Apothem's block is out. Delete that line by hand, with any old "
            f"Apothem text below it, and keep your own lines: {why}.",
            detail={MARKER_LEFT: "1"},
        )
        for path, operation in rewritten.items()
        if stray_begin_at(Path(path))
    ]
