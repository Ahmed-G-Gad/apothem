# SPDX-License-Identifier: MIT

"""The numbered fixes for marker lines Apothem cannot place, followed literally.

Every fix is built from four edits (change a marker line, add a line, move a
line up, delete a range of lines) and checked on a copy of the file before
it is printed. These tests read each printed fix with their own patterns,
apply its steps in the order printed, each line number taken as it stands,
and hold the result to what the fix promises: the next update finds exactly
one whole block (the next uninstall none), and every line of the operator's
that is left reads in a CommonMark viewer (markdown-it) as it did before.
"""

from __future__ import annotations

import random
import re
from collections.abc import Sequence

import pytest
from markdown_it import MarkdownIt

from apothem.harnesses._shared import install_driver_steps as steps
from apothem.harnesses._shared.install_driver_blocktext import (
    REPLACES,
    TAKES_OUT,
    two_blocks_report,
    unclear_block_report,
)
from apothem.harnesses._shared.install_driver_steps import Edit, Step
from apothem.lib.harness_materializer import (
    APOTHEM_BLOCK_BEGIN,
    APOTHEM_BLOCK_END,
    has_stray_begin,
    lone_begins,
    merge_managed_block,
    remove_managed_block,
    uncertain_pairs,
    whole_blocks,
)

B, E = APOTHEM_BLOCK_BEGIN, APOTHEM_BLOCK_END
BLOCK = [B, "rule one", E]

#: The shapes the reviewer named: a code block of yours around Apothem's
#: block with an example below (sA2) or only text (plain); a stray BEGIN
#: whose old text opens the code block (sF); a pair rule 3 fires on, with a
#: marker example of yours after it (sE-b).
SHAPES = {
    "sA2": [
        "My notes:",
        "```",
        "make test",
        "",
        *BLOCK,
        "```",
        "my text KEEP1",
        "```sh",
        "ls KEEP2",
        "```",
        "my tail KEEP3",
    ],
    "plain": ["My notes:", "```", "make test", "", *BLOCK, "```", "my text KEEP1"],
    "sF": [
        "# mine KEEP0",
        B,
        "old rule",
        "```",
        "old code",
        *BLOCK,
        "```",
        "tail KEEP1",
        "KEEP2",
        "KEEP3",
        "KEEP4",
        "KEEP5",
        "KEEP6",
    ],
    "sE-b": [
        "# mine KEEP0",
        B,
        "old rule text",
        "Run:",
        "```sh",
        "npm test",
        E,
        "```",
        "my text KEEP1",
        "Example KEEP2:",
        B,
        "example body KEEPX",
        E,
    ],
}

# The step formats, read with patterns of this test's own.
_FIX = re.compile(r"Fix ([A-Z]+), if (.+?):")
_LABEL = re.compile(r"lines (\d+) to (\d+) are Apothem's block")
_STEP = re.compile(
    r"(?P<id>[A-Z]+)(?P<n>\d+)\. (?:"
    r"Change line (?P<change>\d+): add a word inside its comment"
    r"|(?P<side>Above|Below) line (?P<at>\d+), add (?:a copy of line (?P<copy>\d+)"
    r"|a line of (?P<count>\d+) (?P<kind>backticks|tildes)"
    r"(?:, indented (?P<indent>\d+) spaces?)?)"
    r"|Move line (?P<move>\d+) to just above line (?P<above>\d+)"
    r"|Delete lines (?P<first>\d+) to (?P<last>\d+)"
    r")\."
)


def _text(lines: Sequence[str]) -> str:
    return "".join(f"{line}\n" for line in lines)


