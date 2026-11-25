# SPDX-License-Identifier: MIT

"""Files on which following a printed marker fix, or the run after it, went wrong.

Each test is one class of break the change-only advice property run found
(``test_advice_change_only_property.py``), cut down to its smallest file and
run through the library function the caller uses.
"""

from __future__ import annotations

import re
import threading
import time
from collections.abc import Callable
from pathlib import Path

import pytest

from apothem.cli._stray_begin_report import stray_begin_note
from apothem.harnesses._shared.install_driver_blocks import (
    sentinel_refusal,
    stray_begin_install_warnings,
)
from apothem.harnesses._shared.install_driver_blocktext import (
    REPLACES,
    TAKES_OUT,
    stray_fix_text,
)
from apothem.harnesses._shared.install_driver_retention import (
    unlisted_block_warnings,
)
from apothem.harnesses._shared.install_driver_types import MaterializationResult
from apothem.harnesses.open_claw import rules_file
from apothem.lib import harness_materializer as materializer
from apothem.lib.harness_materializer import (
    APOTHEM_BLOCK_BEGIN,
    APOTHEM_BLOCK_END,
    has_stray_begin,
    merge_managed_block,
    remove_managed_block,
    trailing_fence,
    uncertain_pairs,
    whole_blocks,
)

B = APOTHEM_BLOCK_BEGIN
E = APOTHEM_BLOCK_END


def _lines(*lines: str) -> str:
    """Return *lines* as an LF text that ends in a newline."""
    return "".join(f"{line}\n" for line in lines)


def _strip_within(text: str, seconds: float = 5.0) -> str | None:
    """Return :func:`remove_managed_block` of *text*, or ``None`` when it does not return.

    The strip runs in a daemon thread, so a strip that never returns fails
    the test instead of hanging the run.
    """
    found: list[str] = []
    thread = threading.Thread(
        target=lambda: found.append(remove_managed_block(text)), daemon=True
    )
    thread.start()
    thread.join(seconds)
    return found[0] if found else None


# -- strip-hangs -------------------------------------------------------------


def test_the_strip_returns_when_a_copy_of_the_block_sits_after_frontmatter() -> None:
    """Two whole blocks, each followed by a ``---`` line, then a BEGIN marker.

    Once the first block is out, the file opens with what reads as
    frontmatter right before the copy, and the strip's loop over the copies
    took nothing out and never ended. It must return, and keep both ``---``
    lines and the BEGIN marker line at the end.
    """
    text = _lines(B, "r", E, "---", B, "r", E, "---", B)
    removed = _strip_within(text)
    assert removed is not None, "remove_managed_block never returned"
    lines = removed.split("\n")
    assert lines.count("---") == 2
    assert lines[-2] == B


# -- line-gone ---------------------------------------------------------------


def test_the_strip_keeps_your_opening_lines_that_are_no_frontmatter_mapping() -> None:
    """A file that opens with ``---``, a list item and ``---``, right above the block.

    That reads as frontmatter followed by the BEGIN marker, the shape a
    frontmatter-first rule file has, so the strip took the three lines for
    Apothem's frontmatter and deleted the file. Apothem's own frontmatter is
    a YAML mapping (``alwaysApply: true``, say); these lines are not one, so
    they stay.
    """
    text = _lines("---", "- item", "---", B, "x", E)
    assert remove_managed_block(text) == _lines("---", "- item", "---")


def test_the_strip_still_takes_out_apothem_s_own_frontmatter() -> None:
    """Apothem's frontmatter, a YAML mapping right above its block, goes with it."""
    body = _lines("---", "alwaysApply: true", "---", "Apothem rules.")
    merged = merge_managed_block(_lines("My notes."), body)
    assert merged.startswith(_lines("---", "alwaysApply: true", "---", B))
    assert remove_managed_block(merged) == _lines("My notes.")


