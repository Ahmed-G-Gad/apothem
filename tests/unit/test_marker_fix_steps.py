# SPDX-License-Identifier: MIT

"""The numbered fixes for marker lines Apothem cannot place, followed literally.

Every step changes one BEGIN marker line in place, by a word added inside
its comment (an END marker pairs only with the BEGIN marker right above it,
so it needs no step); one more step closes a code block the file ends in,
when a fix leaves no block for an update to write at the end. These tests
read each
printed fix with their own patterns, apply its steps in the order printed,
and hold the result to what the fix promises: the file then holds the block
the fix names, or none; the next update replaces that block, or writes one
at the end of the file; the next uninstall takes it out, or finds none; and
every line of the file reads in a CommonMark viewer (markdown-it) as it did.
"""

from __future__ import annotations

import random
import re
import time
from collections.abc import Sequence
from pathlib import Path

import pytest
from markdown_it import MarkdownIt

from apothem.harnesses._shared import install_driver_steps as steps
from apothem.harnesses._shared.install_driver_blocktext import (
    REPLACES,
    TAKES_OUT,
    two_blocks_report,
    unclear_block_report,
)
from apothem.harnesses._shared.install_driver_retention import (
    unlisted_block_warnings,
)
from apothem.harnesses._shared.install_driver_steps import Step
from apothem.lib.harness_materializer import (
    APOTHEM_BLOCK_BEGIN,
    APOTHEM_BLOCK_END,
    has_stray_begin,
    lone_begins,
    merge_managed_block,
    remove_managed_block,
    stray_begins,
    uncertain_pairs,
    whole_blocks,
    wrap_managed_block,
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

#: Rule bodies the next update may write: plain, a closed code block, and
#: one the merge closes.
BODIES = ("Apothem rule.", "Run:\n```sh\nnpm test\n```", "Run:\n```sh\nnpm test")

# The step formats, read with patterns of this test's own.
_FIX = re.compile(r"Fix ([A-Z]+)(?:, (.+?))?:")
_LABEL = re.compile(r"if lines (\d+) to (\d+) are Apothem's block")
_STEP = re.compile(
    r"(?P<id>[A-Z]+)(?P<n>\d+)\. (?:"
    r"Change line (?P<change>\d+): add a word inside its comment"
    r"|Below line (?P<at>\d+), add a line of (?P<count>\d+) "
    r"(?P<kind>backticks|tildes)(?:, indented (?P<indent>\d+) spaces?)?"
    r")\."
)
#: Step wordings the change-only fixes no longer print.
_GONE_STEPS = re.compile(r"Move line|Delete lines|add a copy of line|Above line")


def _text(lines: Sequence[str]) -> str:
    return "".join(f"{line}\n" for line in lines)


def _roles(text: str) -> list[str | None]:
    """Return how markdown-it (CommonMark) reads each line of *text*."""
    lines = text.split("\n")[:-1] if text.endswith("\n") else text.split("\n")
    roles: list[str | None] = [None if not ln.strip() else "text" for ln in lines]
    for token in MarkdownIt("commonmark").parse(text):
        if token.map is None or token.level:
            continue
        start, stop = token.map
        for index in range(start, min(stop, len(lines))):
            if lines[index].strip():
                roles[index] = token.type
    return roles


def _follow(lines: list[str], fix: str) -> list[str]:
    """Apply the steps of *fix* in the order printed; return the lines.

    Each CHANGE step must name a BEGIN marker line, and the one closing line
    goes below the file's last line. No number in the fix is left unread.
    """
    texts = list(lines)
    found = list(_STEP.finditer(fix))
    rest = _STEP.sub("", fix[: found[-1].end()] if found else fix.split(":")[0])
    assert not re.search(r"\d", _FIX.sub("", rest)), rest
    for match in found:
        if match["change"]:
            at = int(match["change"]) - 1
            assert texts[at].strip() == B, (fix, texts[at])
            cut = texts[at].rfind("-->")
            texts[at] = texts[at][:cut].rstrip() + " (example) " + texts[at][cut:]
        else:
            assert int(match["at"]) == len(lines), fix
            char = "`" if match["kind"] == "backticks" else "~"
            indent = " " * int(match["indent"] or 0)
            texts.append(indent + char * int(match["count"]))
    return texts


def _fixes(message: str) -> list[tuple[str, str]]:
    """Return each fix of *message*: its label and its text up to the next fix."""
    heads = list(_FIX.finditer(message))
    return [
        (head[2] or "", message[head.start() : nxt.start() if nxt else len(message)])
        for head, nxt in zip(heads, [*heads[1:], None], strict=True)
    ]


def _check(lines: list[str], message: str, *, removes: bool) -> int:
    """Follow every fix in *message* and hold it to its promise; return the count."""
    assert not _GONE_STEPS.search(message), message
    before = _roles(_text(lines))
    count = 0
    for label, fix in _fixes(message):
        fixed = _text(_follow(lines, fix))
        assert _roles(fixed)[: len(before)] == before, (label, fix)
        claim = _LABEL.search(label)
        kept = [(int(claim[1]), int(claim[2]))] if claim else []
        assert whole_blocks(fixed) == kept, (fix, fixed)
        assert not has_stray_begin(fixed), fix
        assert not uncertain_pairs(fixed), fix
        if removes:
            left = remove_managed_block(fixed)
            assert not whole_blocks(left), fix
            assert not has_stray_begin(left), fix
            assert not uncertain_pairs(left), fix
        else:
            for body in BODIES:
                merged = merge_managed_block(fixed, body, recorded=True)
                if kept:
                    # The next update replaces the block in place.
                    above = _text(_follow(lines, fix)[: kept[0][0] - 1])
                    assert merged.startswith(above), (fix, merged)
                    wrapped = wrap_managed_block(body).rstrip("\n")
                    assert wrapped in merged, (fix, merged)
                else:
                    # It writes Apothem's block at the end, read as one block.
                    assert merged.startswith(fixed), (fix, merged)
                    assert len(whole_blocks(merged)) == 1, (fix, merged)
                    assert not has_stray_begin(merged), fix
        count += 1
    return count


def _message(lines: list[str], *, removes: bool) -> str:
    text = _text(lines)
    fixes = steps.unclear_fixes(text, uncertain_pairs(text))
    return steps.render_fixes(fixes, ["Then done"] * len(fixes))


@pytest.mark.parametrize("removes", [False, True], ids=["update", "uninstall"])
@pytest.mark.parametrize("name", sorted(SHAPES))
def test_each_named_shape_gets_change_only_fixes_that_hold(name: str, removes: bool):
    lines = SHAPES[name]
    message = _message(lines, removes=removes)
    assert message.startswith(steps.INTRO)
    assert _check(lines, message, removes=removes) >= 1


@pytest.mark.parametrize("name", ["sA2", "plain"])
def test_a_pair_in_a_code_block_gets_its_begin_marker_line_changed(name: str):
    """markers-r5-1, advice-1: no closing line moves up or is copied below END.

    Apothem's block in a code block of yours is not made whole by moving or
    adding fence lines, which changed how your lines read once the next
    update replaced the block. The one fix changes its BEGIN marker line; the
    next update writes Apothem's block at the end of the file.
    """
    message = _message(SHAPES[name], removes=False)
    assert message == (
        f"{steps.INTRO} Fix A: A1. Change line 5: add a word inside its comment. "
        "Then done."
    )


def test_the_split_pair_gets_no_fix_that_keeps_it():
    """markers-r5-3, advice-1: keeping it re-read the lines below its END marker.

    The pair rule 3 fired on is an older block whose rule left a code block
    open, and line 8 of yours closes it. Kept and replaced by the next
    update, the block would close its own code block, and line 8 would open
    one over your text. So it gets no fix of its own: the pair after it,
    which reads outside code with every code block above it closed, does,
    and one more fix changes both BEGIN marker lines.
    """
    message = _message(SHAPES["sE-b"], removes=False)
    assert message.endswith(
        "Fix A, if lines 11 to 13 are Apothem's block: A1. Change line 2: add a "
        "word inside its comment. Then done. Fix B, in any other case: B1. Change "
        "line 11: add a word inside its comment. B2. Change line 2: add a word "
        "inside its comment. Then done."
    )


def test_a_stray_begin_whose_old_text_opens_a_code_block_changes_every_line():
    """markers-r5-2: sF's fix moved a closing line; it now changes marker lines."""
    message = _message(SHAPES["sF"], removes=False)
    assert "delete line" not in message.lower()
    assert "Move line" not in message
    assert _check(SHAPES["sF"], message, removes=False) == 1


def test_steps_print_from_the_bottom_up():
    lines = ["```", B, "x", E, "```", "", B, "y", E, "", "```md", B, "z", E, "```"]
    message = _message(lines, removes=False)
    for _, fix in _fixes(message):
        numbers = [int(m["change"] or m["at"]) for m in _STEP.finditer(fix)]
        assert numbers == sorted(numbers, reverse=True), fix


@pytest.mark.parametrize(
    ("step", "text"),
    [
        (Step(3), "Change line 3: add a word inside its comment."),
        (Step(9, "```"), "Below line 9, add a line of 3 backticks."),
        (Step(9, "~~~~"), "Below line 9, add a line of 4 tildes."),
        (Step(9, " ~~~"), "Below line 9, add a line of 3 tildes, indented 1 space."),
        (
            Step(9, "  ```"),
            "Below line 9, add a line of 3 backticks, indented 2 spaces.",
        ),
    ],
)
def test_each_step_has_one_wording(step: Step, text: str):
    assert steps.render_step(step) == text


def test_two_blocks_get_one_fix_per_block():
    lines = [*BLOCK, "", "mine KEEP", "", B, "rule two", E]
    text = _text(lines)
    fixes = steps.block_fixes(text, whole_blocks(text))
    message = steps.render_fixes(fixes, ["Then done"] * len(fixes))
    assert (
        "Fix A, if lines 1 to 3 are Apothem's block: A1. Change line 7: add a word "
        "inside its comment. Then done. Fix B, if lines 7 to 9 are Apothem's block: "
        "B1. Change line 1: add a word inside its comment. Then done."
    ) in message
    assert _check(lines, message, removes=False) == 2
    assert _check(lines, message, removes=True) == 2


def test_a_block_below_one_that_holds_a_code_block_gets_no_fix_of_its_own():
    """Once the first block's markers change, its code block is read too.

    Lines 1 to 5 hold a code block, so the layout of the file does not show
    how the lines below read once those marker lines change, and lines 7 to
    9 get no fix of their own. Their case gets the fix that changes every
    marker line.
    """
    lines = [B, "```sh", "x", "```", E, "", B, "new", E]
    text = _text(lines)
    assert whole_blocks(text) == [(1, 5), (7, 9)]
    fixes = steps.block_fixes(text, whole_blocks(text))
    assert [fix.label for fix in fixes] == [
        "if lines 1 to 5 are Apothem's block",
        steps.OTHER_CASE,
    ]
    message = steps.render_fixes(fixes, ["Then done"] * len(fixes))
    assert _check(lines, message, removes=False) == 2


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


def _all_fixes(text: str, *, appends: bool) -> list[steps.Fix]:
    """Return the fixes a warning gives for *text*, whatever its markers hold."""
    blocks = whole_blocks(text)
    if len(blocks) > 1:
        return steps.block_fixes(text, blocks)
    pairs = uncertain_pairs(text)
    if pairs:
        return steps.unclear_fixes(text, pairs)
    return steps.stray_fixes(text, stray_begins(text), blocks, appends=appends)


@pytest.mark.parametrize("removes", [False, True], ids=["update", "uninstall"])
def test_every_fix_for_generated_files_holds_when_followed(removes: bool):
    """Each fix printed for a generated file holds when followed."""
    rng = random.Random(244)  # noqa: S311 - seeded test input, not security
    followed = 0
    for _ in range(600):
        lines = _shape(rng)
        fixes = _all_fixes(_text(lines), appends=not removes)
        if not fixes:
            continue
        message = steps.render_fixes(fixes, ["Then done"] * len(fixes))
        followed += _check(lines, message, removes=removes)
    assert followed > 300


def _report(
    lines: list[str], outcome: str | None = REPLACES, *, held: bool = False
) -> str:
    text = _text(lines)
    pairs = uncertain_pairs(text)
    return unclear_block_report(
        "AGENTS.md", text, pairs, outcome=outcome, lone=lone_begins(text), held=held
    )


@pytest.mark.parametrize("outcome", [REPLACES, TAKES_OUT, None])
@pytest.mark.parametrize("name", ["sA2", "plain", "sE-b"])
def test_every_report_fix_holds_when_followed(name: str, outcome: str | None):
    """Install, update, verify, the OpenClaw retire and the uninstall alike."""
    lines = SHAPES[name]
    message = _report(lines, outcome=outcome, held=True)
    assert _check(lines, message, removes=outcome != REPLACES) >= 1


def test_the_report_promises_what_each_fix_leaves():
    """A kept block is replaced; with none left, Apothem's goes at the end."""
    message = _report(SHAPES["sE-b"], held=True)
    [(_, kept), (_, other)] = _fixes(message)
    assert "Change line 13" not in message
    assert kept.startswith("Fix A, if lines 11 to 13 are Apothem's block:")
    assert "The next update then replaces Apothem's block." in kept
    assert other.startswith("Fix B, in any other case:")
    assert (
        "Apothem then reads none of these lines as its markers, and the next "
        "update writes its block at the end of the file."
    ) in other
    assert (
        "Any old Apothem text below a marker line you change, and its END marker "
        "line if it has one, is then yours to delete by hand."
    ) in other


def test_two_blocks_report_fixes_hold_for_update_and_uninstall():
    lines = [*BLOCK, "", "mine KEEP", "", B, "rule two", E]
    text = _text(lines)
    for outcome in (REPLACES, None):
        message = two_blocks_report(
            "CLAUDE.md", text, whole_blocks(text), outcome=outcome
        )
        assert _check(lines, message, removes=outcome is None) == 2


def test_the_revealed_block_report_changes_the_lines_around_the_block():
    """A BEGIN marker above Apothem's block and an END marker below it.

    The BEGIN marker changes; the END marker then pairs with no BEGIN marker
    above it, so it stays as it is.
    """
    lines = ["# mine", B, "my notes", *BLOCK, "more notes", E, "tail"]
    text = _text(lines)
    assert whole_blocks(text) == [(4, 6)]
    message = two_blocks_report(
        "CLAUDE.md", text, [(4, 6)], revealed=(2, 8), outcome=None
    )
    assert (
        "Fix A, if lines 4 to 6 are Apothem's block: A1. Change line 2: add a word "
        "inside its comment. Lines 4 to 6 are then the one block in the file."
    ) in message
    assert _check(lines, message, removes=True) == 1


#: Files whose text ends inside a code block that no line closes: a pair in a
#: code block of yours, then an open one; and one whose fences start in from
#: the margin, which Apothem reads as Markdown to find where it ends.
OPEN_TAIL = {
    "pair-in-code": ["```", B, "rule", E, "```", "```sh", "tail KEEP1"],
    "indented": [
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


@pytest.mark.parametrize("name", sorted(OPEN_TAIL))
def test_a_fix_closes_the_code_block_the_file_ends_in(name: str):
    """An appended block must not land in an open code block of yours.

    A profile rule that holds a code block would close that code block, and
    the BEGIN marker of the new block would read as code.
    """
    lines = OPEN_TAIL[name]
    message = _report(lines, held=True)
    [(_, fix)] = _fixes(message)
    assert f"A1. Below line {len(lines)}, add a line of 3 backticks." in fix
    fixed = _text(_follow(lines, fix))
    for body in BODIES:
        for recorded in (True, False):
            merged = merge_managed_block(fixed, body, recorded=recorded)
            assert len(whole_blocks(merged)) == 1, (body, recorded, merged)
            assert not uncertain_pairs(merged), (body, merged)
    assert _check(lines, message, removes=False) == 1


@pytest.mark.parametrize("outcome", [TAKES_OUT, None], ids=["retire", "uninstall"])
def test_a_fix_that_takes_the_block_out_closes_the_code_block_too(
    outcome: str | None,
):
    """A later install adds Apothem's block at the end of the file."""
    lines = OPEN_TAIL["pair-in-code"]
    message = _report(lines, outcome=outcome, held=True)
    assert f"A1. Below line {len(lines)}, add a line of 3 backticks." in message
    assert "Apothem then finds no block of its own in this file." in message
    assert _check(lines, message, removes=True) == 1


_GONE = "Apothem then finds no block of its own in this file"


def _unlisted(root: Path, lines: list[str]) -> str:
    """Return the uninstall's warning for *lines* in a CLAUDE.md no record lists."""
    (root / "CLAUDE.md").write_bytes(_text(lines).encode("utf-8"))
    [warning] = unlisted_block_warnings(root)
    return warning.message


def test_the_unlisted_block_text_changes_the_block_s_marker_lines(
    tmp_path: Path,
) -> None:
    """advice-4: deleting the block turned a paragraph above it into a heading.

    The fix deleted lines 3 to 5 with no blank line left in their place, so
    the text above and the ``---`` below read as a setext heading. It now
    changes the block's BEGIN marker line, so no line reads differently; the
    old text below it is yours to delete by hand.
    """
    lines = ["Intro text KEEP1", "", *BLOCK, "---", "more KEEP2"]
    message = _unlisted(tmp_path, lines)
    assert "lines 3 to 5" in message
    assert f"Fix A: A1. Change line 3: add a word inside its comment. {_GONE}." in (
        message
    )
    assert "Delete lines" not in message
    assert _check(lines, message, removes=True) == 1


@pytest.mark.parametrize(
    ("above", "changed"),
    [
        pytest.param([B, "my note"], [2], id="your-begin-marker"),
        pytest.param(["```md", B, "example", E, "```"], [3], id="quoted"),
    ],
)
def test_the_unlisted_block_fix_changes_your_marker_lines_left_behind(
    tmp_path: Path, above: list[str], changed: list[int]
) -> None:
    """Once the block is out, a marker line of yours would read as Apothem's.

    A BEGIN marker of yours above the block would start no block, and a pair
    you quote in a code block would be a pair no rule can place, so the next
    run would warn again. The fix changes those BEGIN marker lines with the
    block's own.
    """
    lines = ["my own text above", *above, "", *BLOCK, "my own text below"]
    begin = len(above) + 3
    message = _unlisted(tmp_path, lines)
    numbers = [begin, *changed]
    changes = " ".join(
        f"A{number}. Change line {line}: add a word inside its comment."
        for number, line in enumerate(numbers, 1)
    )
    assert f"Fix A: {changes} {_GONE}." in message
    assert _check(lines, message, removes=True) == 1


def test_the_fixes_need_no_markdown_reader_of_their_own() -> None:
    """lifecycle-r6-1: the fixes are built from the lines, with no markdown-it."""
    root = Path(steps.__file__).parent
    for name in ("install_driver_steps.py", "install_driver_blocktext.py"):
        source = (root / name).read_text(encoding="utf-8")
        assert "markdown_it" not in source, name
    assert not (root / "install_driver_stepcheck.py").exists()


#: A filler paragraph with a list and a closed code block, about 100 bytes.
_FILLER = (
    "Some text of mine about the project, with a few words.\n\n- item one\n"
    "- item two\n\n```sh\nmake test\n```\n\n"
)


def _large(shape: str) -> str:
    """Return a file of about 1 MB with the marker problem *shape* names."""
    half = _FILLER * (500_000 // len(_FILLER))
    return {
        "two-blocks": f"{half}{B}\nold\n{E}\n\n{half}{B}\nnew\n{E}\n{B}\nx\n{E}\n",
        "unclear": f"{half}```\n{B}\nrule\n{E}\n```\n\n{half}```md\n{B}\nex\n{E}\n```\n",
        "stray": f"{half}{B}\nold\n\n{half}{B}\nnew\n{E}\n",
        "endless": f"{half}{half}- item\n  ```\n  code\n{B}\nold\n",
    }[shape]


@pytest.mark.parametrize("shape", ["two-blocks", "unclear", "stray", "endless"])
def test_the_advice_for_a_large_file_takes_well_under_a_second(shape: str) -> None:
    """lifecycle-r6-1, advice-3: one warning took 17 to 50 s on a 1 MB file.

    The fixes then went through a check that read the file many times over.
    They now go over its lines once, reading them as Markdown at most once
    (the last case, whose fences do not start at the margin). Here a warning
    for a 1 MB file takes about 0.05 to 0.3 s; the bound leaves room for a
    slow runner, and the best of three runs is timed, so a pause elsewhere
    does not fail it.
    """
    text = _large(shape)
    blocks, pairs = whole_blocks(text), uncertain_pairs(text)
    strays, lone = stray_begins(text), lone_begins(text)

    def advice() -> str:
        if len(blocks) > 1:
            return two_blocks_report("CLAUDE.md", text, blocks)
        if pairs:
            return unclear_block_report("AGENTS.md", text, pairs, lone=lone, held=True)
        return steps.render_fixes(
            fixes := steps.stray_fixes(text, strays, blocks, appends=True),
            ["Then done"] * len(fixes),
        )

    took = []
    for _ in range(3):
        start = time.perf_counter()
        message = advice()
        took.append(time.perf_counter() - start)
    assert "Change line" in message
    assert min(took) < 1.5, took
