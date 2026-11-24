# SPDX-License-Identifier: MIT

"""Numbered fixes for Apothem marker lines: each step changes one marker line in place.

The warnings for Apothem marker lines that install, update and uninstall
cannot place (see :mod:`install_driver_blocktext`) give their fixes as
numbered steps of one kind, ``Change line N: add a word inside its
comment.``: the marker line stays where it is, with a word added before its
``-->`` (the warning shows ``<!-- BEGIN APOTHEM MANAGED BLOCK (example) -->``
once, before the first fix), so it no longer reads as a marker. It is still
an HTML comment on a line of its own, so no line moves and a Markdown viewer
reads every other line of the file as before. One more step closes a code
block the file ends in, when a fix leaves no block (the next install or
update writes one at the end of the file): ``Below line N, add a line of 3
backticks.``
(``tildes`` for ``~``, with ``, indented 2 spaces`` for a code block in a list
item; see :func:`render_step`).

Each fix lists its steps under a label such as ``Fix A, if lines 6 to 38 are
Apothem's block:``, read ``A1.``, ``A2.`` and so on, from the bottom of the
file up. Every block, marker pair and stray marker starts at a BEGIN marker,
and an END marker pairs only with the BEGIN marker right above it, so a fix
changes BEGIN marker lines alone: an END marker with no BEGIN marker above
it marks nothing, and a quoted one stays the operator's text as it is. A fix
that keeps a block changes every other BEGIN marker line in the file, a
quoted one included. It is given only where the layout of
the file shows that the block then reads whole (see :func:`_keeps`), so no
fix needs a reading of the file. A fix that keeps no block changes every
BEGIN marker line in the file: Apothem then reads no block, the next update
writes its block at the end of the file, and an uninstall finds no block of
its own there. Everything here builds text and reads no file. It goes over
the lines of the file once per warning, and reads them as Markdown only to
find whether the file ends in an open code block when the layout of its
fences does not show it (see :func:`_closing`).
"""

from __future__ import annotations

import bisect
import re
from collections.abc import Collection, Iterable, Sequence
from dataclasses import dataclass

from apothem.lib.harness_materializer import (
    APOTHEM_BLOCK_BEGIN,
    APOTHEM_BLOCK_END,
    MarkerPlace,
    UncertainPair,
    trailing_fence,
)

#: The word a step adds inside a marker line's comment.
WORD = "(example)"

#: A BEGIN marker line once a step has changed it.
_EXAMPLE = APOTHEM_BLOCK_BEGIN.replace(" -->", f" {WORD} -->")

#: The two marker lines.
_MARKERS = frozenset({APOTHEM_BLOCK_BEGIN, APOTHEM_BLOCK_END})

#: Text every marker line holds; a quick test before the exact one.
_MARKER_TEXT = "APOTHEM MANAGED BLOCK"

_EOL = re.compile(r"\r\n|\r|\n")

#: A line that opens a fenced code block at the left margin, and one that
#: closes one (see ``_FENCE_OPEN`` and ``_FENCE_CLOSE`` in
#: :mod:`apothem.lib.harness_materializer`).
_OPEN = re.compile(r"(`{3,}|~{3,})(.*)\Z", re.DOTALL)
_CLOSE = re.compile(r"(`{3,}|~{3,})[ \t]*\Z")

#: A line that may start an HTML block that runs to the next blank line: a
#: tag after the indent and any list bullets (see ``_HTML_BLOCK_TAG`` in
#: :mod:`apothem.lib.harness_materializer`, of which this is a wider form).
#: In such a block a changed marker line goes on the block's text, where a
#: marker line ends a paragraph, so the lines below it can read differently.
_TAG = re.compile(r"[ \t]*(?:(?:[-+*]|[0-9]{1,9}[.)])[ \t]+)*</?[A-Za-z]")

#: Columns of indentation that make a line indented code.
_CODE_INDENT = 4

#: What every list of numbered fixes says before its first fix.
INTRO = (
    "Each fix below lists its steps from the bottom of the file up. To change "
    f"a marker line, add a word inside its comment, as in {_EXAMPLE}: the line "
    "then no longer reads as a marker, and no other line moves or reads "
    "differently."
)