def _roles(text: str) -> list[str | None]:
    """Return how markdown-it (CommonMark) reads each line of *text*."""
    lines = text.split("\n")[:-1] if text.endswith("\n") else text.split("\n")
    roles: list[str | None] = [None if not ln.strip() else "text" for ln in lines]
    for token in MarkdownIt("commonmark").parse(text):
        if token.map is None or token.type not in {"fence", "code_block"}:
            continue
        start, stop = token.map
        for index in range(start, stop):
            if lines[index].strip():
                roles[index] = "code"
        if token.type == "fence":
            roles[start] = "opener"
            # Closed when the fence's text holds every line between the two.
            if stop - 1 > start and token.content.count("\n") == stop - start - 2:
                roles[stop - 1] = "closer"
    return roles


def _follow(lines: list[str], fix: str) -> tuple[list[str], list[int | None], set[int]]:
    """Apply the steps of *fix* in the order printed, each number as it stands.

    Returns the lines, the 0-based first line of each (``None`` for an added
    line) and the 0-based first lines the steps changed, moved or took out.
    """
    texts = list(lines)
    tags: list[int | None] = list(range(len(texts)))
    named: set[int] = set()
    found = list(_STEP.finditer(fix))
    # No number in a fix is left unread: up to its last step, each one is in
    # a step or the fix's label.
    rest = _STEP.sub("", fix[: found[-1].end()] if found else fix.split(":")[0])
    rest = _FIX.sub("", rest)
    assert not re.search(r"\d", rest), rest
    for match in found:
        if match["change"]:
            at = int(match["change"]) - 1
            named.add(tags[at])
            cut = texts[at].rfind("-->")
            texts[at] = texts[at][:cut].rstrip() + " (example) " + texts[at][cut:]
        elif match["move"]:
            source, target = int(match["move"]) - 1, int(match["above"]) - 1
            assert target < source
            named.add(tags[source])
            texts.insert(target, texts.pop(source))
            tags.insert(target, tags.pop(source))
        elif match["first"]:
            first, last = int(match["first"]) - 1, int(match["last"]) - 1
            named.update(tag for tag in tags[first : last + 1] if tag is not None)
            del texts[first : last + 1], tags[first : last + 1]
        else:
            at = int(match["at"]) - (1 if match["side"] == "Above" else 0)
            if match["copy"]:
                added = texts[int(match["copy"]) - 1]
            else:
                char = "`" if match["kind"] == "backticks" else "~"
                added = " " * int(match["indent"] or 0) + char * int(match["count"])
            texts.insert(at, added)
            tags.insert(at, None)
    return texts, tags, named


def _fixes(message: str) -> list[tuple[str, str]]:
    """Return each fix of *message*: its label and its text up to the next fix."""
    heads = list(_FIX.finditer(message))
    if not heads:
        return []
    return [
        (head[2], message[head.start() : nxt.start() if nxt else len(message)])
        for head, nxt in zip(heads, [*heads[1:], None], strict=True)
    ]


def _check(lines: list[str], message: str, *, removes: bool) -> int:
    """Follow every fix in *message* and hold it to its promise; return the count."""
    before = _roles(_text(lines))
    count = 0
    for label, fix in _fixes(message):
        texts, tags, named = _follow(lines, fix)
        fixed = _text(texts)
        claim = _LABEL.search(label)
        mine = set(range(len(lines))) - named
        if claim:
            mine -= set(range(int(claim[1]) - 1, int(claim[2])))
        assert mine <= {tag for tag in tags if tag is not None}, (label, fix)
        after = _roles(fixed)
        for at, tag in enumerate(tags):
            if tag in mine and before[tag] is not None:
                assert after[at] == before[tag], (label, fix, tag, texts)
        assert not has_stray_begin(fixed), fix
        if removes:
            left = remove_managed_block(fixed)
            assert not whole_blocks(left), fix
            assert not has_stray_begin(left), fix
            assert not uncertain_pairs(left), fix
        else:
            merged = merge_managed_block(fixed, "new rule", recorded=True)
            assert len(whole_blocks(merged)) == 1, (fix, merged)
            assert not has_stray_begin(merged), fix
        count += 1
    return count


