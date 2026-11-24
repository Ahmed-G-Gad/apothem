# SPDX-License-Identifier: MIT

"""Shared building blocks for per-harness materializers.

These helpers cover profile-to-Markdown field extraction and the legacy
managed-YAML body shape retained for compatibility tests. Current harness
materializers that target strict vendor schemas should emit only documented
keys instead of using the generic managed body.
"""

from __future__ import annotations

import bisect
import enum
import functools
import itertools
import re
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field, replace
from typing import Any, Final

import yaml

from apothem.lib.frontmatter import split_frontmatter
from apothem.lib.profile import DEFAULT_LANGUAGE, DEFAULT_STYLE, coerce_profile

# Canonical sentinel pair delimiting the Apothem-managed block inside an
# operator-owned Markdown instruction anchor (AGENTS.md, GEMINI.md, QWEN.md,
# copilot-instructions.md, and the project-scope rule files). The pair is the
# stable, documented merge boundary each harness dossier references: Apothem
# owns only the bytes between the sentinels; operator prose outside is
# preserved verbatim. Changing these strings would orphan every previously
# installed managed block, so they are a frozen contract.
APOTHEM_BLOCK_BEGIN: Final[str] = "<!-- BEGIN APOTHEM MANAGED BLOCK -->"
APOTHEM_BLOCK_END: Final[str] = "<!-- END APOTHEM MANAGED BLOCK -->"


def defuse_sentinels(body: str) -> str:
    """Return *body* with any embedded managed-block sentinel neutralized.

    Profile text (rules, identity strings) reaches the body verbatim. A literal
    sentinel inside it would end the block early (or open a second one), and
    uninstall would then keep the tail as if it were operator prose. Each
    sentinel's opening ``<!--`` is written as the entity ``&lt;!--``: the text
    still reads the same, but it no longer matches the frozen sentinel strings.
    """
    for sentinel in (APOTHEM_BLOCK_BEGIN, APOTHEM_BLOCK_END):
        body = body.replace(sentinel, "&lt;" + sentinel[1:])
    return body


def wrap_managed_block(body: str) -> str:
    """Return *body* wrapped in the canonical Apothem managed-block sentinels.

    The wrapped form is the unit Apothem writes into an operator-owned
    Markdown anchor. The body is stripped of surrounding blank lines so the
    block is byte-stable across re-installs (idempotency depends on the
    wrapped form being identical for identical bodies). Sentinels inside the
    body are neutralized first, so profile text cannot split the block. A code
    fence the body leaves open (a profile rule that opens one and never closes
    it) is closed on a line of its own (see :func:`_close_fence`), so the END
    sentinel never reads as code.
    """
    safe = _close_fence(defuse_sentinels(body.strip()))
    return f"{APOTHEM_BLOCK_BEGIN}\n{safe}\n{APOTHEM_BLOCK_END}\n"


def _close_fence(body: str) -> str:
    """Return *body* with the code fence it leaves open closed, if it leaves one.

    The body is read as Apothem's block reads it (see :func:`_hidden_end`),
    and the closer is the line :func:`trailing_fence` gives.
    """
    found = trailing_fence(body)
    return body if found is None else f"{body}\n{found[1]}"


def trailing_fence(text: str) -> tuple[int, str] | None:
    """Return where the fenced code block *text* ends in opens, and its closing line.

    *text* is read as CommonMark reads it: every fence opener opens, one no
    later line closes included (see :func:`_marker_lines`). The 1-based line
    of the fence's opener, and a line that closes it: a run of the fence's
    character as long as its opener, at the content column of the list item
    the fence sits in. ``None`` when *text* ends in no fenced code block.
    """
    lines = _Lines(text)
    state = _MarkdownState(lines, None)
    state.advance(0, 0, len(lines.texts), len(lines.norm) + 1)
    fence = state.fence
    if fence is None:
        return None
    return fence.line + 1, f"{' ' * fence.column}{fence.char * fence.length}"


_SENTINELS: Final[tuple[str, str]] = (APOTHEM_BLOCK_BEGIN, APOTHEM_BLOCK_END)

#: Text both markers hold: a quick test before the exact one.
_MARKER_WORDS: Final[str] = "APOTHEM MANAGED BLOCK"

#: The byte order mark an editor may put at offset 0 (Notepad's "UTF-8 with
#: BOM", Windows PowerShell 5.1's ``Set-Content -Encoding UTF8``). It is not
#: part of the first line, so a marker right after it still counts.
_BOM: Final[str] = "\ufeff"

_FENCE_OPEN: Final = re.compile(r"(`{3,}|~{3,})(.*)\Z", re.DOTALL)
_FENCE_CLOSE: Final = re.compile(r"(`{3,}|~{3,})[ \t]*\Z")
_LIST_ITEM: Final = re.compile(r"(?:[-+*]|[0-9]{1,9}[.)])(?=[ \t]|\Z)")
#: A thematic break such as ``***`` or ``- - -`` (CommonMark): it is not a list.
_THEMATIC_BREAK: Final = re.compile(r"([-*_])(?:[ \t]*\1){2,}[ \t]*\Z")
#: A setext heading's underline: under a paragraph line it makes a heading.
_SETEXT_UNDERLINE: Final = re.compile(r"(?:-+|=+)[ \t]*\Z")
#: An ATX heading such as ``# Notes``: no paragraph goes on after it.
_ATX_HEADING: Final = re.compile(r"#{1,6}(?:[ \t]|\Z)")
#: A line that starts an HTML block and ends it too, such as ``<!-- note -->``
#: (CommonMark kinds 1 to 5, whose end condition can sit on the same line): no
#: paragraph goes on after it.
_HTML_LINE: Final = re.compile(
    r"<!--.*-->"
    r"|<\?.*\?>"
    r"|<![A-Za-z].*>"
    r"|<!\[CDATA\[.*\]\]>"
    r"|(?i:<(?:pre|script|style|textarea)(?:[ \t>]|\Z).*"
    r"</(?:pre|script|style|textarea)>)",
    re.DOTALL,
)
#: A line that starts an HTML block running to the next blank line (CommonMark
#: kinds 6 and 7): a block-level tag, or any other whole tag alone on its line
#: (that kind only where no paragraph is open). Lines in such a block are its
#: raw text, so a line in it that looks like :data:`_HTML_LINE` starts nothing.
_BLOCK_TAGS: Final = (
    r"address|article|aside|base|basefont|blockquote|body|caption|"
    r"center|col|colgroup|dd|details|dialog|dir|div|dl|dt|fieldset|figcaption|"
    r"figure|footer|form|frame|frameset|h[1-6]|head|header|hr|html|iframe|"
    r"legend|li|link|main|menu|menuitem|nav|noframes|ol|optgroup|option|p|"
    r"param|search|section|summary|table|tbody|td|tfoot|th|thead|title|tr|"
    r"track|ul"
)
_HTML_BLOCK_TAG: Final = re.compile(rf"(?i:</?(?:{_BLOCK_TAGS})(?:[ \t]|/?>|\Z))")
_HTML_LONE_TAG: Final = re.compile(
    r"</?[A-Za-z][A-Za-z0-9-]*(?:[ \t][^<>]*)?/?>[ \t]*\Z"
)