#: The label of a fix that keeps no block, after fixes that keep one.
OTHER_CASE = "in any other case"


@dataclass(frozen=True)
class Step:
    """One numbered step, with the 1-based line it names.

    With no ``fence``, the step changes line ``line``; with one, it adds that
    closing fence line below line ``line``, the last line of the file.
    """

    line: int
    fence: str = ""


@dataclass(frozen=True)
class Fix:
    """One fix: the case it is for, its steps from the bottom up, and its result.

    ``label`` names the case (``if lines 6 to 38 are Apothem's block``), or is
    ``None`` for a fix that holds whichever lines are Apothem's. ``keeps`` is
    True when the file then holds ``block`` (its 1-based first and last line)
    as its one whole block, False when it then holds no block.
    """

    label: str | None
    steps: tuple[Step, ...]
    keeps: bool
    block: tuple[int, int] | None = None


def split_lines(text: str) -> list[str]:
    """Return the lines of *text* as Apothem numbers them.

    They split at CRLF, LF and a lone CR, and a byte order mark at offset 0 is
    no part of the first line, as in
    :func:`apothem.lib.harness_materializer.whole_blocks`.
    """
    lines = _EOL.split(text.removeprefix("﻿"))
    if lines and lines[-1] == "":
        lines.pop()
    return lines


def changed(line: str) -> str:
    """Return the marker line *line* with :data:`WORD` added inside its comment."""
    cut = line.rfind("-->")
    return f"{line[:cut].rstrip()} {WORD} {line[cut:]}"


def render_step(step: Step) -> str:
    """Return the sentence for *step* (see the formats in this module's text)."""
    if not step.fence:
        return f"Change line {step.line}: add a word inside its comment."
    return f"Below line {step.line}, add {_closing_line(step.fence)}."


def _closing_line(fence: str) -> str:
    """Return the closing line *fence* in words: ``a line of 3 backticks``, say."""
    run = fence.lstrip(" ")
    kind = "backticks" if run[0] == "`" else "tildes"
    indent = len(fence) - len(run)
    spaces = "" if not indent else f", indented {indent} space{'s' * (indent > 1)}"
    return f"a line of {len(run)} {kind}{spaces}"


def closing_clause(step: Step) -> str:
    """Return the closing-line *step* as a clause for a sentence of steps.

    ``add a line of 4 backticks below line 6``, say (see :func:`render_step`).
    """
    return f"add {_closing_line(step.fence)} below line {step.line}"


class _Layout:
    """What a fix needs to know about the lines of a file, from one pass over them.

    ``markers`` are the 1-based lines that hold only a marker (whitespace
    aside, as :func:`apothem.lib.harness_materializer.whole_blocks` reads
    them), in code or not, and ``begins`` those of them that hold the BEGIN
    marker; ``runs`` the 0-based lines that hold a run of
    three backticks or tildes; ``first_tag`` the 0-based first line that may
    start an HTML block (see :data:`_TAG`), or ``None``.
    """

    def __init__(self, text: str) -> None:
        self.lines = split_lines(text)
        self.markers = [
            number
            for number, line in enumerate(self.lines, 1)
            if _MARKER_TEXT in line and line.strip() in _MARKERS
        ]
        self.begins = [
            number
            for number in self.markers
            if self.lines[number - 1].strip() == APOTHEM_BLOCK_BEGIN
        ]
        self.runs = [
            index
            for index, line in enumerate(self.lines)
            if "```" in line or "~~~" in line
        ]
        self.first_tag = next(
            (
                index
                for index, line in enumerate(self.lines)
                if "<" in line and _TAG.match(line)
            ),
            None,
        )
        self._as_is: tuple[int, str] | None | bool = False

    def trailing(self, changes: Iterable[int]) -> tuple[int, str] | None:
        """Return where the code block the file ends in opens once *changes* change.

        *changes* are the BEGIN marker lines a fix changes. The 1-based line of the
        opener of the fenced code block the file then ends in, as CommonMark
        reads it, and the line that closes it (see :func:`_closing`); ``None``
        when it ends in none. A changed line reads as the marker did, unless a
        line above it may start an HTML block, so the reading of the file as
        it is serves every fix but such a one.
        """
        numbers = set(changes)
        if self.first_tag is not None and any(n > self.first_tag for n in numbers):
            return _trailing(self, numbers)
        if self._as_is is False:
            self._as_is = _trailing(self, ())
        return None if isinstance(self._as_is, bool) else self._as_is


