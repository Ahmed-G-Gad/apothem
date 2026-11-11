# SPDX-License-Identifier: MIT

"""Shared building blocks for per-harness materializers.

These helpers cover profile-to-Markdown field extraction and the legacy
managed-YAML body shape retained for compatibility tests. Current harness
materializers that target strict vendor schemas should emit only documented
keys instead of using the generic managed body.
"""

from __future__ import annotations

import enum
import itertools
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
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
    body are neutralized first, so profile text cannot split the block.
    """
    safe = defuse_sentinels(body.strip())
    return f"{APOTHEM_BLOCK_BEGIN}\n{safe}\n{APOTHEM_BLOCK_END}\n"


_SENTINELS: Final[tuple[str, str]] = (APOTHEM_BLOCK_BEGIN, APOTHEM_BLOCK_END)

#: The byte order mark an editor may put at offset 0 (Notepad's "UTF-8 with
#: BOM", Windows PowerShell 5.1's ``Set-Content -Encoding UTF8``). It is not
#: part of the first line, so a marker right after it still counts.
_BOM: Final[str] = "﻿"

_EOL: Final = re.compile(r"\r\n|\r|\n")
_FENCE_OPEN: Final = re.compile(r"(`{3,}|~{3,})(.*)\Z", re.DOTALL)
_FENCE_CLOSE: Final = re.compile(r"(`{3,}|~{3,})[ \t]*\Z")
_LIST_ITEM: Final = re.compile(r"(?:[-+*]|[0-9]{1,9}[.)])(?=[ \t]|\Z)")

#: Columns of indentation that make a line indented code (CommonMark).
_CODE_INDENT: Final = 4
#: The widest gap after a list bullet that still sets the item's content column.
_MAX_ITEM_GAP: Final = 4


@dataclass(frozen=True)
class _Line:
    """One line of text: where it starts and its text, without the line ending."""

    start: int
    text: str


@dataclass(frozen=True)
class _Marker:
    """A marker line Apothem could have written, and whether it is in a block."""

    marker: str
    start: int
    end: int
    paired: bool


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


def _split_lines(text: str) -> list[_Line]:
    """Return the lines of *text*, split at ``\\n``, ``\\r\\n`` and ``\\r``.

    A byte order mark at offset 0 is left out of the first line.
    """
    pos = len(_BOM) if text.startswith(_BOM) else 0
    lines: list[_Line] = []
    for match in _EOL.finditer(text, pos):
        lines.append(_Line(pos, text[pos : match.start()]))
        pos = match.end()
    if pos < len(text):
        lines.append(_Line(pos, text[pos:]))
    return lines


def _indent(text: str) -> tuple[int, int]:
    """Return the columns and characters of *text*'s leading spaces and tabs.

    A tab moves to the next multiple of four columns, as in CommonMark.
    """
    column = 0
    for index, char in enumerate(text):
        if char == " ":
            column += 1
        elif char == "\t":
            column += _CODE_INDENT - column % _CODE_INDENT
        else:
            return column, index
    return column, len(text)


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


def _candidate_pairs(lines: list[_Line]) -> dict[int, int]:
    """Map each BEGIN marker line whose next marker line is an END to that END.

    Only whole marker lines count, whatever the code blocks around them; the
    caller decides which of these pairs is Apothem's block. Apothem defuses any
    marker in the text it writes (:func:`defuse_sentinels`), so its own block
    is always such a pair.
    """
    marked = [
        index for index, line in enumerate(lines) if line.text.strip() in _SENTINELS
    ]
    return {
        begin: end
        for begin, end in itertools.pairwise(marked)
        if lines[begin].text.strip() == APOTHEM_BLOCK_BEGIN
        and lines[end].text.strip() == APOTHEM_BLOCK_END
    }


@dataclass
class _MarkdownState:
    """The CommonMark code-block state of a scan, one line at a time.

    Tracks fenced code (with the column of the list item it sits in), indented
    code, and the content columns of the open list items, which is all that
    decides whether a line is code. *ignored* holds the lines of fences found
    to stay open to the end of the text; they open nothing.
    """

    lines: list[_Line]
    ignored: set[int]
    fence: _Fence | None = None
    code_column: int | None = None
    items: list[int] = field(default_factory=list)
    can_interrupt: bool = True

    def reset(self) -> None:
        """Start afresh after an Apothem block, which ends every open construct."""
        self.fence = None
        self.code_column = None
        self.items.clear()
        self.can_interrupt = True

    def step(self, index: int) -> _Kind:
        """Advance over line *index* and return what it is."""
        columns, chars = _indent(self.lines[index].text)
        content = self.lines[index].text[chars:]
        if not content.strip():
            if self.fence is None:
                self.can_interrupt = True
            return _Kind.BLANK
        if self.fence is not None and self._in_fence(self.fence, columns, content):
            return _Kind.CODE
        if self.code_column is not None:
            if columns >= self.code_column + _CODE_INDENT:
                return _Kind.CODE
            self.code_column = None
        while self.items and columns < self.items[-1]:
            self.items.pop()
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
        rest = self._open_items(columns, content)
        opener = _fence_opener(rest)
        if opener is not None and index not in self.ignored:
            column = self.items[-1] if self.items else 0
            self.fence = _Fence(opener[0], opener[1], column, index)
            return _Kind.CODE
        self.can_interrupt = not rest.strip()
        return _Kind.TEXT

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

    def _open_items(self, columns: int, content: str) -> str:
        """Open the list items *content* starts with; return the text after them."""
        rest = content
        while (match := _LIST_ITEM.match(rest)) is not None:
            after = rest[match.end() :]
            gap, gap_chars = _indent(after)
            bullet_end = columns + match.end()
            if not after.strip() or gap > _MAX_ITEM_GAP:
                # An empty item, or one that starts with indented code.
                self.items.append(bullet_end + 1)
                return ""
            columns = bullet_end + gap
            self.items.append(columns)
            rest = after[gap_chars:]
        return rest


def _scan(
    lines: list[_Line], pairs: dict[int, int], ignored: set[int]
) -> tuple[list[_Marker], int | None]:
    """Return the marker lines of *lines* and the line of a fence left open, if any.

    A BEGIN marker line outside code whose next marker line is an END marker
    (see :func:`_candidate_pairs`) is Apothem's block: the lines between are not
    read for code, since a fence in Apothem's own text must not hide its END.
    Such a pair inside code is a quoted example: it is skipped the same way, and
    the code around it goes on. Any other marker line outside code is recorded
    on its own.
    """
    state = _MarkdownState(lines, ignored)
    found: list[_Marker] = []
    index = 0
    while index < len(lines):
        kind = state.step(index)
        end = pairs.get(index)
        if kind is _Kind.MARKER:
            line = lines[index]
            token = line.text.strip()
            start = line.start + line.text.index(token)
            found.append(_Marker(token, start, start + len(token), end is not None))
            if end is not None:
                closing = lines[end]
                stop = closing.start + closing.text.index(APOTHEM_BLOCK_END)
                found.append(
                    _Marker(
                        APOTHEM_BLOCK_END, stop, stop + len(APOTHEM_BLOCK_END), True
                    )
                )
                state.reset()
                index = end
        elif end is not None:
            index = end
        index += 1
    return found, None if state.fence is None else state.fence.line


def _marker_lines(text: str) -> list[_Marker]:
    """Return the markers in *text* that Apothem could have written.

    The rule follows CommonMark, so a marker the operator quotes in code is
    their text:

    - A marker counts only as a line of its own (spaces, tabs and the line
      ending aside) that is not code. A byte order mark at offset 0 is not part
      of the first line.
    - A fence opens on a line indented 0-3 columns (from the content column of
      the list item it sits in) with three or more backticks or tildes; after
      backticks, the info string holds no backtick. It closes on a line of the
      same character, at least as long, indented 0-3 columns, with nothing
      after it, or when its list item ends.
    - A line indented four or more columns past the list item it sits in, after
      a blank line (or at the start), is indented code, as are the lines after
      it that stay indented so.
    - A BEGIN marker line outside code whose next marker line is an END marker
      opens Apothem's block: nothing between them is read as code, so a fence
      in Apothem's own text cannot hide its END marker. Such a pair inside code
      is a quoted example, skipped whole.
    - A fence still open at the end of the text marks nothing for certain:
      CommonMark runs it to the end, but then a block Apothem appended after an
      unclosed fence of the operator's would never be found, and each install
      would add another. So such a fence opener counts as text, and the text is
      read again without it.
    """
    lines = _split_lines(text)
    pairs = _candidate_pairs(lines)
    ignored: set[int] = set()
    while True:
        found, unclosed = _scan(lines, pairs, ignored)
        if unclosed is None:
            return found
        ignored.add(unclosed)


def _block_span(text: str) -> tuple[int, int] | None:
    """Return where the first whole managed block in *text* starts and ends.

    The block is a BEGIN marker line outside code whose next marker line is an
    END marker (see :func:`_marker_lines` for what counts as a marker).
    """
    markers = _marker_lines(text)
    for begin, end in itertools.pairwise(markers):
        if begin.paired and begin.marker == APOTHEM_BLOCK_BEGIN:
            return begin.start, end.end
    return None


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
    :func:`has_stray_begin`).
    """
    span = _block_span(text)
    return None if span is None else text[span[0] : span[1]]


