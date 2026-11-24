# SPDX-License-Identifier: MIT

"""A BEGIN marker with no END marker gets a numbered CHANGE step, not a delete.

Every warning for such a marker (install and update, verify and doctor, the
uninstall's) names the marker's line and gives a numbered step that changes
it: a word added inside its comment, so it no longer reads as a marker. The
step is printed through the same renderer as the other marker fixes and
checked on a copy of the file before it prints; when the check fails, the
warning gives the fallback, which numbers no edit. Deleting a marker line
changed how a line of the operator's read; changing it in place does not.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest
from click.testing import CliRunner

from apothem.cli import main
from apothem.cli._cmd_uninstall import _FIX_STRAY
from apothem.cli._stray_begin_report import stray_begin_note
from apothem.harnesses._shared import install_driver
from apothem.harnesses._shared import install_driver_blocks as blocks
from apothem.harnesses._shared import install_driver_steps as steps
from apothem.harnesses._shared.install_driver_steps import FALLBACK, INTRO
from apothem.lib.harness_materializer import (
    APOTHEM_BLOCK_BEGIN,
    APOTHEM_BLOCK_END,
    has_stray_begin,
    whole_blocks,
)
from apothem.schemas import profile_minimal_path
from tests.unit.test_marker_fix_steps import _fixes, _follow
from tests.unit.test_stray_begin_reporting import (
    SandboxFactory,
    _anchor,
    _flat,
    _holds,
    _names,
    _Sandbox,
    sandbox_factory,
)

__all__ = ["sandbox_factory"]

B = APOTHEM_BLOCK_BEGIN
E = APOTHEM_BLOCK_END

#: A BEGIN marker at line 2 that lost its END marker, then Apothem's block at
#: lines 6 to 8.
_STRAY_ABOVE = f"# top\n{B}\nold rules\nmy own line\n\n{B}\nnew rules\n{E}\n"

_DELETE = re.compile(r"\b[Dd]elete (?:that|the) (?:marker )?line\b")


def _merged(
    path: Path, outcome: str = "updated"
) -> install_driver.MaterializationResult:
    return install_driver.MaterializationResult(
        outcome=outcome, operation="sentinel_merge", path=str(path), message=""
    )


def _uninstalled(path: Path) -> install_driver.MaterializationResult:
    return install_driver.MaterializationResult(
        outcome="updated", operation="surgical_uninstall", path=str(path), message=""
    )


def _lines(text: str) -> list[str]:
    return text.split("\n")[:-1]


# --- each caller names the line and gives the CHANGE step ---------------------


def test_the_install_warning_changes_the_marker_line_it_names(tmp_path: Path) -> None:
    target = tmp_path / "AGENTS.md"
    target.write_text(_STRAY_ABOVE, encoding="utf-8")

    [warning] = blocks.stray_begin_install_warnings([_merged(target)])
    message = warning.message

    assert "BEGIN marker at line 2" in message
    assert INTRO in message
    assert (
        "Fix A, if lines 6 to 8 are Apothem's block: A1. Change line 2: add a word "
        "inside its comment. The next update then replaces Apothem's block."
    ) in message
    assert not _DELETE.search(message), message
    assert _holds(_STRAY_ABOVE, message) == 1


def test_a_preview_with_no_block_yet_changes_the_marker_line(tmp_path: Path) -> None:
    target = tmp_path / "AGENTS.md"
    text = f"# top\n{B}\nold rules\nmy own line\n"
    target.write_text(text, encoding="utf-8")

    [warning] = blocks.stray_begin_install_warnings(
        [_merged(target, "unchanged")], dry_run=True
    )

    assert "Change line 2: add a word inside its comment." in warning.message
    assert "The next update then adds Apothem's block to the file." in warning.message
    assert not _DELETE.search(warning.message), warning.message
    assert _holds(text, warning.message) == 1


def test_the_verify_note_gives_each_file_its_own_steps(tmp_path: Path) -> None:
    one = tmp_path / "one.md"
    two = tmp_path / "two.md"
    one.write_text(_STRAY_ABOVE, encoding="utf-8")
    two.write_text(f"{B}\nold\n\nmine\n\n{B}\nnew\n{E}\n", encoding="utf-8")

    note = stray_begin_note([one, two], then="run apothem update")

    first, second = note.index(str(one)), note.index(str(two))
    assert first < note.index("Change line 2:") < second
    assert second < note.index("Change line 1:")
    assert "an Apothem BEGIN marker at line 2" in note
    assert "an Apothem BEGIN marker at line 1" in note
    assert not _DELETE.search(note), note
    assert note.endswith("Then run apothem update")
    assert _holds(_STRAY_ABOVE, note[first:second]) == 1


def test_several_stray_markers_change_from_the_bottom_up(tmp_path: Path) -> None:
    target = tmp_path / "AGENTS.md"
    text = f"{B}\nold one\n\n{B}\nold two\n\nmine\n\n{B}\nnew\n{E}\n"
    target.write_text(text, encoding="utf-8")

    [warning] = blocks.stray_begin_install_warnings([_merged(target)])

    assert "BEGIN markers at lines 1 and 4" in warning.message
    assert (
        "A1. Change line 4: add a word inside its comment. A2. Change line 1: add "
        "a word inside its comment."
    ) in warning.message
    assert _holds(text, warning.message) == 1


def test_the_endless_block_warning_changes_the_marker_line(tmp_path: Path) -> None:
    target = tmp_path / "CLAUDE.md"
    text = f"# top\n\n{B}\nold rules\nmy own line\n"
    target.write_text(text, encoding="utf-8")

    warning = blocks.endless_block_warning(target, "surgical_uninstall")

    assert warning is not None
    assert "BEGIN marker at line 3" in warning.message
    assert "Change line 3: add a word inside its comment." in warning.message
    assert "No Apothem block is then left in this file." in warning.message
    assert not _DELETE.search(warning.message), warning.message
    assert _holds(text, warning.message) == 1


def test_the_uninstall_warning_for_a_begin_marker_left_changes_it(
    tmp_path: Path,
) -> None:
    target = tmp_path / "CLAUDE.md"
    text = f"# top\n{B}\nold rules\n\nmy own line\n"
    target.write_text(text, encoding="utf-8")

    [warning] = blocks.stray_begin_warnings([_uninstalled(target)])
    [retired] = blocks.stray_begin_warnings(
        [_uninstalled(target)], why=blocks.RETIRED_WHY
    )

    for message in (warning.message, retired.message):
        assert "BEGIN marker at line 2" in message
        assert "Change line 2: add a word inside its comment." in message
        assert not _DELETE.search(message), message
        assert _holds(text, message) == 1


def test_the_uninstall_summary_points_at_the_numbered_step() -> None:
    text = _FIX_STRAY.format(count=1)

    assert "delete that marker line" not in text
    assert "numbered step" in text


def test_a_fix_the_check_refuses_gives_the_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "AGENTS.md"
    target.write_text(_STRAY_ABOVE, encoding="utf-8")
    monkeypatch.setattr(steps, "passes", lambda *_args, **_kwargs: False)

    [warning] = blocks.stray_begin_install_warnings([_merged(target)])
    note = stray_begin_note([target], then="run apothem update")

    for message in (warning.message, note):
        assert "Change line" not in message
        assert FALLBACK.split(".")[0] in message
        assert not _DELETE.search(message), message


def test_the_end_marker_warning_says_why_not_to_add_it_back_instead(
    tmp_path: Path,
) -> None:
    target = tmp_path / "AGENTS.md"
    target.write_text(_STRAY_ABOVE, encoding="utf-8")

    [warning] = blocks.stray_begin_install_warnings([_merged(target)])

    assert warning.message.endswith(
        "Do not add the END marker back instead of changing the marker line: the "
        "file would then hold two Apothem blocks, which install and update leave "
        "as they are."
    )


# --- following the printed step through the CLI -------------------------------


def _update(box: _Sandbox) -> tuple[int, dict[str, Any]]:
    code, output = box.invoke(
        "update", "--profile", str(profile_minimal_path()), "--json"
    )
    payload: dict[str, Any] = json.loads(output)
    return code, payload


@pytest.mark.parametrize("harness_id", ["codex", "claude-code"])
def test_following_the_printed_step_ends_with_one_block_and_verify_passing(
    harness_id: str, sandbox_factory: SandboxFactory
) -> None:
    box = sandbox_factory(harness_id)
    box.install()
    anchor = _anchor(box)
    text = anchor.read_bytes().decode("utf-8")
    lost = text.replace(f"{E}\n", "", 1)
    anchor.write_bytes(f"# my top line\n\n{lost}\nmy own line\n".encode())

    code, payload = _update(box)
    after_first = anchor.read_bytes().decode("utf-8")
    [message] = [
        str(w["message"])
        for w in payload["warnings"]
        if _names(str(w["message"]), anchor)
    ]
    assert code == 0, payload
    assert has_stray_begin(after_first)
    [(_, fix)] = _fixes(message)
    assert re.search(r"Change line \d+: add a word inside its comment\.", fix)
    fixed, _, _ = _follow(_lines(after_first), fix)
    anchor.write_bytes("".join(f"{line}\n" for line in fixed).encode())

    again, again_payload = _update(box)
    verify, verify_output = box.invoke("verify")
    final = anchor.read_bytes().decode("utf-8")

    assert again == 0, again_payload
    assert not [
        w for w in again_payload["warnings"] if _names(str(w["message"]), anchor)
    ]
    assert verify == 0, _flat(verify_output)
    assert len(whole_blocks(final)) == 1
    assert not has_stray_begin(final)
    mine = [line for line in final.splitlines() if line.startswith(("# my", "my "))]
    assert mine == ["# my top line", "my own line"]


def test_the_uninstall_cli_names_the_line_to_change(
    sandbox_factory: SandboxFactory,
) -> None:
    box = sandbox_factory("claude-code")
    box.install()
    anchor = _anchor(box)
    anchor.write_bytes(f"# mine\n{B}\nmy notes\n\n".encode() + anchor.read_bytes())

    code, output = box.invoke("uninstall", "--yes", "--json")
    payload = json.loads(output)
    [message] = [
        _flat(str(w["message"]))
        for w in payload["warnings"]
        if _names(str(w["message"]), anchor)
    ]

    assert code == 0, output
    assert "BEGIN marker at line 2" in message
    assert "Change line 2: add a word inside its comment." in message


@pytest.mark.parametrize("harness_id", ["codex"])
def test_verify_and_doctor_name_the_line_to_change(
    harness_id: str, sandbox_factory: SandboxFactory
) -> None:
    box = sandbox_factory(harness_id)
    box.install()
    anchor = _anchor(box)
    text = anchor.read_bytes().decode("utf-8")
    anchor.write_bytes((text.replace(E, "") + "my own line\n").encode())
    line = _lines(anchor.read_bytes().decode("utf-8")).index(B) + 1

    code, output = box.invoke("verify", "--json")
    doctor = CliRunner().invoke(main, ["doctor", "--json"])
    [check] = [
        c
        for c in json.loads(doctor.output)["checks"]
        if c["code"] == "harness.stray_begin"
    ]

    assert code == 1, output
    [row] = json.loads(output)["results"]
    for message in (row["message"], check["fix"]):
        assert f"BEGIN marker at line {line}" in message
        assert f"Change line {line}: add a word inside its comment." in message