def _layout(text: str) -> _Layout:
    """Return the layout of *text* (see :class:`_Layout`)."""
    return _Layout(text)


def _columns(line: str) -> int:
    """Return the columns of *line*'s indent; a tab reaches the next multiple of 4."""
    indent = line[: len(line) - len(line.lstrip(" \t"))]
    return len(indent.expandtabs(_CODE_INDENT))


def _change(numbers: Iterable[int]) -> tuple[Step, ...]:
    """Return a step that changes each line of *numbers*, from the bottom up."""
    return tuple(Step(number) for number in sorted(set(numbers), reverse=True))


def _every(layout: _Layout, keep: tuple[int, int] | None = None) -> tuple[Step, ...]:
    """Return a step for each BEGIN marker line of *layout* but that of *keep*.

    With no BEGIN marker left but the one of the block *keep*, no other two
    marker lines make a block, a pair or a stray BEGIN marker; an END marker
    alone marks nothing.
    """
    first = keep[0] if keep is not None else 0
    return _change(n for n in layout.begins if n != first)


def _keeps(layout: _Layout, block: tuple[int, int], *, first: bool) -> bool:
    """Return True when *block* is the one whole block once every other BEGIN marker changes.

    *block* is a marker pair whose BEGIN marker reads outside code; *first*
    says no whole block comes before it (Apothem's first whole block, or a
    pair in a file with no whole block). A changed marker line still ends a
    paragraph as the marker did, so the lines above the first changed line
    read as before, and the lines between two marker lines that were a block
    are read once those lines change. Above *block*, with no whole block
    there, only the BEGIN marker of the pair rule 3 fired on reads
    differently once changed: after it, Apothem reads every fence opener as
    one, where it now reads one that no later line closes as text; with no
    code block of the file left open to its end above *block* (see
    :func:`_open_above`), every opener above it is closed by a later line,
    so the two readings are one. Either of two layouts shows that the BEGIN
    marker of *block* still reads outside code, and with no other BEGIN
    marker left, its END marker, the next marker line, ends the one block:

    - *first*, and no line above the last changed line above *block* may
      start an HTML block (where a changed line would go on that block's
      text and a marker line would not): every line above *block* then reads
      as before.
    - No line from the first changed line down to the BEGIN marker holds a
      run of backticks or tildes, so no code block opens there, and the BEGIN
      marker is indented less than four columns, so it is no indented code.

    A block in a code block no line closes keeps no fix (see
    :func:`_open_above`).
    """
    if _open_above(layout, block, _every(layout, block)):
        return False
    above = layout.begins[: bisect.bisect_left(layout.begins, block[0])]
    if not above:
        return True
    if first and (layout.first_tag is None or layout.first_tag >= above[-1]):
        return True
    begin = block[0] - 1
    if _columns(layout.lines[begin]) >= _CODE_INDENT:
        return False
    found = bisect.bisect_left(layout.runs, above[0] - 1)
    return found == len(layout.runs) or layout.runs[found] >= begin


def _plain_end(layout: _Layout) -> tuple[int, str] | None | bool:
    """Return where the code block the file ends in opens, read from its fences.

    When every line that holds a run of backticks or tildes starts with it,
    at the left margin, those lines alone open and close every fenced code
    block, as Apothem reads them for CommonMark (see
    :func:`apothem.lib.harness_materializer.trailing_fence`), whatever the
    marker lines hold: the 1-based line of the opener and the line that
    closes it, or ``None`` when the file ends in none. ``False`` when another
    line holds such a run.
    """
    fence: tuple[str, int, int] | None = None
    for index in layout.runs:
        line = layout.lines[index]
        if not line.startswith(("```", "~~~")):
            return False
        if fence is None:
            opened = _OPEN.match(line)
            if opened is None:
                return False
            run, info = opened.groups()
            if not (run[0] == "`" and "`" in info):
                fence = (run[0], len(run), index + 1)
            continue
        closed = _CLOSE.match(line)
        if closed is not None:
            run = closed.group(1)
            if run[0] == fence[0] and len(run) >= fence[1]:
                fence = None
    return None if fence is None else (fence[2], fence[0] * fence[1])