#: Cursor's rule-file head with its ``globs`` value edited to one Cursor reads
#: but YAML does not: ``*`` starts a YAML alias.
_EDITED_HEAD = (
    "---",
    'description: "Apothem engineering disciplines for this project."',
    "globs: **/*.ts",
    "alwaysApply: true",
    "---",
)


def test_the_strip_takes_out_apothem_s_frontmatter_that_yaml_cannot_read() -> None:
    """identity-1 (round 7): an edited ``globs`` value left Apothem's file behind.

    The head held Apothem's template keys, but YAML could not read it, so it
    did not count as Apothem's and the uninstall left a file with Apothem's
    description and ``alwaysApply: true``. It now goes with the block, and
    the next update replaces it in place.
    """
    text = _lines(*_EDITED_HEAD, B, "Apothem rules.", E)
    assert remove_managed_block(text) == ""
    assert remove_managed_block(text + _lines("", "My notes.")) == _lines("My notes.")
    body = _lines("---", "alwaysApply: true", "---", "New rules.")
    assert merge_managed_block(text, body) == _lines(
        "---", "alwaysApply: true", "---", B, "New rules.", E
    )


def test_the_strip_keeps_your_frontmatter_that_yaml_cannot_read() -> None:
    """A head YAML cannot read and that holds none of Apothem's keys stays."""
    text = _lines("---", "title: [draft", "---", B, "x", E)
    assert remove_managed_block(text) == _lines("---", "title: [draft", "---")


def test_every_rule_file_template_key_counts_as_apothem_s() -> None:
    """Each key Apothem's rule-file templates write is a key the strip knows."""
    root = Path(materializer.__file__).resolve().parents[1] / "harnesses"
    templates = sorted(root.glob("*/templates/apothem-rules.*"))
    assert templates
    for template in templates:
        text = template.read_text(encoding="utf-8")
        if not text.startswith("---\n"):
            continue
        head = text.split("\n---", 1)[0].split("\n")[1:]
        for line in head:
            if line and not line[0].isspace():
                assert materializer._TEMPLATE_KEY.match(line), (template, line)


# -- following a printed fix -------------------------------------------------

_CHANGE = re.compile(r"Change line (\d+): add a word inside its comment\.")


def _changes(message: str) -> list[int]:
    """Return the lines the first fix of *message* says to change, in its order."""
    first = message.split("Fix B")[0]
    return [int(found) for found in _CHANGE.findall(first)]


def _follow(text: str, lines: list[int]) -> str:
    """Return *text* with a word added inside the comment of each of *lines*."""
    split = text.split("\n")
    for line in lines:
        marker = split[line - 1]
        assert marker.strip() in (B, E), f"line {line} is {marker!r}"
        cut = marker.rfind("-->")
        split[line - 1] = f"{marker[:cut]}(changed) {marker[cut:]}"
    return "\n".join(split)


# -- pair-in-code-left -------------------------------------------------------


def test_a_fix_that_keeps_no_block_changes_the_begin_line_of_a_pair_in_code() -> None:
    """A marker pair quoted in a code block, and a BEGIN marker that lost its END.

    The fix changed the stray BEGIN marker line alone. The quoted pair is then
    a pair no rule can place, so with an install record the next update left
    the file as it is and the uninstall stopped at it. A fix that keeps no
    block changes every BEGIN marker line in the file, the quoted one too.
    """
    text = _lines("mine", "````md", B, "ex", E, "````", "", B, "old")
    message = stray_fix_text(text, TAKES_OUT)
    assert _changes(message) == [8, 3]
    fixed = _follow(text, _changes(message))
    assert not uncertain_pairs(fixed)
    assert not has_stray_begin(fixed)
    assert merge_managed_block(fixed, "Rule.", recorded=True) != fixed


# -- promise-remove ----------------------------------------------------------


