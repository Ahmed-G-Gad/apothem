# SPDX-License-Identifier: MIT

"""Properties of the managed-block merge and removal over generated documents.

Each document is built from fragments an operator writes (prose, lists with
tabs, thematic breaks, fences of both kinds and lengths, fences left open,
closers with an info string, indented code, marker lines quoted in code,
together or alone), plus zero or one real block in the format v1.5.0 wrote,
appended as that release appended it. It may start with a byte order mark and
use CRLF or CR line endings. Merge (with and without an install record) and
removal must each return one of:

* the input, unchanged;
* the input with only the real block's span changed (replaced by a merge,
  taken out by a removal);
* the input plus one appended block, only when the document holds no real
  block, or when it holds one but no install record lists the file and the
  merge brings a new body (the merge cannot tell a block of Apothem's inside
  an operator's code block from a quoted pair without a record).

A re-install of the same body never adds a block, and a document whose
fragments hold no code, marker or fence above or below the real block always
has that block replaced.
"""

from __future__ import annotations

from dataclasses import dataclass

from hypothesis import given, settings
from hypothesis import strategies as st

from apothem.lib.harness_materializer import (
    APOTHEM_BLOCK_BEGIN,
    APOTHEM_BLOCK_END,
    complete_managed_block,
    merge_managed_block,
    remove_managed_block,
)

B = APOTHEM_BLOCK_BEGIN
E = APOTHEM_BLOCK_END

#: Fragments with no code and no marker: a real block among only these must
#: always be found.
_PLAIN = [
    "Some notes.",
    "# Heading",
    "- item\n- other item",
    "1. step\n2. next step",
    "-\tItem with a tab",
    "1.\tStep with a tab",
    "10)\tTenth",
    "* * *",
    "- - -",
    "___",
    "Text with `inline code` in it.",
]

#: Fragments that hold code, fences, or marker lines quoted in code.
_CODE = [
    "```\ncode\n```",
    "~~~\ncode\n~~~",
    "````\ncode\n````",
    "```md\ncode\n```",
    "~~~~text\ncode\n~~~~",
    "```bash\nmake\n```bash\nstill code\n```",
    "    indented code",
    "Para\n    continuation",
    f"```\n{B}\nquoted\n{E}\n```",
    f"~~~\n{B}\nquoted\n{E}\n~~~",
    f"````\n{B}\n```\n{E}\n````",
    f"    {B}\n    quoted\n    {E}",
    f"-\tExample:\n\n        {B}\n        quoted\n        {E}",
    f"* * *\n\n    {B}\n    quoted\n    {E}",
    f"```\n{B}\n```",
    f"~~~\n{E}\n~~~",
    f"```md\n{B}\n```",
    f"````\n{E}\n````",
    f"    {B}",
    f"    {E}",
    f"Para\n    {B}",
    "```\ncode\n```  ",
]

#: Fences left open: one may end the operator's text above the real block (an
#: install then appends the block after it) or end the document. Each is
#: generated only where no fragment holding a marker follows it, since a fence
#: left open turns a later fragment's quoted markers into bare ones.
_OPEN = ["```\nleft open", "~~~\nleft open", "````md\nleft open"]

#: Between two fragments, so a list item or indented code in one does not run
#: into the next: each fragment reads as it reads alone.
_JOIN = "\n\nNext.\n\n"

_BODIES = [
    "old rules",
    "rules\n```sh\nls\n```\nmore",
    "## Custom\n\n- Wrap like:\n```bash\nls",
    "rules\n~~~\nx\n~~~",
]
_NEW_BODY = "new rules\n- one\n- two"


def _v150_block(body: str) -> str:
    """Return the block v1.5.0 wrote for *body* (its sentinels defused)."""
    for sentinel in (B, E):
        body = body.replace(sentinel, "&lt;" + sentinel[1:])
    return f"{B}\n{body.strip()}\n{E}\n"


def _v150_append(existing: str, block: str) -> str:
    """Return *existing* with *block* appended as v1.5.0 appended it."""
    if not existing.strip():
        return block
    separator = "" if existing.endswith("\n") else "\n"
    return f"{existing}{separator}\n{block}"


def _eol(text: str, ending: str) -> str:
    return text.replace("\n", ending)


@dataclass(frozen=True)
class _Doc:
    """A generated document and where its real block sits, if it has one."""

    text: str
    real: tuple[int, int] | None
    body: str | None
    plain: bool


