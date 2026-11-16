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
* a text with many fences left open is read a bounded number of times (the
  re-read cap), and past the cap the last reading stands;
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


def test_a_body_with_an_open_fence_and_no_pair_after_it_is_one_block() -> None:
    """Rule 3 needs a pair after the block: alone, the block is replaced."""
    text = "KEEP top\n\n" + wrap_managed_block("rules\n```bash\nls") + "after\n"

    merged = merge_managed_block(text, "new body")

    assert merged == text.replace(wrap_managed_block("rules\n```bash\nls"), NEW)


def test_a_body_fence_an_operator_closer_below_ends_is_still_one_block() -> None:
    """tests-4: a closer of yours below the block is no marker pair after it."""
    block = wrap_managed_block("rules\n```bash\nls")
    text = "KEEP top\n\n" + block + "after\n```\nmore\n"

    merged = merge_managed_block(text, "new body", recorded=True)

    assert merged == text.replace(block, NEW)
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


# --- the re-read cap ---------------------------------------------------------


def test_fences_left_open_are_read_again_at_most_eight_times(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """cr-6: one reading per fence left open, up to nine readings in all."""
    calls: list[int] = []
    scan = harness_materializer._scan

    def counted(*args: object) -> object:
        calls.append(1)
        return scan(*args)  # type: ignore[arg-type]

    monkeypatch.setattr(harness_materializer, "_scan", counted)
    text = "```a\n" * 2000 + OLD

    merged = merge_managed_block(text, "new body", recorded=True)

    assert merged == text
    assert len(calls) <= 2 * 9


@pytest.mark.parametrize(("openers", "found"), [(8, True), (9, False)])
def test_past_eight_fences_left_open_no_block_is_certain(
    openers: int, found: bool
) -> None:
    text = "```a\n" * openers + OLD

    assert (complete_managed_block(text) is not None) is found


def test_a_block_past_the_cap_is_named_inside_the_fence_left_open() -> None:
    """oracle-4, docs-4 (a): the last reading puts it in the ninth code block.

    A test of how :func:`uncertain_block` and :func:`uncertain_pairs` name a
    pair past the cap. The "still found" tests below (four texts, and the
    frontmatter one) cover the reading past the cap itself (tests-8).
    """
    text = "```a\n" * 9 + OLD

    assert uncertain_block(text) == (10, 9)
    assert _pairs(text) == [(10, "FENCE", 9, 12, "FENCE", 9, False)]


def _closers_with_info(count: int) -> str:
    """Return *count* code examples whose closer carries an info string."""
    return "\n".join(f"```bash\nmake step{i}\n```bash\n" for i in range(count))


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
def test_a_block_above_fences_past_the_cap_is_still_found(text: str) -> None:
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


def test_a_frontmatter_block_above_fences_past_the_cap_is_still_found() -> None:
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
    """tests-5 (b): rule 3 holds the file back on the frontmatter path too."""
    old = merge_managed_block("", "---\nalwaysApply: true\n---\nrules\n```bash\nls")
    text = old + f"\nExample:\n\n```\n{B}\nquoted\n{E}\n```\n"

    assert merge_managed_block(text, _FRONTMATTER_BODY) == text


# --- what the docstrings say -------------------------------------------------


def test_a_text_with_only_a_bom_comes_back_unchanged() -> None:
    """cr-10: no block, so remove changes nothing, the byte order mark included."""
    assert remove_managed_block("\ufeff") == "\ufeff"
