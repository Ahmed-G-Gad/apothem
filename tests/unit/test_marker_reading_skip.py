# SPDX-License-Identifier: MIT

"""Passing over lines finds what reading every line finds.

The marker reading (:func:`apothem.lib.harness_materializer._read`) and
:func:`~apothem.lib.harness_materializer.trailing_fence` read a text one line
at a time only where a line can leave a state that lasts: they pass over the
rest, fenced code at the left margin included (see
``_MarkdownState._skip``). Each test here reads generated texts twice, once as
the commands do and once with that pass turned off, so every line is read in
turn, and checks that both readings find the same lines, marker pairs,
markers, places and open fence. The lines of each text, and where each
marker line starts, are checked against a plain split of the text.
"""

from __future__ import annotations

import random
import re
from collections.abc import Iterator

import pytest

from apothem.lib import harness_materializer as materializer
from apothem.lib.harness_materializer import APOTHEM_BLOCK_BEGIN, APOTHEM_BLOCK_END

B, E = APOTHEM_BLOCK_BEGIN, APOTHEM_BLOCK_END
BOM = chr(0xFEFF)
NBSP = chr(0xA0)

#: Lines that open, close or hold each construct the reading tracks, and
#: lines that only look like one.
_VOCABULARY = (
    "",
    "",
    "",
    " ",
    "\t",
    "\x0c",
    NBSP,
    "Some text.",
    "more words",
    "Zebra",
    "- item",
    "* item",
    "+ item",
    "1. one",
    "2) two",
    "-",
    "- ",
    "  - nested",
    "  text in an item",
    "    code",
    "\tcode",
    "```",
    "```sh",
    "````",
    "`````md",
    "~~~",
    "~~~md",
    "~~~~",
    " ```",
    " ~~~",
    "  ```",
    "   ```",
    "    ```",
    "\t```",
    "- ```",
    "1. ~~~",
    "  ~~~",
    "```a`b",
    "``` ",
    "~~~ \t",
    "> quote",
    "> ```",
    "# Heading",
    "***",
    "---",
    "===",
    "- - -",
    "<!-- note",
    "-->",
    "<!-- note -->",
    "<div>",
    "</div>",
    "<pre>",
    "</pre>",
    "<?x",
    "?>",
    "<my-tag>",
    "<![CDATA[",
    "]]>",
    "<!DOCTYPE html",
    ">",
    "- <div>",
    B,
    E,
    B,
    E,
    f"  {B}",
    f"    {B}",
    f"- {B}",
    f"{E} ",
    f"\x0c{B}",
    f"\t{E}",
)

_ENDINGS = ("\n", "\n", "\n", "\r\n", "\r")
_LINE_ENDING = re.compile(r"\r\n|\r|\n")


def _texts(seed: int, count: int) -> Iterator[str]:
    """Yield *count* generated texts, each of 1 to 40 lines."""
    rng = random.Random(seed)  # noqa: S311 - seeded test input, not security
    for _ in range(count):
        lines = [rng.choice(_VOCABULARY) for _ in range(rng.randint(1, 40))]
        if rng.random() < 0.2:
            text = "".join(line + rng.choice(_ENDINGS) for line in lines)
        else:
            ending = rng.choice(_ENDINGS)
            text = ending.join(lines) + (ending if rng.random() < 0.8 else "")
        yield BOM + text if rng.random() < 0.1 else text


def _every_line(
    self: materializer._MarkdownState,
    index: int,
    pos: int,
    stop: int,
    stop_pos: int,
) -> tuple[int, int, int]:
    """Pass over no line: each is read in turn."""
    del self, stop_pos
    return index, pos, stop - 1


def _reading(text: str) -> object:
    """Return what the marker reading and the trailing fence find in *text*."""
    lines, pairs, scan = materializer._read.__wrapped__(text)
    return (
        lines.texts,
        pairs,
        scan.markers,
        scan.hidden,
        scan.places,
        materializer.trailing_fence(text),
    )


def _both_ways(texts: list[str], monkeypatch: pytest.MonkeyPatch) -> None:
    """Assert each of *texts* reads the same with and without passing over lines."""
    fast = [_reading(text) for text in texts]
    monkeypatch.setattr(materializer._MarkdownState, "_skip", _every_line)
    slow = [_reading(text) for text in texts]
    for text, quick, full in zip(texts, fast, slow, strict=True):
        assert quick == full, repr(text[:400])


def _plain_split(text: str) -> tuple[list[str], list[int]]:
    """Return the lines of *text* and where each starts, split by a pattern."""
    pos = 1 if text.startswith(BOM) else 0
    texts, starts = [], []
    for match in _LINE_ENDING.finditer(text, pos):
        texts.append(text[pos : match.start()])
        starts.append(pos)
        pos = match.end()
    if pos < len(text):
        texts.append(text[pos:])
        starts.append(pos)
    return texts, starts


@pytest.mark.parametrize("seed", range(8))
def test_passing_over_lines_finds_what_reading_each_line_finds(
    seed: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    _both_ways(list(_texts(seed, 1_500)), monkeypatch)


def test_long_stretches_read_the_same_both_ways(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Long runs of each construct, fences no later line closes among them."""
    chunks = (
        "Text of mine.\n\n- item one\n- item two\n\n```sh\nmake test\n```\n\n",
        "- item\n  ```\n  code\n\nAfter.\n\n",
        "<!-- a comment\n```\nstill a comment -->\n\n",
        "<div>\n```\n</div>\n\nText.\n\n",
        "````\n```\n````\n\n",
        f"~~~md\n{B}\nquoted\n{E}\n~~~\n\n",
        "    indented code\n\n",
        "`````never closed\n",
        "~~~~\n",
    )
    tails = ("", f"{B}\nrule\n{E}\n", f"{B}\nold\n", "```\n", "````x\n")
    rng = random.Random(7)  # noqa: S311 - seeded test input, not security
    texts = [
        "".join(rng.choice(chunks) * rng.randint(1, 30) for _ in range(6))
        + rng.choice(tails)
        for _ in range(300)
    ]
    _both_ways(texts, monkeypatch)


@pytest.mark.parametrize("seed", range(4))
def test_the_lines_and_marker_offsets_match_a_plain_split(seed: int) -> None:
    for text in _texts(100 + seed, 1_500):
        lines = materializer._Lines(text)
        texts, starts = _plain_split(text)
        assert lines.texts == texts, repr(text)
        marked = {
            index: start
            for index, (line, start) in enumerate(zip(texts, starts, strict=True))
            if "APOTHEM MANAGED BLOCK" in line and line.strip() in (B, E)
        }
        assert {line: found[0] for line, found in lines.marked.items()} == marked
        for line, (_, start) in lines.marked.items():
            assert lines.norm[start:].split("\n", 1)[0] == texts[line]
