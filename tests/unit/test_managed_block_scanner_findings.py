# SPDX-License-Identifier: MIT

"""How Apothem finds its managed block next to code an operator wrote.

Each test is one input the review of the marker scanner found, run through
the library functions an install, update and uninstall use:

* a marker quoted in one code block never pairs with one outside it, so the
  text between two quoted markers is never cut (rule 1);
* a block inside a code block of the operator's that a later fence closes is
  left as it is when an install record lists the file, or when the same
  block is already there, and is named by :func:`uncertain_block` (the merge
  rule);
* a BEGIN marker whose END is hidden in code with another pair after it is
  no certain block (rule 3);
* a text with fences left open is read once, however many there are, and a
  block below them is still found; a fence Apothem's own block would leave
  open is closed when the block is written;
* a tab after a list bullet and a thematic break such as ``* * *`` read as
  CommonMark reads them, and so do the list items CommonMark does not open
  (one that would interrupt a paragraph, a setext underline, an empty item
  past its first blank line);
* those rules hold only for a line that stays in the list item holding the
  paragraph, so an item opens after a line of the item's text that goes on
  at the left margin, and after a block quote's line;
* :func:`uncertain_pairs` names every marker pair no rule can place, with
  where each of its marker lines reads, and reads nothing for code in a text
  with no marker pair.
"""

from __future__ import annotations

import pytest

from apothem.lib import harness_materializer
from apothem.lib.harness_materializer import (
    APOTHEM_BLOCK_BEGIN,
    APOTHEM_BLOCK_END,
    complete_managed_block,
    has_stray_begin,
    merge_managed_block,
    remove_managed_block,
    uncertain_block,
    wrap_managed_block,
)

B = APOTHEM_BLOCK_BEGIN
E = APOTHEM_BLOCK_END
OLD = wrap_managed_block("old body")
NEW = wrap_managed_block("new body")


def _appended(text: str, body: str = "new body") -> str:
    """Return *text* with the block for *body* appended, as a merge appends it."""
    separator = "" if text.endswith("\n") else "\n"
    return f"{text}{separator}\n{wrap_managed_block(body)}"


# --- rule 1: a marker quoted in code never pairs across code blocks ----------


@pytest.mark.parametrize(
    "quotes",
    [
        pytest.param(
            f"```md\n{B}\n```\n\nEnds with\n\n~~~md\n{E}\n~~~\n", id="```-~~~"
        ),
        pytest.param(f"````\n{B}\n````\n\nEnds with\n\n```\n{E}\n```\n", id="````-```"),
        pytest.param(f"```\n{B}\n```\n\nEnds with\n\n    {E}\n", id="fence-indented"),
        pytest.param(f"Some text\n    {B}\n\nEnds with\n\n```\n{E}\n```\n", id="para"),
    ],
)
def test_markers_quoted_in_two_code_blocks_leave_the_real_block_found(
    quotes: str,
) -> None:
    """cmo-1: the real block below two separately quoted markers is replaced."""
    text = f"Starts with\n\n{quotes}\n{OLD}\nExample:\n\n```sh\nls\n```\n"

    merged = merge_managed_block(text, "new body")

    assert merged == text.replace(OLD, NEW)
    assert merged.count(B) == text.count(B)
    assert remove_managed_block(text) == text.replace(f"\n{OLD}", "")


def test_a_lone_quoted_begin_does_not_pair_with_an_end_in_prose() -> None:
    """fuzz-1: the quoted BEGIN and the END below it stay; a block is added."""
    text = f"```\n{B}\n```\n\n{E}"

    assert merge_managed_block(text, "APX body") == _appended(text, "APX body")
    assert remove_managed_block(text) == text


def test_a_quoted_begin_and_an_indented_end_are_not_a_block() -> None:
    """cr-1: the first install appends, and uninstall keeps every line."""
    text = f"# Notes\nOpen:\n```\n{B}\n```\nClose:\n\n    {E}\n\nKeep.\n"

    merged = merge_managed_block(text, "new body")

    assert merged == _appended(text)
    assert remove_managed_block(merged) == text


@pytest.mark.parametrize(
    "text",
    [
        pytest.param(
            f"Start marker:\n~~~\n{B}\n~~~\nEnd marker:\n```\n{E}\n```\n", id="~~~-```"
        ),
        pytest.param(
            f"Start marker:\n```\n{B}\n```\nEnd marker:\n\n    {E}\n", id="```-indented"
        ),
        pytest.param(
            f"Start marker:\n````\n{B}\n````\nEnd marker:\n```\n{E}\n```\n",
            id="````-```",
        ),
    ],
)
def test_begin_and_end_quoted_in_separate_code_blocks_stay(text: str) -> None:
    """split-1: both examples and the prose between them are kept."""
    merged = merge_managed_block(text, "new body")

    assert merged == _appended(text)
    assert remove_managed_block(text) == text
    assert remove_managed_block(merged) == text


# --- the merge rule: a block inside an operator's code block -----------------

_INSIDE_A_FENCE = {
    "info-closer": (
        f"# Notes\n\n```bash\nmake\n```bash\n\n{OLD}\nExample:\n\n```sh\nls\n```\n",
        7,
        3,
    ),
    "closed-below": (f"Intro\n```\ncode\n\n{OLD}\nNew:\n```bash\nnpm ci\n```\n", 5, 2),
    "fence-added-later": (
        f"# Notes\n```bash\nnpm ci\n\n{OLD}\n## More\n```bash\nmake\n```\n",
        5,
        2,
    ),
}


@pytest.mark.parametrize(
    ("text", "begin", "fence"),
    list(_INSIDE_A_FENCE.values()),
    ids=list(_INSIDE_A_FENCE),
)
def test_a_recorded_block_inside_an_operator_fence_is_left_as_it_is(
    text: str, begin: int, fence: int
) -> None:
    """cmo-2, cr-2, unclosed-1: no second block, nothing cut, the place named."""
    assert merge_managed_block(text, "new body", recorded=True) == text
    assert merge_managed_block(text, "old body") == text
    assert merge_managed_block(text, "old body", recorded=True) == text
    assert remove_managed_block(text) == text
    assert complete_managed_block(text) is None
    assert uncertain_block(text) == (begin, fence)


def test_an_unrecorded_block_inside_an_operator_fence_gets_a_block_appended() -> None:
    """Without a record, the pair may be a quote of the operator's: append."""
    text, _, _ = _INSIDE_A_FENCE["closed-below"]

    merged = merge_managed_block(text, "new body")

    assert merged == _appended(text)
    assert uncertain_block(merged) is None


