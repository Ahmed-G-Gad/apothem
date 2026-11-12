# SPDX-License-Identifier: MIT

"""What a managed-block file shows, and the warnings for the markers left in one.

A managed-block file (``sentinel_merge``) holds the operator's text beside
Apothem's block, which runs from a BEGIN marker to the next END marker. This
module reads such a file as install evidence (a whole block counts; a BEGIN
marker without its END counts only while the install may be open) and builds
the warnings an uninstall gives when it leaves a file because of its markers:
a block that lost its END marker, another whole block that is not a copy of
Apothem's own, and a BEGIN marker of the operator's left alone once Apothem's
block is out. Each of those warnings carries :data:`MARKER_LEFT`. It also
finds the BEGIN markers that start no whole block, which install and update
keep as they are and verify reports (:func:`stray_begin_files`), and the
files whose marker pairs no rule can place (:func:`unclear_pairs_at`), which
install and update leave as they are once an install recorded the file. The
text for those names each pair, where its marker lines read, and a fix for
each case with what follows from it (:func:`unclear_block_report`).
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from apothem.harnesses._shared import install_driver
from apothem.lib import install_ledger
from apothem.lib.harness_materializer import (
    APOTHEM_BLOCK_END,
    MarkerLine,
    MarkerPlace,
    UncertainPair,
    complete_managed_block,
    extract_managed_block,
    has_stray_begin,
    remove_managed_block,
    uncertain_block,
    uncertain_pairs,
)
from apothem.lib.install_ledger import LedgerTarget
from apothem.lib.propagation import resolve_target

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
#: fails until the operator deletes it; in a file with two whole blocks, it
#: writes over the first; a file with an unclear pair it leaves as it is. So an
#: uninstall whose next step is ``apothem update`` says to fix such a file first.
MARKER_LEFT = "marker_left"

#: ``kept_reason`` of a file that holds another whole block besides Apothem's
#: own (see :func:`another_block_warning`); it leaves the uninstall unfinished.
ANOTHER_BLOCK = "another-block"

#: ``kept_reason`` of a file whose marker pairs no rule can place (see
#: :func:`unclear_block_warning`): a recorded one, or one where rule 3 fired.
#: The uninstall finishes: the file no longer counts as Apothem's, as with a
#: BEGIN marker that lost its END.
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
    the BEGIN marker, and of the code block's fence (``None`` for indented
    code). ``None`` when the file holds a whole block, no such pair, or cannot
    be read.
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


#: What the next update does with a marker pair once both of its lines read
#: outside code (see :func:`unclear_block_report`); ``{lines}`` names them.
REPLACES = "the next update then replaces {lines}"

#: The same for a rules file an install or update takes Apothem's block out of.
TAKES_OUT = "the next install, update or uninstall then takes {lines} out"


def _reads(marker: MarkerLine) -> str:
    """Return what the line of *marker* reads as, after the marker's name."""
    if marker.place is MarkerPlace.FENCE:
        return f"sits inside a code block that opens at line {marker.fence}"
    if marker.place is MarkerPlace.INDENTED:
        return "sits in indented code"
    if marker.place is MarkerPlace.PARAGRAPH:
        return "reads as part of the paragraph above it"
    return "is outside code"


#: What both marker lines of a pair read as, when they read alike.
_BOTH = {
    MarkerPlace.INDENTED: "sit in indented code",
    MarkerPlace.PARAGRAPH: "read as part of the paragraph above them",
    MarkerPlace.OUTSIDE: "are outside code: that pair may be Apothem's block",
}


def _outside(pair: UncertainPair) -> bool:
    """Return True when both marker lines of *pair* read outside code."""
    return pair.begin.place is pair.end.place is MarkerPlace.OUTSIDE


