# SPDX-License-Identifier: MIT

"""The text of the warnings for Apothem marker lines Apothem cannot place.

Three kinds of file get such a warning, from install, update, verify, doctor
and uninstall alike (see :mod:`install_driver_blocks`): one whose marker
pairs no rule can place (:func:`unclear_block_report`), which names each pair
and where its marker lines read; one that holds two or more whole blocks
(:func:`two_blocks_report`), which names each block by its lines (a block
that shows only once Apothem's is out, by its two marker lines); and one
with a BEGIN marker that starts no whole block, which each caller names by
its line (see :func:`stray_fix_text`). Another text,
:func:`unlisted_block_report`, is for the one whole block an uninstall with
no install record leaves. Each then gives its fixes as numbered steps that
change BEGIN marker lines in place (see :mod:`install_driver_steps`): one
fix for each case whose block the layout of the file shows then reads whole
(this pair or block is Apothem's), and one that changes every BEGIN marker
line, so Apothem finds no block of its own. Old Apothem text below a changed
line, with its END marker line, is the operator's to delete by hand.
Everything here builds text from the file's text and reads nothing.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from apothem.lib.harness_materializer import (
    APOTHEM_BLOCK_END,
    MarkerLine,
    MarkerPlace,
    UncertainPair,
    stray_begins,
    whole_blocks,
)

from .install_driver_steps import (
    Fix,
    block_fixes,
    render_fixes,
    stray_fixes,
    unclear_fixes,
    unlisted_fixes,
)

#: The outcome of an install or update (see :func:`unclear_block_report`): the
#: next update replaces Apothem's block once a fix makes it the one whole
#: block, or writes it at the end of a file that then holds none.
REPLACES = "the next update then replaces {lines}"

#: The same for a rules file an install or update takes Apothem's block out of.
TAKES_OUT = "the next install, update or uninstall then takes {lines} out"

#: What a fix that leaves no block says the next run then does: Apothem reads
#: none of the lines it changed as its markers.
_NONE_LEFT = "Apothem then finds no block of its own in this file"
_AT_END = (
    "Apothem then reads none of these lines as its markers, and the next update "
    "writes its block at the end of the file"
)

#: What the next run does after a fix, by outcome (``None``: an uninstall),
#: when the file then holds Apothem's block and when it holds none.
_PROMISES: dict[str | None, tuple[str, str]] = {
    REPLACES: ("The next update then replaces Apothem's block", _AT_END),
    TAKES_OUT: (
        "The next install, update or uninstall then takes Apothem's block out",
        _NONE_LEFT,
    ),
    None: ("The uninstall run again then takes Apothem's block out", _NONE_LEFT),
}

#: The outcomes whose next run writes Apothem's block, at the end of a file
#: that holds none.
_WRITES = frozenset({REPLACES})

#: What every list of fixes says about the text below the marker lines it
#: changes.
OLD_TEXT = (
    "Any old Apothem text below a marker line you change, and its END marker "
    "line if it has one, is then yours to delete by hand."
)

#: What a two-block text says about which block is Apothem's.
_FRONTMATTER = (
    "In a file that starts with Apothem's frontmatter, Apothem's block is the one "
    "right below it."
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
    the marker lines between are changed.
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

    Then :data:`OLD_TEXT`, since every fix changes marker lines.
    """
    kept, gone = _PROMISES[outcome]
    promises = [kept if fix.keeps else gone for fix in fixes]
    return f"{render_fixes(fixes, promises)} {OLD_TEXT}"


def _example_reads(pairs: Sequence[UncertainPair]) -> str:
    """Return where a marker example of the operator's among *pairs* reads.

    In code (a fenced code block or indented code), as part of a paragraph
    (a marker line indented four or more columns under a line of text), or
    either, after "A marker example of yours".
    """
    code = paragraph = False
    for pair in pairs:
        if pair.split or _outside(pair):
            continue
        places = {pair.begin.place, pair.end.place}
        if places & {MarkerPlace.FENCE, MarkerPlace.INDENTED}:
            code = True
        else:
            paragraph = True
    if code and paragraph:
        return "in code or in a paragraph"
    return "in code" if code else "that reads as part of a paragraph"