#: A line that holds a fence's closing run and nothing else but spaces and tabs.
_CLOSING_LINE: Final = re.compile(r"^[ \t]*(`{3,}|~{3,})[ \t]*$", re.MULTILINE)
#: Where a pass over lines that need no reading one at a time stops (see
#: :meth:`_MarkdownState._skip`), in a text whose line endings are all
#: ``\n``: a fence's run indented at most three spaces (``run``, with the
#: rest of the line in ``info``), or a line whose text, after any list
#: bullets, starts with a fence's run or with what may start an HTML block
#: (a wider form of :data:`_HTML_LINE`, :data:`_HTML_BLOCK_TAG` and
#: :data:`_HTML_LONE_TAG`), which can open a fence in a list item or an HTML
#: block. ``body`` is the line.
_SKIP_EVENT_BODY: Final = (
    r"(?P<body> {0,3}(?P<run>`{3,}|~{3,})(?P<info>[^\n]*)"
    r"|[ \t]*(?:(?:[-+*]|[0-9]{1,9}[.)])[ \t]+)*(?:```|~~~|<(?:[!?/]"
    rf"|(?i:pre|script|style|textarea|{_BLOCK_TAGS})(?:[ \t>/]|(?=\n|\Z))"
    r"|[A-Za-z][A-Za-z0-9-]*(?:[ \t][^<>\n]*)?/?>[ \t]*(?=\n|\Z))))"
)
#: :data:`_SKIP_EVENT_BODY` on the first line of a text.
_SKIP_EVENT_FIRST: Final = re.compile(_SKIP_EVENT_BODY)
#: :data:`_SKIP_EVENT_BODY` on any later line: the line ending before it is
#: matched, and a line whose first character cannot start one fails at once.
_SKIP_EVENT: Final = re.compile(r"\n(?=[ \t`~<0-9+*\-])" + _SKIP_EVENT_BODY)

#: Fewer lines than this passed over count as a pass that passed over none,
#: and after the most of those in a row, :meth:`_MarkdownState.advance`
#: reads 2 ** that many lines one at a time before it passes over lines again.
_PASSED: Final = 2
_MAX_MISSES: Final = 8

#: Columns of indentation that make a line indented code (CommonMark).
_CODE_INDENT: Final = 4
#: The widest gap after a list bullet that still sets the item's content column.
_MAX_ITEM_GAP: Final = 4
#: The paragraph column of a block quote's paragraph (see
#: :class:`_MarkdownState`): no line without the quote's ">" stays in it.
_QUOTED: Final = 1 << 30


class _Lines:
    """The lines of a text, split at ``\\n``, ``\\r\\n`` and ``\\r``.

    A byte order mark at offset 0 is left out of the first line. ``texts``
    holds each line without its line ending. ``norm`` is the text after the
    mark with each line ending written as ``\\n``, so the line a position of
    it is on is found by counting ``\\n`` (see :meth:`_MarkdownState._skip`).
    ``marked`` maps each line that holds only a marker (whitespace aside, in
    or out of code) to where it starts in the text and in ``norm``. No offset
    of any other line is worked out: a 1 MB file has about 100,000 lines.
    """

    def __init__(self, text: str) -> None:
        self.norm = _one_ending(text)
        self.texts = self.norm.split("\n")
        if self.texts[-1] == "":
            self.texts.pop()
        self.marked = self._marker_lines(text)
        #: For a fence character and run length, where no later line holds a
        #: closing run of that character at least that long.
        self.unclosed: dict[tuple[str, int], int] = {}

    def _marker_lines(self, text: str) -> dict[int, tuple[int, int]]:
        """Return each marker line, with where it starts in *text* and in ``norm``.

        The marker words hold no line ending, so the k-th time they appear in
        ``norm`` is the k-th time in *text*, and the line's text before them
        is the same in both.
        """
        norm, found = self.norm, {}
        line, prev = 0, 0
        pos, source = norm.find(_MARKER_WORDS), text.find(_MARKER_WORDS)
        while pos != -1:
            line += norm.count("\n", prev, pos)
            prev = pos
            if line not in found and self.texts[line].strip() in _SENTINELS:
                start = norm.rfind("\n", 0, pos) + 1
                found[line] = (source - (pos - start), start)
            pos = norm.find(_MARKER_WORDS, pos + len(_MARKER_WORDS))
            source = text.find(_MARKER_WORDS, source + len(_MARKER_WORDS))
        return found

    def never_closed(self, char: str, length: int, pos: int) -> bool:
        """Return True when no line after *pos* closes a fence of *char* this long.

        Known only for a fence opener an earlier pass found no closing line for
        (see :meth:`_MarkdownState._skip`), so each kind of fence is looked
        for to the end of the text once.
        """
        return any(
            kind == char and run <= length and start <= pos
            for (kind, run), start in self.unclosed.items()
        )

    def after(self, line: int) -> int:
        """Return where the line after marker line *line* starts in ``norm``."""
        return self.marked[line][1] + len(self.texts[line]) + 1


def _one_ending(text: str) -> str:
    """Return *text* without a byte order mark at offset 0, each line ending a ``\n``."""
    body = text.removeprefix(_BOM)
    if "\r" not in body:
        return body
    return body.replace("\r\n", "\n").replace("\r", "\n")


def numbered_lines(text: str) -> list[str]:
    """Return the lines of *text*, numbered as :func:`whole_blocks` numbers them.

    Split at ``\n``, ``\r\n`` and ``\r``, without their line endings; a byte
    order mark at offset 0 is no part of the first line.
    """
    lines = _one_ending(text).split("\n")
    if lines[-1] == "":
        lines.pop()
    return lines


@dataclass(frozen=True)
class _Marker:
    """A marker line Apothem could have written, and whether it is in a block.

    ``line`` is its 0-based line; ``start`` and ``end`` are offsets in the text.
    """

    marker: str
    start: int
    end: int
    paired: bool
    line: int


@dataclass(frozen=True)
class _Fence:
    """An open fenced code block: its character, run length, column and line."""

    char: str
    length: int
    column: int
    line: int


class _Kind(enum.Enum):
    """What :meth:`_MarkdownState.step` found a line to be."""

    BLANK = "blank"
    CODE = "code"
    MARKER = "marker"
    TEXT = "text"


def _indent(text: str, start: int = 0) -> tuple[int, int]:
    """Return the columns and characters of *text*'s leading spaces and tabs.

    *text* starts at column *start* of its line. A tab moves to the next
    multiple of four columns of the line, as in CommonMark.
    """
    column = start
    for index, char in enumerate(text):
        if char == " ":
            column += 1
        elif char == "\t":
            column += _CODE_INDENT - column % _CODE_INDENT
        else:
            return column - start, index
    return column - start, len(text)


def _fence_opener(text: str) -> tuple[str, int] | None:
    """Return the character and run length of the fence *text* opens, if any.

    A run of three or more backticks or tildes; after backticks, the rest of the
    line (the info string) holds no backtick, so a line that starts with inline
    code such as ``` ```npm ci``` must pass ``` opens nothing.
    """
    match = _FENCE_OPEN.match(text)
    if match is None:
        return None
    run, info = match.groups()
    if run[0] == "`" and "`" in info:
        return None
    return run[0], len(run)