def _pair_text(pair: UncertainPair, later: UncertainPair | None) -> str:
    """Return where the marker lines of *pair* read; *later* is the next pair."""
    begin, end = pair.begin, pair.end
    subject = f"The BEGIN marker at line {begin.line}"
    if pair.split:
        follows = (
            f"the marker pair from line {later.begin.line} to line {later.end.line} "
            "comes after them: that pair may be Apothem's block"
            if later is not None and _outside(later)
            else "another marker pair comes after them"
        )
        return (
            f"{subject} is outside code, but its END marker at line {end.line} "
            f"{_reads(end)}, and {follows}."
        )
    if begin.place is end.place and begin.fence == end.fence:
        both = (
            f"sit inside a code block that opens at line {begin.fence}"
            if begin.place is MarkerPlace.FENCE
            else _BOTH[begin.place]
        )
        return f"{subject} and the END marker at line {end.line} {both}."
    return (
        f"{subject} {_reads(begin)}, and the END marker at line {end.line} "
        f"{_reads(end)}."
    )


def _split_fix(pair: UncertainPair, later: UncertainPair | None, outcome: str) -> str:
    """Return how to fix the pair rule 3 fired on, each choice with its result.

    Its BEGIN marker may be a line of the operator's; or the pair is
    Apothem's block, and the code that hides its END marker then came from
    the profile (Apothem writes its END marker at the margin).
    """
    begin, end = pair.begin, pair.end
    yours = f"If the BEGIN marker at line {begin.line} is yours, delete or change it"
    if later is not None and _outside(later):
        span = f"lines {later.begin.line} to {later.end.line}"
        yours += f": {outcome.format(lines=span)}"
    done = outcome.format(lines="those lines")
    if end.place is MarkerPlace.FENCE:
        ours = (
            f"the code block that opens at line {end.fence} comes from a rule in "
            f"your profile: close it above line {end.line} and fix that rule; {done}"
        )
    else:
        ours = f"start line {end.line} at the left margin: {done}"
    return f"{yours}. If lines {begin.line} to {end.line} are Apothem's block, {ours}."


def _pair_fix(pair: UncertainPair, later: UncertainPair | None, outcome: str) -> str:
    """Return how to fix *pair* by hand, each choice with what follows from it.

    *outcome* (:data:`REPLACES` or :data:`TAKES_OUT`) is what the next run
    does once both marker lines of a pair read outside code. A pair whose
    lines both read outside code already needs no fix of its own: a pair
    before it is what holds it back.
    """
    if pair.split:
        return _split_fix(pair, later, outcome)
    if _outside(pair):
        return ""
    begin, end = pair.begin, pair.end
    done = outcome.format(lines="those lines")
    if begin.place is end.place and begin.fence == end.fence:
        step = (
            f"close that code block above line {begin.line}"
            if begin.place is MarkerPlace.FENCE
            else f"start lines {begin.line} and {end.line} at the left margin"
        )
        ours = f"{step}: {done}"
    else:
        ours = "delete them by hand, keeping your own text"
    return (
        f"If lines {begin.line} to {end.line} are Apothem's block, {ours}. If they "
        "are text of yours, change or delete those two marker lines."
    )


def _delete_by_hand(pairs: Sequence[UncertainPair]) -> str:
    """Return the advice an uninstall gives: delete Apothem's block by hand."""
    spans = [f"lines {pair.begin.line} to {pair.end.line}" for pair in pairs]
    if len(spans) == 1:
        return (
            f"If {spans[0]} are Apothem's block, delete them by hand, keeping "
            "your own text."
        )
    listed = f"{', '.join(spans[:-1])}, or {spans[-1]}"
    return (
        f"If one of these pairs is Apothem's block ({listed}), delete it by hand, "
        "keeping your own text."
    )


def unclear_block_report(
    path: str | Path,
    pairs: Sequence[UncertainPair],
    *,
    outcome: str | None = REPLACES,
    left: bool = True,
) -> str:
    """Return what is wrong with *path*, whose marker pairs are *pairs*, and the fix.

    Each pair is named with the lines of its two marker lines and what they
    read as (see :func:`unclear_pairs_at`), then how to fix it by hand: if
    those lines are Apothem's block, what makes both read outside code, and
    *outcome* says what the next run then does; if they are text of the
    operator's, change or delete the marker lines. A pair after the one rule 3
    fired on, both of whose lines read outside code, is named with that pair.
    Without *outcome* (an uninstall), the fix is to delete Apothem's block by
    hand. With *left*, the text says Apothem left the file as it is.
    """
    head = (
        f"{path}: Apothem cannot tell whether the marker lines in this file mark "
        "its block or text of yours"
    )
    parts = [f"{head}, so it left the file as it is." if left else f"{head}."]
    for index, pair in enumerate(pairs):
        if index and pairs[index - 1].split and _outside(pair):
            continue
        later = pairs[index + 1] if index + 1 < len(pairs) else None
        parts.append(_pair_text(pair, later))
        if outcome is not None:
            parts.append(_pair_fix(pair, later, outcome))
    if outcome is None:
        parts.append(_delete_by_hand(pairs))
    return " ".join(part for part in parts if part)