def _held_until(pairs: Sequence[UncertainPair], held: bool, wrote: bool) -> str:
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
    With *wrote* (the run that gives the text wrote its block, and ends as a
    success), the text says that holds from the next run on. The example
    sentence says where the operator's pairs read (see :func:`_example_reads`).
    """
    if not held and not any(pair.split for pair in pairs):
        return ""
    when = "From the next run on, until" if wrote else "Until"
    text = (
        f"{when} you fix these marker lines as this text says, install and update "
        "leave this file as it is and end as partial (exit code 2)."
    )
    if held and any(not pair.split and not _outside(pair) for pair in pairs):
        text += (
            f" A marker example of yours {_example_reads(pairs)} holds the file "
            "back the same way, until you change its BEGIN marker line."
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
    wrote: bool = False,
) -> str:
    """Return what is wrong with *path*, whose text *text* holds *pairs*, and the fix.

    Each pair is named with the lines of its two marker lines and what they
    read as (see :func:`install_driver_blocks.unclear_pairs_at`), and so is
    each BEGIN marker on lines *lone*, outside code, that starts no pair (see
    :func:`install_driver_blocks.lone_begins_at`). A pair after the one rule
    3 fired on, both of whose lines read outside code, is named with that
    pair. Then come the numbered fixes (see
    :func:`install_driver_steps.unclear_fixes`): one for each pair the layout
    of *text* shows reads as the one whole block once every other BEGIN
    marker line changes, and one that changes every BEGIN marker line.
    *outcome* is what
    the next run does once a fix is made: :data:`REPLACES` for an install or
    update, :data:`TAKES_OUT` for a rules file an install or update takes Apothem's
    block out of, and ``None`` for an uninstall, which stays unfinished while
    such a file holds a pair, so its text ends by saying to run it again.
    With *left*, the text says Apothem left the file as it is, or, with
    *dry_run*, that it would. With :data:`REPLACES`, the text
    ends by saying that install and update leave the file as it is, and end
    as partial, until its marker lines are fixed, where the merge holds the
    file back: while *held*, or for the pair rule 3 fired on (see
    :func:`_held_until`); with *wrote* (the run wrote its block), from the
    next run on.
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
    fixes = unclear_fixes(text, pairs)
    parts.append(_fixes_text(fixes, outcome))
    if outcome is None:
        parts.append("Then run the uninstall again.")
    elif outcome in _WRITES:
        parts.append(_held_until(pairs, held, wrote))
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
    outcome: str | None = REPLACES,
) -> str:
    """Return what is wrong with *path*, whose text *text* holds whole *blocks*.

    Each block is named by the lines of its BEGIN and END marker (see
    :func:`apothem.lib.harness_materializer.whole_blocks`). Apothem writes one
    block per file, so it cannot tell which one is its own: one numbered fix
    for each block, for the case that it is Apothem's, changes the BEGIN
    marker line of every other one, and every other BEGIN marker line (see
    :func:`install_driver_steps.block_fixes`); a block whose fix the layout of
    *text* does not show holds gets none, and one more fix then changes every
    BEGIN marker line. *outcome* is what the next run does once a fix is made, as
    for :func:`unclear_block_report`. With *left*, the text says Apothem left
    the file as it is, or, with *dry_run*, that it would. *then* is the step
    after the fix, when the text names it. One block in *blocks* is a file
    that shows a second whole block only once that one is out (a BEGIN
    marker above Apothem's block and an END marker below it): *revealed* is
    that block, and the one fix changes its BEGIN marker line.
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
    fixes = block_fixes(text, blocks, revealed=revealed is not None)
    promises = [
        f"Lines {fix.block[0]} to {fix.block[1]} are then the one block in the file"
        if fix.block is not None
        else _PROMISES[outcome][1]
        for fix in fixes
    ]
    parts.append(f"{render_fixes(fixes, promises)} {OLD_TEXT}")
    if any(fix.keeps for fix in fixes):
        parts.append(_FRONTMATTER)
    if then is not None:
        parts.append(f"{then[0].upper()}{then[1:]}.")
    return " ".join(parts)


def unlisted_block_report(path: str | Path, text: str, block: tuple[int, int]) -> str:
    """Return the warning for *path*, whose text *text* holds one whole *block*.

    For an uninstall with no install record in place: nothing shows which
    install wrote the block, so the file is left as it is. The text names the
    block by its lines and gives the fix that changes every BEGIN marker line,
    the block's included (see :func:`install_driver_steps.unlisted_fixes`): a
    deleted marker line can change how the lines around it read, a changed
    one cannot. The old text below it is the operator's to delete.
    """
    fixes = unlisted_fixes(text)
    return (
        f"{path} still holds Apothem's managed block (lines {block[0]} to "
        f"{block[1]}): no install record lists the file, so the uninstall leaves "
        "it as it is. If you no longer want the block, take it out by hand. "
        + _fixes_text(fixes, None)
    )


def _at(lines: Sequence[int]) -> str:
    """Return where *lines* are, after a marker's name: `` at line 2``, say.

    `` at lines 1 and 4`` for two or more, and empty for none.
    """
    if len(lines) < 2:
        return f" at line {lines[0]}" if lines else ""
    listed = ", ".join(str(line) for line in lines[:-1])
    return f" at lines {listed} and {lines[-1]}"


def stray_subject(
    text: str, *, article: str = "an", strays: Sequence[int] | None = None
) -> str:
    """Return the BEGIN markers in *text* that start no whole block, by their lines.

    ``an Apothem BEGIN marker at line 2``, or ``Apothem BEGIN markers at lines
    1 and 4``; *article* is the word before one marker, and *strays* their
    lines, when the caller has them (see
    :func:`apothem.lib.harness_materializer.stray_begins`). Without the line
    when the text holds no such marker (a file that cannot be read).
    """
    lines = stray_begins(text) if strays is None else strays
    if len(lines) > 1:
        return f"Apothem BEGIN markers{_at(lines)}"
    return f"{article} Apothem BEGIN marker{_at(lines)}"


def stray_fix_text(
    text: str,
    outcome: str | None = REPLACES,
    *,
    strays: Sequence[int] | None = None,
    blocks: Sequence[tuple[int, int]] | None = None,
) -> str:
    """Return the numbered fix for the BEGIN markers in *text* that start no whole block.

    A step that changes each (see :func:`install_driver_steps.stray_fixes`),
    ended by what the next run then does (*outcome*, as for
    :func:`unclear_block_report`) and by what the old Apothem text below such
    a marker then is: the operator's to delete, so no step names it.
    *strays* and *blocks* are those markers' lines and the whole blocks of
    *text*, when the caller has them. Empty when *text* holds no such marker.
    """
    found = stray_begins(text) if strays is None else strays
    whole = whole_blocks(text) if blocks is None else blocks
    fixes = stray_fixes(text, found, whole, appends=outcome in _WRITES)
    return _fixes_text(fixes, outcome) if fixes else ""


def not_back_text(text: str, *, blocks: Sequence[tuple[int, int]] | None = None) -> str:
    """Return why not to add the END marker back instead of changing the marker line.

    With a whole block in *text* (an install or update wrote Apothem's block
    apart from the marker), the file would then hold two Apothem blocks. With
    none, putting it back right below the old Apothem text leaves one whole
    block, but the next run would take any line of the operator's between the
    two markers for Apothem's, and once a run writes Apothem's block apart
    from the marker, two blocks follow. Once the marker line is changed, an
    END marker below it pairs with nothing, so this holds only for the END
    marker added back in place of the fix. *blocks* are the whole blocks of
    *text*, when the caller has them.
    """
    if whole_blocks(text) if blocks is None else blocks:
        return (
            "Do not add the END marker back instead of changing the marker line: "
            "the file would then hold two Apothem blocks, which install and "
            "update leave as they are."
        )
    return (
        "If you add the END marker back instead of changing the marker line, put "
        "no line of yours between the two markers: the next run would replace or "
        "take out every line between them. Once an install or update has written "
        "Apothem's block apart from the marker, do not add it back at all: the "
        "file would then hold two Apothem blocks, which install and update leave "
        "as they are."
    )


def endless_block_report(path: str | Path, text: str, *, left: str) -> str:
    """Return the warning for *path*, whose block in *text* lost its END marker.

    The marker is named by its line, and the fix changes it (see
    :func:`stray_fix_text`); *left* is ``left`` or ``would leave``.
    """
    strays = stray_begins(text)
    fix = stray_fix_text(text, TAKES_OUT, strays=strays)
    return (
        f"{path} has {stray_subject(text, article='the', strays=strays)} but no "
        f"END marker ({APOTHEM_BLOCK_END}) after it, so Apothem cannot tell where "
        f"its block ends and {left} the file as it is. {fix}"
    )


def begin_left_report(path: str | Path, text: str, *, why: str) -> str:
    """Return the warning for *path*, which holds a BEGIN marker alone in *text*.

    For a file an uninstall (or an update that retires it) took Apothem's
    block out of: the marker is named by its line, *why* says why it matters,
    and the fix changes it (see :func:`stray_fix_text`).
    """
    lines = stray_begins(text)
    which = "lines that read" if len(lines) > 1 else "a line that reads"
    return (
        f"{path} still holds {which} as the Apothem BEGIN marker{_at(lines)}, "
        f"with no END marker ({APOTHEM_BLOCK_END}) "
        f"after it, now that Apothem's block is out: {why}. "
        f"{stray_fix_text(text, TAKES_OUT, strays=lines)}"
    )


def stray_install_report(path: str | Path, text: str) -> str:
    """Return the install or update warning for *path*, whose *text* holds a stray BEGIN.

    A BEGIN marker that starts no whole block, named by its line: install and
    update keep the text after it and write Apothem's block apart from it, so
    the fix changes the marker line (see :func:`stray_fix_text`), and the
    text says not to add the END marker back instead (see
    :func:`not_back_text`). With no whole block yet (a preview reads the
    file before the write), the text says a block, not a whole block.
    """
    strays, blocks = stray_begins(text), whole_blocks(text)
    one = len(strays) < 2
    block = "a whole block" if blocks else "a block"
    gone = (
        f"its END marker {APOTHEM_BLOCK_END} is gone, or the marker is yours"
        if one
        else f"their END markers {APOTHEM_BLOCK_END} are gone, or the markers are yours"
    )
    return (
        f"{path} has {stray_subject(text, strays=strays)} that "
        f"{'starts' if one else 'start'} "
        f"no whole block of {'its' if one else 'their'} own ({gone}). Apothem "
        "never cuts the text after it: install and update keep that text as it "
        f"is and write {block} of their own apart from it, and apothem verify "
        "fails for this tool until you change "
        f"{'that marker line' if one else 'those marker lines'}. "
        f"{stray_fix_text(text, strays=strays, blocks=blocks)} "
        f"{not_back_text(text, blocks=blocks)}"
    )