#: A block that lost its END marker (lines 2-3), above an example of the
#: markers you quote in a code block (lines 7-11).
_LOST_END_ABOVE_A_QUOTE = (
    f"# top\n{B}\nold apothem text\n\n## Notes\n\n```md\n{B}\nquoted\n{E}\n```\n"
    "my tail\n"
)


def test_a_recorded_file_whose_block_lost_its_end_is_left_as_it_is() -> None:
    """markers-2, regress-2: with a record, the pair quoted in code holds it back.

    Without a record the pair in code is text you quote, and the merge adds a
    fresh block after the text. With one, that pair may be Apothem's block in
    a code block of yours, and nothing tells the BEGIN marker outside code
    that starts no pair from a line of yours, so the file is left as it is.
    """
    unrecorded = merge_managed_block(_LOST_END_ABOVE_A_QUOTE, "new body")
    recorded = merge_managed_block(_LOST_END_ABOVE_A_QUOTE, "new body", recorded=True)

    assert unrecorded == _appended(_LOST_END_ABOVE_A_QUOTE)
    assert recorded == _LOST_END_ABOVE_A_QUOTE


def _indented(text: str) -> str:
    """Return *text* with each line indented four spaces: indented code."""
    return "".join(f"    {line}\n" for line in text.rstrip("\n").split("\n"))


#: Apothem's recorded block (the one for "old body") read as code of yours,
#: beside a BEGIN marker outside code that starts no pair: a line of yours, or
#: what is left of an older block.
_RECORDED_BLOCK_IN_CODE = {
    "lone-begin-above-a-fence": (
        f"# Notes\n{B}\nmy heading line\n\n```\n{OLD}```\n\nafter\n"
    ),
    "lone-begin-below-a-fence": f"# Notes\n\n```\n{OLD}```\n\n{B}\nmy line\n",
    "indented-block": f"# Notes\n\n{_indented(OLD)}\n{B}\nmine\n",
    # A code block of yours left open above the block, closed by the opening
    # fence of the example below it: the quoted BEGIN line reads outside code.
    "fence-closed-by-a-quote": (
        f"My notes:\n\n```sh\nmake test\n\n{OLD}\n## How the block starts\n\n"
        f"```\n{B}\n```\n"
    ),
}


@pytest.mark.parametrize(
    "text", list(_RECORDED_BLOCK_IN_CODE.values()), ids=list(_RECORDED_BLOCK_IN_CODE)
)
def test_a_recorded_block_in_code_beside_a_lone_begin_gets_no_second_block(
    text: str,
) -> None:
    """regress-2, advice-1, cmark-1, docs-2: a changed body added a second block.

    The old block stayed in the code block, where the tool still read it, and
    an uninstall then took out only the new one. The record says the pair in
    code may be Apothem's block, whatever the BEGIN marker outside code is.
    """
    assert merge_managed_block(text, "new body", recorded=True) == text


@pytest.mark.parametrize(
    "text",
    [
        pytest.param(f"# top\n\n```md\n{B}\nquoted\n{E}\n```\n", id="no-lost-end"),
        pytest.param(
            f"# top\n{B}\nold text\n\n```md\n{B}\nquoted\n```\n{E}\n",
            id="an-end-outside-code",
        ),
    ],
)
def test_a_recorded_file_whose_pair_may_be_the_block_is_still_held_back(
    text: str,
) -> None:
    """A pair in code, or one with a marker line outside code, may be the block.

    Apothem's block in a code block of yours, or one whose END marker you left
    outside the code block, is no quote: the record keeps the file as it is.
    """
    assert merge_managed_block(text, "new body", recorded=True) == text


#: Two whole blocks: an old block whose END marker came back above the block
#: an update appended below it.
_TWO_BLOCKS = f"# top\n{B}\nold body\n{E}\n\nmy text\n\n{B}\nnew body\n{E}\n"


@pytest.mark.parametrize(
    "text",
    [
        pytest.param(_TWO_BLOCKS, id="old-and-new"),
        pytest.param(f"Notes:\n{B}\nmy example\n{E}\n\n{OLD}", id="your-pair-above"),
        pytest.param(f"{OLD}\n{OLD}", id="pasted-twice"),
    ],
)
def test_a_file_with_two_whole_blocks_is_left_as_it_is(text: str) -> None:
    """lifecycle-2: one block per file, so which to replace is not certain.

    An update used to replace the first and leave the second, so the tool
    loaded two Apothem blocks, one of them stale.
    """
    for recorded in (False, True):
        assert merge_managed_block(text, "newer body", recorded=recorded) == text
    frontmatter = merge_managed_block(text, "---\nalwaysApply: true\n---\nrules")
    assert frontmatter == text


def test_whole_blocks_names_each_block_by_its_lines() -> None:
    assert harness_materializer.whole_blocks(_TWO_BLOCKS) == [(2, 4), (8, 10)]
    assert harness_materializer.whole_blocks(f"x\n{OLD}") == [(2, 4)]
    assert harness_materializer.whole_blocks("no block\n") == []


@pytest.mark.parametrize(
    "body",
    [
        "rules\n```sh\nls\n```\nmore",
        "rules\n```sh\nls",
        "rules\n~~~\nls\n~~~\n````\nx",
    ],
    ids=["balanced", "unbalanced", "mixed"],
)
def test_reinstalling_a_body_with_fences_never_adds_a_second_block(body: str) -> None:
    """Priority 3: a re-install over every such shape keeps one block."""
    for operator in ("```\nleft open\n", "```\nleft open\n\n", "Intro\n```\ncode\n"):
        for tail in ("", "\nNew:\n```bash\nnpm ci\n```\n"):
            text = merge_managed_block(operator, body) + tail

            again = merge_managed_block(text, body)

            assert again.count(B) == 1, (operator, tail)
            assert merge_managed_block(again, body) == again


# --- rule 3: a BEGIN whose END is hidden in code, with a pair after it ------


def test_a_stray_begin_whose_end_is_quoted_in_code_is_no_block() -> None:
    """residual-1: nothing is cut; the stray marker is reported."""
    text = f"{B}\nop text A\n```\n{E}\n```\nop text B\n\n{OLD}"

    assert merge_managed_block(text, "new body") == text
    assert merge_managed_block(text, "new body", recorded=True) == text
    assert remove_managed_block(text) == text
    assert has_stray_begin(text)
    assert uncertain_block(text) == (1, 3)


#: A block an earlier release wrote for a profile rule that opens a code block
#: and never closes it: its END marker reads as code.
_OPEN_BODY_BLOCK = f"{B}\nrules\n```bash\nls\n{E}\n"


