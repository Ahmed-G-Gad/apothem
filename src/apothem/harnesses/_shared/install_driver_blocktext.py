# SPDX-License-Identifier: MIT

"""The text of the warnings for Apothem marker lines Apothem cannot place.

Two kinds of file get such a warning, from install, update, verify, doctor and
uninstall alike (see :mod:`install_driver_blocks`): one whose marker pairs no
rule can place (:func:`unclear_block_report`), which names each pair, where
its marker lines read and a fix for each case with what follows from it; and
one that holds two or more whole blocks (:func:`two_blocks_report`), which
names each block by its lines (a block that shows only once Apothem's is out,
by its two marker lines). Everything here builds text and reads nothing.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from apothem.lib.harness_materializer import MarkerLine, MarkerPlace, UncertainPair

#: What the next update does with a marker pair once both of its lines read
#: outside code (see :func:`unclear_block_report`); ``{lines}`` names them.
REPLACES = "the next update then replaces {lines}"

#: The same for a rules file an install or update takes Apothem's block out of.
TAKES_OUT = "the next install, update or uninstall then takes {lines} out"


def _left(left: bool, dry_run: bool) -> str:
    """Return how a warning's first sentence ends: what Apothem did with the file."""
    if not left:
        return "."
    if dry_run:
        return ", so it would leave the file as it is."
    return ", so it left the file as it is."


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