def _message(lines: list[str], *, removes: bool) -> str:
    text = _text(lines)
    fixes = steps.unclear_fixes(
        text, uncertain_pairs(text), lone_begins(text), removes=removes
    )
    return steps.render_fixes(fixes, ["Then done"] * len(fixes), "FALLBACK")


@pytest.mark.parametrize("removes", [False, True], ids=["update", "uninstall"])
@pytest.mark.parametrize("name", sorted(SHAPES))
def test_each_named_shape_gets_numbered_fixes_that_hold(name: str, removes: bool):
    lines = SHAPES[name]
    message = _message(lines, removes=removes)
    assert message.startswith(steps.INTRO)
    assert _check(lines, message, removes=removes) >= 2


@pytest.mark.parametrize("name", ["sA2", "plain"])
def test_a_closing_line_right_below_the_end_marker_moves_up(name: str):
    """Only a blank line or none sits between END and the closing line: move it."""
    message = _message(SHAPES[name], removes=False)
    assert "Fix A, if lines 5 to 7 are Apothem's block: A1. Move line 8 to just " in (
        message
    )


def test_a_closing_line_further_down_stays_and_the_code_block_opens_again():
    """With a line of yours between END and the closing line, both stay code."""
    lines = ["Notes:", "```", "make", *BLOCK, "more code KEEP", "```", "text KEEP"]
    message = _message(lines, removes=False)
    assert (
        "A1. Below line 6, add a copy of line 2. A2. Above line 4, add a line of "
        "3 backticks." in message
    )
    _check(lines, message, removes=False)


def test_the_split_pair_fix_changes_the_pair_after_it():
    """markers-r5-3: the pair after it is then yours, so its lines change too."""
    message = _message(SHAPES["sE-b"], removes=False)
    assert (
        "Fix A, if lines 2 to 7 are Apothem's block: A1. Change line 13: add a "
        "word inside its comment. A2. Change line 11: add a word inside its "
        "comment. A3. Move line 8 to just above line 7." in message
    )


def test_no_step_deletes_a_line_by_a_number_an_earlier_step_shifted():
    """markers-r5-2: the old fix's ', and delete line N' is gone."""
    message = _message(SHAPES["sF"], removes=False)
    assert "delete line" not in message.lower()
    assert "A1. Move line 9 to just above line 6. A2. Change line 2" in message


def test_steps_print_from_the_bottom_up():
    shuffled = [
        Step(Edit.CHANGE, 2),
        Step(Edit.ADD, 4, fence="```"),
        Step(Edit.CHANGE, 9),
        Step(Edit.ADD, 6, 2, below=True),
    ]
    assert steps._order(shuffled) == (
        Step(Edit.CHANGE, 9),
        Step(Edit.ADD, 6, 2, below=True),
        Step(Edit.ADD, 4, fence="```"),
        Step(Edit.CHANGE, 2),
    )


@pytest.mark.parametrize(
    ("step", "text"),
    [
        (Step(Edit.CHANGE, 7), "Change line 7: add a word inside its comment."),
        (Step(Edit.ADD, 6, 2), "Above line 6, add a copy of line 2."),
        (Step(Edit.ADD, 6, 2, below=True), "Below line 6, add a copy of line 2."),
        (Step(Edit.ADD, 6, fence="```"), "Above line 6, add a line of 3 backticks."),
        (
            Step(Edit.ADD, 6, fence="  ~~~~"),
            "Above line 6, add a line of 4 tildes, indented 2 spaces.",
        ),
        (
            Step(Edit.ADD, 6, fence=" ```"),
            "Above line 6, add a line of 3 backticks, indented 1 space.",
        ),
        (Step(Edit.MOVE, 9, 5), "Move line 9 to just above line 5."),
        (Step(Edit.DELETE, 5, 7), "Delete lines 5 to 7."),
    ],
)
def test_each_step_has_one_wording(step: Step, text: str):
    assert steps.render_step(step) == text
    assert _STEP.fullmatch(f"A1. {text}") is not None


