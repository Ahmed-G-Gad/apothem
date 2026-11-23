# SPDX-License-Identifier: MIT

"""The text of the warnings for Apothem marker lines Apothem cannot place.

Two kinds of file get such a warning, from install, update, verify, doctor and
uninstall alike (see :mod:`install_driver_blocks`): one whose marker pairs no
rule can place (:func:`unclear_block_report`), which names each pair and
where its marker lines read; and one that holds two or more whole blocks
(:func:`two_blocks_report`), which names each block by its lines (a block
that shows only once Apothem's is out, by its two marker lines). Each then
gives its fixes as numbered steps, one list for each case (this pair is
Apothem's block, or that one, or none is), each checked on a copy of the file
before it is printed (see :mod:`install_driver_steps`); a case whose steps
fail that check is left out, and with no case left the text gives
:data:`install_driver_steps.FALLBACK`, which numbers no edit. Everything here
builds text from the file's text and reads nothing.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from apothem.lib.harness_materializer import MarkerLine, MarkerPlace, UncertainPair

from .install_driver_steps import (
    FALLBACK,
    Fix,
    block_fixes,
    render_fixes,
    unclear_fixes,
)

#: The outcome of an install or update (see :func:`unclear_block_report`): the
#: next update replaces Apothem's block once a fix makes it whole.
REPLACES = "the next update then replaces {lines}"

#: The same for a rules file an install or update takes Apothem's block out of.
TAKES_OUT = "the next install, update or uninstall then takes {lines} out"

#: What the next run does after a fix, by outcome (``None``: an uninstall),
#: when the file then holds Apothem's block and when it holds none.
_PROMISES: dict[str | None, tuple[str, str]] = {
    REPLACES: (
        "The next update then replaces Apothem's block",
        "The next update then adds Apothem's block to the file",
    ),
    TAKES_OUT: (
        "The next install, update or uninstall then takes Apothem's block out",
        "No Apothem block is then left in this file",
    ),
    None: (
        "The uninstall run again then takes Apothem's block out",
        "The uninstall run again then finds no Apothem block in this file",
    ),
}

#: What a fix says about the old Apothem text below a BEGIN marker it changes.
_OLD_TEXT = (
    "Any old Apothem text below a BEGIN marker line you change is then yours "
    "to keep or delete."
)

#: What a two-block fix says about the block it leaves.
_FRONTMATTER = (
    "Old Apothem text between marker lines you change is then yours to keep or "
    "delete. In a file that starts with Apothem's frontmatter, Apothem's block "
    "is the one right below it."
)


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


def _lone_text(lone: Sequence[int]) -> str:
    """Return what the BEGIN markers on lines *lone*, which start no pair, are.

    Each fix changes them (see :func:`install_driver_steps.unclear_fixes`):
    left in place, such a marker can pair with an END marker below it once
    the pairs between are fixed.
    """
    if not lone:
        return ""
    if len(lone) == 1:
        return (
            f"The BEGIN marker at line {lone[0]} starts no marker pair: its END "
            "marker is gone, or the marker is yours."
        )
    listed = ", ".join(str(line) for line in lone[:-1])
    return (
        f"The BEGIN markers at lines {listed} and {lone[-1]} start no marker pair: "
        "their END markers are gone, or the markers are yours."
    )


def _fixes_text(fixes: Sequence[Fix], outcome: str | None) -> str:
    """Return *fixes*, numbered, each ended by what the next run then does.

    With no fix, the text that numbers no edit (see
    :data:`install_driver_steps.FALLBACK`).
    """
    kept, gone = _PROMISES[outcome]
    promises = [kept if fix.keeps else gone for fix in fixes]
    return render_fixes(fixes, promises, FALLBACK.format(then=gone))


def _held_until(pairs: Sequence[UncertainPair], held: bool) -> str:
    """Return how long install and update leave a file with *pairs* as it is.

    Until its marker lines are fixed, whoever wrote them, but only where the
    merge holds the file back: the pair rule 3 fired on does with or without
    an install record, and while *held* (an install record lists the file,
    as an install or update reads it, or will once the run that gives the
    text is recorded, or that run left the file as it is) every pair does.
    A pair in code may then be Apothem's block, so a marker example of the
    operator's in code holds the file back too, and nothing else ends that.
    A pair that holds exactly the block the merge writes holds the file back
    with or without a record: an install or update that met one left the
    file as it is and passes *held*, but verify and doctor do not check for
    it, so their text then leaves this out. Each such run ends as partial. Empty
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
    text: str,
    pairs: Sequence[UncertainPair],
    *,
    outcome: str | None = REPLACES,
    left: bool = True,
    lone: Sequence[int] = (),
    dry_run: bool = False,
    held: bool = False,
) -> str:
    """Return what is wrong with *path*, whose text *text* holds *pairs*, and the fix.

    Each pair is named with the lines of its two marker lines and what they
    read as (see :func:`install_driver_blocks.unclear_pairs_at`), and so is
    each BEGIN marker on lines *lone*, outside code, that starts no pair (see
    :func:`install_driver_blocks.lone_begins_at`). A pair after the one rule
    3 fired on, both of whose lines read outside code, is named with that
    pair. Then come the numbered fixes, one for each case (see
    :func:`install_driver_steps.unclear_fixes`), each checked on *text*: a
    case whose steps fail the check is left out, and with none left the text
    numbers no edit. *outcome* is what the next run does once a fix is made:
    :data:`REPLACES` for an install or update, :data:`TAKES_OUT` for a rules
    file an install or update takes Apothem's block out of, and ``None`` for
    an uninstall, which stays unfinished while such a file holds a pair, so
    its text ends by saying to run it again. With *left*, the text says
    Apothem left the file as it is, or, with *dry_run*, that it would. With
    :data:`REPLACES`, the text ends by saying that install and update leave
    the file as it is, and end as partial, until its marker lines are fixed,
    where the merge holds the file back: while *held*, or for the pair rule
    3 fired on (see :func:`_held_until`).
    """
    head = (
        f"{path}: Apothem cannot tell whether the marker lines in this file mark "
        "its block or text of yours"
    )
    parts = [f"{head}{_left(left, dry_run)}", _lone_text(lone)]
    for index, pair in enumerate(pairs):
        if index and pairs[index - 1].split and _outside(pair):
            continue
        later = pairs[index + 1] if index + 1 < len(pairs) else None
        parts.append(_pair_text(pair, later))
    fixes = unclear_fixes(text, pairs, lone, removes=outcome != REPLACES)
    parts.append(_fixes_text(fixes, outcome))
    if lone and fixes:
        parts.append(_OLD_TEXT)
    if outcome is None:
        parts.append("Then run the uninstall again.")
    elif outcome == REPLACES:
        parts.append(_held_until(pairs, held))
    return " ".join(part for part in parts if part)


