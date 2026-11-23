# SPDX-License-Identifier: MIT

"""The check every numbered fix for Apothem marker lines passes before it is printed.

A fix (see :mod:`install_driver_steps`) is a list of steps, each one of four
edits, with the line numbers of the file as it is. :func:`passes` applies
them to a copy of the file, as printed and by first line numbers, and holds
the result to what the fix promises: the file then holds exactly the block
the fix names (or none), the next update or uninstall holds that, and every
line of the operator's that is left reads as before. Everything here builds
and checks text and reads no file.
"""

from __future__ import annotations

import enum
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from apothem.lib.harness_materializer import (
    has_stray_begin,
    line_roles,
    merge_managed_block,
    remove_managed_block,
    uncertain_pairs,
    whole_blocks,
)

#: The word a CHANGE step adds inside a marker line's comment.
WORD = "(example)"

#: The bodies the check merges into a fixed file (see :func:`passes`): a
#: plain rule, a rule that holds a closed code block, and one that leaves a
#: code block open (the merge closes it). A code block's closing line in the
#: body closes a code block of the operator's that no line of theirs closes.
_PROBES = (
    "Apothem probe rule.",
    "Run:\n```sh\nnpm test\n```",
    "Run:\n```sh\nnpm test",
)

_EOL = re.compile(r"\r\n|\r|\n")


class Edit(enum.Enum):
    """The four edits a step makes."""

    CHANGE = "change"
    ADD = "add"
    MOVE = "move"
    DELETE = "delete"


@dataclass(frozen=True)
class Step:
    """One numbered edit, with 1-based line numbers of the file as it is.

    ``line`` is the line a CHANGE rewords, the line an ADD goes above (or,
    with ``below``, below), the line a MOVE takes, or the first line a DELETE
    takes out. ``other`` is the line a MOVE puts it just above, the last line
    a DELETE takes out, or the line an ADD copies (``0``: it adds ``fence``,
    a closing fence line, instead).
    """

    edit: Edit
    line: int
    other: int = 0
    below: bool = False
    fence: str = ""


def split_lines(text: str) -> list[str]:
    """Return the lines of *text* as Apothem numbers them.

    They split at CRLF, LF and a lone CR, and a byte order mark at offset 0 is
    no part of the first line, as in
    :func:`apothem.lib.harness_materializer.whole_blocks`.
    """
    lines = _EOL.split(text.removeprefix("\ufeff"))
    if lines and lines[-1] == "":
        lines.pop()
    return lines


def joined(lines: Sequence[str]) -> str:
    """Return *lines* as one text, each line ended by LF."""
    return "".join(f"{line}\n" for line in lines)


def _changed(text: str) -> str:
    """Return the marker line *text* with :data:`WORD` added inside its comment."""
    cut = text.rfind("-->")
    return f"{text[:cut].rstrip()} {WORD} {text[cut:]}"


def apply_steps(
    lines: Sequence[str], steps: Iterable[Step], *, literal: bool
) -> tuple[list[str], list[int | None]] | None:
    """Return *lines* after *steps*, with the 0-based first line of each line.

    With *literal*, each number is the line at that place when its step runs,
    as an operator reads the steps; otherwise each number is the line it named
    before any step ran. A line a step adds has no first line (``None``).
    ``None`` when a step names a line that is not there.
    """
    texts = list(lines)
    tags: list[int | None] = list(range(len(texts)))

    def at(number: int) -> int | None:
        if literal:
            return number - 1 if 0 < number <= len(texts) else None
        return tags.index(number - 1) if number - 1 in tags else None

    for step in steps:
        here = at(step.line)
        if here is None:
            return None
        if step.edit is Edit.CHANGE:
            texts[here] = _changed(texts[here])
        elif step.edit is Edit.DELETE:
            last = at(step.other)
            if last is None or last < here:
                return None
            del texts[here : last + 1], tags[here : last + 1]
        elif step.edit is Edit.MOVE:
            target = at(step.other)
            if target is None or target >= here:
                return None
            texts.insert(target, texts.pop(here))
            tags.insert(target, tags.pop(here))
        else:
            source = at(step.other) if step.other else None
            if step.other and source is None:
                return None
            added = step.fence if source is None else texts[source]
            spot = here + 1 if step.below else here
            texts.insert(spot, added)
            tags.insert(spot, None)
    return texts, tags


def _named(steps: Iterable[Step]) -> set[int]:
    """Return the 0-based lines *steps* change, move or take out."""
    named: set[int] = set()
    for step in steps:
        if step.edit is Edit.DELETE:
            named.update(range(step.line - 1, step.other))
        elif step.edit is not Edit.ADD:
            named.add(step.line - 1)
    return named


def _viewer_roles(text: str) -> list[str | None] | None:
    """Return how a CommonMark viewer reads each line of *text*, as :func:`_roles` does.

    The reader is markdown-it, which the ``rich`` package the CLI needs brings
    along; ``None`` when it cannot be imported, and the check then reads
    with Apothem's own reader alone. A fence's last line is its closing line
    only when the fence's text holds every line between the two.
    """
    try:
        from markdown_it import MarkdownIt
    except ImportError:  # pragma: no cover - rich always brings it
        return None
    lines = split_lines(text)
    roles: list[str | None] = [None if not line.strip() else "text" for line in lines]
    for token in MarkdownIt("commonmark").parse(text):
        if token.map is None or token.type not in {"fence", "code_block"}:
            continue
        start, stop = token.map
        for index in range(start, min(stop, len(lines))):
            if lines[index].strip():
                roles[index] = "code"
        if token.type == "fence":
            roles[start] = "opener"
            if stop - 1 > start and token.content.count("\n") == stop - start - 2:
                roles[stop - 1] = "closer"
    return roles