def test_a_body_with_an_open_fence_and_no_pair_after_it_is_one_block() -> None:
    """Rule 3 needs a pair after the block: alone, the block is replaced."""
    text = "KEEP top\n\n" + _OPEN_BODY_BLOCK + "after\n"

    merged = merge_managed_block(text, "new body")

    assert merged == text.replace(_OPEN_BODY_BLOCK, NEW)


def test_a_body_fence_an_operator_closer_below_ends_is_still_one_block() -> None:
    """tests-4: a closer of yours below the block is no marker pair after it."""
    block = _OPEN_BODY_BLOCK
    text = "KEEP top\n\n" + block + "after\n```\nmore\n"

    merged = merge_managed_block(text, "new body", recorded=True)

    assert merged == text.replace(block, NEW)
    assert not has_stray_begin(text)
    assert uncertain_block(text) is None


@pytest.mark.parametrize(
    ("body", "closer"),
    [
        pytest.param("rules\n```sh\nnpm test", "```", id="backticks"),
        pytest.param("rules\n~~~~md\nx", "~~~~", id="tildes"),
        pytest.param("rules\n````md\n```\nx", "````", id="longer-run"),
        pytest.param("- Run:\n  ```sh\n  npm test", "  ```", id="in-a-list-item"),
    ],
)
def test_a_fence_the_body_leaves_open_is_closed_in_the_block(
    body: str, closer: str
) -> None:
    """markers-4: Apothem's own END marker never reads as code.

    The closer is a run of the fence's character, as long as its opener, at
    the column of the list item the fence sits in.
    """
    assert wrap_managed_block(body) == f"{B}\n{body}\n{closer}\n{E}\n"


def test_a_body_whose_fences_close_gets_no_closer() -> None:
    body = "rules\n```sh\nls\n```\nmore"

    assert wrap_managed_block(body) == f"{B}\n{body}\n{E}\n"


def test_a_reinstall_over_a_block_an_earlier_release_wrote_adds_no_second_block() -> (
    None
):
    """markers-4: that block left the rule's code block open; this one closes it.

    The block an earlier release wrote for the same body still counts as the
    block the install writes, here inside a code block of yours with no
    install record, so the re-install adds no second block.
    """
    body = "## Custom\n\n- Wrap like:\n```bash\nls"
    text = f"```\nleft open\n\n{B}\n{body}\n{E}\n\n```\nleft open\n"

    assert merge_managed_block(text, body) == text


def test_a_block_whose_rule_opens_a_fence_stays_whole_beside_a_quoted_pair() -> None:
    """markers-4: update and uninstall still find it with your example below.

    Before, the rule's code block hid the END marker, and the example's marker
    pair after it made the block unclear: no update refreshed it and no
    uninstall took it out.
    """
    block = wrap_managed_block("## Apothem\n\n- Run:\n```sh\nnpm test")
    example = f"\n## Example\n\n```md\n{B}\nq\n{E}\n```\n"
    text = f"# mine\n\n{block}{example}"

    assert complete_managed_block(text) == block.rstrip("\n")
    assert uncertain_block(text) is None
    for recorded in (False, True):
        assert merge_managed_block(text, "new body", recorded=recorded) == (
            text.replace(block, NEW)
        )
    assert remove_managed_block(text) == f"# mine\n{example}"


def test_a_stray_begin_takes_an_end_quoted_in_code_below_it_as_its_end() -> None:
    """markers-1, pinned: with no marker pair after them, they are one block.

    A BEGIN marker that lost its END marker pairs with the next marker line
    even when that END marker is quoted in code, so a merge replaces the text
    between them and a removal takes it out. The reading cannot tell this
    from a block an earlier release wrote whose body left a fence open (the
    last test above), which it must still find; see the docstring of
    ``_marker_lines``.
    """
    text = (
        f"# My notes\n\n{B}\nold\n## My notes on Apothem\n\nIt closes its block "
        f"with:\n```\n{E}\n```\nKeep this section.\n"
    )
    begin = text.index(B)
    end = text.index(E) + len(E)

    assert complete_managed_block(text) == text[begin:end]
    assert not has_stray_begin(text)
    assert uncertain_block(text) is None


def test_a_stray_begin_whose_end_sits_in_a_fence_left_open_cuts_nothing() -> None:
    """cmark-8: rule 3 is decided before a fence left open is read as text."""
    text = f"{B}\nop text A\n```\n{E}\nop text B\n\n{OLD}"

    for recorded in (False, True):
        assert merge_managed_block(text, "new body", recorded=recorded) == text
    assert remove_managed_block(text) == text
    assert has_stray_begin(text)
    assert uncertain_block(text) == (1, 3)


# --- fences left open: one reading, however many ------------------------------


def test_a_text_with_fences_left_open_is_read_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """markers-5: one reading, and the block below the fences is replaced."""
    calls: list[int] = []
    scan = harness_materializer._scan

    def counted(*args: object) -> object:
        calls.append(1)
        return scan(*args)  # type: ignore[arg-type]

    monkeypatch.setattr(harness_materializer, "_scan", counted)
    text = "```a\n" * 2000 + OLD

    merged = merge_managed_block(text, "new body", recorded=True)

    assert merged == text.replace(OLD, NEW)
    assert len(calls) == 1


def _closers_with_info(count: int) -> str:
    """Return *count* code examples whose closer carries an info string."""
    return "\n".join(f"```bash\nmake step{i}\n```bash\n" for i in range(count))


@pytest.mark.parametrize(
    "above",
    [
        pytest.param("```a\n" * 8, id="eight"),
        pytest.param("```a\n" * 9, id="nine"),
        pytest.param("```py\nx\n" * 40, id="forty"),
        pytest.param(_closers_with_info(5) + "\n", id="closers-with-info"),
    ],
)
def test_a_block_below_fences_left_open_is_found(above: str) -> None:
    """markers-5: from the ninth such fence on, the block used to read as code.

    Each update then added another block, or, with an install record, never
    refreshed the one there.
    """
    text = above + OLD

    assert complete_managed_block(text) == OLD.rstrip("\n")
    assert uncertain_block(text) is None
    for recorded in (False, True):
        merged = merge_managed_block(text, "new body", recorded=recorded)
        assert merged == text.replace(OLD, NEW), recorded
    assert remove_managed_block(text) == above.rstrip("\n") + "\n"