class _Lookahead:
    """Which fence openers of a text some later line closes.

    A fence at column *c* closes on the first later line that is not blank and
    is indented less than *c* (its list item ends), or on a closing run of its
    character at least as long as its opener, indented less than *c* + 4 (see
    :meth:`_MarkdownState._in_fence`); a blank line never closes one. The
    closing runs are found once, on the first question that needs them, and
    the line that ends a list item is looked for from the fence on, each line
    read once for each indent asked about, so a text is still read in one
    pass however many fences it leaves open.
    """

    def __init__(self, lines: _Lines) -> None:
        self._lines = lines
        self._lower: dict[int, tuple[int, int]] = {}
        self._closers: dict[tuple[str, int], _Closers] | None = None

    def _lower_after(self, index: int, column: int) -> bool:
        """Return True when a line after *index* that is not blank is left of *column*.

        Kept for each column: the lines from the first one read up to the line
        found (or the end) hold no such line.
        """
        texts = self._lines.texts
        first = index + 1
        known = self._lower.get(column)
        if known is not None and known[0] <= first <= known[1]:
            return known[1] < len(texts)
        found = first
        while found < len(texts):
            text = texts[found]
            content = text.lstrip(" \t")
            if content.strip() and _columns(text, content) < column:
                break
            found += 1
        self._lower[column] = (first, found)
        return found < len(texts)

    def _closers_by_kind(self) -> dict[tuple[str, int], _Closers]:
        """Return the closing runs of the text, keyed by character and indent."""
        if self._closers is not None:
            return self._closers
        found: dict[tuple[str, int], list[tuple[int, int]]] = {}
        norm, texts = self._lines.norm, self._lines.texts
        line, prev = 0, 0
        for close in _CLOSING_LINE.finditer(norm):
            line += norm.count("\n", prev, close.start())
            prev = close.start()
            text = texts[line]
            run, columns = close.group(1), _columns(text, text.lstrip(" \t"))
            found.setdefault((run[0], columns), []).append((len(run), line))
        self._closers = {key: _Closers.build(runs) for key, runs in found.items()}
        return self._closers

    def closes(self, index: int, char: str, length: int, column: int) -> bool:
        """Return True when a line after *index* closes a fence opened on it."""
        if column and self._lower_after(index, column):
            return True
        closers = self._closers_by_kind()
        return any(
            (found := closers.get((char, indent))) is not None
            and found.last_after(length) > index
            for indent in range(column, column + _CODE_INDENT)
        )


def _closing_line(fence: _Fence) -> re.Pattern[str]:
    """Return a pattern for a line that closes *fence*, a fence at the left margin.

    A run of its character at least as long as its opener, indented at most
    three columns (a tab reaches column four), with only spaces and tabs
    after it (see :meth:`_MarkdownState._in_fence`).
    """
    return _closing_run(fence.char, fence.length)


@functools.lru_cache(maxsize=64)
def _closing_run(char: str, length: int) -> re.Pattern[str]:
    """Return the pattern :func:`_closing_line` gives for *char* and *length*."""
    run = re.escape(char)
    return re.compile(rf"^ {{0,3}}{run}{{{length},}}[ \t]*$", re.MULTILINE)


def _events(norm: str, at: int, stop: int) -> Iterator[re.Match[str]]:
    """Return each line of *norm* from *at* to *stop* :data:`_SKIP_EVENT` matches.

    *at* is where a line starts.
    """
    found = _SKIP_EVENT.finditer(norm, max(at - 1, 0), stop)
    if at == 0 and (first := _SKIP_EVENT_FIRST.match(norm, 0, stop)) is not None:
        return itertools.chain((first,), found)
    return found


def _columns(text: str, content: str) -> int:
    """Return the columns of the indent of *text*, whose rest is *content*.

    Spaces count one column each; a tab needs the full count (see
    :func:`_indent`).
    """
    columns = len(text) - len(content)
    return _indent(text)[0] if "\t" in text[:columns] else columns


@dataclass(frozen=True)
class _Closers:
    """The closing runs of one character at one indent: run lengths, ascending.

    ``last[k]`` is the last line of the runs at least ``lengths[k]`` long.
    """

    lengths: list[int]
    last: list[int]

    @classmethod
    def build(cls, runs: list[tuple[int, int]]) -> _Closers:
        """Return the table for *runs*, each a run length and its line."""
        ordered = sorted(runs)
        last = [line for _, line in ordered]
        for k in range(len(last) - 2, -1, -1):
            last[k] = max(last[k], last[k + 1])
        return cls([length for length, _ in ordered], last)

    def last_after(self, length: int) -> int:
        """Return the last line of a run at least *length* long, or -1."""
        k = bisect.bisect_left(self.lengths, length)
        return self.last[k] if k < len(self.last) else -1


def _candidate_pairs(lines: _Lines) -> dict[int, int]:
    """Map each BEGIN marker line whose next marker line is an END to that END.

    Only whole marker lines count, whatever the code blocks around them; the
    caller decides which of these pairs is Apothem's block. Apothem defuses any
    marker in the text it writes (:func:`defuse_sentinels`), so its own block
    is always such a pair.
    """
    texts = lines.texts
    return {
        begin: end
        for begin, end in itertools.pairwise(sorted(lines.marked))
        if texts[begin].strip() == APOTHEM_BLOCK_BEGIN
        and texts[end].strip() == APOTHEM_BLOCK_END
    }