def test_the_check_refuses_steps_out_of_order():
    """An ADD above the pair first would shift the END marker the next step names."""
    lines = ["Notes:", "```", "make", *BLOCK, "more code KEEP", "```", "text KEEP"]
    good = (Step(Edit.ADD, 6, 2, below=True), Step(Edit.ADD, 4, fence="```"))
    assert steps.passes(lines, good, block=(4, 6), keeps=True, removes=False)
    assert not steps.passes(lines, good[::-1], block=(4, 6), keeps=True, removes=False)


def test_the_check_refuses_a_closing_line_that_turns_your_text_into_code():
    """markers-r5-1: the old 'close that code block above line 5' for sA2."""
    lines = SHAPES["sA2"]
    added = (Step(Edit.ADD, 5, fence="```"),)
    assert not steps.passes(lines, added, block=(5, 7), keeps=True, removes=False)
    moved = (Step(Edit.MOVE, 8, 5),)
    assert steps.passes(lines, moved, block=(5, 7), keeps=True, removes=False)


def test_the_check_refuses_a_promise_the_next_run_breaks():
    """markers-r5-3: the old split-pair fix left two whole blocks."""
    lines = SHAPES["sE-b"]
    old = (Step(Edit.MOVE, 8, 7),)
    assert not steps.passes(lines, old, block=(2, 7), keeps=True, removes=False)


def test_with_no_fix_that_passes_the_text_is_the_fallback():
    fallback = steps.FALLBACK.format(then="The next update then adds the block")
    assert steps.render_fixes([], [], fallback) == fallback
    assert not re.search(r"line \d", fallback)
    assert "Change every Apothem marker line in it instead" in fallback


def test_a_list_item_code_block_whose_copy_would_open_an_item_falls_back():
    """No fix of the four edits keeps every line of this file reading as now."""
    lines = ["- ```", "  make", *(f"  {line}" for line in BLOCK), "  more", "  ```"]
    text = _text(lines)
    pairs = uncertain_pairs(text)
    assert pairs
    fixes = steps.unclear_fixes(text, pairs, lone_begins(text), removes=False)
    message = steps.render_fixes(fixes, ["Then done"] * len(fixes), "FALLBACK")
    _check(lines, message, removes=False)


def test_two_blocks_get_one_fix_per_block():
    lines = ["mine", *BLOCK, "more", B, "example", E, "tail"]
    text = _text(lines)
    fixes = steps.block_fixes(text, whole_blocks(text), removes=False)
    message = steps.render_fixes(fixes, ["Then done"] * len(fixes), "FALLBACK")
    assert "Fix A, if lines 2 to 4 are Apothem's block: A1. Change line 8" in message
    assert "Fix B, if lines 6 to 8 are Apothem's block: B1. Change line 4" in message
    assert _check(lines, message, removes=False) == 2
    assert _check(lines, message, removes=True) == 2


def _shape(rng: random.Random) -> list[str]:
    """Prose, blanks, fences at indent 0-3, list items, indented code, 1-3 pairs."""
    parts: list[list[str]] = []
    for _ in range(rng.randint(1, 3)):
        body = rng.choice([["rule"], ["Run:", "```sh", "npm test"], ["a", "b"]])
        parts.append([B, *body, E])
    if rng.random() < 0.3:
        parts.append([B, "old rule"])
    for _ in range(rng.randint(2, 9)):
        pick = rng.random()
        indent = " " * rng.randint(0, 3)
        if pick < 0.3:
            parts.append([rng.choice(["text KEEP", "My notes:", "# head", "Run:"])])
        elif pick < 0.45:
            parts.append([""])
        elif pick < 0.75:
            parts.append([indent + rng.choice(["```", "~~~", "```sh", "````"])])
        elif pick < 0.85:
            parts.append(["- item", rng.choice(["  more", "", "  ```"])])
        else:
            parts.append(["", "    code KEEP"])
    rng.shuffle(parts)
    return [line for part in parts for line in part]