def test_updates_below_fences_left_open_keep_one_block() -> None:
    """markers-5: each new body replaces the block; none is stacked."""
    text = "```py\nx\n" * 9 + "\n" + OLD

    for body in ("body one", "body two", "body three"):
        for recorded in (False, True):
            text = merge_managed_block(text, body, recorded=recorded)
            assert text.count(B) == 1, (body, recorded)
            assert body in text


def test_rule_3_still_reads_a_fence_left_open_below_its_begin_marker() -> None:
    """A fence left open still hides an END marker where rule 3 reads it.

    Read as text, the fence would make a whole block of the pair your BEGIN
    marker starts with the END marker quoted below it. The nine tilde fences
    above it, which nothing closes, read as text as before.
    """
    text = "~~~a\n" * 9 + f"{B}\nop text A\n```\n{E}\nop text B\n\n{OLD}"

    for recorded in (False, True):
        assert merge_managed_block(text, "new body", recorded=recorded) == text
    assert remove_managed_block(text) == text
    assert uncertain_block(text) == (10, 12)


@pytest.mark.parametrize(
    "text",
    [
        pytest.param(
            OLD
            + "\nExamples:\n\n"
            + "```bash\nmake\n```bash\n\n" * 4
            + "```bash\nls\n",
            id="oracle-1",
        ),
        pytest.param(
            f"{B}\nold body\n{E}\n\n" + "Run:\n\n```bash\nnpm ci\n```bash\n\n" * 5,
            id="cmark-2",
        ),
        pytest.param(OLD + "\n# My notes\n\n" + _closers_with_info(5), id="diff-4a"),
        pytest.param(
            "# Notes\n\n"
            + _closers_with_info(4)
            + "\n"
            + OLD
            + "\n```bash\nx\n```bash\n",
            id="diff-4d",
        ),
    ],
)
def test_a_block_above_fences_left_open_is_still_found(text: str) -> None:
    """oracle-1, cmark-2, diff-4: fences that open after a block cannot hide it."""
    block = complete_managed_block(text)
    removed = remove_managed_block(text)

    for recorded in (False, True):
        merged = merge_managed_block(text, "new body", recorded=recorded)
        assert merged.count(B) == 1, recorded
        assert "old body" not in merged
    assert block is not None
    assert B not in removed
    assert removed.replace("\n", "") == text.replace(block, "").replace("\n", "")
    assert uncertain_block(text) is None
    assert not has_stray_begin(text)


def test_a_frontmatter_block_above_fences_left_open_is_still_found() -> None:
    """oracle-1: the frontmatter-first block is replaced, not stacked."""
    body = "---\nalwaysApply: true\n---\nnew rules"
    old = "---\nalwaysApply: true\n---\n" + wrap_managed_block("old rules")
    text = old + "\nExamples:\n\n" + "```bash\nmake\n```bash\n\n" * 4 + "```bash\nls\n"

    for recorded in (False, True):
        merged = merge_managed_block(text, body, recorded=recorded)
        assert merged.count(B) == 1, recorded
        assert "old rules" not in merged


# --- a tab after a list bullet -----------------------------------------------


@pytest.mark.parametrize("bullet", ["-\t", "- \t", "1.\t", "10)\t"])
def test_a_tab_after_a_bullet_sets_the_content_column_at_four(bullet: str) -> None:
    """cmo-3 / cr-4: eight columns is code in the item, so the quote stays."""
    quoted = f"        {B}\n        quoted\n        {E}\n"
    text = f"{bullet}Example:\n\n{quoted}\nMore.\n\n{OLD}"

    merged = merge_managed_block(text, "new body")

    assert merged == text.replace(OLD, NEW)
    assert quoted in remove_managed_block(text)


def test_a_block_one_tab_under_a_numbered_item_is_the_block() -> None:
    """cmo-3: one tab reaches the item's content column, so it is replaced."""
    text = f"1.\tFirst step\n\n\t{B}\n\told body\n\t{E}\n"

    merged = merge_managed_block(text, "new body")

    assert merged.count(B) == 1
    assert "old body" not in merged


# --- a thematic break --------------------------------------------------------


@pytest.mark.parametrize("rule", ["* * *", "- - -", "_ _ _", "***", "-  -  -"])
def test_a_thematic_break_is_not_a_list(rule: str) -> None:
    """cmo-4: an indented example after the break is code and stays."""
    example = f"    {B}\n    example body\n    {E}\n"
    text = f"# Notes\n\n{rule}\n\n{example}\nMore prose.\n\n{OLD}"

    merged = merge_managed_block(text, "new body")

    assert merged == text.replace(OLD, NEW)
    assert example in remove_managed_block(text)


# --- list items CommonMark does not open --------------------------------------


def _quote_stays(text: str, quote: str) -> None:
    """Assert the merge replaces only OLD in *text* and removal keeps *quote*."""
    for recorded in (False, True):
        assert merge_managed_block(text, "new body", recorded=recorded) == text.replace(
            OLD, NEW
        ), recorded
    assert quote in remove_managed_block(text)


@pytest.mark.parametrize("item", ["10.\t", "10. ", "2. ", "10)\t"])
def test_an_item_not_numbered_one_does_not_interrupt_a_paragraph(item: str) -> None:
    """oracle-3 (a): the paragraph goes on, so the quote after it is code."""
    quote = f"    {B}\n    my quoted example\n    {E}\n"
    text = f"Notes for the team.\n{item}Set up:\n\n{quote}\nMore.\n\n{OLD}"

    _quote_stays(text, quote)


def test_a_dash_under_a_paragraph_opens_no_item_before_a_fence() -> None:
    """oracle-3 (b): a setext underline, then a fence that holds the quote."""
    quote = f"  ```md\n{B}\nmy quoted example\n{E}\n```\n"
    text = f"Setup\n-\n{quote}\n{OLD}"

    _quote_stays(text, quote)


def test_a_closer_after_an_item_that_cannot_interrupt_opens_no_fence() -> None:
    """oracle-3 (c): the closer ends the fence, so the block below is found."""
    text = (
        "Steps go on:\n3. Run the tests\n   ```\n   pytest\n```\n\n"
        f"{OLD}\nExample:\n\n```sh\nls\n```\n"
    )

    for recorded in (False, True):
        merged = merge_managed_block(text, "new body", recorded=recorded)
        assert merged == text.replace(OLD, NEW), recorded


@pytest.mark.parametrize(
    "underline", ["-", " -", "  -", "   -", "- ", "-\t", "-\n", "--", "=", "==="]
)
def test_a_setext_underline_ends_the_paragraph_and_opens_no_item(
    underline: str,
) -> None:
    """cmark-4: the indented quote under the heading is code."""
    quote = f"    {B}\n    quoted example\n    {E}\n"
    text = f"Para\n{underline}\n{quote}\nMore.\n\n{OLD}"

    _quote_stays(text, quote)