@dataclass
class _MarkdownState:
    """The CommonMark code-block state of a scan, one line at a time.

    Tracks fenced code (with the column of the list item it sits in), indented
    code, the content columns of the open list items, and whether a paragraph
    is open (``can_interrupt`` is False then), which is all that decides
    whether a line is code. *ahead* tells which fence openers a later line
    closes: one that no later line closes opens nothing (its line is text);
    with ``None``, every fence opener opens, as in CommonMark (see
    :func:`_marker_lines`). ``empty_item`` is True while the innermost list
    item has nothing after its bullet yet.
    ``para_column`` is the content column of the list item that holds the open
    paragraph (0 outside a list, :data:`_QUOTED` in a block quote). Only a line
    indented that far stays in that item, so only such a line is held to the
    rules for a line under a paragraph; a line left of it goes on the
    paragraph lazily (CommonMark), and the column stays for the lines after
    it.
    """

    lines: _Lines
    ahead: _Lookahead | None
    fence: _Fence | None = None
    code_column: int | None = None
    items: list[int] = field(default_factory=list)
    can_interrupt: bool = True
    empty_item: bool = False
    para_column: int = 0
    raw_html: bool = False

    def reset(self) -> None:
        """Start afresh after an Apothem block, which ends every open construct."""
        self.fence = None
        self.code_column = None
        self.items.clear()
        self.can_interrupt = True
        self.empty_item = False
        self.para_column = 0
        self.raw_html = False

    def advance(self, index: int, pos: int, stop: int, stop_pos: int) -> None:
        """Advance over lines *index* up to *stop*, which start at *pos* and *stop_pos*.

        Each line is read as :meth:`step` reads it, but a stretch that holds
        no line that can open an HTML block or a fence in a list item is
        passed over (see :meth:`_skip`); only the lines from the last place
        whose state is certain up to the next such line are read one at a
        time. Positions are offsets in the text's ``norm``.
        """
        texts = self.lines.texts
        # Lines to read one at a time before the next pass, and how many passes
        # in a row passed over nothing: in a stretch where most lines can open
        # something, each pass would cost more than it saves.
        wait = misses = 0
        while index < stop:
            if wait or self.raw_html or self._listed_fence():
                pos += len(texts[index]) + 1
                self.step(index)
                index += 1
                wait = max(wait - 1, 0)
                continue
            start = index
            index, pos, last = self._skip(index, pos, stop, stop_pos)
            if index - start < _PASSED:
                misses = min(misses + 1, _MAX_MISSES)
                wait = 1 << misses
            else:
                misses = 0
            while index <= last:
                pos += len(texts[index]) + 1
                self.step(index)
                index += 1

    def _listed_fence(self) -> bool:
        """Return True when the open fence sits in a list item."""
        return self.fence is not None and self.fence.column > 0

    def _skip(
        self, index: int, pos: int, stop: int, stop_pos: int
    ) -> tuple[int, int, int]:
        """Pass over lines from *index* that need no reading one at a time.

        No HTML block and no fence in a list item is open. Only three kinds of
        line then leave a state that lasts past the next blank line: a fence
        opener at the left margin (indented at most one column, so it ends
        every list item), which runs to its closing line; a line that can open
        an HTML block or a fence in a list item (see :data:`_SKIP_EVENT`),
        where this pass stops; and the stop line. After a fence's closing
        line, the state is certain; so it is before a line right after an
        empty line that starts at the margin with no blank character (see
        :meth:`_restart`). Returns the line to read on from, its position, and
        the last line to read one at a time; the state is set for the line to
        read on from.
        """
        lines, norm, ahead = self.lines, self.lines.norm, self.ahead
        # The open fence's character ("" for none) and run length.
        char, length = (
            ("", 0) if self.fence is None else (self.fence.char, self.fence.length)
        )
        opened, safe_pos, closed, hazard, at = -1, pos, False, -1, pos
        while True:
            for event in _events(norm, at, stop_pos):
                run, info = event.group("run", "info")
                if char:
                    if (
                        run is not None
                        and run[0] == char
                        and len(run) >= length
                        and not info.strip(" \t")
                    ):
                        char, opened, closed = "", -1, True
                        safe_pos = event.end() + 1
                    continue
                start = event.start("body")
                if (
                    run is None
                    or event.start("run") - start > 1
                    or (run[0] == "`" and "`" in info)
                ):
                    hazard = start
                    break
                if (
                    ahead is None
                    or not lines.unclosed
                    or not lines.never_closed(run[0], len(run), start)
                ):
                    char, length, opened = run[0], len(run), start
                # Otherwise it reads as text (see _opens_fence); what it leaves
                # ends at the next restart.
            if not char or opened < 0 or ahead is None:
                break
            # No line up to the stop line closes the fence this pass opened.
            if _closing_run(char, length).search(norm, stop_pos) is not None:
                break
            # No later line does: its opener reads as text, so the lines after
            # it are read again.
            lines.unclosed[char, length] = opened
            char, at = "", norm.find("\n", opened) + 1
            if at == 0:
                break
        if char:
            # The fence runs past the stop line: every line up to it is code.
            if opened >= 0:
                line = index + norm.count("\n", pos, opened)
                self.fence = _Fence(char, length, 0, line)
                self.items.clear()
                self.code_column = None
                self.can_interrupt = True
            if pos < stop_pos:
                self.empty_item = False
            return stop, stop_pos, stop - 1
        if closed:
            self.fence = None
            self.items.clear()
            self.code_column = None
            self.can_interrupt = True
            self.empty_item = False
        last_pos = stop_pos if hazard < 0 else hazard
        resume_pos = self._restart(safe_pos, last_pos)
        if resume_pos is None:
            resume_pos = safe_pos
        last = stop - 1 if hazard < 0 else index + norm.count("\n", pos, hazard)
        resume = index + norm.count("\n", pos, resume_pos)
        if resume_pos > len(norm):
            resume += 1  # after a closing line with no line ending: the end
        return resume, resume_pos, last

    def _restart(self, start: int, stop: int) -> int | None:
        """Return the last line start from *start* to *stop* whose state is certain.

        Such a line comes right after an empty line, starts with a character
        that is not blank, and is before *stop*. After the empty line no
        paragraph is open, so the line ends every list item and indented
        code, and what it leaves does not depend on the lines above it: the
        state is set to a fresh one for it. ``None`` when there is none.
        """
        norm = self.lines.norm
        end = stop = min(stop, len(norm))
        while (found := norm.rfind("\n\n", max(start - 1, 0), end)) != -1:
            begin = found + 2
            if begin < stop and not norm[begin].isspace():
                self.fence = None
                self.code_column = None
                self.items.clear()
                self.can_interrupt = True
                self.empty_item = False
                self.para_column = 0
                return begin
            end = found + 1
        return None

    def step(self, index: int) -> _Kind:
        """Advance over line *index* and return what it is."""
        text = self.lines.texts[index]
        if not text.strip():
            self._blank()
            return _Kind.BLANK
        if text[0].isalpha() and not self.raw_html:
            return self._plain(text)
        columns, chars = _indent(text)
        content = text[chars:]
        self.empty_item = False
        if self.fence is not None and self._in_fence(self.fence, columns, content):
            return _Kind.CODE
        if self.code_column is not None:
            if columns >= self.code_column + _CODE_INDENT:
                return _Kind.CODE
            self.code_column = None
        while self.items and columns < self.items[-1]:
            self.items.pop()
        # The rules for a line under a paragraph hold only for a line that
        # stays in the list item holding the paragraph (CommonMark): a line
        # left of that item's text goes on it lazily, outside the item.
        open_paragraph = not self.can_interrupt
        paragraph = open_paragraph and columns >= self.para_column
        kept = len(self.items)
        base = self.items[-1] if self.items else 0
        if columns - base >= _CODE_INDENT:
            # Indented code, or a paragraph's continuation line: neither is a
            # marker line of its own.
            if self.can_interrupt:
                self.code_column = base
                return _Kind.CODE
            return _Kind.TEXT
        if content.strip() in _SENTINELS:
            self.can_interrupt = True
            return _Kind.MARKER
        if paragraph and _SETEXT_UNDERLINE.match(content):
            # The underline of a setext heading ends the paragraph; it opens
            # no list item, even a lone "-".
            self.can_interrupt = True
            return _Kind.TEXT
        rest = self._open_items(columns, content, interrupt=paragraph)
        if self._opens_fence(index, rest):
            # A fence ends the paragraph: the line after the code block
            # starts a new one, even when its list item ended the fence.
            self.can_interrupt = True
            return _Kind.CODE
        # A thematic break, a heading or an HTML block that ends on its own
        # line ends a paragraph as a blank line does.
        self.can_interrupt = (
            not rest.strip()
            or bool(_THEMATIC_BREAK.match(rest) or _ATX_HEADING.match(rest))
            or self._html_line(rest, open_paragraph=open_paragraph)
        )
        if self.can_interrupt:
            return _Kind.TEXT
        if rest.startswith(">"):
            # A block quote: no later line without its ">" goes on its paragraph.
            self.para_column = _QUOTED
        elif not open_paragraph or len(self.items) > kept:
            # A paragraph starts on this line, in the innermost list item; a
            # line that goes on one keeps its column.
            self.para_column = self.items[-1] if self.items else 0
        return _Kind.TEXT

    def _plain(self, text: str) -> _Kind:
        """Advance over *text*, a line that starts with a letter at the left margin.

        Such a line opens nothing: no list item, fence, heading, break, HTML
        block or block quote, and it is no marker. It closes no fence either.
        So it is code in a fence at the left margin, and otherwise it ends
        every list item and indented code and goes on the open paragraph or
        starts one, as the full reading in :meth:`step` finds; that reading
        costs several pattern matches a line, and most lines of a file are
        such lines.
        """
        self.empty_item = False
        if self.fence is not None:
            if self.fence.column == 0:
                return _Kind.CODE
            self.fence = None
        self.code_column = None
        self.items.clear()
        if self.can_interrupt:
            self.can_interrupt = False
            self.para_column = 0
        return _Kind.TEXT

    def _blank(self) -> None:
        """Advance over a blank line.

        Outside a fence it ends a paragraph, and it ends a list item that
        holds nothing yet: CommonMark lets an item start with one blank line
        at most.
        """
        if self.fence is None:
            self.can_interrupt = True
            self.raw_html = False
            if self.empty_item:
                self.items.pop()
        self.empty_item = False

    def _html_line(self, rest: str, *, open_paragraph: bool) -> bool:
        """Return True when *rest* is an HTML block that ends on its own line.

        A line in an HTML block that runs to the next blank line (see
        :data:`_HTML_BLOCK_TAG`) is that block's raw text, so it is none;
        such a line starts that kind of block, and an HTML line in it then
        starts nothing.
        """
        if self.raw_html:
            return False
        if _HTML_LINE.match(rest):
            return True
        self.raw_html = bool(
            _HTML_BLOCK_TAG.match(rest)
            or (not open_paragraph and _HTML_LONE_TAG.match(rest))
        )
        return False

    def _in_fence(self, fence: _Fence, columns: int, content: str) -> bool:
        """Return True when the open *fence* holds this line (its closer included)."""
        if columns < fence.column:
            # The list item the fence sits in ended, and the fence with it.
            self.fence = None
            return False
        close = _FENCE_CLOSE.match(content)
        if (
            close is not None
            and columns - fence.column < _CODE_INDENT
            and close.group(1)[0] == fence.char
            and len(close.group(1)) >= fence.length
        ):
            self.fence = None
            self.can_interrupt = True
        return True

    def _opens_fence(self, index: int, rest: str) -> bool:
        """Open the fence *rest* (line *index* after its list bullets) opens, if any.

        A fence no later line closes opens nothing while *ahead* is set (see
        :class:`_Lookahead`): its line then reads as text.
        """
        opener = _fence_opener(rest)
        if opener is None:
            return False
        char, length = opener
        column = self.items[-1] if self.items else 0
        if self.ahead is not None and not self.ahead.closes(
            index, char, length, column
        ):
            return False
        self.fence = _Fence(char, length, column, index)
        return True

    def _open_items(self, columns: int, content: str, *, interrupt: bool) -> str:
        """Open the list items *content* starts with; return the text after them.

        *content* starts at column *columns*. A thematic break such as
        ``* * *`` opens no item. With *interrupt* (the line would go on an
        open paragraph), the first item opens only where CommonMark lets a
        list interrupt a paragraph: the item is not empty and, when ordered,
        is numbered 1; otherwise the line is paragraph text.
        """
        rest = content
        while (
            not _THEMATIC_BREAK.match(rest)
            and (match := _LIST_ITEM.match(rest)) is not None
        ):
            after = rest[match.end() :]
            if interrupt and not _may_interrupt(match.group(), after):
                return rest
            interrupt = False
            bullet_end = columns + match.end()
            gap, gap_chars = _indent(after, bullet_end)
            if not after.strip() or gap > _MAX_ITEM_GAP:
                # An empty item, or one that starts with indented code.
                self.items.append(bullet_end + 1)
                self.empty_item = not after.strip()
                return ""
            columns = bullet_end + gap
            self.items.append(columns)
            rest = after[gap_chars:]
        return rest