def _revealed_text(block: tuple[int, int], revealed: tuple[int, int]) -> str:
    """Return why the block from *block* stays, when *revealed* shows once it is out.

    *revealed* is a BEGIN marker above Apothem's block and an END marker
    below it. Deleting Apothem's block would leave them the one block in the
    file, and the next run would take the lines between them for Apothem's.
    """
    (begin, end), (outer, outer_end) = block, revealed
    return (
        f"Do not delete the block from line {begin} to line {end}: the next run "
        f"would then read lines {outer} to {outer_end} as Apothem's block, and "
        "replace or take out what is between them."
    )


def two_blocks_report(
    path: str | Path,
    text: str,
    blocks: Sequence[tuple[int, int]],
    *,
    left: bool = True,
    dry_run: bool = False,
    then: str | None = None,
    revealed: tuple[int, int] | None = None,
    quoted: MarkerLine | None = None,
    removes: bool = False,
) -> str:
    """Return what is wrong with *path*, whose text *text* holds whole *blocks*.

    Each block is named by the lines of its BEGIN and END marker (see
    :func:`apothem.lib.harness_materializer.whole_blocks`). Apothem writes one
    block per file, so it cannot tell which one is its own: one numbered fix
    for each block, for the case that it is Apothem's, changes the marker
    lines of every other one (see :func:`install_driver_steps.block_fixes`),
    each checked on *text* for the next update or, with *removes*, the next
    uninstall. With *left*, the text says Apothem left the file as it is, or,
    with *dry_run*, that it would. *then* is the step after the fix, when the
    text names it. One block in *blocks* is a file that shows a second whole
    block only once that one is out (a BEGIN marker above Apothem's block and
    an END marker below it): *revealed* is that block, and the one fix
    changes its marker lines (its BEGIN marker alone when *quoted*, its END
    marker line, reads as code or as text).
    """
    if len(blocks) > 1:
        spans = [f"lines {begin} to {end}" for begin, end in blocks]
        listed = f"{', '.join(spans[:-1])}, and {spans[-1]}"
        head = (
            f"{path} holds {len(blocks)} whole blocks between Apothem's markers "
            f"({listed})"
        )
    else:
        head = f"{path} holds two different blocks between Apothem's markers"
    parts: list[str] = []
    if len(blocks) == 1 and revealed is not None:
        (begin, stop), (outer, outer_end) = blocks[0], revealed
        head += (
            f": once the block from line {begin} to line {stop} is out, the "
            f"BEGIN marker at line {outer} and the END marker at line "
            f"{outer_end} make another"
        )
        parts.append(_revealed_text(blocks[0], revealed))
    parts.insert(
        0,
        f"{head}. Apothem writes one block per file and cannot tell which one is "
        f"its own{_left(left, dry_run)}",
    )
    fixes = block_fixes(
        text, blocks, removes=removes, revealed=revealed, quoted=quoted is not None
    )
    promises = [
        f"Lines {fix.block[0]} to {fix.block[1]} are then the one block in the file"
        for fix in fixes
        if fix.block is not None
    ]
    gone = _PROMISES[None if removes else REPLACES][1]
    parts.append(render_fixes(fixes, promises, FALLBACK.format(then=gone)))
    if fixes:
        parts.append(_FRONTMATTER)
    if then is not None:
        parts.append(f"{then[0].upper()}{then[1:]}.")
    return " ".join(parts)