@pytest.mark.parametrize(
    "bullet", ["-", "*", "+", "1.", "10)", "-\t", "- ", " -", "  *"]
)
def test_an_empty_item_ends_at_its_first_blank_line(bullet: str) -> None:
    """cmark-5: the item holds nothing, so the indented quote is code."""
    quote = f"    {B}\n    my example\n    {E}\n"
    text = f"{bullet}\n\n{quote}\n{OLD}"

    _quote_stays(text, quote)


def test_an_item_that_cannot_interrupt_a_paragraph_keeps_a_tab_indented_quote() -> None:
    """cmark-6: '2.' after a paragraph line is text, and so is the quote."""
    quote = f"\t{B}\n\tmy example\n\t{E}\n"
    text = f"Steps\n2.\tRun it\n{quote}\n{OLD}"

    _quote_stays(text, quote)


def test_a_fence_after_an_item_that_cannot_interrupt_holds_the_quote() -> None:
    """cmark-6: the fence is not in a list item, so the column-0 quote is code."""
    quote = f"   ```\n{B}\nmy example\n{E}\n   ```\n"
    text = f"Steps\n2. Run:\n{quote}\n{OLD}"

    _quote_stays(text, quote)


@pytest.mark.parametrize(
    "lead", ["# Heading\n-\n", "# Heading\n2. step\n", "- item\n-\n", "1. a\n2. b\n"]
)
def test_after_a_heading_or_an_item_a_new_item_still_opens(lead: str) -> None:
    """A heading leaves no paragraph open, and a sibling item is no interrupt.

    So the item opens, and the pair indented four columns sits inside it, as
    marker lines outside code (CommonMark reads them as HTML blocks).
    """
    pair = f"    {B}\n    my text\n    {E}\n"
    text = f"{lead}{pair}\n{OLD}"

    assert complete_managed_block(text) == f"{B}\n    my text\n    {E}"


@pytest.mark.parametrize("bullet", ["*", "+", "1.", "1)"])
def test_an_empty_item_right_under_a_paragraph_line_opens_nothing(bullet: str) -> None:
    """tests-1: an empty item cannot interrupt a paragraph, so the quote is text."""
    quote = f"    {B}\n    quoted\n    {E}\n"
    text = f"Para\n{bullet}\n{quote}\n{OLD}"

    _quote_stays(text, quote)


def test_a_setext_underline_leaves_the_quote_under_it_in_indented_code() -> None:
    """regress-3, tests-2: the underline ends the paragraph, so this is code."""
    text = f"Para\n-\n    {B}\n    quoted\n    {E}\n"

    assert _pairs(text) == [(3, "INDENTED", None, 5, "INDENTED", None, False)]


def test_an_item_opens_after_a_setext_underline() -> None:
    """regress-3, tests-2: '2. x' under the heading holds the pair, outside code."""
    text = f"Para\n-\n2. x\n    {B}\n    quoted\n    {E}\n\n{B}\nreal\n{E}\n"

    assert complete_managed_block(text) == f"{B}\n    quoted\n    {E}"


def test_only_the_first_bullet_on_a_line_is_held_to_the_interrupt_rules() -> None:
    """tests-5: '2.' after '- ' opens a list in the item, not under the paragraph."""
    text = f"Para\n- 2. step\n\n      {B}\n      quoted\n      {E}\n\n{OLD}"

    assert complete_managed_block(text) == f"{B}\n      quoted\n      {E}"


def test_an_empty_item_whose_text_starts_on_the_next_line_stays_open() -> None:
    """tests-6: once the item holds text, a blank line does not end it."""
    text = f"-\n  text\n\n    {B}\n    quoted\n    {E}\n\n{OLD}"

    assert complete_managed_block(text) == f"{B}\n    quoted\n    {E}"


# --- a line left of the list item that holds the paragraph --------------------


def test_the_quote_in_the_item_after_a_wrapped_one_stays() -> None:
    """cmark-1: '2.' after a line that goes on at the margin opens an item.

    So its fence ends with the item, the quoted pair is code in it, and the
    first install appends its block after the example.
    """
    text = (
        "# Agent notes\n\n1. Install Apothem and make sure the apothem command is on "
        "your PATH before\nyou run the next step.\n2. Apothem writes its rules "
        f"between two marker lines, like this:\n   ```md\n   {B}\n   (generated "
        f"rules)\n   {E}\n\nThen run apothem install.\n"
    )

    assert merge_managed_block(text, "new body") == _appended(text)
    assert merge_managed_block(text, "new body", recorded=True) == text
    assert remove_managed_block(text) == text
    assert _pairs(text) == [(7, "FENCE", 6, 9, "FENCE", 6, False)]


def test_a_block_below_the_item_after_a_wrapped_one_is_found() -> None:
    """cmark-2: the fence of item 2 ends with the item, so the block is outside it."""
    text = (
        "# Setup\n\n1. Install the tool and make sure it is on your PATH before you "
        "go\non to the next step.\n2. Build it:\n   ```sh\n   make\n\n"
        f"{OLD}\n## Debugging\n\n```sh\napothem doctor\n```\n"
    )

    for recorded in (False, True):
        merged = merge_managed_block(text, "new body", recorded=recorded)
        assert merged == text.replace(OLD, NEW), recorded
    assert remove_managed_block(text) == text.replace(f"\n{OLD}", "")
    assert uncertain_block(text) is None


@pytest.mark.parametrize(
    ("first", "item"),
    [("-", "-"), ("*", "*"), ("1.", "2."), ("1)", "1)"), ("1.", "2. Build it:")],
)
def test_after_a_line_at_the_margin_the_next_item_opens(first: str, item: str) -> None:
    """cmark-2: an empty item and one not numbered 1 open there too.

    The line at the margin goes on the paragraph of the first item, inside
    that item, so the next line is no line under a paragraph.
    """
    pad = " " * (len(item.split(" ")[0]) + 1)
    text = (
        f"{first} Install the tool before you go\non to the next step.\n{item}\n"
        f"{pad}```sh\n{pad}make\n\n{OLD}\nMore:\n\n```sh\nls\n```\n"
    )

    for recorded in (False, True):
        merged = merge_managed_block(text, "new body", recorded=recorded)
        assert merged == text.replace(OLD, NEW), recorded
    assert remove_managed_block(text) == text.replace(f"\n{OLD}", "")