def _close_above(pair: UncertainPair, block: str, line: int) -> str:
    """Return the step that closes *block*, the code block holding *pair*, above *line*.

    When the line that closes that code block further down would then open
    a code block of its own that nothing closes (see
    :attr:`UncertainPair.closer`), the step moves that line up instead of
    adding a closing line: added, the old closing line would turn the rest of
    the file into code in a Markdown viewer.
    """
    if pair.closer is None:
        return f"close {block} above line {line}"
    return (
        f"move line {pair.closer}, which closes {block} further down, up above "
        f"line {line}"
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
        close = _close_above(pair, "it", end.line)
        ours = (
            f"the code block that opens at line {end.fence} comes from a rule in "
            f"your profile: {close} and fix that rule; {done}"
        )
    else:
        ours = f"start line {end.line} at the left margin: {done}"
    return f"{yours}. If lines {begin.line} to {end.line} are Apothem's block, {ours}."


def _old_text(
    fence: int | None, lone: Sequence[int], pairs: Sequence[UncertainPair]
) -> int | None:
    """Return the lone BEGIN marker whose old text may hold the line *fence*.

    The nearest BEGIN marker on lines *lone* (see :func:`_lone_text`) above
    *fence*, with no marker line of *pairs* between them: deleting the old
    Apothem text below it, as that step says, may take the fence's line out,
    which ends the code block.
    """
    if fence is None:
        return None
    above = [line for line in lone if line < fence]
    if not above:
        return None
    start = max(above)
    marked = (line for pair in pairs for line in (pair.begin.line, pair.end.line))
    return None if any(start < line < fence for line in marked) else start


def _pair_fix(
    pair: UncertainPair,
    later: UncertainPair | None,
    outcome: str,
    split: UncertainPair | None = None,
    old: int | None = None,
) -> str:
    """Return how to fix *pair* by hand, each choice with what follows from it.

    *outcome* (:data:`REPLACES` or :data:`TAKES_OUT`) is what the next run
    does once both marker lines of a pair read outside code. A pair whose
    lines both read outside code already needs no fix of its own: a pair
    before it is what holds it back. A pair whose BEGIN marker sits in a code
    block and whose END marker is outside code, if it is Apothem's block, sits
    below a code block of the operator's that a line in the block closes:
    closing that code block above the BEGIN marker fixes it, where deleting
    the block by hand would only bring it back with the next update. *split*
    is the pair rule 3 fired on, before *pair*: if *pair* is Apothem's block,
    that pair's BEGIN marker is the operator's, and it must go too, or it
    pairs with the END marker in code once *pair* is fixed. *old* is a lone
    BEGIN marker whose old text may hold the line that opens the code block
    (see :func:`_old_text`): deleting that line with that text ends the code
    block too, and a line added above the BEGIN marker after that would open
    a new one. When the line that closes that code block below the END marker
    must move (see :func:`_close_above`), the step moves it, and deleting the
    opening line with the old text deletes that closing line too.
    """
    if pair.split:
        return _split_fix(pair, later, outcome)
    if _outside(pair):
        return ""
    begin, end = pair.begin, pair.end
    also = (
        ""
        if split is None
        else f", and delete or change the BEGIN marker at line {split.begin.line}"
    )
    unless = (
        ""
        if old is None
        else f", or, if line {begin.fence} is part of the old Apothem text below "
        f"the BEGIN marker at line {old}, delete it with that text"
        + ("" if pair.closer is None else f", and delete line {pair.closer}")
    )
    if begin.place is end.place and begin.fence == end.fence:
        step = (
            f"{_close_above(pair, 'that code block', begin.line)}{unless}"
            if begin.place is MarkerPlace.FENCE
            else f"start lines {begin.line} and {end.line} at the left margin"
        )
        ours = f"{step}{also}: {outcome.format(lines='those lines')}"
    elif begin.place is MarkerPlace.FENCE and end.place is MarkerPlace.OUTSIDE:
        ours = (
            f"close the code block that opens at line {begin.fence} above line "
            f"{begin.line}{unless}{also}: {outcome.format(lines='those lines')}"
        )
    else:
        ours = f"delete them by hand, keeping your own text{also}"
    return (
        f"If lines {begin.line} to {end.line} are Apothem's block, {ours}. If they "
        "are text of yours, change or delete those two marker lines."
    )


def _pairs_later(outcome: str | None) -> str:
    """Return what a run can do with a BEGIN marker left that starts no pair.

    It pairs with an END marker below it once the pairs between are fixed:
    an install or update then replaces the lines between them, and in a
    rules file Apothem takes its block out of (*outcome* :data:`TAKES_OUT`),
    or after an uninstall (no *outcome*), the run takes them out.
    """
    if outcome == TAKES_OUT:
        return (
            "a later install, update or uninstall can pair it with an END marker "
            "below it and take the lines between them out"
        )
    if outcome is None:
        return (
            "the uninstall run again can pair it with an END marker below it and "
            "take the lines between them out, as a later install or update "
            "replaces them"
        )
    return (
        "a later install or update can pair it with an END marker below it and "
        "replace the lines between them"
    )


def _lone_text(lone: Sequence[int], outcome: str | None = REPLACES) -> str:
    """Return what to do with the BEGIN markers on lines *lone*, which start no pair.

    Left in place, such a marker can pair with an END marker below it once
    the pairs between are fixed (see :func:`_pairs_later`).
    """
    if not lone:
        return ""
    later = _pairs_later(outcome)
    if len(lone) == 1:
        return (
            f"The BEGIN marker at line {lone[0]} starts no marker pair: its END "
            "marker is gone, or the marker is yours. Delete or change it by hand, "
            "with any old Apothem text below it, and keep your own text. If you "
            f"leave it, {later}."
        )
    listed = ", ".join(str(line) for line in lone[:-1])
    return (
        f"The BEGIN markers at lines {listed} and {lone[-1]} start no marker pair: "
        "their END markers are gone, or the markers are yours. Delete or change "
        "them by hand, with any old Apothem text below them, and keep your own "
        f"text. If you leave one, {later}."
    )


def _begin_first(pair: UncertainPair) -> str:
    """Return the step an uninstall gives for the pair rule 3 fired on.

    Once no pair comes after it, its BEGIN marker and the END marker in code
    read as a whole block, which the uninstall run again takes out, as a
    later install or update replaces it: so a BEGIN marker of the operator's
    goes before that run.
    """
    begin, end = pair.begin.line, pair.end.line
    return (
        f"If the BEGIN marker at line {begin} is yours, delete or change it "
        "before you run the uninstall again: left in place once no marker pair "
        f"comes after it, it pairs with the END marker at line {end}, and the "
        f"uninstall then takes lines {begin} to {end} out, as a later install "
        "or update replaces them."
    )


def _delete_by_hand(pairs: Sequence[UncertainPair]) -> str:
    """Return the advice an uninstall gives: delete Apothem's block by hand.

    Each other pair is the operator's, and its marker lines go too: while a
    marker pair stays in a file an install record lists, the uninstall leaves
    that file and stays unfinished. Of the pair rule 3 fired on, only the
    BEGIN marker goes: its END marker reads as code, in the operator's own
    code block, and needs no change once that BEGIN marker is gone (a BEGIN
    marker above it that starts no pair goes too, see :func:`_lone_text`).
    """
    spans = [f"lines {pair.begin.line} to {pair.end.line}" for pair in pairs]
    if len(spans) == 1:
        fix = (
            f"If {spans[0]} are Apothem's block, delete them by hand, keeping your "
            "own text; if they are text of yours, change or delete those two "
            "marker lines."
        )
    else:
        listed = f"{', '.join(spans[:-1])}, or {spans[-1]}"
        split = next((pair for pair in pairs if pair.split), None)
        alone = (
            ""
            if split is None
            else f" (for the pair from line {split.begin.line} to line "
            f"{split.end.line}, its BEGIN marker alone)"
        )
        fix = (
            f"If one of these pairs is Apothem's block ({listed}), delete it by "
            "hand, keeping your own text, and change or delete the two marker "
            f"lines of each pair of yours{alone}."
        )
    return f"{fix} Then run the uninstall again."


def _held_until(pairs: Sequence[UncertainPair], held: bool) -> str:
    """Return how long install and update leave a file with *pairs* as it is.

    Until its marker lines are fixed, whoever wrote them, but only where the
    merge holds the file back: the pair rule 3 fired on does with or without
    an install record, and while *held* (an install record lists the file,
    as an install or update reads it, or will once the run that gives the
    text is recorded) every pair does. A pair in code may then be Apothem's
    block, so a marker example of the operator's in code holds the file back
    too, and nothing else ends that. Each such run ends as partial. Empty
    when nothing holds the file back: the next update then adds its block
    after the pairs, so the text must not say it leaves the file as it is.
    """
    if not held and not any(pair.split for pair in pairs):
        return ""
    text = (
        "Until you fix these marker lines as this text says, install and update "
        "leave this file as it is and end as partial (exit code 2)."
    )
    if held and any(not pair.split and not _outside(pair) for pair in pairs):
        text += (
            " A marker example of yours in code holds the file back the same "
            "way, until you change its two marker lines."
        )
    return text


def unclear_block_report(
    path: str | Path,
    pairs: Sequence[UncertainPair],
    *,
    outcome: str | None = REPLACES,
    left: bool = True,
    lone: Sequence[int] = (),
    dry_run: bool = False,
    held: bool = False,
) -> str:
    """Return what is wrong with *path*, whose marker pairs are *pairs*, and the fix.

    Each pair is named with the lines of its two marker lines and what they
    read as (see :func:`install_driver_blocks.unclear_pairs_at`), then how to
    fix it by hand: if those lines are Apothem's block, what makes both read
    outside code, and *outcome* says what the next run then does; if they are
    text of the operator's, change or delete the marker lines. A pair after
    the one rule 3 fired on, both of whose lines read outside code, is named
    with that pair; any other pair after it is Apothem's block only if that
    pair's BEGIN marker is the operator's, so its fix says to delete or change
    that marker too. Without *outcome* (an uninstall, which stays unfinished
    while such a file holds a pair), the fix is to delete Apothem's block by
    hand and to change or delete the marker lines of each pair of the
    operator's (of the pair rule 3 fired on, the BEGIN marker alone), then to
    run the uninstall again. A step before it says to delete or change that
    BEGIN marker first: left in place once no pair follows it, it pairs with
    the END marker in code, and the uninstall run again takes the lines
    between them out. With *left*, the text says Apothem left the file as it
    is, or, with *dry_run*, that it would. *lone* names the BEGIN markers
    outside code that start no pair (see
    :func:`install_driver_blocks.lone_begins_at`): each must go too, or it can
    pair with an END marker once the pairs are fixed. With :data:`REPLACES`,
    the text ends by saying that install and update leave the file as it is,
    and end as partial, until its marker lines are fixed, where the merge
    holds the file back: while *held*, or for the pair rule 3 fired on (see
    :func:`_held_until`).
    """
    head = (
        f"{path}: Apothem cannot tell whether the marker lines in this file mark "
        "its block or text of yours"
    )
    parts = [f"{head}{_left(left, dry_run)}", _lone_text(lone, outcome)]
    split = next((pair for pair in pairs if pair.split), None)
    for index, pair in enumerate(pairs):
        if index and pairs[index - 1].split and _outside(pair):
            continue
        later = pairs[index + 1] if index + 1 < len(pairs) else None
        parts.append(_pair_text(pair, later))
        if outcome is not None:
            after = (
                split
                if split is not None and split.begin.line < pair.begin.line
                else None
            )
            old = _old_text(pair.begin.fence, lone, pairs)
            parts.append(_pair_fix(pair, later, outcome, after, old))
    if outcome is None:
        if split is not None:
            parts.append(_begin_first(split))
        parts.append(_delete_by_hand(pairs))
    elif outcome == REPLACES:
        parts.append(_held_until(pairs, held))
    return " ".join(part for part in parts if part)


#: How to fix a file with two or more blocks (see :func:`two_blocks_report`).
#: A marker pair of the operator's comes first: it keeps its text and loses
#: its marker lines. Moving the pair into a code block is not offered: once
#: Apothem's own block in the file is not whole (its END marker lost, say),
#: a pair in code holds the file as it is while an install record lists it
#: (see :func:`_held_until`). Deleting Apothem's block instead would leave
#: that pair the one block in the file, which the next update replaces and
#: the next uninstall takes out. An Apothem block that is not the one kept
#: (an older one, or one pasted in a second time) goes whole, since deleting
#: only its marker lines would leave its text behind where no later run
#: finds it; a line of the operator's inside it (an END marker put back
#: below that line makes it part of the block) stays. In a file that starts
#: with Apothem's frontmatter the block kept is the one right below it: only
#: there does the frontmatter count as Apothem's, so an uninstall takes it
#: out with that block.
_FIX_BLOCKS = (
    "For a marker pair of yours (an example you quote, say), change or delete "
    "its two marker lines, keeping your own text; do not delete Apothem's "
    "block instead, since the next run would then read your pair as Apothem's "
    "block and replace or take out the lines between its markers. Of Apothem's "
    "own blocks (an older one, or one pasted in a second time), keep one (in a "
    "file that starts with Apothem's frontmatter, the one right below it) and "
    "delete each other one from its BEGIN marker line to its END marker line, "
    "keeping any line of your own inside it"
)


def _revealed_fix(
    block: tuple[int, int], revealed: tuple[int, int], quoted: MarkerLine | None
) -> str:
    """Return how to fix a file whose second block shows once *block* is out.

    *revealed* is that block: a BEGIN marker above Apothem's block and an END
    marker below it, say. Its marker lines go, never the lines between them,
    which hold Apothem's block and the operator's text; deleting Apothem's
    block instead would leave them the one block in the file. One code block
    around both lines would hold Apothem's block too, so the text offers no
    code block. *quoted* is the END marker line when it reads as code or as
    text (the operator quotes it in a code block, say): it stays, and the
    BEGIN marker alone goes.
    """
    (begin, end), (outer, outer_end) = block, revealed
    keep = (
        f"Delete or change the marker lines at lines {outer} and {outer_end} "
        f"instead, keeping your own text (if line {outer} is what is left of an "
        "older Apothem block, delete the old Apothem text below it too)"
        if quoted is None
        else f"Delete or change the BEGIN marker at line {outer} instead, keeping "
        "your own text (if it is what is left of an older Apothem block, delete "
        f"the old Apothem text below it too); the END marker at line {outer_end} "
        f"{_reads(quoted)}, so it can stay as it is"
    )
    return (
        f"Do not delete the block from line {begin} to line {end}: the next run "
        f"would then read lines {outer} to {outer_end} as Apothem's block, and "
        f"replace or take out what is between them. {keep}"
    )


def two_blocks_report(
    path: str | Path,
    blocks: Sequence[tuple[int, int]],
    *,
    left: bool = True,
    dry_run: bool = False,
    then: str | None = None,
    revealed: tuple[int, int] | None = None,
    quoted: MarkerLine | None = None,
) -> str:
    """Return what is wrong with *path*, which holds two or more whole *blocks*.

    Each block is named by the lines of its BEGIN and END marker (see
    :func:`apothem.lib.harness_materializer.whole_blocks`). Apothem writes one
    block per file, so it cannot tell which one is its own: the operator
    changes the marker lines of each pair of theirs and keeps one Apothem
    block (see :data:`_FIX_BLOCKS`). With *left*, the text says Apothem left
    the file as it is, or, with *dry_run*, that it would. *then* is the step
    after the fix, when the text names it. One block in *blocks* is a file
    that shows a second whole block only once that one is out (a BEGIN marker
    above Apothem's block and an END marker below it): *revealed* is that
    block, and the fix is its marker lines (see :func:`_revealed_fix`; *quoted*
    is its END marker line when that reads as code or as text).
    """
    fix = _FIX_BLOCKS
    if len(blocks) > 1:
        spans = [f"lines {begin} to {end}" for begin, end in blocks]
        listed = f"{', '.join(spans[:-1])}, and {spans[-1]}"
        head = (
            f"{path} holds {len(blocks)} whole blocks between Apothem's markers "
            f"({listed})"
        )
    else:
        head = f"{path} holds two different blocks between Apothem's markers"
        if blocks and revealed is not None:
            (begin, stop), (outer, outer_end) = blocks[0], revealed
            head += (
                f": once the block from line {begin} to line {stop} is out, the "
                f"BEGIN marker at line {outer} and the END marker at line "
                f"{outer_end} make another"
            )
            fix = _revealed_fix(blocks[0], revealed, quoted)
    end = "." if then is None else f"; {then}."
    return (
        f"{head}. Apothem writes one block per file and cannot tell which one is "
        f"its own{_left(left, dry_run)} {fix}{end}"
    )
