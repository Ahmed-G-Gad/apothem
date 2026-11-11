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
  re-read cap);
* a tab after a list bullet and a thematic break such as ``* * *`` read as
  CommonMark reads them.
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


# --- what the docstrings say -------------------------------------------------


def test_a_text_with_only_a_bom_comes_back_unchanged() -> None:
    """cr-10: no block, so remove changes nothing, the byte order mark included."""
    assert remove_managed_block("﻿") == "﻿"
