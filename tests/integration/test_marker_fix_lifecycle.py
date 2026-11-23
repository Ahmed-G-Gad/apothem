# SPDX-License-Identifier: MIT

"""Each numbered fix a warning prints, followed literally, through the real CLI.

For Codex and Claude Code, on a clean HOME: install, then reshape the file
Apothem keeps its block in so Apothem cannot place its marker lines (its
block inside a code block of yours, with an example or only text below; a
BEGIN marker that lost its END above it; an older block whose END marker a
rule hid in code, with a marker example of yours below it). The update is
partial (exit code 2) and its warning prints numbered fixes. Each fix is
then followed on its own, step by step in the order printed, each line
number taken as it stands; after it the update exits 0, verify exits 0, the
file holds one Apothem BEGIN marker, and every line of yours outside the
lines the fix calls Apothem's block is still there and reads as before in a
CommonMark viewer (markdown-it). The uninstall's first fix is followed the
same way, and the uninstall run again then finishes and leaves no marker.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest

from apothem.lib.harness_materializer import (
    APOTHEM_BLOCK_BEGIN,
    APOTHEM_BLOCK_END,
    complete_managed_block,
)
from tests.integration.test_unclear_block_lifecycle import (
    _PROFILE,
    SandboxFactory,
    _recorded_anchors,
    sandbox_factory,
)
from tests.unit.test_marker_fix_steps import _fixes, _follow, _roles

B, E = APOTHEM_BLOCK_BEGIN, APOTHEM_BLOCK_END
# The fixture the tests below take by name.
__all__ = ["sandbox_factory"]


def _sA2(block: str) -> str:
    return (
        f"OP My notes:\n```\nOP make test\n\n{block}\n```\nOP my text KEEP1\n"
        "```sh\nOP ls KEEP2\n```\nOP my tail KEEP3\n"
    )


def _plain(block: str) -> str:
    return f"OP My notes:\n```\nOP make test\n\n{block}\n```\nOP my text KEEP1\n"


def _sF(block: str) -> str:
    tail = "".join(f"OP KEEP{n}\n" for n in range(2, 7))
    return (
        f"OP # mine KEEP0\n{B}\nold rule\n```\nold code\n{block}\n```\n"
        f"OP tail KEEP1\n{tail}"
    )


def _sEb(block: str) -> str:
    del block
    return (
        f"OP # mine KEEP0\n{B}\nold rule text\nRun:\n```sh\nnpm test\n{E}\n```\n"
        f"OP my text KEEP1\nOP Example KEEP2:\n{B}\nOP example body KEEPX\n{E}\n"
    )


SHAPES = {"sA2": _sA2, "plain": _plain, "sF": _sF, "sE-b": _sEb}
FIXES = {"sA2": "AB", "plain": "AB", "sF": "AB", "sE-b": "ABC"}


def _reshape(anchor: Path, shape: str) -> list[str]:
    """Put *anchor*'s block into *shape*; return the file's lines."""
    text = anchor.read_bytes().decode("utf-8")
    block = complete_managed_block(text)
    assert block is not None, text[:200]
    at = text.index(block)
    after = text[at + len(block) :].lstrip("\n")
    new = text[:at] + SHAPES[shape](block) + (f"\n{after}" if after else "")
    anchor.write_bytes(new.encode("utf-8"))
    return new.split("\n")[:-1]


def _lines(anchor: Path) -> list[str]:
    """Return the lines of *anchor*, none when the uninstall deleted it."""
    text = anchor.read_bytes().decode("utf-8") if anchor.exists() else ""
    return text.split("\n")[:-1] if text.endswith("\n") else text.split("\n")


def _message(payload: dict[str, Any], anchor: Path) -> str:
    [message] = [
        str(warning["message"])
        for warning in payload["warnings"]
        if Path(str(warning["path"])) == anchor
        and "Fix A, if " in str(warning["message"])
    ]
    return message


def _apply(anchor: Path, lines: list[str], message: str, letter: str) -> set[int]:
    """Follow fix *letter* of *message* on *anchor*; return the lines it may drop.

    Those are the 0-based lines the fix names or calls Apothem's block.
    """
    [(label, fix)] = [
        (label, fix)
        for label, fix in _fixes(message)
        if fix.startswith(f"Fix {letter},")
    ]
    texts, _, named = _follow(lines, fix)
    anchor.write_bytes("".join(f"{line}\n" for line in texts).encode("utf-8"))
    claim = re.search(r"lines (\d+) to (\d+) are Apothem's block", label)
    if claim:
        named |= set(range(int(claim[1]) - 1, int(claim[2])))
    return named


def _assert_yours_kept(anchor: Path, lines: list[str], dropped: set[int]) -> None:
    """Each line of yours outside *dropped* is there and reads as before."""
    now = _lines(anchor)
    before = _roles("".join(f"{line}\n" for line in lines))
    after = _roles("".join(f"{line}\n" for line in now))
    mine = [
        (line, before[at])
        for at, line in enumerate(lines)
        if line.startswith("OP ") and at not in dropped
    ]
    seen = [(line, after[at]) for at, line in enumerate(now) if line.startswith("OP ")]
    for item in mine:
        assert item in seen, (item, now)
    assert sum(1 for line in now if line.strip() == B) == 1, now


@pytest.mark.parametrize("harness_id", ["codex", "claude-code"])
@pytest.mark.parametrize(
    ("shape", "letter"),
    [(shape, letter) for shape, letters in FIXES.items() for letter in letters],
)
def test_following_an_update_fix_lets_the_next_update_pass(
    harness_id: str, shape: str, letter: str, sandbox_factory: SandboxFactory
) -> None:
    box = sandbox_factory(harness_id)
    box.install()
    [anchor] = _recorded_anchors(harness_id)
    lines = _reshape(anchor, shape)

    payload = box.partial("update", "--profile", _PROFILE)
    dropped = _apply(anchor, lines, _message(payload, anchor), letter)
    code, output = box.invoke("update", "--profile", _PROFILE, "--json")
    verify, verify_output = box.invoke("verify", "--json")

    assert code == 0, output
    assert json.loads(output)["status"] == "success"
    assert verify == 0, verify_output
    _assert_yours_kept(anchor, lines, dropped)


@pytest.mark.parametrize("harness_id", ["codex", "claude-code"])
@pytest.mark.parametrize("shape", sorted(SHAPES))
def test_following_the_uninstall_fix_lets_the_uninstall_finish(
    harness_id: str, shape: str, sandbox_factory: SandboxFactory
) -> None:
    box = sandbox_factory(harness_id)
    box.install()
    [anchor] = _recorded_anchors(harness_id)
    lines = _reshape(anchor, shape)

    code, output = box.invoke("uninstall", "--yes", "--json")
    assert code == 2, output
    dropped = _apply(anchor, lines, _message(json.loads(output), anchor), "A")
    again, again_output = box.invoke("uninstall", "--yes")

    assert again == 0, again_output
    now = _lines(anchor)
    assert not [line for line in now if line.strip() in {B, E}], now
    before = _roles("".join(f"{line}\n" for line in lines))
    after = _roles("".join(f"{line}\n" for line in now))
    mine = [
        (line, before[at])
        for at, line in enumerate(lines)
        if line.startswith("OP ") and at not in dropped
    ]
    seen = [(line, after[at]) for at, line in enumerate(now) if line.startswith("OP ")]
    for item in mine:
        assert item in seen, (item, now)