def test_a_fix_that_keeps_a_block_leaves_no_marker_for_the_uninstall_to_show() -> None:
    """A stray BEGIN marker above a whole block, and BEGIN markers in code below it.

    The fix changed the stray marker line alone. Once the update replaced
    the block, the uninstall's strip joined the list item above it with the
    indented code block below, and the BEGIN markers that were in code read
    as a whole block and a stray BEGIN. The fix now changes every BEGIN
    marker line but the block's own.
    """
    text = _lines(
        "- item",
        B,
        "- rule item",
        B,
        "rule one",
        E,
        "  ```sh",
        "code",
        B,
        B,
        "```",
        E,
    )
    message = stray_fix_text(text, REPLACES)
    assert "if lines 4 to 6 are Apothem's block" in message
    assert _changes(message) == [10, 9, 2]
    fixed = _follow(text, _changes(message))
    merged = merge_managed_block(fixed, "New rule.")
    assert whole_blocks(merged) == [(4, 6)]
    removed = remove_managed_block(merged)
    assert not whole_blocks(removed)
    assert not has_stray_begin(removed)


# -- promise-refusal ---------------------------------------------------------


def _size_refusal(tmp_path: Path, text: str) -> str:
    """Return OpenClaw's size refusal for a rules file that holds *text*."""
    workspace = rules_file.Workspace(tmp_path / "workspace")
    workspace.rules_file.parent.mkdir(parents=True)
    workspace.rules_file.write_bytes(text.encode("utf-8"))
    config = {"agents": {"defaults": {"bootstrapMaxChars": 1}}}
    reason = rules_file.refusal(
        merge_managed_block(text, "Apothem rule."), config, workspace
    )
    assert reason is not None
    return reason


def test_the_size_refusal_names_every_marker_line_its_fix_needs(
    tmp_path: Path,
) -> None:
    """A stray BEGIN marker above a code block no line closes, then more markers.

    The refusal named only the line that reads as a stray BEGIN marker now
    (line 1). Once it changed, the BEGIN marker at line 5 started no whole
    block in its turn, and the file still did not fit. Every other caller
    gives this file one fix: a closing line for the code block, and lines
    5, 4 and 1 changed. The refusal now names the same lines.
    """
    text = _lines("   " + B, "````", E, B, B, E)
    reason = _size_refusal(tmp_path, text)
    assert (
        "add a line of 4 backticks below line 6, change lines 1, 4 and 5 by "
        "adding a word inside each comment, and delete that old text by hand"
    ) in reason
    fixed = _follow(text, [5, 4, 1]) + "````\n"
    assert not has_stray_begin(fixed)
    assert not whole_blocks(fixed)


def test_the_size_refusal_for_one_stray_marker_still_names_its_line(
    tmp_path: Path,
) -> None:
    """A block that lost its END marker: its BEGIN marker line is the only one."""
    reason = _size_refusal(tmp_path, _lines("# mine", B, "old rule"))
    assert (
        "change line 2 by adding a word inside its comment and delete that old "
        "text by hand"
    ) in reason


# -- close-reads-opener ------------------------------------------------------


_NO_STEPS = "Apothem cannot give numbered steps for this fix."


def test_no_numbered_steps_where_an_html_comment_holds_the_fence_opener() -> None:
    """An END marker that lost its ``-->`` opens an HTML comment block.

    In CommonMark the comment runs to the next line that holds ``-->`` (the
    BEGIN marker line), so ``~~~md`` is no fence opener; Apothem reads it as
    one. A closing line added below the last line would then open a code
    block in a viewer, over the block the next update appends, so the fix
    gives no numbered steps and says why.
    """
    text = _lines("<!-- END APOTHEM MANAGED BLOCK", "~~~md", B)
    assert trailing_fence(text) == (2, "~~~")
    message = stray_fix_text(text, REPLACES)
    assert "Below line" not in message
    assert _changes(message) == []
    assert _NO_STEPS in message
    assert "a code block that opens at line 2," in message