def test_every_fix_for_generated_files_holds_when_followed():
    """Each fix printed for a generated file holds when followed; few fall back."""
    rng = random.Random(244)  # noqa: S311 - seeded test input, not security
    followed = files = fallbacks = 0
    for _ in range(600):
        lines = _shape(rng)
        text = _text(lines)
        pairs, blocks = uncertain_pairs(text), whole_blocks(text)
        for removes in (False, True):
            if pairs:
                fixes = steps.unclear_fixes(
                    text, pairs, lone_begins(text), removes=removes
                )
            elif len(blocks) > 1:
                fixes = steps.block_fixes(text, blocks, removes=removes)
            else:
                continue
            files += 1
            fallbacks += not fixes
            message = steps.render_fixes(fixes, ["Then done"] * len(fixes), "FB")
            followed += _check(lines, message, removes=removes)
    assert files > 300
    assert followed > files
    assert fallbacks * 50 < files


def _report(lines: list[str], **kwargs: object) -> str:
    text = _text(lines)
    return unclear_block_report(
        "F.md", text, uncertain_pairs(text), lone=lone_begins(text), **kwargs
    )


@pytest.mark.parametrize("outcome", [REPLACES, TAKES_OUT, None])
@pytest.mark.parametrize("name", sorted(SHAPES))
def test_every_report_fix_holds_when_followed(name: str, outcome: str | None):
    """Install, update, verify, the OpenClaw retire and the uninstall alike."""
    lines = SHAPES[name]
    message = _report(lines, outcome=outcome, held=True)
    assert _check(lines, message, removes=outcome != REPLACES) >= 2
    assert "close that code block" not in message
    assert "delete line " not in message


def test_the_split_pair_report_promises_what_the_next_update_does():
    """markers-r5-3: the later pair's lines change, so one block is left."""
    message = _report(SHAPES["sE-b"], held=True)
    fix = _fixes(message)[0][1]
    assert fix.startswith("Fix A, if lines 2 to 7 are Apothem's block:")
    texts, _, _ = _follow(SHAPES["sE-b"], fix)
    assert whole_blocks(_text(texts)) == [(2, 8)]
    assert "The next update then replaces Apothem's block." in fix


def test_a_closing_line_with_text_below_moves_up_in_the_report():
    """markers-r5-1, fixes-1, lifecycle-r5-4: sA2 gets the move, not an added line."""
    message = _report(SHAPES["sA2"], held=True)
    assert "Fix A, if lines 5 to 7 are Apothem's block: A1. Move line 8 to just " in (
        message
    )
    assert "add a line of" not in message


def test_two_blocks_report_fixes_hold_for_update_and_uninstall():
    lines = ["mine", *BLOCK, "more", B, "example", E, "tail"]
    text = _text(lines)
    for removes in (False, True):
        message = two_blocks_report("F.md", text, whole_blocks(text), removes=removes)
        assert _check(lines, message, removes=removes) == 2


def test_the_revealed_block_report_changes_the_lines_around_the_block():
    lines = [B, "mine KEEP", *BLOCK, "tail KEEP", E]
    text = _text(lines)
    message = two_blocks_report(
        "F.md", text, whole_blocks(text), revealed=(1, 7), removes=True
    )
    assert "A1. Change line 7: add a word inside its comment. A2. Change line 1:" in (
        message
    )
    assert _check(lines, message, removes=True) == 1


#: Bodies the next update can write: plain, a closed code block, and a rule
#: that leaves a code block open (the merge closes that one).
BODIES = ("new rule", "Run:\n```sh\nnpm test\n```", "Run:\n```sh\nnpm test")

#: Files whose text ends inside a code block that no line closes: the pair in
#: a code block of yours, then an open one (Fix B changes the marker lines);
#: and a pair whose fix deletes it, with an open one below.
OPEN_TAIL = {
    "pair-in-code": ["```", B, "rule", E, "```", "```sh", "tail KEEP1"],
    "deleted-pair": [
        "  `````",
        "code",
        B,
        "Run:",
        "~~~",
        "npm test",
        f"   {E}",
        "  `````",
        "```md",
        "",
        "",
        "  ~~~",
        "   ~~~",
    ],
}