def stray_begin_files(
    harness_name: str,
    *,
    harness_root: Path | None,
    project_root: Path | None,
) -> list[Path]:
    """Return the managed-block files of *harness_name* that hold a stray BEGIN.

    The files looked at are the ones this tool's install keeps a managed block
    in: the manifest's ``sentinel_merge`` targets, resolved against the root as
    ``verify_install`` resolves them, and the ``sentinel_merge`` targets of the
    current install record at that root (the anchors written outside the
    manifest, such as a profile document or an OpenClaw workspace's rules file).
    Without a readable record only the manifest targets count: nothing then
    shows which other file the install wrote, and a file of the project's own,
    such as its ``CLAUDE.md``, must not fail this tool's verify. Each existing
    file :func:`stray_begin_at` or :func:`unclear_block_at` flags is returned
    once, manifest targets first, then the record's, in their own order.
    """
    rules = install_driver.load_rules(harness_name)
    candidates = [
        resolve_target(
            entry.target, harness_root=harness_root, project_root=project_root
        )
        for entry in rules.install
        if entry.mode == "sentinel_merge"
    ]
    root = _root_for(harness_root, project_root)
    try:
        record = install_ledger.current_install_record(harness_name, root=root)
    except (OSError, install_ledger.LedgerError):
        record = None
    if record is not None:
        candidates.extend(
            Path(target.path)
            for target in record.targets
            if target.mode == "sentinel_merge"
        )
    unique: dict[str, Path] = {}
    for path in candidates:
        unique.setdefault(path_key(path), path)
    return [
        path
        for path in unique.values()
        if path.is_file() and (stray_begin_at(path) or unclear_block_at(path))
    ]