def _may_interrupt(bullet: str, after: str) -> bool:
    """Return True when an item with *bullet* and text *after* may end a paragraph.

    CommonMark: a list that interrupts a paragraph starts with an item that
    is not empty and, when ordered, is numbered 1.
    """
    if not after.strip():
        return False
    return bullet[-1] not in ".)" or int(bullet[:-1]) == 1


@dataclass(frozen=True)
class _Scan:
    """What one reading of a text found.

    ``markers`` are the marker lines outside code, in order. ``hidden`` is the
    line of a BEGIN marker outside code whose END marker reads as code with
    another BEGIN/END pair after it (rule 3): no block is certain then.
    ``places`` maps each marker line of a candidate pair (see
    :func:`_candidate_pairs`) the reading went through to what it read as, and
    the line of the fence holding it when that is fenced code.
    """

    markers: list[_Marker]
    hidden: int | None = None
    places: dict[int, tuple[_Kind, int | None]] = field(default_factory=dict)

    @property
    def unclear(self) -> bool:
        """Return True when rule 3 fired, so no block is certain."""
        return self.hidden is not None


def _hidden_end(state: _MarkdownState, begin: int, end: int) -> bool:
    """Return whether the END marker at *end* reads as code after *begin*.

    The lines between are read on a copy of *state*, so the scan itself goes
    on unchanged. Every fence opener there opens, one no later line closes
    included (see :func:`_marker_lines`).
    """
    copy = replace(state, items=list(state.items), ahead=None)
    lines = copy.lines
    copy.advance(begin + 1, lines.after(begin), end, lines.marked[end][1])
    return copy.step(end) is not _Kind.MARKER


def _found(lines: _Lines, index: int, end: int | None) -> list[_Marker]:
    """Return the marker on line *index*, with the END marker on line *end*.

    A marker with no *end* is not in a block; one with an *end* is the BEGIN
    marker of Apothem's block, which runs to the END marker on that line.
    """
    text = lines.texts[index]
    token = text.strip()
    start = lines.marked[index][0] + text.index(token)
    found = [_Marker(token, start, start + len(token), end is not None, index)]
    if end is not None:
        stop = lines.marked[end][0] + lines.texts[end].index(APOTHEM_BLOCK_END)
        found.append(
            _Marker(APOTHEM_BLOCK_END, stop, stop + len(APOTHEM_BLOCK_END), True, end)
        )
    return found


def _scan(lines: _Lines, pairs: dict[int, int]) -> _Scan:
    """Read *lines* once; see :func:`_marker_lines` for the rules.

    A BEGIN marker line outside code whose next marker line is an END marker
    (see :func:`_candidate_pairs`) is Apothem's block, and the lines between
    are not read for code. Every other line is read in turn, a BEGIN marker in
    code included, so a pair quoted across two code blocks marks nothing.
    The lines after the last marker line change nothing found, so the reading
    stops there. Only a marker line can read as a marker, so the lines
    between two of them are passed over as :meth:`_MarkdownState.advance`
    does.
    """
    state = _MarkdownState(lines, _Lookahead(lines))
    found: list[_Marker] = []
    places: dict[int, tuple[_Kind, int | None]] = {}
    marked = {*pairs, *pairs.values()}
    last = max(pairs, default=-1)
    hidden: int | None = None
    index, pos = 0, 0
    for line in sorted(lines.marked):
        if line < index:
            continue  # inside Apothem's block, which is not read for code
        state.advance(index, pos, line, lines.marked[line][1])
        kind = state.step(line)
        if line in marked:
            fence = state.fence if kind is _Kind.CODE else None
            places[line] = (kind, None if fence is None else fence.line)
        index = line + 1
        if kind is _Kind.MARKER:
            end = None if hidden is not None else pairs.get(line)
            if end is not None and last > end and _hidden_end(state, line, end):
                # The END is in code, and another pair follows: either pair
                # can be Apothem's, so neither is taken. From here on a fence
                # no later line closes opens as it did for that END marker:
                # read as text, it would make a whole block of the pair.
                hidden, end = line, None
                state.ahead = None
            found.extend(_found(lines, line, end))
            if end is not None:
                state.reset()
                index = end + 1
        pos = lines.after(index - 1)
    return _Scan(found, hidden, places)


@functools.lru_cache(maxsize=4)
def _read(text: str) -> tuple[_Lines, dict[int, int], _Scan]:
    """Return the lines of *text*, its candidate pairs and its reading.

    See :func:`_marker_lines` for the rules. A command reads the same text
    many times over (the merge, the warning, the steps of each fix), so the
    last few readings are kept; no caller changes what it gets back.
    """
    lines = _Lines(text)
    pairs = _candidate_pairs(lines)
    return lines, pairs, _scan(lines, pairs)