def has_stray_begin(text: str) -> bool:
    """Return True when *text* holds a begin sentinel that starts no whole block.

    A begin sentinel outside code whose next marker line is not an end
    sentinel is stray: a block that lost its end sentinel, or a marker line the
    operator wrote (see :func:`_marker_lines`). Install and update keep the
    text after it and write a block of their own apart from it, and verify
    reports the file.
    """
    return any(
        marker.marker == APOTHEM_BLOCK_BEGIN and not marker.paired
        for marker in _marker_lines(text)
    )


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


def merge_managed_block(existing: str, body: str) -> str:
    """Merge an Apothem managed block carrying *body* into *existing* text.

    Three cases, all preserving operator prose:

    - *existing* is empty — return the wrapped block alone.
    - *existing* already carries a whole managed block — replace that block
      in place, leaving operator prose before and after it untouched.
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
    return bom + _merge_block(rest, body)


def _merge_block(existing: str, body: str) -> str:
    """Merge *body* into *existing*, which has no byte order mark at offset 0.

    See :func:`merge_managed_block`.
    """
    body_parts = split_frontmatter(body)
    if body_parts is not None:
        return _merge_frontmatter_block(existing, *body_parts)
    wrapped = wrap_managed_block(body)
    if not existing.strip():
        return wrapped
    span = _block_span(existing)
    if span is not None:
        # Spliced by position: a copy of the block the operator quotes in a
        # code example above it must stay as it is.
        return existing[: span[0]] + wrapped.rstrip("\n") + existing[span[1] :]
    separator = "" if existing.endswith("\n") else "\n"
    return f"{existing}{separator}\n{wrapped}"


def _owned_frontmatter_split(text: str) -> tuple[str, str] | None:
    """Return ``(frontmatter, rest)`` when *text* has the frontmatter-first shape.

    The shape is a byte-0 frontmatter block immediately followed by the BEGIN
    sentinel, with no blank line between them. Only
    :func:`_merge_frontmatter_block` writes it, so the frontmatter is Apothem's.
    An operator file with its own frontmatter that later received an appended
    block always has a blank line (and usually prose) before the sentinel, so it
    never matches.
    """
    parts = split_frontmatter(text)
    if parts is None or parts[1].split("\n", 1)[0].strip() != APOTHEM_BLOCK_BEGIN:
        return None
    return parts


def _merge_frontmatter_block(existing: str, frontmatter: str, body: str) -> str:
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
    """
    owned = _owned_frontmatter_split(existing)
    if owned is None and split_frontmatter(existing) is not None:
        return _merge_block(existing, body)
    remainder = owned[1] if owned is not None else existing
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
    quotes, stays. A byte order mark at offset 0 stays in front of what is
    left, and goes with the file when nothing else is left.
    """
    bom, rest = _split_bom(existing)
    first = complete_managed_block(rest)
    text = _remove_block(rest)
    while first is not None and complete_managed_block(text) == first:
        text = _remove_block(text)
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