def _next_update_holds(fixed: str) -> None:
    """Assert the next update, with any body in :data:`BODIES`, gives one block."""
    for body in BODIES:
        for recorded in (True, False):
            merged = merge_managed_block(fixed, body, recorded=recorded)
            assert len(whole_blocks(merged)) == 1, (body, recorded, merged)
            assert not has_stray_begin(merged), (body, merged)
            assert not uncertain_pairs(merged), (body, merged)
            left = remove_managed_block(merged)
            assert not whole_blocks(left), (body, left)


@pytest.mark.parametrize("name", sorted(OPEN_TAIL))
def test_a_fix_closes_the_code_block_the_file_ends_in(name: str):
    """An appended block must not land in an open code block of yours.

    A profile rule that holds a code block would close that code block, and
    the BEGIN marker of the new block would read as code.
    """
    lines = OPEN_TAIL[name]
    message = _report(lines, held=True)
    found = _fixes(message)
    assert found, message
    for label, fix in found:
        texts, _, _ = _follow(lines, fix)
        fixed = _text(texts)
        if "are Apothem's block" in label and whole_blocks(fixed):
            continue
        _next_update_holds(fixed)
    _check(lines, message, removes=False)


def test_the_closing_line_goes_below_the_last_line():
    message = _report(OPEN_TAIL["pair-in-code"], held=True)
    assert (
        "Fix B, if lines 2 to 4 are text of yours: B1. Below line 7, add a line "
        "of 3 backticks. B2. Change line 4" in message
    )


def test_the_check_tries_a_body_that_holds_a_code_block():
    """With the code block left open, a body's closing line closes it."""
    lines = OPEN_TAIL["pair-in-code"]
    changed = (Step(Edit.CHANGE, 4), Step(Edit.CHANGE, 2))
    assert not steps.passes(lines, changed, block=None, keeps=False, removes=False)
    closed = (Step(Edit.ADD, 7, fence="```", below=True), *changed)
    assert steps.passes(lines, closed, block=None, keeps=False, removes=False)


def test_a_kept_block_in_a_code_block_no_line_closes_is_taken_out_of_it():
    """A viewer reads the code block from line 1 to the end; Apothem reads text.

    A code block in the rules the next update writes would close it, so each
    fix closes it above the block it keeps and opens it again below.
    """
    lines = ["```", "My notes:", "My notes:", *BLOCK, B, "old rule", *BLOCK]
    text = _text(lines)
    blocks = whole_blocks(text)
    assert blocks == [(4, 6), (9, 11)]
    message = two_blocks_report("F.md", text, blocks, removes=False)
    found = _fixes(message)
    assert len(found) == 2, message
    for _label, fix in found:
        texts, _, _ = _follow(lines, fix)
        _next_update_holds(_text(texts))
    assert "Below line 6, add a copy of line 1. A5. Above line 4, add a line " in (
        message
    )
    assert "B1. Above line 9, add a line of 3 backticks." in message
    assert _check(lines, message, removes=False) == 2


@pytest.mark.parametrize("outcome", [TAKES_OUT, None], ids=["retire", "uninstall"])
def test_a_fix_that_takes_the_block_out_closes_the_code_block_too(
    outcome: str | None,
):
    """A later install adds Apothem's block at the end of the file."""
    lines = OPEN_TAIL["deleted-pair"]
    message = _report(lines, outcome=outcome, held=True)
    found = _fixes(message)
    assert found, message
    for _label, fix in found:
        assert "add a line of 3 backticks" in fix, fix
        texts, _, _ = _follow(lines, fix)
        _next_update_holds(_text(texts))
    _check(lines, message, removes=True)