def _marker_lines(text: str) -> list[_Marker]:
    """Return the markers in *text* that Apothem could have written.

    The rule follows CommonMark, so a marker the operator quotes in code is
    their text:

    - A marker counts only as a line of its own (whitespace and the line
      ending aside, as :meth:`str.strip` reads it) that is not code. A byte
      order mark at offset 0 is not part of the first line.
    - A fence opens on a line indented 0-3 columns (from the content column of
      the list item it sits in) with three or more backticks or tildes; after
      backticks, the info string holds no backtick. It closes on a line of the
      same character, at least as long, indented 0-3 columns, with nothing
      after it, or when its list item ends.
    - A list item's content starts after its bullet and the spaces or tab
      after it (a tab reaches the next multiple of four columns of the line).
      A thematic break such as ``* * *`` or ``- - -`` is not a list item.
      Under a paragraph line, an empty item, or an ordered one not numbered
      1, opens nothing (the line goes on the paragraph), and a line of only
      ``-`` or only ``=`` is a setext underline that ends the paragraph.
      Those rules hold only for a line that stays in the list item holding
      the paragraph: a line left of that item's text, such as one after a
      line of the item's text that goes on at the left margin, or one after
      a block quote's line, is held to none of them. A fence ends a
      paragraph, and so does an HTML block that ends on the line it starts
      (``<!-- note -->``, say). An item with nothing after its bullet ends at
      the next blank line.
    - A line indented four or more columns past the content column of the list
      item it sits in (or past the margin outside a list), after a blank line,
      a heading or break, or at the start, is indented code, as are the lines
      after it that stay indented so.
    - A BEGIN marker line outside code whose next marker line is an END marker
      opens Apothem's block: nothing between them is read as code. But when
      the lines between, read as Markdown, leave that END marker in code and
      another BEGIN/END pair follows, no block is certain (rule 3, see
      :func:`uncertain_pairs`). With no pair after them, they are a whole
      block even when the END marker reads as code: that is how a block an
      earlier release wrote reads when a profile rule left a fence open in it
      (:func:`wrap_managed_block` now closes it), and it is also how a BEGIN
      marker that lost its END marker reads above an END marker quoted in code
      further down, which then closes it.
    - Every other line is read in turn, a BEGIN marker in code included: a
      marker pair inside one code block is a quoted example and marks nothing,
      and a BEGIN marker quoted in code never pairs with an END marker outside
      it.
    - A fence that no later line closes marks nothing for certain: CommonMark
      runs it to the end, but then a block Apothem appended after an unclosed
      fence of the operator's would never be found, and each install would add
      another. So such a fence opener counts as text, however many there are.
      It opens as a fence again where rule 3 reads: in the lines between a
      BEGIN marker and its END marker that the rule reads, and after a BEGIN
      marker it fired on. There a fence left open hides an END marker, as
      CommonMark reads it; read as text, it would make a whole block of the
      pair. The text is still read once, from start to end.
    """
    return _read(text)[2].markers


def _block_spans(text: str) -> list[tuple[int, int]]:
    """Return where each whole managed block in *text* starts and ends, in order.

    A block is a BEGIN marker line outside code whose next marker line is an
    END marker (see :func:`_marker_lines` for what counts as a marker).
    """
    return [
        (begin.start, end.end)
        for begin, end in itertools.pairwise(_marker_lines(text))
        if begin.paired and begin.marker == APOTHEM_BLOCK_BEGIN
    ]


def _block_span(text: str) -> tuple[int, int] | None:
    """Return where the first whole managed block in *text* starts and ends."""
    spans = _block_spans(text)
    return spans[0] if spans else None


def whole_blocks(text: str) -> list[tuple[int, int]]:
    """Return the 1-based lines of each whole block's BEGIN and END marker.

    In order; see :func:`complete_managed_block` for a whole block. Apothem
    writes one block per file, so a text with two or more holds a marker pair
    of the operator's outside code, a block pasted in twice, or an old Apothem
    block whose END marker came back after a newer block was written below
    it. Install and update leave such a text as it is (see
    :func:`merge_managed_block`).
    """
    return [
        (begin.line + 1, end.line + 1)
        for begin, end in itertools.pairwise(_read(text)[2].markers)
        if begin.paired and begin.marker == APOTHEM_BLOCK_BEGIN
    ]


class MarkerPlace(enum.Enum):
    """What a marker line of a pair no rule can place reads as.

    ``OUTSIDE`` is a marker line outside code; ``FENCE`` a line in a fenced
    code block; ``INDENTED`` a line of indented code; ``PARAGRAPH`` a line
    indented four or more columns under a line of text, which goes on that
    paragraph.
    """

    OUTSIDE = "outside"
    FENCE = "fence"
    INDENTED = "indented"
    PARAGRAPH = "paragraph"


@dataclass(frozen=True)
class MarkerLine:
    """One marker line: its 1-based line, what it reads as, and its fence.

    ``fence`` is the 1-based line of the fence that opens the code block
    holding it, for :attr:`MarkerPlace.FENCE`; otherwise ``None``.
    """

    line: int
    place: MarkerPlace
    fence: int | None = None


@dataclass(frozen=True)
class UncertainPair:
    """A BEGIN marker line whose next marker line is an END, in no whole block.

    ``split`` is True for the pair rule 3 fired on: its BEGIN marker is
    outside code, its END marker reads as code, and another pair follows, so
    either pair can be Apothem's block.
    """

    begin: MarkerLine
    end: MarkerLine
    split: bool = False


def _marker_line(index: int, scan: _Scan) -> MarkerLine:
    """Return line *index* of a candidate pair as *scan* read it."""
    kind, fence = scan.places.get(index, (_Kind.TEXT, None))
    if kind is _Kind.MARKER:
        return MarkerLine(index + 1, MarkerPlace.OUTSIDE)
    if kind is _Kind.TEXT:
        return MarkerLine(index + 1, MarkerPlace.PARAGRAPH)
    if fence is None:
        return MarkerLine(index + 1, MarkerPlace.INDENTED)
    return MarkerLine(index + 1, MarkerPlace.FENCE, fence + 1)


def uncertain_pairs(text: str) -> list[UncertainPair]:
    """Return each marker pair in *text* that no rule can place, in order.

    Only a text with no whole block (see :func:`complete_managed_block`) has
    such pairs: each BEGIN marker line whose next marker line is an END
    marker, with what each of its two lines reads as. Apothem's block inside a
    code block of the operator's that a later fence closes is one; so is a
    pair the operator quotes in code. An install that recorded a block in the
    file leaves it as it is (see :func:`merge_managed_block`).
    """
    if APOTHEM_BLOCK_BEGIN not in text or APOTHEM_BLOCK_END not in text:
        # No pair to place, so no reading for code: an install check reads
        # every anchor, most of which hold no marker line at all.
        return []
    _, pairs, scan = _read(text)
    if not pairs:
        return []
    if any(marker.paired for marker in scan.markers):
        return []
    return [
        UncertainPair(
            _marker_line(begin, scan),
            _marker_line(end, scan),
            begin == scan.hidden,
        )
        for begin, end in sorted(pairs.items())
    ]


def lone_begins(text: str) -> list[int]:
    """Return the 1-based lines of the BEGIN markers outside code that start no pair.

    Such a marker's next marker line is not an END marker (see
    :func:`_candidate_pairs`): what is left of a block that lost its END
    marker, or a marker line of the operator's. Once the marker pairs after
    it are fixed, it can pair with an END marker below it. Empty when *text*
    holds a whole block: a BEGIN marker beside one is the stray marker
    :func:`has_stray_begin` reports.
    """
    _, pairs, scan = _read(text)
    if any(marker.paired for marker in scan.markers):
        return []
    return [
        marker.line + 1
        for marker in scan.markers
        if marker.marker == APOTHEM_BLOCK_BEGIN and marker.line not in pairs
    ]


def uncertain_block(text: str) -> tuple[int, int | None] | None:
    """Return where *text* holds a marker pair no rule can place, if it does.

    The 1-based line of the first BEGIN marker :func:`uncertain_pairs` names,
    and the 1-based line of the fence that holds it, or that hides its END
    marker when rule 3 fired on it (``None`` when no fence does). ``None``
    when *text* holds a whole block or no such pair.
    """
    found = uncertain_pairs(text)
    if not found:
        return None
    first = found[0]
    holder = first.end if first.split else first.begin
    return first.begin.line, holder.fence