def test_an_item_in_the_wrapped_item_s_column_still_goes_on_its_paragraph() -> None:
    """'   2. step' stays in item 1, under its paragraph, so it opens no item."""
    quote = f"       {B}\n       quoted\n       {E}\n"
    text = (
        "1. Install the tool before you go\non to the next step.\n   2. step\n\n"
        f"{quote}\n{OLD}"
    )

    _quote_stays(text, quote)


@pytest.mark.parametrize(
    "lead",
    [
        pytest.param("> Note: run the setup first.\n", id="block-quote"),
        pytest.param("Setup\n- Install the tool first.\n", id="item-under-paragraph"),
    ],
)
def test_an_item_after_a_line_outside_the_paragraph_s_item_opens(lead: str) -> None:
    """cmark-1: no paragraph goes on into '2. Example:', so its fence holds the quote.

    A block quote's paragraph takes no line without its ">", and the item
    that interrupted 'Setup' holds the paragraph after its bullet.
    """
    text = (
        f"{lead}2. Example:\n   ```md\n   {B}\n   (generated rules)\n   {E}\n\n"
        "Then run apothem install.\n"
    )

    assert merge_managed_block(text, "new body") == _appended(text)
    assert merge_managed_block(text, "new body", recorded=True) == text
    assert remove_managed_block(text) == text


def test_a_fence_ends_the_paragraph_even_when_its_item_ends_the_fence() -> None:
    """The line after such a fence starts a paragraph, and '2. Then:' goes on it."""
    quote = f"    {B}\n    quoted\n    {E}\n"
    text = f"- Build it:\n  ```sh\n  make\nThat builds it.\n2. Then:\n{quote}\n{OLD}"

    _quote_stays(text, quote)


@pytest.mark.parametrize(
    "html",
    [
        "<!-- note -->",
        "<!-- markdownlint-disable MD029 -->",
        "<?php echo 1; ?>",
        "<!DOCTYPE html>",
        "<![CDATA[ x ]]>",
        "<pre>x</pre>",
    ],
)
def test_an_html_line_that_ends_its_block_leaves_no_paragraph_open(html: str) -> None:
    """markers-3: so '2.' under it opens an item, and its fence holds the quote.

    CommonMark ends such an HTML block on the line it starts; the reading
    used to take that line for paragraph text, which '2.' cannot interrupt,
    so the fence on the '2.' line opened nothing and the quoted pair read as
    Apothem's block.
    """
    quote = f"2. ```md\n   {B}\n   quoted\n   {E}\n   ```\n"
    text = f"{html}\n{quote}\n{OLD}"

    _quote_stays(text, quote)


def test_an_html_line_inside_a_block_tag_s_html_starts_nothing() -> None:
    """Lines under a block tag such as <div> are raw HTML up to a blank line.

    CommonMark reads every line there as HTML, the marker lines included, so
    an HTML comment there does not end a paragraph and open the item below.
    """
    text = f"<div>\n<!-- note -->\n2. ```md\n   {B}\n   quoted\n   {E}\n   ```\n"

    assert complete_managed_block(text) is not None


# --- every pair no rule can place, with where it reads ------------------------


def _pairs(text: str) -> list[tuple[int, str, int | None, int, str, int | None, bool]]:
    """Return each uncertain pair as lines, places, fences and the rule-3 flag."""
    return [
        (
            pair.begin.line,
            pair.begin.place.name,
            pair.begin.fence,
            pair.end.line,
            pair.end.place.name,
            pair.end.fence,
            pair.split,
        )
        for pair in harness_materializer.uncertain_pairs(text)
    ]


_EXAMPLE = f"# Notes\n\n```md\n{B}\nexample\n{E}\n```\n\n"

_WHERE = {
    "fenced-around": (
        f"Intro\n```\ncode\n\n{OLD}New:\n```bash\nnpm ci\n```\n",
        [(5, "FENCE", 2, 7, "FENCE", 2, False)],
    ),
    "residual-1": (
        f"{B}\nop text A\n```\n{E}\n```\nop text B\n\n{OLD}",
        [
            (1, "OUTSIDE", None, 4, "FENCE", 3, True),
            (8, "OUTSIDE", None, 10, "OUTSIDE", None, False),
        ],
    ),
    "two-code-blocks": (
        f"Start marker:\n```\n{B}\n```\nEnd marker:\n```\n{E}\n```\n",
        [(3, "FENCE", 2, 7, "FENCE", 6, False)],
    ),
    "indented": (
        f"Intro\n\n    {B}\n    old\n    {E}\n",
        [(3, "INDENTED", None, 5, "INDENTED", None, False)],
    ),
    "paragraph": (
        f"Example of the markers:\n    {B}\n    quoted\n    {E}\n",
        [(2, "PARAGRAPH", None, 4, "PARAGRAPH", None, False)],
    ),
    "rule-3-indented-end": (
        f"{B}\n    {E}\n\n{OLD}",
        [
            (1, "OUTSIDE", None, 2, "INDENTED", None, True),
            (4, "OUTSIDE", None, 6, "OUTSIDE", None, False),
        ],
    ),
    "rule-3-paragraph-end": (
        f"{B}\nsome text\n    {E}\n\n{B}\nreal\n{E}\n",
        [
            (1, "OUTSIDE", None, 3, "PARAGRAPH", None, True),
            (5, "OUTSIDE", None, 7, "OUTSIDE", None, False),
        ],
    ),
    "example-above-a-fenced-block": (
        f"{_EXAMPLE}My notes:\n\n```\nmake test\n\n{OLD}\nMore:\n\n```sh\nls\n```\n",
        [
            (4, "FENCE", 3, 6, "FENCE", 3, False),
            (14, "FENCE", 11, 16, "FENCE", 11, False),
        ],
    ),
    "example-then-rule-3": (
        f"{_EXAMPLE}{B}\nop text A\n```\n{E}\n```\n\n{OLD}",
        [
            (4, "FENCE", 3, 6, "FENCE", 3, False),
            (9, "OUTSIDE", None, 12, "FENCE", 11, True),
            (15, "OUTSIDE", None, 17, "OUTSIDE", None, False),
        ],
    ),
}


@pytest.mark.parametrize(("text", "expected"), list(_WHERE.values()), ids=list(_WHERE))
def test_every_pair_no_rule_can_place_is_named_with_where_it_reads(
    text: str, expected: list[tuple[int, str, int | None, int, str, int | None, bool]]
) -> None:
    """oracle-2, cmark-3, diff-3, docs-1, oracle-4, diff-6, docs-4."""
    assert _pairs(text) == expected


