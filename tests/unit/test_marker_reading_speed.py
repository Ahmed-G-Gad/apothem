# SPDX-License-Identifier: MIT

"""A command reads a 1 MB managed-block file for its markers in well under a second.

Each install, update, verify, doctor and uninstall reads the file it writes
for Apothem's marker lines, and a file with marker problems also gets a
message with numbered fixes. On a file of about 1 MB, dense with lists and
fenced code, one message took 0.5 to 1 s, and the reading for a file with
one whole block at its end, which every update, verify and uninstall makes,
took 0.5 to 0.9 s. Each test here times what a command does, file read
included, on a text no earlier run read (its first line differs), so a
reading kept from an earlier run cannot hide the cost.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path

import pytest

from apothem.cli._stray_begin_report import stray_begin_note
from apothem.harnesses._shared.install_driver_blocks import (
    markers_to_fix_at,
    sentinel_refusal,
    stray_begin_install_warnings,
)
from apothem.harnesses._shared.install_driver_retention import unlisted_block_warnings
from apothem.harnesses._shared.install_driver_types import MaterializationResult
from apothem.lib.harness_materializer import (
    APOTHEM_BLOCK_BEGIN,
    APOTHEM_BLOCK_END,
    merge_managed_block,
    remove_managed_block,
)

B, E = APOTHEM_BLOCK_BEGIN, APOTHEM_BLOCK_END

#: A heading, a paragraph, a list and two closed code blocks, about 160 bytes.
_PART = (
    "## Notes\n\nA line of my own text, then a list.\n\n* first\n* second\n\n"
    "~~~text\nplain\n~~~\n\n```py\nprint(1)\n```\n\n"
)

#: The most one message or one command may take, in seconds.
_BOUND = 0.5


def _filler(size: int) -> str:
    """Return *size* bytes or so of :data:`_PART`."""
    return _PART * (size // len(_PART))


def _shape(name: str) -> str:
    """Return a file of about 1 MB with the marker problem *name*."""
    quarter = _filler(250_000)
    quoted = f"~~~md\n{B}\nan example\n{E}\n~~~\n\n"
    return {
        "lone-begin-after-a-list-fence": (
            f"{quarter}{quarter}{quoted}{quarter}1. step\n   ```sh\n   run\n"
            f"{quarter}{B}\nold rule\n"
        ),
        "two-blocks-and-a-stray-begin": (
            f"{B}\nfirst\n{E}\n\n{quarter}{B}\nstray\n\n{quarter}{quoted}"
            f"{quarter}{B}\nsecond\n{E}\n\n{quarter}"
        ),
        "a-pair-in-code-and-a-lone-begin": (
            f"{quarter}```\n{B}\nrule\n{E}\n```\n\n{quarter}{B}\nold\n\n"
            f"{quarter}{quarter}"
        ),
    }[name]


def _result(path: Path, outcome: str, operation: str) -> MaterializationResult:
    return MaterializationResult(
        outcome=outcome, operation=operation, path=str(path), message=""
    )


def _timer(
    tmp_path: Path, text: str
) -> tuple[Path, Path, Callable[[Callable[[str], object]], float]]:
    """Return the file, a folder holding a copy, and a timer for runs on *text*.

    Each run writes a text no earlier run read. A run under the bound
    counts, so a pause elsewhere does not fail the test; at most three runs
    are timed.
    """
    target = tmp_path / "CLAUDE.md"
    folder = tmp_path / "unlisted"
    folder.mkdir()
    runs = iter(range(1_000))

    def timed(run: Callable[[str], object]) -> float:
        took = []
        for _ in range(3):
            variant = f"Run {next(runs)} of my notes.\n\n{text}"
            for path in (target, folder / "CLAUDE.md"):
                path.write_bytes(variant.encode("utf-8"))
            start = time.perf_counter()
            run(variant)
            took.append(time.perf_counter() - start)
            if took[-1] < _BOUND:
                break
        return round(min(took), 3)

    return target, folder, timed


@pytest.mark.parametrize(
    "name",
    [
        "lone-begin-after-a-list-fence",
        "two-blocks-and-a-stray-begin",
        "a-pair-in-code-and-a-lone-begin",
    ],
)
def test_each_message_for_a_fresh_1_mb_file_with_marker_problems_is_quick(
    tmp_path: Path, name: str
) -> None:
    text = _shape(name)
    assert len(text) > 900_000
    target, folder, timed = _timer(tmp_path, text)

    def printed(build: Callable[[], object]) -> Callable[[str], object]:
        def run(_variant: str) -> object:
            found = build()
            assert found, "the file has marker problems, so a message is printed"
            return found

        return run

    took = {
        "install": timed(
            printed(
                lambda: stray_begin_install_warnings(
                    [_result(target, "unchanged", "sentinel_merge")]
                )
            )
        ),
        "uninstall, recorded": timed(
            printed(lambda: sentinel_refusal(target, recorded=True))
        ),
        "uninstall": timed(printed(lambda: sentinel_refusal(target))),
        "verify": timed(
            printed(lambda: stray_begin_note([target], then="run apothem update"))
        ),
        "uninstall, no record": timed(printed(lambda: unlisted_block_warnings(folder))),
    }
    slow = {caller: seconds for caller, seconds in took.items() if seconds >= _BOUND}
    assert not slow, f"seconds per message: {took}"


@pytest.mark.parametrize("where", ["end", "top", "end-crlf"])
def test_each_command_on_a_fresh_1_mb_file_with_one_block_is_quick(
    tmp_path: Path, where: str
) -> None:
    """The file holds one whole block and no marker problem, as an install leaves it."""
    block = f"{B}\nApothem rule.\n{E}\n"
    filler = _filler(1_000_000)
    text = f"{block}\n{filler}" if where == "top" else f"{filler}{block}"
    if where == "end-crlf":
        text = text.replace("\n", "\r\n")
    target, folder, timed = _timer(tmp_path, text)
    body = "Apothem rule one.\nRun:\n```sh\nmake test\n```"

    def update(variant: str) -> None:
        target.write_bytes(merge_managed_block(variant, body, recorded=True).encode())
        assert not stray_begin_install_warnings(
            [_result(target, "updated", "sentinel_merge")]
        )

    def uninstall(variant: str) -> None:
        assert sentinel_refusal(target, recorded=True) is None
        assert B not in remove_managed_block(variant)

    def verify(_variant: str) -> None:
        assert not markers_to_fix_at(target)

    def unlisted(_variant: str) -> None:
        assert unlisted_block_warnings(folder)

    took = {
        name: timed(command)
        for name, command in {
            "update": update,
            "verify": verify,
            "uninstall": uninstall,
            "uninstall, no record": unlisted,
        }.items()
    }
    slow = {name: seconds for name, seconds in took.items() if seconds >= _BOUND}
    assert not slow, f"seconds per command: {took}"