def _earlier_wrap(body: str) -> str:
    """Return the block releases before this one wrote for *body*.

    They did not close a fence the body leaves open (see :func:`_close_fence`).
    """
    safe = defuse_sentinels(body.strip())
    return f"{APOTHEM_BLOCK_BEGIN}\n{safe}\n{APOTHEM_BLOCK_END}\n"


def _held_back(text: str, body: str, *, recorded: bool) -> bool:
    """Return True when a merge of *body* must leave *text* as it is.

    *text* holds no whole block, and either a marker pair in it already reads
    as the block for *body*, as this release or an earlier one wrote it (each
    line compared without its surrounding whitespace, so a re-install adds no
    second block), or a pair is there that may be Apothem's block: a pair's END
    marker is hidden in code with another pair after it, or an install
    recorded a block in this file. A BEGIN marker outside code that starts no
    pair changes nothing: it may be what is left of Apothem's block or a line
    of the operator's, and a pair in code may be a quote of theirs or
    Apothem's recorded block inside a code block of theirs.
    """
    lines, pairs, scan = _read(text)
    if not pairs or any(marker.paired for marker in scan.markers):
        return False
    wants = [
        [line.strip() for line in form.rstrip("\n").split("\n")]
        for form in (wrap_managed_block(body), _earlier_wrap(body))
    ]
    for begin, end in pairs.items():
        if [line.strip() for line in lines.texts[begin : end + 1]] in wants:
            return True
    if scan.unclear:
        return True
    return recorded


def complete_managed_block(text: str) -> str | None:
    """Return the managed block in *text* only when it has both sentinels.

    The block is the first BEGIN marker line outside code whose next marker
    line is an END marker, returned with both, exactly as in *text*. A sentinel
    counts only as a line of its own that is not code (see
    :func:`_marker_lines`), so one an operator quotes is their text. So a begin
    sentinel left without its end above a whole block is not taken as the start
    of the block, and the text after it stays. A begin sentinel with no end
    sentinel after it (a block cut short or edited by hand) returns ``None``:
    nothing shows where Apothem's text stops and the operator's starts, so no
    install, update or uninstall cuts the text after it (see
    :func:`has_stray_begin`). An END sentinel the operator quotes in code
    further down does follow it, though: with no marker pair after them, the
    two read as a whole block (see :func:`_marker_lines`), so the text between
    them is taken for the block.
    """
    span = _block_span(text)
    return None if span is None else text[span[0] : span[1]]


def has_stray_begin(text: str) -> bool:
    """Return True when *text* holds a begin sentinel that starts no whole block.

    A begin sentinel outside code whose next marker line is not an end
    sentinel is stray: a block that lost its end sentinel, or a marker line the
    operator wrote (see :func:`_marker_lines`). So is one whose end sentinel
    reads as code with another marker pair after it (see
    :func:`uncertain_block`). Install and update keep the text after it, and
    verify reports the file.
    """
    return any(
        marker.marker == APOTHEM_BLOCK_BEGIN and not marker.paired
        for marker in _marker_lines(text)
    )


def stray_begins(text: str) -> list[int]:
    """Return the 1-based lines of the BEGIN markers :func:`has_stray_begin` reports.

    In order, numbered as :func:`whole_blocks` numbers its lines. Empty when
    *text* holds no such marker.
    """
    return [
        marker.line + 1
        for marker in _read(text)[2].markers
        if marker.marker == APOTHEM_BLOCK_BEGIN and not marker.paired
    ]


def extract_managed_block(text: str) -> str | None:
    """Return the managed-block region found in *text*, or ``None``.

    A whole block (see :func:`complete_managed_block`) is returned as it is.
    A begin sentinel with no end sentinel after it returns the region from that
    sentinel to the end of the text, so callers can tell such a marker is there
    (an uninstall names the file; an install keeps the text). Nothing removes
    or replaces that region. ``None`` only when no begin sentinel is present.
    """
    span = _block_span(text)
    if span is not None:
        return text[span[0] : span[1]]
    begins = [
        marker.start
        for marker in _marker_lines(text)
        if marker.marker == APOTHEM_BLOCK_BEGIN
    ]
    return text[begins[0] :] if begins else None


def _split_bom(text: str) -> tuple[str, str]:
    """Return *text*'s byte order mark at offset 0 (or ``""``) and the rest."""
    if text.startswith(_BOM):
        return _BOM, text[len(_BOM) :]
    return "", text


def merge_managed_block(existing: str, body: str, *, recorded: bool = False) -> str:
    """Merge an Apothem managed block carrying *body* into *existing* text.

    Five cases, all preserving operator prose:

    - *existing* is empty — return the wrapped block alone.
    - *existing* already carries a whole managed block — replace that block
      in place, leaving operator prose before and after it untouched.
    - *existing* carries two or more whole blocks (see :func:`whole_blocks`)
      — return it unchanged: Apothem writes one block per file, so which one
      to replace is not certain.
    - *existing* carries no whole block, but a BEGIN marker line whose next
      marker line is an END marker (see :func:`uncertain_block`) — return
      *existing* unchanged when such a pair already reads as the wrapped block,
      when *recorded* (an install record lists the file, so the pair may be
      Apothem's block, a BEGIN marker that starts no pair beside it or not),
      or when a pair's END marker reads as code with another pair after it.
      Otherwise append, as below.
    - *existing* carries no whole managed block — append the wrapped block
      after the operator's content, separated by one blank line. A begin
      sentinel with no end after it is such a case: its text is kept, and the
      next merge finds the appended block by its own sentinels.

    The merge is idempotent: re-merging the same *body* into text that
    already carries the resulting block returns byte-identical output.

    A *body* that opens with YAML frontmatter (the rule-file templates whose
    activation keys a harness reads from byte 0) is emitted frontmatter first;
    see :func:`_merge_frontmatter_block`. A byte order mark at offset 0 of
    *existing* stays there, in front of everything the merge returns.
    """
    bom, rest = _split_bom(existing)
    return bom + _merge_block(rest, body, recorded=recorded)


def _merge_block(existing: str, body: str, *, recorded: bool) -> str:
    """Merge *body* into *existing*, which has no byte order mark at offset 0.

    See :func:`merge_managed_block`.
    """
    body_parts = split_frontmatter(body)
    if body_parts is not None:
        return _merge_frontmatter_block(existing, *body_parts, recorded=recorded)
    wrapped = wrap_managed_block(body)
    if not existing.strip():
        return wrapped
    spans = _block_spans(existing)
    if len(spans) > 1:
        # One block per file: which of them to replace is not certain.
        return existing
    if spans:
        # Spliced by position: a copy of the block the operator quotes in a
        # code example above it must stay as it is.
        start, end = spans[0]
        return existing[:start] + wrapped.rstrip("\n") + existing[end:]
    if _held_back(existing, body, recorded=recorded):
        return existing
    separator = "" if existing.endswith("\n") else "\n"
    return f"{existing}{separator}\n{wrapped}"