def test_the_size_refusal_gives_no_steps_where_the_other_warnings_give_none(
    tmp_path: Path,
) -> None:
    """OpenClaw's size refusal says the same as the other warnings for the file."""
    text = _lines("<!-- END APOTHEM MANAGED BLOCK", "~~~md", B, "old")
    reason = _size_refusal(tmp_path, text)
    assert "by adding a word" not in reason
    assert "add a line of" not in reason
    assert (
        "Apothem cannot give the steps that fix that marker line. It reads the "
        "file as ending inside a code block that opens at line 2,"
    ) in reason
    assert reason.endswith(
        "Delete that old text by hand, keeping your own text, or shorten the "
        "profile's custom rules, or raise the limit."
    )


def test_the_scanner_reads_a_fence_in_an_html_block_as_a_fence() -> None:
    """Apothem reads a code fence in an HTML block as it reads any other one.

    A Markdown viewer reads the lines of an HTML block as its text; the
    warnings name that limit, and a fix whose closing line it would change
    gives no numbered steps (see the test above).
    """
    assert trailing_fence(_lines("<!-- draft", "```", "-->")) == (2, "```")
    assert trailing_fence(_lines("<div>", "```", "")) == (2, "```")
    assert trailing_fence(_lines("<!-- note -->", "```")) == (2, "```")


def test_a_marker_line_in_an_html_block_still_reads_as_a_marker() -> None:
    """A marker line after an HTML block's first line is still a marker."""
    assert whole_blocks(_lines("<!-- draft", B, "rule", E)) == [(2, 4)]
    assert whole_blocks(_lines("<div>", B, "rule", E, "</div>")) == [(2, 4)]
    assert whole_blocks(_lines("<pre>", "```", B, "rule", E, "</pre>")) == [(3, 5)]


# -- timing ------------------------------------------------------------------

#: A paragraph, a list and a closed code block, about 100 bytes.
_FILLER = (
    "Some text of mine about the project, with a few words.\n\n- item one\n"
    "- item two\n\n```sh\nmake test\n```\n\n"
)