def _trailing(layout: _Layout, changes: Collection[int]) -> tuple[int, str] | None:
    """Return where the code block the file ends in opens once *changes* change.

    See :meth:`_Layout.trailing`. The fences alone tell where the file's code
    blocks end when each starts at the left margin (see :func:`_plain_end`);
    otherwise the file, its BEGIN marker lines *changes* changed, is read as
    Markdown once.
    """
    if not layout.runs:
        return None
    found = _plain_end(layout)
    if found is False:
        fixed = (
            changed(line) if number in changes else line
            for number, line in enumerate(layout.lines, 1)
        )
        found = trailing_fence("".join(f"{line}\n" for line in fixed))
    return found if isinstance(found, tuple) else None


def _closing(layout: _Layout, steps: Sequence[Step]) -> Step | None:
    """Return the step that closes the code block the file ends in after *steps*, if any.

    An install or update adds Apothem's block at the end of a file that holds
    none; a code block in its rules would otherwise close the operator's, and
    a Markdown viewer would read Apothem's block as code. The step adds the
    closing line below the last line: the fence's character, as many as its
    opener, at the content column of the list item it sits in (see
    :func:`apothem.lib.harness_materializer.trailing_fence`). ``None`` when
    the file ends in no fenced code block.
    """
    found = layout.trailing(step.line for step in steps)
    return None if found is None else Step(len(layout.lines), found[1])


def _open_above(layout: _Layout, block: tuple[int, int], steps: Sequence[Step]) -> bool:
    """Return True when a code block that opens above *block* runs to the end of the file.

    A Markdown viewer reads *block* as code then, while Apothem reads that
    code block's opening line as text, since no line closes it; a code block
    in the rules the next update writes into *block* would close it, and the
    BEGIN marker would read as code. No fix keeps such a block: the fix that
    changes every BEGIN marker line closes that code block below the last
    line (see :func:`_closing`).
    """
    found = layout.trailing(step.line for step in steps)
    return found is not None and found[0] < block[0]


def _none(layout: _Layout, label: str | None) -> Fix:
    """Return the fix that changes every BEGIN marker line of *layout*: no block is left.

    The fix first closes the code block the file ends in, if it ends in one
    (see :func:`_closing`): an install or update writes Apothem's block at
    the end of a file that holds none, whether it runs next or after an
    uninstall.
    """
    steps = _every(layout)
    tail = _closing(layout, steps)
    return Fix(label, steps if tail is None else (tail, *steps), keeps=False)


def _label(block: tuple[int, int]) -> str:
    """Return the label of a fix that keeps *block*."""
    return f"if lines {block[0]} to {block[1]} are Apothem's block"


def _kept(layout: _Layout, block: tuple[int, int]) -> Fix:
    """Return the fix that keeps *block* and changes every other BEGIN marker line."""
    return Fix(_label(block), _every(layout, block), keeps=True, block=block)


def unclear_fixes(text: str, pairs: Sequence[UncertainPair]) -> list[Fix]:
    """Return the fixes for *text*, whose marker pairs no rule can place.

    One fix for each pair whose two marker lines read outside code (a pair
    after the one rule 3 fired on), for the case that it is Apothem's block:
    every other BEGIN marker line changes, the pair then reads as the one
    whole block, and the next update replaces it. It is given only where the
    layout shows that (see :func:`_keeps`). The pair rule 3 fired on gets no
    such fix: its END marker reads as code, as an older block whose rule left
    a code block open reads, and a line of the operator's below it closes
    that code block; once the next update replaced the block, that line
    would open a code block instead. Then one fix for every other case,
    which changes every BEGIN marker line (see :func:`_none`).
    """
    layout = _layout(text)
    fixes = [
        _kept(layout, (pair.begin.line, pair.end.line))
        for pair in pairs
        if pair.begin.place is pair.end.place is MarkerPlace.OUTSIDE
        and _keeps(layout, (pair.begin.line, pair.end.line), first=True)
    ]
    fixes.append(_none(layout, OTHER_CASE if fixes else None))
    return fixes