def _owned_frontmatter_split(text: str) -> tuple[str, str] | None:
    """Return ``(frontmatter, rest)`` when *text* has the frontmatter-first shape.

    The shape is a byte-0 frontmatter block immediately followed by the BEGIN
    sentinel, with no blank line between them, and a frontmatter that holds a
    YAML mapping, as the rule-file templates' keys do (``alwaysApply: true``,
    say). Only :func:`_merge_frontmatter_block` writes it, so the frontmatter
    is Apothem's. An operator file with its own frontmatter that later
    received an appended block always has a blank line (and usually prose)
    before the sentinel, so it never matches; nor do opening lines of the
    operator's that only read as frontmatter, such as a ``---`` line, a list
    item and another ``---`` line right above the BEGIN marker.
    """
    parts = split_frontmatter(text)
    if parts is None or parts[1].split("\n", 1)[0].strip() != APOTHEM_BLOCK_BEGIN:
        return None
    inner = parts[0].split("\n", 1)[1].rsplit("---", 1)[0]
    try:
        keys = yaml.safe_load(inner)
    except yaml.YAMLError:
        return None
    return parts if isinstance(keys, dict) and keys else None


def _merge_frontmatter_block(
    existing: str, frontmatter: str, body: str, *, recorded: bool
) -> str:
    """Merge a frontmatter-carrying managed body, keeping the frontmatter first.

    Emits ``frontmatter``, then the BEGIN sentinel, *body* and the END sentinel,
    then any operator prose. Three cases for *existing*:

    - It already has the frontmatter-first shape: Apothem's frontmatter and
      block are both replaced; operator prose after the block is kept.
    - It opens with the operator's own frontmatter: that frontmatter governs the
      file, so the block (without Apothem's frontmatter) is folded in as for a
      plain body.
    - Anything else (empty, operator prose, or a legacy install whose
      frontmatter sat inside the block): any existing block is removed and the
      frontmatter-first unit is written at the top, with the operator prose
      moved below it.

    A text with two or more whole blocks, or with no whole block and a marker
    pair that may be Apothem's block, is returned unchanged, as
    :func:`merge_managed_block` says.
    """
    owned = _owned_frontmatter_split(existing)
    if owned is None and split_frontmatter(existing) is not None:
        return _merge_block(existing, body, recorded=recorded)
    remainder = owned[1] if owned is not None else existing
    if len(_block_spans(remainder)) > 1 or _held_back(
        remainder, body, recorded=recorded
    ):
        return existing
    operator = _remove_block(remainder)
    head = frontmatter if frontmatter.endswith("\n") else f"{frontmatter}\n"
    emitted = head + wrap_managed_block(body)
    if operator.strip():
        emitted += f"\n{operator}"
    return emitted


def remove_managed_block(existing: str) -> str:
    """Return *existing* with the Apothem managed block surgically removed.

    The inverse of :func:`merge_managed_block`: strips the managed block (and the
    blank-line separator the merge inserted around it) while preserving operator
    prose before and after it. When the remainder is whitespace-only — i.e. the
    anchor was Apothem-only — returns the empty string so the caller can delete
    the now-empty file rather than leaving a stub. Returns *existing* unchanged
    when it carries no complete managed block: a begin sentinel with no end
    sentinel after it stays, with any text below it, since nothing shows where
    the block ended (see :func:`complete_managed_block`).

    Round-trips byte-for-byte for the canonical case: an operator prose block
    ending in a single newline, merged-then-removed, returns the original.

    For the frontmatter-first shape (Apothem's frontmatter directly followed by
    the block), the frontmatter is removed together with the block. The first
    whole block goes, and so does each later exact copy of it (a block pasted
    in twice); any other whole block, such as a marker pair the operator
    quotes, stays. A copy the strip cannot take out (one right after what
    reads as Apothem's frontmatter once the block above it is out) stays too.
    A byte order mark at offset 0 stays in front of what is left, and goes
    with the file when nothing else is left.
    """
    bom, rest = _split_bom(existing)
    first = complete_managed_block(rest)
    if first is None:
        return existing
    text = _remove_block(rest)
    while complete_managed_block(text) == first:
        shorter = _remove_block(text)
        if shorter == text:
            break
        text = shorter
    return bom + text if text else ""


def _remove_block(existing: str) -> str:
    """Return *existing* without its first whole block.

    Only the first whole block goes (see :func:`complete_managed_block`); the
    frontmatter merge uses it so a second block, or a marker pair the
    operator quotes, stays. See :func:`remove_managed_block`.
    """
    owned = _owned_frontmatter_split(existing)
    if owned is not None:
        rest = _remove_block(owned[1])
        # No block to take out after Apothem's frontmatter: keep the file whole.
        return existing if rest == owned[1] else rest
    span = _block_span(existing)
    if span is None:
        return existing
    before = existing[: span[0]].rstrip("\n")
    after = existing[span[1] :].lstrip("\n")
    if before and after:
        remainder = f"{before}\n\n{after}"
    elif before:
        remainder = f"{before}\n"
    else:
        remainder = after
    return "" if not remainder.strip() else remainder


@dataclass(frozen=True)
class MarkdownProfileFields:
    """The profile fields the Markdown-output adapters render into their body.

    Carries the full identity (name/role/email/website/github), both
    preference scalars (language/style), the seriousness band, the rules
    list (+ its pre-rendered block), and the opted-in enforcement flags. The
    optional fields default to absent so an empty profile renders cleanly; the
    projection seam omits any field with no value.
    """

    name: str
    role: str
    language: str
    rules: list[str]
    seriousness: str
    extra_rules_block: str
    style: str = DEFAULT_STYLE
    email: str | None = None
    website: str | None = None
    github: str | None = None
    enforcement: Mapping[str, bool] = field(default_factory=dict)


def extract_markdown_fields(profile: dict[str, Any]) -> MarkdownProfileFields:
    """Extract the canonical Markdown-output field set from *profile*.

    The defaults are delegated to the canonical profile model so Markdown
    helpers and schema-backed profile loading cannot drift. Accepts either a
    raw profile dict or a ``CanonicalProfile.for_harness`` projection.
    """
    canonical = coerce_profile(profile)
    normalized = canonical.to_dict()
    identity = normalized["identity"]
    preferences = normalized["preferences"]
    rules: list[str] = normalized["rules"]
    return MarkdownProfileFields(
        name=identity["name"],
        role=identity["role"],
        language=preferences["language"],
        rules=rules,
        seriousness=normalized["seriousness"],
        extra_rules_block=_render_extra_rules_block(rules),
        style=preferences["style"],
        email=identity.get("email"),
        website=identity.get("website"),
        github=identity.get("github"),
        enforcement=dict(normalized["enforcement"]),
    )


def _render_extra_rules_block(rules: list[str]) -> str:
    """Format the optional ``## Custom Rules`` Markdown block.

    Empty when *rules* is empty; otherwise a two-newline-separated
    section header followed by a bullet list of rules.
    """
    if not rules:
        return ""
    body = "\n".join(f"- {r}" for r in rules)
    return f"\n\n## Custom Rules\n\n{body}"


def build_yaml_managed_config(profile: dict[str, Any], header: str) -> str:
    """Render the canonical ``apothem_managed`` YAML config body.

    Retained for compatibility with earlier generic materializers. The body
    carries the apothem-managed sentinel, the full identity + preferences
    sub-dicts (with their per-key defaults), the seriousness band, and an
    optional rules list.
    """
    normalized = coerce_profile(profile).to_dict()
    identity = normalized["identity"]
    preferences = normalized["preferences"]
    rules: list[str] = normalized["rules"]

    config: dict[str, Any] = {
        "apothem_managed": True,
        "identity": {
            "name": identity.get("name", ""),
            "role": identity.get("role", ""),
            "email": identity.get("email", ""),
        },
        "preferences": {
            "language": preferences.get("language", DEFAULT_LANGUAGE),
            "style": preferences.get("style", DEFAULT_STYLE),
        },
        "apothem_support": "apothem",
        "seriousness": normalized["seriousness"],
    }
    if rules:
        config["rules"] = rules

    return header + yaml.safe_dump(config, default_flow_style=False, allow_unicode=True)