def test_a_text_with_a_whole_block_has_no_uncertain_pair() -> None:
    text = f"{_EXAMPLE}{OLD}"

    assert harness_materializer.uncertain_pairs(text) == []


def test_a_text_with_no_marker_pair_is_not_read_for_code(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """diff-3: an install check reads every anchor; one with no pair costs nothing."""
    readings: list[str] = []
    read = harness_materializer._read

    def counted(text: str) -> object:
        readings.append(text)
        return read(text)

    monkeypatch.setattr(harness_materializer, "_read", counted)
    text = "```bash\nnpm ci\n" * 9 + f"{B}\nold rules, no END marker\n"

    assert harness_materializer.uncertain_pairs(text) == []
    assert uncertain_block(text) is None
    assert readings == []


# --- the frontmatter merge path ----------------------------------------------

_FRONTMATTER_BODY = "---\nalwaysApply: true\n---\nnew rules"


def test_a_recorded_unclear_file_with_a_frontmatter_body_is_left_as_it_is() -> None:
    """tests-5 (a): no frontmatter-first block is stacked on the unclear one."""
    text = f"Intro\n```\ncode\n\n{B}\nold rules\n{E}\nNew:\n```bash\nnpm ci\n```\n"

    assert merge_managed_block(text, _FRONTMATTER_BODY, recorded=True) == text


def test_a_frontmatter_block_whose_end_rule_3_hides_is_left_as_it_is() -> None:
    """tests-5 (b): rule 3 holds the file back on the frontmatter path too.

    The block is one an earlier release wrote for a rule that opens a code
    block and never closes it.
    """
    old = f"---\nalwaysApply: true\n---\n{_OPEN_BODY_BLOCK}"
    text = old + f"\nExample:\n\n```\n{B}\nquoted\n{E}\n```\n"

    assert merge_managed_block(text, _FRONTMATTER_BODY) == text


# --- what the docstrings say -------------------------------------------------


def test_a_text_with_only_a_bom_comes_back_unchanged() -> None:
    """cr-10: no block, so remove changes nothing, the byte order mark included."""
    assert remove_managed_block("\ufeff") == "\ufeff"


# --- the line that closes a code block around a pair --------------------------


def _code_lines(text: str) -> str:
    """Return every line a CommonMark reading of *text* shows as code, joined."""
    from markdown_it import MarkdownIt

    tokens = MarkdownIt("commonmark").parse(text)
    return "".join(t.content for t in tokens if t.type in {"fence", "code_block"})


def _move_line(text: str, line: int, above: int) -> str:
    """Return *text* with its 1-based line *line* moved up above line *above*."""
    lines = text.split("\n")
    moved = lines.pop(line - 1)
    lines.insert(above - 1, moved)
    return "\n".join(lines)


def _add_closer(text: str, pair: harness_materializer.UncertainPair) -> str:
    """Return *text* with a closing line added above *pair*'s BEGIN marker.

    The line is indented as the line that opens the code block holding the
    pair, so it closes that code block inside a list item too.
    """
    lines = text.split("\n")
    assert pair.begin.fence is not None
    opener = lines[pair.begin.fence - 1]
    indent = opener[: len(opener) - len(opener.lstrip())]
    at = pair.begin.line - 1
    return "\n".join([*lines[:at], f"{indent}```", *lines[at:]])


def _code_line_numbers(text: str) -> set[int]:
    """Return the 0-based lines a CommonMark reading of *text* shows as code."""
    from markdown_it import MarkdownIt

    code: set[int] = set()
    for token in MarkdownIt("commonmark").parse(text):
        if token.type in {"fence", "code_block"} and token.map is not None:
            code.update(range(*token.map))
    return code


def _read_differently(text: str, fixed: str, lines: dict[int, int]) -> list[str]:
    """Return the lines of *text* that read as code in one text and not the other.

    *lines* maps each 0-based line of *text* to compare to its line in *fixed*.
    """
    before, after = _code_line_numbers(text), _code_line_numbers(fixed)
    split = text.split("\n")
    return [split[at] for at, to in lines.items() if (at in before) != (to in after)]


#: Apothem's block (lines 6 to 8) inside a code block of yours that opens at
#: line 3 and that a fence closes at line 9, below it, then text of yours.
_WRAPPED = f"My notes:\n\n```\nmake test\n\n{OLD}```\n\nafter fence\n\nmy tail\n"

#: The same with a code block of yours further down: added, a closing line
#: above the block would turn line 9 into an opener that line 11 closes, so
#: the opener on line 13 would run to the end of the file.
_CASCADE = f"My notes:\n\n```\nmake test\n\n{OLD}```\n\n```\nlater\n```\nmy tail\n"

#: The block in your code block, closed at line 9, and then text and code
#: examples of yours. Added, a closing line above the block turns line 9 into
#: an opener that the last line of your first example closes (an opening line
#: with an info string, such as ```sh, closes nothing), so the text between
#: reads as code; below that line both readings agree again.
_LATER_EXAMPLES = {
    "text-then-an-example": "\nafter fence\n\nMore:\n\n```sh\nls\n```\n\nmy tail\n",
    "a-line-then-an-example": "\nsome prose\n\n```sh\nls\n```\n",
    "two-examples": ("\nafter\n\n```sh\nls\n```\n\nmid\n\n```py\nx = 1\n```\n\ntail\n"),
    "a-later-line-closes-what-it-opens": "more code\n```\n",
}


@pytest.mark.parametrize(
    "text",
    [
        pytest.param(_WRAPPED, id="text-to-the-end"),
        pytest.param(_CASCADE, id="a-code-block-further-down"),
        *(
            pytest.param(f"My notes:\n\n```\nmake test\n\n{OLD}```\n{tail}", id=name)
            for name, tail in _LATER_EXAMPLES.items()
        ),
    ],
)
def test_a_closing_line_that_would_open_a_code_block_is_named_to_move(
    text: str,
) -> None:
    """lifecycle-r4-4: a closing fence added above the BEGIN marker, as the fix
    said, turned the old closing line below the block into an opener, and a
    Markdown viewer showed the rest of the file as code.

    The pair named that line only when the code block it opened ran to the
    end of the file. With a code example of yours further down, the readings
    agreed again at the last line of that example, so the fix still said to
    add a closing line: done that way, your text between (and the line that
    opens your example) read as code, and the next update and verify passed.
    The pair now names that line when, moved, it keeps more lines of yours
    below it reading as before than an added closing line would; moved as
    the fix says, every line of yours reads as before.
    """
    [pair] = harness_materializer.uncertain_pairs(text)
    lines = text.split("\n")
    moved = _move_line(text, 9, above=6)
    above = {at: at for at in range(5)}
    below = range(9, len(lines))

    assert (pair.begin.line, pair.end.line, pair.closer) == (6, 8, 9)
    assert _read_differently(
        text, _add_closer(text, pair), {at: at + 1 for at in below}
    )
    assert not _read_differently(text, moved, {**above, **{at: at for at in below}})
    assert complete_managed_block(moved) == OLD.rstrip("\n")
    assert merge_managed_block(moved, "new body", recorded=True) == moved.replace(
        OLD.rstrip("\n"), NEW.rstrip("\n")
    )


#: Code examples of yours right below the line that closes the code block
#: around Apothem's block, or after a blank line: added, a closing line above
#: the block turns that line into an opener whose code block takes in the
#: example's opening line (```sh closes nothing) and the blank line before
#: it, while no line of yours that is not blank turns from text into code.
_EXAMPLES_BELOW = {
    "an-example-right-below": "```sh\nls\n```\n\nmy tail\n",
    "a-blank-line-then-an-example": "\n```sh\nls\n```\n\nmy tail\n",
    "a-longer-fence": "\n````sh\nls\n````\n\nmy tail\n",
    "an-example-quoting-the-markers": f"\n```md\n{B}\nx\n{E}\n```\n\nmy tail\n",
}


def _code_blocks_below(text: str, line: int) -> list[tuple[str, str, str]]:
    """Return each code block a CommonMark reading of *text* opens below *line*.

    *line* is 0-based. Each code block is its kind, info string and text.
    """
    from markdown_it import MarkdownIt

    return [
        (token.type, token.info, token.content)
        for token in MarkdownIt("commonmark").parse(text)
        if token.type in {"fence", "code_block"}
        and token.map is not None
        and token.map[0] > line
    ]


@pytest.mark.parametrize(
    "tail", list(_EXAMPLES_BELOW.values()), ids=list(_EXAMPLES_BELOW)
)
def test_a_closing_line_with_your_example_below_is_named_to_move(tail: str) -> None:
    """r13-F1: with a code example of yours right below the line that closes
    the code block around the pair, or after a blank line, the fix still said
    to add a closing line above the block. Done that way, the old closing
    line opened a code block that took in the example's opening line (and
    the blank line before it): the example lost its info string and showed
    that line as code. The readings were compared only by whether a line that
    is not blank reads as code, which that change leaves as it was. The pair
    now names that line to move; moved, every code block of yours below it
    reads as before.
    """
    text = f"My notes:\n\n```\nmake test\n\n{OLD}```\n{tail}"
    pair = harness_materializer.uncertain_pairs(text)[0]
    yours = _code_blocks_below(text, 8)

    assert (pair.begin.line, pair.end.line, pair.closer) == (6, 8, 9)
    assert _code_blocks_below(_move_line(text, 9, above=6), 8) == yours
    assert _code_blocks_below(_add_closer(text, pair), 8) != yours


def test_a_closing_line_is_added_where_moving_it_changes_more_lines_below() -> None:
    """r13-F2: a line of yours between the END marker and the line that closes
    the code block around the pair starts a list item, and an indented line of
    yours follows the closing line. Moved up, the closing line would let the
    indented line join the list item as text; added, a closing line above the
    block keeps it code. The fix said to move the line; it now says to add one.
    """
    text = f"My notes:\n\n```\nmake test\n\n{OLD}1. one\n```\n    indented code\n```\n"
    [pair] = harness_materializer.uncertain_pairs(text)
    below = range(10, len(text.split("\n")))
    moved = _move_line(text, 10, above=6)

    assert pair.closer is None
    assert not _read_differently(
        text, _add_closer(text, pair), {at: at + 1 for at in below}
    )
    assert _read_differently(text, moved, {at: at for at in below}) == [
        "    indented code"
    ]


#: The block in your code block, then a code example of yours whose opening
#: line (```sh) the code block holds: line 13 closes that code block, and,
#: once a closing line above the block ends it, your example.
_CLOSES_YOUR_EXAMPLE = f"My notes:\n\n```\nmake test\n\n{OLD}More:\n\n```sh\nls\n```\n"


@pytest.mark.parametrize(
    ("text", "close"),
    [
        pytest.param(_CLOSES_YOUR_EXAMPLE, 13, id="closes-a-later-code-block-of-yours"),
        pytest.param(
            f"{_CLOSES_YOUR_EXAMPLE}\nmy tail\n",
            13,
            id="closes-a-later-code-block-of-yours-then-text",
        ),
        pytest.param(
            f"- item\n\n  ```\n  make test\n\n  {B}\n  old body\n  {E}\nafter list\n",
            None,
            id="its-list-item-ends-it",
        ),
    ],
)
def test_a_closing_line_is_added_where_that_changes_no_line_below(
    text: str, close: int | None
) -> None:
    """The fix adds a closing line above the pair, and no line below changes.

    The closing line below the block (*close*) is the last line of a code
    example of yours whose opening line the first code block held: added, a
    closing line above the block leaves it closing that example, where moved
    it would leave the example open. Or no closing line ends the code block
    at all: its list item does. Every line of yours below that line (below
    the END marker, without one) reads as it does now.
    """
    [pair] = harness_materializer.uncertain_pairs(text)
    start = pair.end.line if close is None else close

    assert pair.closer is None
    assert not _read_differently(
        text,
        _add_closer(text, pair),
        {at: at + 1 for at in range(start, len(text.split("\n")))},
    )


def test_moving_the_last_line_of_your_example_would_leave_it_open() -> None:
    """Why the fix adds a closing line there: moved, line 13 no longer closes
    your example, which then runs to the end of the file over your text.
    """
    text = f"{_CLOSES_YOUR_EXAMPLE}\nmy tail\n"

    assert "my tail" not in _code_lines(text)
    assert "my tail" in _code_lines(_move_line(text, 13, above=6))


def test_the_end_marker_a_rule_s_code_block_hides_names_its_closing_line() -> None:
    """The pair rule 3 fired on: closing the rule's code block above the END
    marker would turn the old closing line below it into an opener.
    """
    text = f"{B}\nop text A\n```\n{E}\n```\nop text B\n\n{OLD}"
    split, later = harness_materializer.uncertain_pairs(text)
    moved = _move_line(text, 5, above=4)

    assert (split.split, split.closer, later.closer) == (True, 5, None)
    assert "op text B" not in _code_lines(moved)