def _large(seed: int) -> str:
    """Return a file of about 1 MB with a pair in code and a stray BEGIN marker.

    *seed* goes into the text, so no run reads a text an earlier run read.
    """
    part = _FILLER * (250_000 // len(_FILLER)) + f"seed {seed}\n\n"
    return (
        f"{part}```\n{B}\nrule\n{E}\n```\n\n{part}{B}\nold\n\n{part}"
        f"```md\n{B}\nex\n{E}\n```\n\n{part}"
    )


@pytest.mark.parametrize("caller", ["install", "uninstall", "verify", "unlisted"])
def test_each_message_for_a_1_mb_file_takes_well_under_a_second(
    tmp_path: Path, caller: str
) -> None:
    """lifecycle-r6-1: each message for a 1 MB file took 0.6 to 5.6 seconds.

    Each read of the file for its markers cost about half a second, and a
    caller read the same text up to ten times. Every run here builds its
    message from a text no earlier run read, so it is timed as a command
    meets the file. The best of three runs must stay under a second; each
    takes about 0.45 seconds where it took 1.4 to 5.6 before.
    """
    target = tmp_path / "CLAUDE.md"
    builds: dict[str, Callable[[], object]] = {
        "install": lambda: stray_begin_install_warnings([_result(target, "unchanged")]),
        "uninstall": lambda: sentinel_refusal(target, recorded=True),
        "verify": lambda: stray_begin_note([target], then="run apothem update"),
        "unlisted": lambda: unlisted_block_warnings(tmp_path),
    }
    took = []
    for seed in range(3):
        target.write_bytes(_large(seed).encode("utf-8"))
        start = time.perf_counter()
        assert builds[caller]()
        took.append(time.perf_counter() - start)
    assert min(took) < 1.0, took


def _result(path: Path, outcome: str) -> MaterializationResult:
    """Return an install result for the managed-block file *path*."""
    return MaterializationResult(
        outcome=outcome, operation="sentinel_merge", path=str(path), message=""
    )


def test_no_numbered_steps_after_a_lazy_list_item_line() -> None:
    """A list item's text goes on at the left margin, then a fence in the item.

    CommonMark keeps the item open across that line, so the fence indented
    three columns sits in it and ends with it at the next line at the margin.
    Apothem ends the item at that line and reads the fence as open to the
    end of the file. A closing line added there would open a code block in a
    viewer, so the fix gives no numbered steps and says why.
    """
    text = _lines("- item", "lazy", "   ~~~md", "code", "# Head", B, "old")
    assert trailing_fence(text) == (3, "~~~")
    message = stray_fix_text(text, TAKES_OUT)
    assert "Below line" not in message
    assert _changes(message) == []
    assert _NO_STEPS in message
    assert "a code block that opens at line 3," in message


def test_a_closing_line_is_still_given_where_a_viewer_reads_alike() -> None:
    """With no HTML block and no lazy list line above it, the fix closes the code block."""
    text = _lines(B, "old", "", "- item", "  more", "  ~~~md", "  code")
    message = stray_fix_text(text, TAKES_OUT)
    assert "A1. Below line 7, add a line of 3 tildes, indented 2 spaces." in message
    assert _NO_STEPS not in message
    lazy = _lines(B, "old", "", "- item", "more", "  ~~~md", "  code")
    assert _NO_STEPS in stray_fix_text(lazy, TAKES_OUT)


def test_no_numbered_steps_where_a_lazy_list_line_moves_a_fence_at_the_margin() -> None:
    """A fence in a list item after a lazy line changes how the fences below it pair.

    CommonMark keeps the item open across ``text``, so the indented opener
    starts a code block in it, which the first line of four backticks ends
    by ending the item; that line then opens a code block of its own, which
    the second one closes. Apothem ends the item at ``text`` and pairs the
    indented opener with the first line of four backticks, so it reads the
    second one as opening the code block the file ends in. A closing line
    added below the last line would open a code block in a viewer, so the
    fix gives no numbered steps, though that opener is not indented.
    """
    text = _lines("- item", "text", "  ```md", "````", "````", B)
    assert trailing_fence(text) == (5, "````")
    message = stray_fix_text(text, REPLACES)
    assert "Below line" not in message
    assert _changes(message) == []
    assert _NO_STEPS in message
    assert "a code block that opens at line 5," in message
    tilde = _lines("2) item", "text", "   ~~~sh", "~~~", "```", B, " ~~~")
    assert trailing_fence(tilde) == (5, "```")
    message = stray_fix_text(tilde, REPLACES)
    assert _changes(message) == []
    assert "a code block that opens at line 5," in message


def test_no_numbered_steps_after_a_lazy_line_below_a_blank_line_in_the_item() -> None:
    """A list item stays open across a blank line for a line indented to its text.

    ``more`` sits in the item after the blank line, ``lazy`` goes on its text
    at the left margin, and the fence below sits in the item for a viewer
    but not for Apothem.
    """
    text = _lines("- item", "", "  more", "lazy", "  ```md", B, "old")
    assert trailing_fence(text) == (5, "```")
    message = stray_fix_text(text, TAKES_OUT)
    assert _changes(message) == []
    assert "a code block that opens at line 5," in message


def test_a_closing_line_is_given_once_the_item_of_a_lazy_line_ends() -> None:
    """A line at the left margin after a blank line ends the item for a viewer too.

    So does a list item at the left margin: the indented fence after either
    reads alike, and the fix closes its code block.
    """
    text = _lines("- item", "lazy", "", "# Head", "", "  ```md", B, "old")
    message = stray_fix_text(text, TAKES_OUT)
    assert _NO_STEPS not in message
    assert "A1. Below line 8, add a line of 3 backticks." in message
    sibling = _lines(B, "old", "", "- a", "- b", "  ```md", "  code")
    message = stray_fix_text(sibling, TAKES_OUT)
    assert _NO_STEPS not in message
    assert "A1. Below line 7, add a line of 3 backticks, indented 2 spaces." in message
