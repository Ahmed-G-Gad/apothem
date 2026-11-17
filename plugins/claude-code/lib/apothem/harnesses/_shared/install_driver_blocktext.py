# SPDX-License-Identifier: MIT

"""The text of the warnings for Apothem marker lines Apothem cannot place.

Two kinds of file get such a warning, from install, update, verify, doctor and
uninstall alike (see :mod:`install_driver_blocks`): one whose marker pairs no
rule can place (:func:`unclear_block_report`), which names each pair, where
its marker lines read and a fix for each case with what follows from it; and
one that holds two or more whole blocks (:func:`two_blocks_report`), which
names each block by its lines. Everything here builds text and reads nothing.
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


def _pair_fix(
    pair: UncertainPair,
    later: UncertainPair | None,
    outcome: str,
    split: UncertainPair | None = None,
) -> str:
    """Return how to fix *pair* by hand, each choice with what follows from it.

    *outcome* (:data:`REPLACES` or :data:`TAKES_OUT`) is what the next run
    does once both marker lines of a pair read outside code. A pair whose
    lines both read outside code already needs no fix of its own: a pair
    before it is what holds it back. *split* is the pair rule 3 fired on,
    before *pair*: if *pair* is Apothem's block, that pair's BEGIN marker is
    the operator's, and it must go too, or it pairs with the END marker in
    code once *pair* is fixed.
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
    if begin.place is end.place and begin.fence == end.fence:
        step = (
            f"close that code block above line {begin.line}"
            if begin.place is MarkerPlace.FENCE
            else f"start lines {begin.line} and {end.line} at the left margin"
        )
        ours = f"{step}{also}: {outcome.format(lines='those lines')}"
    else:
        ours = f"delete them by hand, keeping your own text{also}"
    return (
        f"If lines {begin.line} to {end.line} are Apothem's block, {ours}. If they "
        "are text of yours, change or delete those two marker lines."
    )


def _lone_text(lone: Sequence[int]) -> str:
    """Return what to do with the BEGIN markers on lines *lone*, which start no pair.

    Left in place, such a marker can pair with an END marker below it once
    the pairs between are fixed, and a later run then replaces the lines
    between them.
    """
    if not lone:
        return ""
    if len(lone) == 1:
        return (
            f"The BEGIN marker at line {lone[0]} starts no marker pair: its END "
            "marker is gone, or the marker is yours. Delete or change it by hand, "
            "with any old Apothem text below it, and keep your own text. If you "
            "leave it, a later install or update can pair it with an END marker "
            "below it and replace the lines between them."
        )
    listed = ", ".join(str(line) for line in lone[:-1])
    return (
        f"The BEGIN markers at lines {listed} and {lone[-1]} start no marker pair: "
        "their END markers are gone, or the markers are yours. Delete or change "
        "them by hand, with any old Apothem text below them, and keep your own "
        "text. If you leave one, a later install or update can pair it with an "
        "END marker below it and replace the lines between them."
    )


def _begin_first(pair: UncertainPair) -> str:
    """Return the step an uninstall gives for the pair rule 3 fired on.

    Once no pair comes after it, its BEGIN marker and the END marker in code
    read as a whole block, which a later install or update replaces.
    """
    begin, end = pair.begin.line, pair.end.line
    return (
        f"If the BEGIN marker at line {begin} is yours, delete or change it. If "
        "you leave it and no marker pair comes after it any more, a later "
        f"install or update reads lines {begin} to {end} as Apothem's block and "
        "replaces them."
    )


def _delete_by_hand(pairs: Sequence[UncertainPair]) -> str:
    """Return the advice an uninstall gives: delete Apothem's block by hand.

    Each other pair is the operator's, and its marker lines go too: while a
    marker pair stays in a file an install record lists, the uninstall leaves
    that file and stays unfinished.
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
        fix = (
            f"If one of these pairs is Apothem's block ({listed}), delete it by "
            "hand, keeping your own text, and change or delete the two marker "
            "lines of each pair of yours."
        )
    return f"{fix} Then run the uninstall again."


def unclear_block_report(
    path: str | Path,
    pairs: Sequence[UncertainPair],
    *,
    outcome: str | None = REPLACES,
    left: bool = True,
    lone: Sequence[int] = (),
    dry_run: bool = False,
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
    operator's, after a step for the BEGIN marker of the pair rule 3 fired
    on: left in place once no pair follows it, it pairs with the END marker
    in code; then the uninstall runs again. With *left*, the text says
    Apothem left the file as it is, or, with *dry_run*, that it would. *lone*
    names the BEGIN markers outside code that start no pair (see
    :func:`install_driver_blocks.lone_begins_at`): each must go too, or it can
    pair with an END marker once the pairs are fixed.
    """
    head = (
        f"{path}: Apothem cannot tell whether the marker lines in this file mark "
        "its block or text of yours"
    )
    parts = [f"{head}{_left(left, dry_run)}", _lone_text(lone)]
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
            parts.append(_pair_fix(pair, later, outcome, after))
    if outcome is None:
        if split is not None:
            parts.append(_begin_first(split))
        parts.append(_delete_by_hand(pairs))
    return " ".join(part for part in parts if part)


def two_blocks_report(
    path: str | Path,
    blocks: Sequence[tuple[int, int]],
    *,
    left: bool = True,
    dry_run: bool = False,
) -> str:
    """Return what is wrong with *path*, which holds two or more whole *blocks*.

    Each block is named by the lines of its BEGIN and END marker (see
    :func:`apothem.lib.harness_materializer.whole_blocks`). Apothem writes one
    block per file, so it cannot tell which one is its own: the operator
    keeps one, deletes each other Apothem block and changes the marker lines
    of each pair of their own. With *left*, the text says Apothem left the
    file as it is, or, with *dry_run*, that it would.
    """
    spans = [f"lines {begin} to {end}" for begin, end in blocks]
    listed = f"{', '.join(spans[:-1])}, and {spans[-1]}"
    return (
        f"{path} holds {len(blocks)} whole blocks between Apothem's markers "
        f"({listed}). Apothem writes one block per file and cannot tell which "
        f"one is its own{_left(left, dry_run)} Keep one block and fix the others "
        "by hand, keeping your own text: delete an Apothem block from its BEGIN "
        "marker line to its END marker line, and for a marker pair of yours (an "
        "example you quote, say), change or delete its two marker lines."
    )