def _roles(text: str) -> list[tuple[str | None, str | None]]:
    """Return how each line of *text* reads: to Apothem, and to a Markdown viewer.

    Apothem's reading is :func:`apothem.lib.harness_materializer.line_roles`;
    the viewer's is CommonMark's (see :func:`_viewer_roles`), which differs
    from Apothem's after a list item whose text goes on at the left margin,
    say. A fix must keep both.
    """
    own = line_roles(text)
    viewer = _viewer_roles(text)
    return list(zip(own, own if viewer is None else viewer, strict=True))


def _keeps_roles(
    before: Sequence[tuple[str | None, str | None]],
    text: str,
    tags: Sequence[int | None],
    skip: set[int],
) -> bool:
    """Return True when every line of *tags* outside *skip* reads as *before* said.

    *text* holds the lines *tags* names, in order; a blank line has no role.
    """
    after = _roles(text)
    if len(after) != len(tags):
        return False
    return all(
        tag is None
        or tag in skip
        or before[tag] == (None, None)
        or after[at] == before[tag]
        for at, tag in enumerate(tags)
    )


def _removed(
    texts: list[str], tags: list[int | None], block: tuple[int, int]
) -> tuple[list[str], list[int | None]]:
    """Return *texts* and *tags* as an uninstall leaves them without *block*.

    The lines of *block* (1-based) go, with the blank lines next to it, and
    one blank line joins what is left above and below it (see
    :func:`apothem.lib.harness_materializer.remove_managed_block`).
    """
    above = list(zip(texts[: block[0] - 1], tags[: block[0] - 1], strict=True))
    below = list(zip(texts[block[1] :], tags[block[1] :], strict=True))
    while above and not above[-1][0]:
        above.pop()
    while below and not below[0][0]:
        below.pop(0)
    rows = [*above, *([("", None)] if above and below else []), *below]
    return [text for text, _ in rows], [tag for _, tag in rows]


def passes(
    lines: Sequence[str],
    steps: Sequence[Step],
    *,
    block: tuple[int, int] | None,
    keeps: bool,
    removes: bool,
) -> bool:
    """Return True when *steps*, followed as printed, fix the file of *lines*.

    *block* is the 1-based first and last line of what the fix calls
    Apothem's block (``None`` when it calls no pair Apothem's); *keeps* says
    the file then holds that block, *removes* that the next run takes it out
    (an uninstall) rather than replacing it (an install or update). Each
    holds:

    - the steps, each number taken as it stands, give the file they give with
      each number taken as the line it named first;
    - the file then holds exactly that block (or no block), no marker pair no
      rule can place and no BEGIN marker that starts no whole block;
    - the next update then holds one whole block and no such BEGIN marker,
      or the next uninstall leaves no block, pair or BEGIN marker;
    - every line of the operator's that is left (not in *block*, not named
      by a step) reads as before (see :func:`_roles`), after the steps and
      after the uninstall.
    """
    done = apply_steps(lines, steps, literal=False)
    literal = apply_steps(lines, steps, literal=True)
    if done is None or literal is None or literal[0] != done[0]:
        return False
    texts, tags = done
    fixed = joined(texts)
    want: list[tuple[int, int]] = []
    if keeps and block is not None:
        first, last = block[0] - 1, block[1] - 1
        if first not in tags or last not in tags:
            return False
        want = [(tags.index(first) + 1, tags.index(last) + 1)]
    if whole_blocks(fixed) != want or has_stray_begin(fixed) or uncertain_pairs(fixed):
        return False
    before = _roles(joined(lines))
    skip = _named(steps)
    if block is not None:
        skip.update(range(block[0] - 1, block[1]))
    if not _keeps_roles(before, fixed, tags, skip):
        return False
    if not removes:
        return _next_update_holds(fixed)
    if not want:
        return True
    left = remove_managed_block(fixed)
    if whole_blocks(left) or has_stray_begin(left) or uncertain_pairs(left):
        return False
    rest, rest_tags = _removed(texts, tags, want[0])
    if joined(rest) != left:
        return False
    return _keeps_roles(before, left, rest_tags, skip)


def _next_update_holds(fixed: str) -> bool:
    """Return True when the next update holds one whole block in *fixed*.

    With each body of :data:`_PROBES`, with and without an install record:
    the merge gives exactly one whole block, no BEGIN marker that starts
    none and no marker pair no rule can place, and an uninstall after it
    leaves none of the three.
    """
    for body in _PROBES:
        for recorded in (True, False):
            merged = merge_managed_block(fixed, body, recorded=recorded)
            left = remove_managed_block(merged)
            if (
                len(whole_blocks(merged)) != 1
                or has_stray_begin(merged)
                or uncertain_pairs(merged)
                or whole_blocks(left)
                or has_stray_begin(left)
                or uncertain_pairs(left)
            ):
                return False
    return True
