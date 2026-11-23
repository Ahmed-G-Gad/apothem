# SPDX-License-Identifier: MIT

"""Numbered fixes for Apothem marker lines, each checked on a copy of the file.

The warnings for marker lines Apothem cannot place (see
:mod:`install_driver_blocktext`) give their fixes as numbered steps built from
four edits only, so an operator, or a script, can follow them line by line:

- CHANGE: ``Change line N: add a word inside its comment.`` The marker line
  stays where it is, with a word added before its ``-->`` (the text says
  ``<!-- BEGIN APOTHEM MANAGED BLOCK (example) -->`` once, before the first
  fix), so it no longer reads as a marker.
- ADD: ``Above line N, add a copy of line K.`` or ``Below line N, add a copy
  of line K.``, or, for a closing fence line, ``Above line N, add a line of
  3 backticks, indented 2 spaces.`` (``tildes`` for ``~``; the indent part is
  left out for a line at the left margin).
- MOVE: ``Move line N to just above line M.`` (M is above N.)
- DELETE: ``Delete lines B to E.`` (a whole range, never one marker line).

Each fix is a list of such steps under a label such as ``Fix A, if lines 6
to 38 are Apothem's block:``, and each step reads ``A1.``, ``A2.``, and so on.
Every line number is the line's number in the file as it is before any step,
and the steps run from the bottom of the file up, so no step moves a line a
later step names: the steps give the same file whether they are read in
order, each number taken as it stands, or each number taken as the line it
named first.

No fix is printed before it passes :func:`passes` (see
:mod:`install_driver_stepcheck`) on a copy of the file: its
steps, applied as printed, give the same file as applied by first numbers;
the file then holds exactly the block the fix promises (or none), with no
marker pair left that no rule can place and no BEGIN marker that starts no
whole block; the next update (or uninstall) then holds that promise; and
every line of the operator's that is left keeps how a Markdown viewer reads
it (text, code, a code block's opening line, its closing line). When no fix
passes, the warning gives :data:`FALLBACK` instead, which numbers no edit.
Everything here builds and checks text and reads no file.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from apothem.lib.harness_materializer import (
    APOTHEM_BLOCK_BEGIN,
    APOTHEM_BLOCK_END,
    MarkerPlace,
    UncertainPair,
)

from .install_driver_stepcheck import WORD as _WORD
from .install_driver_stepcheck import Edit, Step, passes, split_lines

#: A BEGIN marker line once a CHANGE step has changed it.
_EXAMPLE = APOTHEM_BLOCK_BEGIN.replace(" -->", f" {_WORD} -->")

#: The two marker lines a CHANGE step can change.
_MARKERS = frozenset({APOTHEM_BLOCK_BEGIN, APOTHEM_BLOCK_END})

_RUN = re.compile(r"`{3,}|~{3,}")

#: What every list of numbered fixes says before its first fix.
INTRO = (
    "Each fix below lists its steps from the bottom of the file up. Do them "
    "in that order, and read each line number as the line's number in the "
    "file as it is now: no step moves a line that a later step names. To "
    "change a marker line, add a word inside its comment, as in "
    f"{_EXAMPLE}: the line then no longer reads as a marker."
)

#: What a warning says when no fix passes :func:`passes` (see
#: :func:`render_fixes`); ``{then}`` is what the next run then does.
FALLBACK = (
    "Apothem has no step-by-step fix it could check for this file. Change "
    "every Apothem marker line in it instead: add a word inside each comment, "
    f"as in {_EXAMPLE}. That adds and removes no line, so "
    "nothing else in the file reads differently. {then}; old Apothem text "
    "between those lines is yours to delete."
)


@dataclass(frozen=True)
class Fix:
    """One checked fix: the case it is for, its steps in order, and its result.

    ``label`` names the case (``if lines 6 to 38 are Apothem's block``), and
    ``block`` the 1-based first and last line of the block it calls
    Apothem's (``None`` when it calls no pair Apothem's); ``keeps`` is True
    when the file then holds that block, False when it then holds no block
    (the steps took the block out, or the case says no pair is Apothem's).
    """

    label: str
    steps: tuple[Step, ...]
    keeps: bool
    block: tuple[int, int] | None = None


def _closing_line(opener: str) -> str | None:
    """Return a line that closes the code block the line *opener* opens.

    The opener's run of backticks or tildes, at the column it starts at
    (``None`` when the line holds no such run).
    """
    match = _RUN.search(opener)
    if match is None:
        return None
    column = len(opener[: match.start()].expandtabs(4))
    return " " * column + match.group()


def render_step(step: Step) -> str:
    """Return the sentence for *step* (see the formats in this module's text)."""
    if step.edit is Edit.CHANGE:
        return f"Change line {step.line}: add a word inside its comment."
    if step.edit is Edit.MOVE:
        return f"Move line {step.line} to just above line {step.other}."
    if step.edit is Edit.DELETE:
        return f"Delete lines {step.line} to {step.other}."
    where = f"{'Below' if step.below else 'Above'} line {step.line}"
    if step.other:
        return f"{where}, add a copy of line {step.other}."
    run = step.fence.lstrip(" ")
    kind = "backticks" if run[0] == "`" else "tildes"
    indent = len(step.fence) - len(run)
    spaces = "" if not indent else f", indented {indent} space{'s' * (indent > 1)}"
    return f"{where}, add a line of {len(run)} {kind}{spaces}."


def _order(steps: Iterable[Step]) -> tuple[Step, ...]:
    """Return *steps* from the bottom of the file up, each once.

    By the first line a step can move: the line a CHANGE, an ADD or a DELETE
    names, or the line a MOVE puts a line above; the lowest last. At one
    line a CHANGE goes first, then an ADD below it, then an ADD above it or
    a MOVE to above it, so no step moves a line a later one names.
    """

    def key(step: Step) -> tuple[int, int, int, int]:
        if step.edit is Edit.MOVE:
            low, rank = step.other, 2
        elif step.edit is Edit.ADD:
            low, rank = step.line, 1 if step.below else 2
        else:
            low, rank = step.line, 0
        return -low, rank, -step.line, -step.other

    return tuple(sorted(dict.fromkeys(steps), key=key))


def _close_steps(
    lines: Sequence[str], fence: int, at: int, end: int, closer: int | None
) -> list[Step] | None:
    """Return the steps that close, above line *at*, the code block of line *fence*.

    *end* is the marker line that code block holds lowest, and *closer* the
    line that closes it below *end* (``None`` when no line does). With only
    blank lines between *end* and *closer*, that line moves up above *at*;
    otherwise a closing line goes above *at*, and, when a line that is not
    blank follows *end* in that code block, a copy of line *fence* below
    *end* opens the code block again for the lines down to *closer*.
    """
    below = range(end, len(lines) if closer is None else closer - 1)
    held = any(lines[index].strip() for index in below)
    if closer is not None and not held:
        return [Step(Edit.MOVE, closer, at)]
    closing = _closing_line(lines[fence - 1])
    if closing is None:
        return None
    steps = [Step(Edit.ADD, at, fence=closing)]
    return [*steps, Step(Edit.ADD, end, fence, below=True)] if held else steps


def _whole_steps(lines: Sequence[str], pair: UncertainPair) -> list[Step] | None:
    """Return the steps that make *pair* read as a whole block, if any.

    Both marker lines in one code block: close it above the BEGIN marker (see
    :func:`_close_steps`). The BEGIN marker in a code block whose closing
    line sits in the pair, the END marker outside code: a closing line above
    the BEGIN marker. The BEGIN marker outside code and the END marker in a
    code block that opens in the pair (the pair rule 3 fired on, or an older
    block whose rule left a code block open): close it above the END marker.
    ``None`` for any other pair: no step of these four makes it whole.
    """
    begin, end = pair.begin, pair.end
    if begin.place is MarkerPlace.FENCE and begin.fence is not None:
        if end.place is MarkerPlace.FENCE and end.fence == begin.fence:
            return _close_steps(lines, begin.fence, begin.line, end.line, pair.closer)
        if end.place is MarkerPlace.OUTSIDE:
            closing = _closing_line(lines[begin.fence - 1])
            return (
                None if closing is None else [Step(Edit.ADD, begin.line, fence=closing)]
            )
        return None
    if (
        begin.place is MarkerPlace.OUTSIDE
        and end.place is MarkerPlace.FENCE
        and end.fence is not None
        and end.fence > begin.line
    ):
        return _close_steps(lines, end.fence, end.line, end.line, pair.closer)
    return None


def _change_pairs(pairs: Iterable[UncertainPair], *, split_both: bool) -> list[Step]:
    """Return the CHANGE steps for the marker lines of *pairs*.

    Of the pair rule 3 fired on, only the BEGIN marker, unless *split_both*:
    its END marker reads as code of the operator's once that BEGIN is theirs.
    """
    steps: list[Step] = []
    for pair in pairs:
        steps.append(Step(Edit.CHANGE, pair.begin.line))
        if split_both or not pair.split:
            steps.append(Step(Edit.CHANGE, pair.end.line))
    return steps


def _every_marker(lines: Sequence[str], keep: tuple[int, int] | None) -> list[Step]:
    """Return a CHANGE step for each marker line of *lines* outside *keep*.

    Each line that holds only a marker, in code or not, so no marker line is
    left to pair once the others change: what a fix falls back on when
    changing the marker lines it names does not pass.
    """
    first, last = keep if keep is not None else (0, 0)
    return [
        Step(Edit.CHANGE, number)
        for number, line in enumerate(lines, 1)
        if line.strip() in _MARKERS and not first <= number <= last
    ]


def _both(pairs: Iterable[UncertainPair]) -> tuple[bool, ...]:
    """Return the ways to change the pair rule 3 fired on, if *pairs* hold it.

    Its BEGIN marker alone first, then both marker lines; one way when no
    pair of *pairs* is that pair.
    """
    return (False, True) if any(pair.split for pair in pairs) else (False,)


def _first_passing(
    lines: Sequence[str],
    variants: Iterable[tuple[list[Step], bool]],
    *,
    label: str,
    block: tuple[int, int] | None,
    removes: bool,
) -> Fix | None:
    """Return the first of *variants* (steps, and whether they keep *block*) that passes."""
    for steps, keeps in variants:
        ordered = _order(steps)
        if passes(lines, ordered, block=block, keeps=keeps, removes=removes):
            return Fix(label, ordered, keeps, block)
    return None


def unclear_fixes(
    text: str,
    pairs: Sequence[UncertainPair],
    lone: Sequence[int],
    *,
    removes: bool,
) -> list[Fix]:
    """Return the checked fixes for *text*, whose marker pairs no rule can place.

    One fix for each pair, for the case that it is Apothem's block: the marker
    lines of every other pair change (of the pair rule 3 fired on, its BEGIN
    marker first, both if that does not pass), and so does each BEGIN marker
    on lines *lone*, which starts no pair; the pair itself is made whole (see
    :func:`_whole_steps`), or deleted from its BEGIN marker line to its END
    marker line. For an install or update the first passes first; for an
    uninstall (*removes*) the second. One more fix for the case that no pair
    is Apothem's: every marker line named changes. A case whose steps all
    fail :func:`passes` is left out.
    """
    lines = split_lines(text)
    lone_steps = [Step(Edit.CHANGE, line) for line in lone]
    fixes: list[Fix] = []
    for pair in pairs:
        span = (pair.begin.line, pair.end.line)
        others = [other for other in pairs if other is not pair]
        own: list[tuple[list[Step], bool]] = []
        if pair.begin.place is pair.end.place is MarkerPlace.OUTSIDE:
            own.append(([], True))
        else:
            whole = _whole_steps(lines, pair)
            delete = ([Step(Edit.DELETE, *span)], False)
            made = [] if whole is None else [(whole, True)]
            own.extend([delete, *made] if removes else [*made, delete])
        variants = [
            ([*steps, *changes], keeps)
            for changes in (
                *(
                    [*_change_pairs(others, split_both=both), *lone_steps]
                    for both in _both(others)
                ),
                _every_marker(lines, span),
            )
            for steps, keeps in own
        ]
        label = f"if lines {span[0]} to {span[1]} are Apothem's block"
        found = _first_passing(
            lines, variants, label=label, block=span, removes=removes
        )
        if found is not None:
            fixes.append(found)
    label = (
        f"if lines {pairs[0].begin.line} to {pairs[0].end.line} are text of yours"
        if len(pairs) == 1
        else "if none of these pairs is Apothem's block"
    )
    found = _first_passing(
        lines,
        (
            *(
                ([*_change_pairs(pairs, split_both=both), *lone_steps], False)
                for both in _both(pairs)
            ),
            (_every_marker(lines, None), False),
        ),
        label=label,
        block=None,
        removes=removes,
    )
    if found is not None:
        fixes.append(found)
    return fixes


def block_fixes(
    text: str,
    blocks: Sequence[tuple[int, int]],
    *,
    removes: bool,
    revealed: tuple[int, int] | None = None,
    quoted: bool = False,
) -> list[Fix]:
    """Return the checked fixes for *text*, which holds two or more whole *blocks*.

    One fix for each block, for the case that it is Apothem's: the two marker
    lines of every other block change. With *revealed* (a BEGIN marker above
    the one block and an END marker below it, which make a second block once
    it is out), one fix: those two marker lines change, or the BEGIN marker
    alone when *quoted* (its END marker reads as code or text). A case whose
    steps fail :func:`passes` is left out.
    """
    lines = split_lines(text)
    cases: list[tuple[tuple[int, int], list[Step]]]
    if revealed is not None and blocks:
        outer = [Step(Edit.CHANGE, revealed[0])]
        if not quoted:
            outer.append(Step(Edit.CHANGE, revealed[1]))
        cases = [(blocks[0], outer)]
    else:
        cases = [
            (
                block,
                [
                    Step(Edit.CHANGE, line)
                    for other in blocks
                    if other != block
                    for line in other
                ],
            )
            for block in blocks
        ]
    fixes: list[Fix] = []
    for block, steps in cases:
        label = f"if lines {block[0]} to {block[1]} are Apothem's block"
        variants = [(steps, True), (_every_marker(lines, block), True)]
        found = _first_passing(
            lines, variants, label=label, block=block, removes=removes
        )
        if found is not None:
            fixes.append(found)
    return fixes


def _letter(index: int) -> str:
    """Return the letter of fix number *index* (0-based): A, B, ... Z, then AA."""
    letters = ""
    index += 1
    while index:
        index, rest = divmod(index - 1, 26)
        letters = chr(ord("A") + rest) + letters
    return letters


def render_fixes(fixes: Sequence[Fix], promises: Sequence[str], fallback: str) -> str:
    """Return *fixes*, numbered, each ended by its promise; or *fallback*.

    *promises* holds one sentence per fix, what the next run then does.
    *fallback* is the text when there is no fix (see :data:`FALLBACK`).
    """
    if not fixes:
        return fallback
    parts = [INTRO]
    for index, (fix, promise) in enumerate(zip(fixes, promises, strict=True)):
        letter = _letter(index)
        steps = " ".join(
            f"{letter}{number}. {render_step(step)}"
            for number, step in enumerate(fix.steps, 1)
        )
        head = f"Fix {letter}, {fix.label}:"
        parts.append(f"{head} {steps} {promise}." if steps else f"{head} {promise}.")
    return " ".join(parts)