def stray_begin_install_warnings(
    results: list[MaterializationResult],
) -> list[MaterializationResult]:
    """Name each managed-block file an install or update keeps a stray BEGIN in.

    The text after a BEGIN marker with no END is kept as it is, and Apothem's
    own block is written apart from it, so the text an old block left below
    the marker repeats Apothem's rules. The marker stays until the operator
    deletes it, with that old text; verify reports the file until then. A file
    the merge left as it is (outcome ``unchanged``, a dry run's preview
    included) whose marker pairs no rule can place (:func:`unclear_pairs_at`)
    gets its own warning, which names each pair and how to fix it. A merge
    that writes the file (a first install appends its block after a pair the
    operator quotes) gets no such warning.
    """
    held: dict[str, bool] = {}
    for result in results:
        if result.operation == "sentinel_merge" and result.outcome != "error":
            unchanged = result.outcome == "unchanged"
            held[result.path] = held.get(result.path, False) or unchanged
    warnings: list[MaterializationResult] = []
    for path, unchanged in held.items():
        pairs = unclear_pairs_at(Path(path)) if unchanged else []
        if pairs:
            message = (
                f"{unclear_block_report(path, pairs)} Then run apothem update "
                "again. apothem verify fails for this tool until you fix the file."
            )
        elif stray_begin_at(Path(path)):
            message = (
                f"{path} has an Apothem BEGIN marker that starts no whole block of "
                f"its own (its END marker {APOTHEM_BLOCK_END} is gone, or the "
                "marker is yours). Apothem never cuts the text after it: install "
                "and update keep that text as it is and write a whole block of "
                "their own apart from it. Delete that marker line by hand, with "
                "the old Apothem text below it that repeats the rules in Apothem's "
                "whole block, and keep your own lines; apothem verify fails for "
                "this tool until you do."
            )
        else:
            continue
        warnings.append(_result("warning", "stray_begin", Path(path), message))
    return warnings


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
    return entry.mode == "sentinel_merge" and stray_begin_at(Path(entry.path))


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
    Apothem's (see :func:`whole_block_left`). A BEGIN marker outside code
    whose END marker reads as code, with another marker pair after it, did
    not lose its END marker: it gets the warning that names each pair (see
    :func:`unclear_block_warning`), install record or not. ``None`` when the
    file holds a whole block, holds no marker, or cannot be read.
    """
    try:
        text = target.read_bytes().decode("utf-8", errors="replace")
    except OSError:
        return None
    if extract_managed_block(text) is None or complete_managed_block(text):
        return None
    if any(pair.split for pair in uncertain_pairs(text)):
        return unclear_block_warning(target, operation)
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
    try:
        text = target.read_bytes().decode("utf-8", errors="replace")
    except OSError:
        return None
    if complete_managed_block(remove_managed_block(text)):
        return another_block_warning(target)
    return None


#: The next step :func:`another_block_warning` gives an uninstall.
UNINSTALL_AGAIN = "then run the uninstall again"


def unclear_block_warning(
    target: Path, operation: str, *, outcome: str | None = None
) -> MaterializationResult | None:
    """Return a warning when *target*, a recorded file, holds an unclear block.

    Marker pairs no rule can place (:func:`unclear_pairs_at`): one may be
    Apothem's block, or text the operator quotes, so nothing is changed, and
    the file no longer counts as Apothem's (an uninstall finishes). Each pair
    is named (see :func:`unclear_block_report`). *outcome* is what the next
    run does once the operator makes a pair read outside code, such as
    :data:`TAKES_OUT`; without it, as for an uninstall, the warning says to
    delete Apothem's block by hand. ``None`` when the file holds a whole block
    or no such pair. The caller checks that an install record lists the file:
    a file Apothem never wrote may quote a pair, and that is not Apothem's to
    report (rule 3 aside, see :func:`endless_block_warning`).
    """
    pairs = unclear_pairs_at(target)
    if not pairs:
        return None
    return _result(
        "warning",
        operation,
        target,
        unclear_block_report(_path_text(target), pairs, outcome=outcome),
        detail={KEPT_REASON: UNCLEAR_BLOCK, MARKER_LEFT: "1"},
    )


def another_block_warning(
    target: Path,
    *,
    operation: str = "surgical_uninstall",
    then: str = UNINSTALL_AGAIN,
) -> MaterializationResult:
    """Name a file that holds another whole block besides Apothem's own.

    It is not a copy of Apothem's block, so it may be the operator's (a marker
    pair they quote): nothing changes, and the uninstall stays unfinished.
    Apothem writes one block per file, so the fix is the marker lines the
    operator added, never Apothem's block: with those gone, the strip takes
    out the one block left, whichever came first. *then* is the step after the
    fix (an install or update that retires the file gives its own).
    """
    return _result(
        "warning",
        operation,
        target,
        f"{_path_text(target)} holds two different blocks between Apothem's "
        "markers, so Apothem cannot tell which one is its own and left the file "
        "as it is. Delete or reword the marker lines you added there (a marker "
        "pair you quoted, or a block you pasted in a second time), or move them "
        f"inside a code block, keeping your own text; {then}.",
        detail={KEPT_REASON: ANOTHER_BLOCK, MARKER_LEFT: "1"},
    )


def stray_begin_warnings(
    results: list[MaterializationResult],
) -> list[MaterializationResult]:
    """Name each file the uninstall rewrote that still holds a BEGIN marker alone.

    Taking Apothem's whole block out can leave such a line above where it was
    (a stray line of the operator's, say). An install keeps it as it is and
    verify reports the file, so the operator deletes it by hand.
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
            "Apothem's block is out. Delete that line by hand: an install keeps "
            "it as it is, and apothem verify fails until you do.",
            detail={MARKER_LEFT: "1"},
        )
        for path, operation in rewritten.items()
        if stray_begin_at(Path(path))
    ]