def block_fixes(
    text: str,
    blocks: Sequence[tuple[int, int]],
    *,
    revealed: bool = False,
) -> list[Fix]:
    """Return the fixes for *text*, which holds two or more whole *blocks*.

    One fix for each block, for the case that it is Apothem's: the BEGIN
    marker line of every other block changes, and every other BEGIN marker
    line too. With *revealed* (*blocks* holds the one block, and a BEGIN
    marker above it and an END marker below it make a second block once it
    is out), the one fix changes that BEGIN marker line and every other. A
    fix is given only where the layout shows its block then reads whole (see
    :func:`_keeps`); when a block gets none, one more fix changes every BEGIN
    marker line (see :func:`_none`).
    """
    layout = _layout(text)
    cases = list(blocks[:1] if revealed else blocks)
    fixes = [
        _kept(layout, block)
        for index, block in enumerate(cases)
        if _keeps(layout, block, first=index == 0)
    ]
    if len(fixes) < len(cases):
        fixes.append(_none(layout, OTHER_CASE if fixes else None))
    return fixes


def stray_fixes(
    text: str, strays: Sequence[int], blocks: Sequence[tuple[int, int]]
) -> list[Fix]:
    """Return the fix for the BEGIN markers on lines *strays*, which start no whole block.

    *blocks* are the whole blocks of *text*. With one whole block, the fix
    keeps it and changes every other BEGIN marker line, where the layout
    shows the block then reads whole (see :func:`_keeps`); otherwise it
    changes every BEGIN marker line (see :func:`_none`). Either way no BEGIN
    marker line is left but the kept block's: changing the stray lines alone
    would leave a BEGIN marker quoted in code, which can pair with an END
    marker once the uninstall takes the block out and the lines around it
    join, or which an install record keeps as a pair no rule can place. The
    old text below such a marker stays: no step names it. Empty when *text*
    holds no such marker, or two or more whole blocks (see
    :func:`block_fixes`).
    """
    if not strays or len(blocks) > 1:
        return []
    layout = _layout(text)
    if blocks and _keeps(layout, blocks[0], first=True):
        return [_kept(layout, blocks[0])]
    return [_none(layout, None)]


def stray_fix(
    text: str, strays: Sequence[int], blocks: Sequence[tuple[int, int]]
) -> Fix:
    """Return the one fix for *text*, whose BEGIN markers on lines *strays* start no block.

    The fix :func:`stray_fixes` gives, or, for a file with two or more whole
    *blocks*, the fix that changes every BEGIN marker line (see :func:`_none`).
    For a text that names its steps in a sentence, such as OpenClaw's size
    refusal, which gives one fix.
    """
    found = stray_fixes(text, strays, blocks)
    return found[0] if found else _none(_layout(text), None)


def unlisted_fixes(text: str) -> list[Fix]:
    """Return the fix for the one whole block an uninstall with no record leaves.

    It changes every BEGIN marker line, the block's included, so no block is
    left (see :func:`_none`): the operator deletes the old text by hand.
    """
    return [_none(_layout(text), None)]


def _letter(index: int) -> str:
    """Return the letter of fix number *index* (0-based): A, B, ... Z, then AA."""
    letters = ""
    index += 1
    while index:
        index, rest = divmod(index - 1, 26)
        letters = chr(ord("A") + rest) + letters
    return letters


def render_fixes(fixes: Sequence[Fix], promises: Sequence[str]) -> str:
    """Return :data:`INTRO`, then *fixes*, numbered, each ended by its promise.

    *promises* holds one sentence per fix, what the next run then does.
    """
    parts = [INTRO]
    for index, (fix, promise) in enumerate(zip(fixes, promises, strict=True)):
        letter = _letter(index)
        steps = " ".join(
            f"{letter}{number}. {render_step(step)}"
            for number, step in enumerate(fix.steps, 1)
        )
        head = f"Fix {letter}:" if fix.label is None else f"Fix {letter}, {fix.label}:"
        parts.append(f"{head} {steps} {promise}.")
    return " ".join(parts)