@st.composite
def _documents(draw: st.DrawFn) -> _Doc:
    plain_only = draw(st.booleans())
    pool = _PLAIN if plain_only else _PLAIN + _CODE
    before = draw(st.lists(st.sampled_from(pool), max_size=5))
    after = draw(st.lists(st.sampled_from(pool), max_size=4))
    if not plain_only:
        marked = any(B in fragment or E in fragment for fragment in after)
        if not marked and draw(st.booleans()):
            before.append(draw(st.sampled_from(_OPEN)))
        if draw(st.booleans()):
            after.append(draw(st.sampled_from(_OPEN)))
    has_real = draw(st.booleans())
    bom = "﻿" if draw(st.booleans()) else ""
    ending = draw(st.sampled_from(["\n", "\n", "\r\n", "\r"]))
    if not has_real:
        text = _JOIN.join(before + after) + "\n"
        if not text.strip():
            text = "Some notes.\n"
        return _Doc(bom + _eol(text, ending), None, None, plain_only)
    head = _JOIN.join(before) + ("\n" if before else "")
    tail = ("\n" + _JOIN.join(after) + "\n") if after else ""
    body = draw(st.sampled_from(_BODIES))
    written = _v150_append(head, _v150_block(body))
    core = written[: len(written) - 1]  # the block without its last newline
    start = len(bom) + len(_eol(written[: written.rindex(B)], ending))
    end = len(bom) + len(_eol(core, ending))
    text = bom + _eol(written + tail, ending)
    return _Doc(text, (start, end), body, plain_only)


def _appended(text: str, body: str) -> str:
    separator = "" if text.endswith("\n") else "\n"
    return f"{text}{separator}\n{_v150_block(body)}"


def _spliced(doc: _Doc, body: str) -> str:
    assert doc.real is not None
    start, end = doc.real
    return doc.text[:start] + _v150_block(body).rstrip("\n") + doc.text[end:]


def _removed(doc: _Doc, out: str) -> bool:
    """Return True when *out* is *doc* with only its real block taken out."""
    assert doc.real is not None
    start, end = doc.real
    head = doc.text[:start].rstrip("\r\n")
    tail = doc.text[end:].lstrip("\r\n")
    if not (head + tail).strip(" \t\r\n﻿"):
        return out == ""
    # The blank lines around the block collapse to one blank line; CR endings
    # next to it may stay (removal joins with LF), so only line endings and
    # blank lines may sit between the text before and after it.
    middle = out[len(head) : len(out) - len(tail)]
    return (
        len(out) >= len(head) + len(tail)
        and out.startswith(head)
        and out.endswith(tail)
        and not middle.strip()
    )


def _pairable(text: str) -> bool:
    """Return True when a BEGIN marker line in *text* has an END marker after it.

    Then some BEGIN marker's next marker line is an END marker: a marker pair
    the merge may take for Apothem's block.
    """
    return B in text and E in text[text.index(B) :]


def _check_merge(doc: _Doc, out: str, body: str, *, recorded: bool) -> None:
    if out == doc.text:
        return
    if doc.real is None:
        assert not (recorded and _pairable(doc.text)), "a recorded pair was passed"
        assert out == _appended(doc.text, body), "not a plain append"
        return
    if out == _spliced(doc, body):
        return
    assert not recorded, "a recorded file gained a block next to its own"
    assert body != doc.body, "a re-install added a second block"
    assert complete_managed_block(doc.text) is None
    assert out == _appended(doc.text, body), "not a plain append"


@settings(derandomize=True, max_examples=300, deadline=None)
@given(_documents())
def test_merge_and_remove_change_only_the_real_block(doc: _Doc) -> None:
    bodies = [_NEW_BODY] if doc.body is None else [_NEW_BODY, doc.body]
    for body in bodies:
        for recorded in (False, True):
            merged = merge_managed_block(doc.text, body, recorded=recorded)

            _check_merge(doc, merged, body, recorded=recorded)
            assert merge_managed_block(merged, body, recorded=recorded) == merged
            if doc.real is not None and doc.plain:
                assert merged == _spliced(doc, body), "a plain block was missed"

    removed = remove_managed_block(doc.text)

    if doc.real is None:
        assert removed == doc.text
    else:
        assert removed == doc.text or _removed(doc, removed)
        if doc.plain:
            assert removed != doc.text, "a plain block was not taken out"
