# SPDX-License-Identifier: MIT

"""verify and doctor name the file a stray Apothem BEGIN marker fails them in.

A BEGIN marker that starts no whole block (its END marker is gone) fails verify
for the tool whose managed-block file holds it, and install and update keep it,
so re-running them does not help. A failed verify row and doctor's failed check
name each such file and say to delete the marker line; the plain verify line
then leaves out the adapter's output path, which can be another file. Only the
files a tool's install keeps a block in count: a project's own CLAUDE.md does
not fail a project-scope tool's verify.

A file whose marker pairs no rule can place gets its own text: each pair with
the lines of its markers and where they read, each BEGIN marker that starts no
pair, and a fix for each case that says what follows from it. Install gives
that text when the merge left the file as it is, and when it wrote its block
and the file holds no whole block (a rule in the profile left the pair rule 3
fires on, or a code block of yours left open above the block is closed by a
line in it); a recorded file in that state still counts as an install.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import yaml
from click.testing import CliRunner

import apothem
from apothem.cli import main
from apothem.cli._stray_begin_report import stray_begin_note
from apothem.harnesses._shared import install_driver, install_driver_merge
from apothem.harnesses._shared import install_driver_blocks as blocks
from apothem.harnesses._shared.install_driver_blocks import (
    stray_begin_files,
    stray_begin_install_warnings,
)
from apothem.harnesses._shared.install_driver_blocktext import TAKES_OUT
from apothem.harnesses._shared.install_driver_evidence import (
    _carries_managed_block,
    listed_in_record,
)
from apothem.harnesses._shared.install_driver_layout import _load_rules
from apothem.harnesses._shared.install_driver_ownership import current_target
from apothem.harnesses._shared.install_driver_steps import split_lines
from apothem.lib import install_ledger
from apothem.lib.harness_materializer import (
    APOTHEM_BLOCK_BEGIN,
    APOTHEM_BLOCK_END,
    complete_managed_block,
    has_stray_begin,
    merge_managed_block,
    uncertain_pairs,
    whole_blocks,
    wrap_managed_block,
)
from apothem.lib.harness_registry import HARNESS_REGISTRY, HarnessRegistryEntry
from apothem.lib.install_ledger import LedgerRecord, LedgerTarget
from apothem.schemas import profile_minimal_path
from tests.unit.test_marker_fix_steps import _check, _fixes, _follow


class _Sandbox:
    """A clean HOME and project, plus a CLI runner bound to one harness."""

    def __init__(
        self, entry: HarnessRegistryEntry, tmp_path: Path, mp: pytest.MonkeyPatch
    ) -> None:
        self.entry = entry
        self.home = tmp_path / "home"
        self.project = tmp_path / "project"
        self.home.mkdir()
        self.project.mkdir()
        mp.setenv("HOME", str(self.home))
        mp.setenv("USERPROFILE", str(self.home))
        mp.delenv("CODEX_HOME", raising=False)
        mp.delenv("XDG_CONFIG_HOME", raising=False)

    def scope(self) -> list[str]:
        if self.entry.scope == "project":
            return ["--project", str(self.project)]
        return []

    def invoke(self, *args: str) -> tuple[int, str]:
        result = CliRunner().invoke(
            main, [*args, "--harness", self.entry.public_id, *self.scope()]
        )
        return result.exit_code, result.output

    def install(self) -> dict[str, Any]:
        code, output = self.invoke(
            "install", "--profile", str(profile_minimal_path()), "--json"
        )
        assert code == 0, output
        payload: dict[str, Any] = json.loads(output)
        return payload

    def partial(self, *args: str) -> dict[str, Any]:
        """Run *args* with --json; it leaves a file as it is, so it is partial.

        The exit code is 2, the status ``partial``, and a warning carries
        ``left_as_is``.
        """
        code, output = self.invoke(*args, "--json")
        assert code == 2, output
        payload: dict[str, Any] = json.loads(output)
        assert payload["status"] == "partial", payload["status"]
        assert [
            w for w in payload["warnings"] if w.get("detail", {}).get("left_as_is")
        ], payload["warnings"]
        return payload


SandboxFactory = Callable[[str], _Sandbox]


@pytest.fixture
def sandbox_factory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> SandboxFactory:
    def make(harness_id: str) -> _Sandbox:
        entry = next(e for e in HARNESS_REGISTRY if e.public_id == harness_id)
        return _Sandbox(entry, tmp_path, monkeypatch)

    return make


def _anchor(box: _Sandbox) -> Path:
    """Return the file the sandbox harness's install keeps its managed block in."""
    return {
        "codex": box.home / ".codex" / "AGENTS.md",
        "claude-code": box.home / ".claude" / "CLAUDE.md",
        "gemini-cli": box.project / "GEMINI.md",
    }[box.entry.public_id]


def _drop_end_marker(anchor: Path) -> None:
    """Cut the END marker out of *anchor* and add a line of the operator's."""
    text = anchor.read_text(encoding="utf-8").replace(APOTHEM_BLOCK_END, "")
    anchor.write_bytes((text + "my own line\n").encode())


def _key(path: str | Path) -> str:
    """Return *path* in the form two spellings of one location share."""
    return os.path.normcase(os.path.normpath(str(path)))


def _names(text: str, path: Path) -> bool:
    """Return True when *text* names *path*, case folded where the OS does."""
    return os.path.normcase(str(path)) in os.path.normcase(text)


# --- verify ------------------------------------------------------------------


@pytest.mark.parametrize("harness_id", ["codex", "gemini-cli"])
def test_a_failed_verify_row_names_the_file_with_the_stray_marker(
    harness_id: str, sandbox_factory: SandboxFactory
) -> None:
    box = sandbox_factory(harness_id)
    box.install()
    anchor = _anchor(box)
    _drop_end_marker(anchor)

    code, output = box.invoke("verify", "--json")

    assert code == 1, output
    [row] = json.loads(output)["results"]
    assert row["verified"] is False
    assert [_key(path) for path in row["stray_begin"]["files"]] == [_key(anchor)]
    assert _names(row["message"], anchor)
    assert "add a word inside its comment" in row["message"]
    assert row["stray_begin"]["message"] in row["message"]


def test_the_plain_verify_line_names_the_marked_file_not_the_adapter_output(
    sandbox_factory: SandboxFactory,
) -> None:
    """The adapter's output path is its settings.json; the marker is in CLAUDE.md."""
    box = sandbox_factory("claude-code")
    box.install()
    anchor = _anchor(box)
    _drop_end_marker(anchor)

    code, output = box.invoke("verify")

    assert code == 1, output
    assert "expected path" not in output
    assert "settings.json" not in output
    [note] = [line for line in output.splitlines() if "Note:" in line]
    assert _names(note, anchor)
    assert "add a word inside its comment" in note


def test_a_verify_failure_without_a_stray_marker_keeps_the_expected_path(
    sandbox_factory: SandboxFactory,
) -> None:
    box = sandbox_factory("codex")
    box.install()
    _anchor(box).unlink()

    code, output = box.invoke("verify")

    assert code == 1, output
    assert "expected path" in output
    assert "BEGIN marker" not in output


def test_a_project_claude_md_with_a_begin_marker_does_not_fail_a_tool_without_a_record(
    sandbox_factory: SandboxFactory,
) -> None:
    """Without an install record, only the manifest's block files are checked."""
    box = sandbox_factory("gemini-cli")
    box.install()
    install_ledger.ledger_path("gemini_cli").unlink()
    (box.project / "CLAUDE.md").write_text(
        f"# Notes\n\n{APOTHEM_BLOCK_BEGIN}\nmy own text\n", encoding="utf-8"
    )
    assert install_ledger.current_install_record("gemini_cli", root=box.project) is None

    code, output = box.invoke("verify", "--json")

    assert code == 0, output
    assert json.loads(output)["verified"] is True


# --- doctor ------------------------------------------------------------------


def test_doctor_names_the_marked_file_in_its_fix_and_still_starts_the_hooks(
    sandbox_factory: SandboxFactory,
) -> None:
    box = sandbox_factory("codex")
    box.install()
    anchor = _anchor(box)
    _drop_end_marker(anchor)

    result = CliRunner().invoke(main, ["doctor", "--json"])

    assert result.exit_code == 1, result.output
    payload = json.loads(result.output)
    failed = [c for c in payload["checks"] if c["status"] == "fail"]
    assert [c["code"] for c in failed] == ["harness.stray_begin"]
    [check] = failed
    assert check["harness"] == "codex"
    assert _names(check["fix"], anchor)
    assert "add a word inside its comment" in check["fix"]
    [row] = [r for r in payload["harnesses"] if r["name"] == "codex"]
    assert row["status"] == "verify_failed"
    assert row["verified"] is False
    assert row["hooks"]["probed"] >= 1
    assert row["hooks"]["failed"] == []


# --- the files stray_begin_files looks at ------------------------------------


def _marked(path: Path) -> Path:
    """Write *path* with a BEGIN marker that starts no whole block; return it."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"{APOTHEM_BLOCK_BEGIN}\nold rules\nmy own line\n", encoding="utf-8"
    )
    return path


def _record(harness: str, root: Path, *paths: Path) -> None:
    """Append an install record at *root* that lists *paths* as block files."""
    install_ledger.append_record(
        LedgerRecord.create(
            harness=harness,
            root=root,
            kind="install",
            targets=tuple(
                LedgerTarget(str(path), "sentinel_merge", "operator-owned")
                for path in paths
            ),
        )
    )


def test_a_file_the_manifest_and_the_record_both_name_is_listed_once(
    tmp_path: Path,
) -> None:
    root = tmp_path / ".codex"
    anchor = _marked(root / "AGENTS.md")
    _record("codex", root, anchor)

    found = stray_begin_files("codex", harness_root=root, project_root=None)

    assert found == [anchor]


def test_the_record_s_other_block_files_follow_the_manifest_s(tmp_path: Path) -> None:
    root = tmp_path / ".codex"
    anchor = _marked(root / "AGENTS.md")
    elsewhere = _marked(tmp_path / "workspace" / "AGENTS.md")
    _record("codex", root, elsewhere, anchor)

    found = stray_begin_files("codex", harness_root=root, project_root=None)

    assert found == [anchor, elsewhere]


def test_a_ledger_that_cannot_be_read_leaves_the_manifest_s_files(
    tmp_path: Path,
) -> None:
    root = tmp_path / ".codex"
    anchor = _marked(root / "AGENTS.md")
    ledger = install_ledger.ledger_path("codex")
    ledger.parent.mkdir(parents=True, exist_ok=True)
    # Bytes that are not UTF-8 make the ledger raise.
    ledger.write_bytes(b"\xff\xfe not utf-8\n")

    found = stray_begin_files("codex", harness_root=root, project_root=None)

    assert found == [anchor]


def test_a_project_file_of_its_own_is_not_looked_at_without_a_record(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    _marked(project / "CLAUDE.md")
    (project / "GEMINI.md").write_text("my own notes\n", encoding="utf-8")

    found = stray_begin_files("gemini_cli", harness_root=None, project_root=project)

    assert found == []


# --- what the messages say ---------------------------------------------------


def test_the_install_warning_says_to_change_the_marker_line(
    tmp_path: Path,
) -> None:
    target = tmp_path / "AGENTS.md"
    target.write_text(
        f"{APOTHEM_BLOCK_BEGIN}\nold rules\nmy own line\n\n"
        f"{APOTHEM_BLOCK_BEGIN}\nnew rules\n{APOTHEM_BLOCK_END}\n",
        encoding="utf-8",
    )
    merged = install_driver.MaterializationResult(
        outcome="updated",
        operation="sentinel_merge",
        path=str(target),
        message="merged",
    )

    [warning] = stray_begin_install_warnings([merged])

    assert warning.outcome == "warning"
    assert str(target) in warning.message
    assert APOTHEM_BLOCK_END in warning.message
    assert "BEGIN marker at line 1" in warning.message
    assert "A1. Change line 1: add a word inside its comment." in warning.message
    assert _OLD_TEXT in warning.message


def test_the_note_names_every_file(tmp_path: Path) -> None:
    files = [tmp_path / name for name in ("one.md", "two.md", "three.md")]
    for path in files:
        _marked(path)

    note = stray_begin_note(files, then="run apothem verify again")

    assert note.startswith(
        f"{files[0]} has an Apothem BEGIN marker at line 1 with no END marker."
    )
    places = [note.index(f"{path} has") for path in files]
    assert places == sorted(places)
    assert note.count("A1. Change line 1: add a word inside its comment.") == 3
    assert note.endswith("Then run apothem verify again")


def test_the_report_module_imports_in_a_fresh_interpreter() -> None:
    """The verify and doctor helper loads the install driver before its parts.

    In-process tests import the driver shim first, which hides an import cycle
    that only a fresh interpreter (the real ``apothem verify``) meets.
    """
    src_root = Path(apothem.__file__).resolve().parents[1]
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        part for part in (str(src_root), env.get("PYTHONPATH", "")) if part
    )
    result = subprocess.run(
        [sys.executable, "-c", "import apothem.cli._stray_begin_report"],
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert result.returncode == 0, result.stderr


# --- a byte order mark, CRLF endings, a project's own CLAUDE.md --------------


def _resave_with_a_bom(anchor: Path) -> None:
    """Re-save *anchor* as "UTF-8 with BOM" with a line of the operator's added."""
    anchor.write_bytes(b"\xef\xbb\xbf" + anchor.read_bytes() + b"\nmy own line\n")


def test_a_bom_in_front_of_the_block_still_counts_as_an_install(
    tmp_path: Path,
) -> None:
    anchor = tmp_path / "AGENTS.md"
    anchor.write_text(
        "\ufeff" + wrap_managed_block("rules") + "\nmine\n", encoding="utf-8"
    )

    assert _carries_managed_block(anchor, lambda: False)


def test_install_and_uninstall_find_the_block_behind_a_bom(
    sandbox_factory: SandboxFactory,
) -> None:
    """Notepad's "UTF-8 with BOM" must not hide Apothem's block in AGENTS.md."""
    box = sandbox_factory("codex")
    box.install()
    anchor = _anchor(box)
    _resave_with_a_bom(anchor)

    box.install()
    resaved = anchor.read_bytes()
    verify_code, verify_output = box.invoke("verify")
    uninstall_code, uninstall_output = box.invoke("uninstall", "--yes")

    assert resaved.count(APOTHEM_BLOCK_BEGIN.encode()) == 1
    assert verify_code == 0, verify_output
    assert uninstall_code == 0, uninstall_output
    assert "not installed" not in uninstall_output
    assert anchor.read_bytes() == b"\xef\xbb\xbfmy own line\n"


def test_a_crlf_anchor_shows_no_drift_under_verify_profile(
    sandbox_factory: SandboxFactory,
) -> None:
    box = sandbox_factory("codex")
    box.install()
    anchor = _anchor(box)
    anchor.write_bytes(
        anchor.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
    )

    code, output = box.invoke("verify", "--profile", str(profile_minimal_path()))

    assert code == 0, output


def test_a_project_claude_md_shows_no_drift_for_a_tool_without_a_record(
    sandbox_factory: SandboxFactory,
) -> None:
    box = sandbox_factory("gemini-cli")
    box.install()
    install_ledger.ledger_path("gemini_cli").unlink()
    (box.project / "CLAUDE.md").write_text("# Notes\n\nmy own text\n", encoding="utf-8")

    code, output = box.invoke("verify", "--profile", str(profile_minimal_path()))

    assert code == 0, output


# --- a marker pair no rule can place -----------------------------------------

B = APOTHEM_BLOCK_BEGIN
E = APOTHEM_BLOCK_END
OLD = wrap_managed_block("old body")

#: An example of the operator's in a closed fence above Apothem's block, which
#: an open fence of the operator's holds (lines 4-6 in a code block opening at
#: line 3, lines 14-16 in one opening at line 11).
_EXAMPLE_ABOVE = (
    f"# Notes\n\n```md\n{B}\nexample\n{E}\n```\n\nMy notes:\n\n```\nmake test\n\n"
    f"{OLD}\nMore:\n\n```sh\nls\n```\n"
)
#: A stray BEGIN of the operator's whose END is quoted in a code block, then
#: Apothem's block at lines 8-10.
_RESIDUAL = f"{B}\nop text A\n```\n{E}\n```\nop text B\n\n{OLD}"
#: The same with Apothem's block at lines 8-12, whose body opens a code block
#: it never closes (a rule in the profile did), so its END marker reads as code.
_OPEN_BODY = (
    f"{B}\nop text A\n```\n{E}\n```\nop text B\n\n{B}\nrule one\n```\nrule two\n{E}\n"
)
#: _RESIDUAL under a BEGIN marker of the operator's that starts no pair (line
#: 1): the pair rule 3 fires on is at lines 4 to 7, Apothem's block at 11-13.
_TWO_BEGINS = f"{B}\nop stray\n\n{_RESIDUAL}"
#: Apothem's block at lines 6-11, below a code block of yours left open (line
#: 3) that the closing line of the rule's code block in the block closes: the
#: BEGIN marker reads as code, and the END marker outside it.
_HIDDEN_BLOCK = (
    f"# Notes\n\n```bash\nmake test\n\n{B}\nRun:\n```sh\nnpm test\n```\n{E}\n"
)


#: What every list of fixes says about the text below the marker lines it
#: changes.
_OLD_TEXT = (
    "Any old Apothem text below a marker line you change, and its END marker "
    "line if it has one, is then yours to delete by hand."
)

#: What a fix that leaves no block says the next update then does.
_AT_END = (
    "Apothem then reads none of these lines as its markers, and the next update "
    "writes its block at the end of the file."
)


def _flat(text: str) -> str:
    return " ".join(text.split())


def _text_of(lines: list[str]) -> str:
    """Return *lines* as one text, each line ended by LF."""
    return "".join(f"{line}\n" for line in lines)


def _holds(text: str, message: str, *, removes: bool = False) -> int:
    """Follow each numbered fix of *message* on *text*; return how many held.

    Each fix is read with patterns of the test's own, applied step by step in
    the order printed, and held to its promise (see
    :mod:`tests.unit.test_marker_fix_steps`).
    """
    return _check(split_lines(text), message, removes=removes)


def _held(tmp_path: Path, text: str) -> tuple[Path, list[str]]:
    """Write *text* as an anchor a merge left as it is; return its warnings."""
    target = tmp_path / "AGENTS.md"
    target.write_bytes(text.encode())
    merged = install_driver.MaterializationResult(
        outcome="unchanged", operation="sentinel_merge", path=str(target), message=""
    )
    return target, [w.message for w in stray_begin_install_warnings([merged])]


def test_the_install_warning_names_every_pair_and_conditions_each_fix(
    tmp_path: Path,
) -> None:
    """docs-1, cmark-3, diff-3, oracle-2: the example is not the only pair named.

    Both pairs sit in code blocks, so no step that only changes marker lines
    makes either one a whole block: the one fix changes both BEGIN marker
    lines (advice-1: the fixes that moved or added fence lines changed how
    lines of yours read once the next update replaced the block). Followed
    step by step, it holds: the next update writes Apothem's block at the end.
    """
    target, [message] = _held(tmp_path, _EXAMPLE_ABOVE)

    assert message.startswith(
        f"{target}: Apothem cannot tell whether the marker lines in this file "
        "mark its block or text of yours, so it left the file as it is."
    )
    for begin, end, fence in ((4, 6, 3), (14, 16, 11)):
        assert (
            f"The BEGIN marker at line {begin} and the END marker at line {end} sit "
            f"inside a code block that opens at line {fence}."
        ) in message
    assert (
        "Fix A: A1. Change line 14: add a word inside its comment. A2. Change line "
        f"4: add a word inside its comment. {_AT_END} {_OLD_TEXT}"
    ) in message
    assert _holds(_EXAMPLE_ABOVE, message) == 1
    assert message.endswith(
        "Then run apothem update again. apothem verify fails for this tool until "
        "you fix the file."
    )


def test_the_rule_3_warning_names_the_begin_and_the_later_pair(
    tmp_path: Path,
) -> None:
    """lifecycle-3, tests-6, oracle-2, tests-4, markers-r5-3: each fix holds.

    The fix that calls lines 8 to 10 Apothem's block changes the BEGIN marker
    at line 1, so the next update finds one block and replaces it, and one
    more fix changes both BEGIN marker lines. Lines 1 to 4 get no fix of
    their own: line 5 of yours closes the code block their END marker sits
    in, and once the next update replaced them, it would open one.
    """
    target, [message] = _held(tmp_path, _RESIDUAL)

    assert message.startswith(
        f"{target}: Apothem cannot tell whether the marker lines in this file mark "
        "its block or text of yours, so it left the file as it is. The BEGIN marker "
        "at line 1 is outside code, but its END marker at line 4 sits inside a code "
        "block that opens at line 3, and the marker pair from line 8 to line 10 "
        "comes after them: that pair may be Apothem's block."
    )
    assert (
        "Fix A, if lines 8 to 10 are Apothem's block: A1. Change line 1: add a "
        "word inside its comment. The next update then replaces Apothem's block. "
        "Fix B, in any other case: B1. Change line 8: add a word inside its "
        "comment. B2. Change line 1: add a word inside its comment."
    ) in message
    assert message.endswith(
        "Until you fix these marker lines as this text says, install and update "
        "leave this file as it is and end as partial (exit code 2). Then run "
        "apothem update again. apothem verify fails for this tool until you fix "
        "the file."
    )
    assert message.count("may be Apothem's block") == 1
    assert _holds(_RESIDUAL, message) == 2


@pytest.mark.parametrize(
    ("text", "where", "fix"),
    [
        pytest.param(
            f"Start marker:\n```\n{B}\n```\nEnd marker:\n```\n{E}\n```\n",
            "The BEGIN marker at line 3 sits inside a code block that opens at line "
            "2, and the END marker at line 7 sits inside a code block that opens at "
            "line 6.",
            f"Fix A: A1. Change line 3: add a word inside its comment. {_AT_END}",
            id="two-code-blocks",
        ),
        pytest.param(
            f"Intro\n\n    {B}\n    old\n    {E}\n",
            "The BEGIN marker at line 3 and the END marker at line 5 sit in indented "
            "code.",
            "Fix A: A1. Change line 3: add a word inside its comment.",
            id="indented",
        ),
        pytest.param(
            f"Example of the markers:\n    {B}\n    quoted\n    {E}\n",
            "The BEGIN marker at line 2 and the END marker at line 4 read as part of "
            "the paragraph above them.",
            "Fix A: A1. Change line 2: add a word inside its comment.",
            id="paragraph",
        ),
        pytest.param(
            f"{B}\n    {E}\n\n{OLD}",
            "The BEGIN marker at line 1 is outside code, but its END marker at line "
            "2 sits in indented code, and the marker pair from line 4 to line 6 "
            "comes after them: that pair may be Apothem's block.",
            "Fix A, if lines 4 to 6 are Apothem's block: A1. Change line 1: add a "
            "word inside its comment. The next update then replaces Apothem's "
            "block. Fix B, in any other case: B1. Change line 4",
            id="rule-3-indented-end",
        ),
        pytest.param(
            f"{B}\nsome text\n    {E}\n\n{B}\nreal\n{E}\n",
            "The BEGIN marker at line 1 is outside code, but its END marker at line "
            "3 reads as part of the paragraph above it, and the marker pair from "
            "line 5 to line 7 comes after them: that pair may be Apothem's block.",
            "Fix A, if lines 5 to 7 are Apothem's block: A1. Change line 1: add a "
            "word inside its comment. The next update then replaces Apothem's "
            "block. Fix B, in any other case: B1. Change line 5",
            id="rule-3-paragraph-end",
        ),
        pytest.param(
            f"Example:\n    {B}\n\n```\n{E}\n```\n",
            "The BEGIN marker at line 2 reads as part of the paragraph above it, and "
            "the END marker at line 5 sits inside a code block that opens at line 4.",
            "Fix A: A1. Change line 2: add a word inside its comment.",
            id="paragraph-then-fence",
        ),
        pytest.param(
            _HIDDEN_BLOCK,
            "The BEGIN marker at line 6 sits inside a code block that opens at line "
            "3, and the END marker at line 11 is outside code.",
            f"Fix A: A1. Change line 6: add a word inside its comment. {_AT_END}",
            id="fence-above-closed-in-the-block",
        ),
    ],
)
def test_each_shape_gets_its_own_place_and_fix(
    tmp_path: Path, text: str, where: str, fix: str
) -> None:
    """docs-4, oracle-4, diff-6, tests-7, tests-3: each line named as it reads.

    Each numbered fix, followed step by step, holds.
    """
    _, [message] = _held(tmp_path, text)

    assert where in message
    assert fix in message
    assert _holds(text, message) >= 1


def test_the_uninstall_warning_says_to_delete_whichever_pair_is_apothems(
    tmp_path: Path,
) -> None:
    """docs-1: every pair is named, and the fix changes each marker line."""
    target = tmp_path / "AGENTS.md"
    target.write_bytes(_EXAMPLE_ABOVE.encode())

    warning = blocks.unclear_block_warning(target, "surgical_uninstall")

    assert warning is not None
    assert warning.detail == {"kept_reason": "unclear-block", "marker_left": "1"}
    assert "A2. Change line 4: add a word inside its comment." in warning.message
    assert "Delete lines" not in warning.message
    assert warning.message.endswith(
        f"Apothem then finds no block of its own in this file. {_OLD_TEXT} Then "
        "run the uninstall again."
    )
    assert "sit inside a code block that opens at line 11" in warning.message
    assert _holds(_EXAMPLE_ABOVE, warning.message, removes=True) == 1


def test_the_uninstall_warning_for_one_pair_says_what_to_do_if_it_is_yours(
    tmp_path: Path,
) -> None:
    """lifecycle-1: the uninstall stays unfinished while the pair is there.

    So the warning says how to clear it whoever wrote it (change its BEGIN
    marker line: Apothem then finds no block of its own there), and that the
    uninstall runs again after.
    """
    text = f"Intro\n```\ncode\n\n{OLD}New:\n```bash\nnpm ci\n```\n"
    target = tmp_path / "AGENTS.md"
    target.write_bytes(text.encode())

    warning = blocks.unclear_block_warning(target, "surgical_uninstall")

    assert warning is not None
    assert (
        "Fix A: A1. Change line 5: add a word inside its comment. Apothem then "
        "finds no block of its own in this file."
    ) in warning.message
    assert warning.message.endswith("Then run the uninstall again.")
    assert _holds(text, warning.message, removes=True) == 1


def test_the_verify_note_names_every_pair_with_its_fix(tmp_path: Path) -> None:
    """tests-7: the verify and doctor note for an unclear file."""
    target = tmp_path / "AGENTS.md"
    target.write_bytes(_EXAMPLE_ABOVE.encode())

    note = stray_begin_note(
        [target], then="run apothem update and apothem verify again"
    )

    assert note.startswith(
        f"{target}: Apothem cannot tell whether the marker lines in this file mark "
        "its block or text of yours. The BEGIN marker at line 4"
    )
    assert "Fix A: A1. Change line 14: add a word inside its comment." in note
    assert note.endswith(" Then run apothem update and apothem verify again")
    assert _holds(_EXAMPLE_ABOVE, note) == 1


# --- the BEGIN markers a fix must take along ----------------------------------


def test_the_uninstall_text_for_a_split_pair_names_your_begin_marker(
    tmp_path: Path,
) -> None:
    """regress-1, messages-1, diff-1: deleting only Apothem's block would cut text.

    With the pair after it gone, your BEGIN marker at line 1 and the END marker
    you quote at line 4 read as a whole block, which the uninstall run again
    takes out: so the fix for the case that lines 8 to 10 are Apothem's block
    changes that BEGIN marker. The END marker you quote stays your code as it
    is (advice-4): with no BEGIN marker above it, it pairs with nothing.
    """
    target = tmp_path / "AGENTS.md"
    target.write_bytes(_RESIDUAL.encode())

    warning = blocks.unclear_block_warning(target, "surgical_uninstall")

    assert warning is not None
    assert (
        "Fix A, if lines 8 to 10 are Apothem's block: A1. Change line 1: add a "
        "word inside its comment. The uninstall run again then takes Apothem's "
        "block out."
    ) in warning.message
    assert "Change line 4" not in warning.message
    assert warning.message.endswith("Then run the uninstall again.")
    assert _holds(_RESIDUAL, warning.message, removes=True) == 2


@pytest.mark.parametrize(
    ("text", "fix"),
    [
        pytest.param(
            f"{B}\nop text A\n```\n{E}\nop text B\n\n{OLD}",
            "Fix A: A1. Below line 9, add a line of 3 backticks. A2. Change line 7: "
            "add a word inside its comment. A3. Change line 1: add a word inside its "
            "comment.",
            id="fence-left-open",
        ),
        pytest.param(
            _OPEN_BODY,
            "Fix A: A1. Below line 12, add a line of 3 backticks. A2. Change line 8: "
            "add a word inside its comment. A3. Change line 1: add a word inside its "
            "comment.",
            id="block-body-opens-a-code-block",
        ),
    ],
)
def test_the_fix_for_a_pair_after_a_split_one_takes_its_begin_marker_along(
    tmp_path: Path, text: str, fix: str
) -> None:
    """oracle-1, regress-7, docs-5: that BEGIN marker would hold the update back.

    Deleted by hand without it, Apothem's block leaves your BEGIN marker and
    the END marker you quote as a whole block, which the next update replaces.
    Each fix changes it. Here a code block left open above the pair after
    it, which a viewer reads to the end of the file, holds that pair, and no
    fix keeps it: a code block in the rules the next update writes would
    close that code block. So the one fix changes every BEGIN marker line
    and closes the open code block below the last line.
    """
    _, [message] = _held(tmp_path, text)

    assert fix in message
    assert _holds(text, message) == 1


def test_a_begin_marker_that_starts_no_pair_is_named_in_every_text(
    tmp_path: Path,
) -> None:
    """diff-2, regress-8, messages-3, docs-2: it pairs once the pairs are fixed.

    So every fix changes it, in the text of install, uninstall and verify.
    """
    target, [install] = _held(tmp_path, _TWO_BEGINS)
    uninstall = blocks.unclear_block_warning(target, "surgical_uninstall")
    note = stray_begin_note([target], then="run apothem update")
    lone = (
        "The BEGIN marker at line 1 starts no marker pair: its END marker is gone, "
        "or the marker is yours."
    )

    assert uninstall is not None
    for message, removes in (
        (install, False),
        (uninstall.message, True),
        (note, False),
    ):
        assert lone in message
        assert message.count("starts no marker pair") == 1
        fixes = re.findall(r"Fix [A-Z], .*?(?=Fix [A-Z], |$)", message)
        assert len(fixes) == 2
        assert all("Change line 1: add a word inside its comment." in f for f in fixes)
        assert _holds(_TWO_BEGINS, message, removes=removes) == 2
    assert "Fix A, if lines 11 to 13 are Apothem's block: A1. Change line 4" in install


def test_a_begin_marker_that_starts_no_pair_in_a_file_apothem_retires_takes_out(
    tmp_path: Path,
) -> None:
    """A rules file Apothem takes its block out of: no later run replaces lines.

    Each fix there says the next install, update or uninstall takes Apothem's
    block out, or that Apothem then finds no block of its own, and changes the
    BEGIN marker that starts no pair.
    """
    target = tmp_path / "AGENTS.md"
    target.write_bytes(_TWO_BEGINS.encode())

    warning = blocks.unclear_block_warning(target, "retire_anchor", outcome=TAKES_OUT)

    assert warning is not None
    assert (
        "The BEGIN marker at line 1 starts no marker pair: its END marker is gone, "
        "or the marker is yours."
    ) in warning.message
    assert "The next install, update or uninstall then takes Apothem's block out." in (
        warning.message
    )
    assert "replace" not in warning.message
    assert _holds(_TWO_BEGINS, warning.message, removes=True) == 2


def test_begin_markers_that_start_no_pair_are_named_together(tmp_path: Path) -> None:
    """Two blocks that lost their END marker, above a pair quoted in code."""
    text = (
        f"{B}\nold rules\n\n{B}\nmore old rules\n\nMy notes:\n\n```md\n{B}\n"
        f"example\n{E}\n```\n"
    )

    _, [message] = _held(tmp_path, text)

    assert (
        "The BEGIN markers at lines 1 and 4 start no marker pair: their END markers "
        "are gone, or the markers are yours."
    ) in message
    assert (
        "The BEGIN marker at line 10 and the END marker at line 12 sit inside a "
        "code block that opens at line 9."
    ) in message
    assert (
        "A2. Change line 4: add a word inside its comment. A3. Change line 1: add "
        "a word inside its comment."
    ) in message
    assert _OLD_TEXT in message
    assert _holds(text, message) == 1


# --- a write that leaves the pair rule 3 fires on -----------------------------


def _profile(tmp_path: Path, name: str, rules: list[str]) -> str:
    """Write the minimal profile with *rules*; return its path."""
    data = yaml.safe_load(Path(profile_minimal_path()).read_text(encoding="utf-8"))
    data["rules"] = rules
    path = tmp_path / name
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    return str(path)


#: A rule whose code block Apothem's block never closes.
_OPEN_RULE = "Run the tests with:\n```bash"
#: An example of the markers you quote in a code block below Apothem's block.
_QUOTED_BELOW = f"\nExample of the markers:\n\n```markdown\n{B}\nexample\n{E}\n```\n"


def test_a_write_that_leaves_a_split_pair_names_it_and_the_rule(
    tmp_path: Path,
) -> None:
    """regress-2: no stray-marker text, whose fix deletes the block just written.

    The block is one an earlier release wrote for a rule that opens a code
    block and never closes it; this release closes such a code block in the
    block it writes (see the next test).
    """
    written = f"{B}\nRule one.\n{_OPEN_RULE}\n{E}\n{_QUOTED_BELOW}"
    target = tmp_path / "CLAUDE.md"
    target.write_bytes(written.encode())
    result = install_driver.MaterializationResult(
        outcome="updated", operation="sentinel_merge", path=str(target), message=""
    )

    [warning] = stray_begin_install_warnings([result])

    assert warning.message.startswith(
        f"{target}: Apothem cannot tell whether the marker lines in this file mark "
        "its block or text of yours. The BEGIN marker at line 1 is outside code, "
        "but its END marker at line 5 sits inside a code block that opens at line 4"
    )
    assert "Fix A: A1. Change line 10: add a word inside its comment. A2. Change " in (
        warning.message
    )
    assert "left the file as it is" not in warning.message
    assert "starts no whole block" not in warning.message
    assert _holds(written, warning.message) == 1


def test_a_write_whose_block_reads_as_code_names_it_and_the_code_block(
    tmp_path: Path,
) -> None:
    """lifecycle-1, cmark-2: the write that left no whole block was silent.

    A code block of yours left open above Apothem's block, which the closing
    line of a rule's code block in the block closes: the block just written
    reads as code from its BEGIN marker on. The fix changes its BEGIN marker
    line, and the next update writes Apothem's block at the end of the file;
    deleting the block by hand only brought it back.
    """
    target = tmp_path / "CLAUDE.md"
    target.write_bytes(_HIDDEN_BLOCK.encode())
    result = install_driver.MaterializationResult(
        outcome="updated", operation="sentinel_merge", path=str(target), message=""
    )

    [warning] = stray_begin_install_warnings([result])

    assert warning.message.startswith(
        f"{target}: Apothem cannot tell whether the marker lines in this file mark "
        "its block or text of yours. The BEGIN marker at line 6 sits inside a code "
        "block that opens at line 3, and the END marker at line 11 is outside code."
    )
    assert (
        f"Fix A: A1. Change line 6: add a word inside its comment. {_AT_END} "
        f"{_OLD_TEXT}"
    ) in warning.message
    assert warning.message.endswith(
        "Then run apothem update again. apothem verify fails for this tool until "
        "you fix the file."
    )
    assert _holds(_HIDDEN_BLOCK, warning.message) == 1


def test_a_write_says_the_file_is_held_back_from_the_next_run_on(
    tmp_path: Path,
) -> None:
    """markers-r5-4: a run that wrote the file said it leaves the file as it is.

    That run ends as a success (exit code 0), yet its warning said install and
    update leave the file as it is and end as partial. It now says that holds
    from the next run on; the warning of a run that left the file says it as
    before.
    """
    target = tmp_path / "CLAUDE.md"
    target.write_bytes(_HIDDEN_BLOCK.encode())
    runs = {
        outcome: install_driver.MaterializationResult(
            outcome=outcome, operation="sentinel_merge", path=str(target), message=""
        )
        for outcome in ("updated", "unchanged")
    }

    [written] = stray_begin_install_warnings([runs["updated"]])
    [left] = stray_begin_install_warnings([runs["unchanged"]])

    assert (
        "From the next run on, until you fix these marker lines as this text says, "
        "install and update leave this file as it is and end as partial (exit code "
        "2)."
    ) in written.message
    assert "Until you fix" not in written.message
    assert (
        "Until you fix these marker lines as this text says, install and update "
        "leave this file as it is and end as partial (exit code 2)."
    ) in left.message
    assert "From the next run on" not in left.message


def test_a_marker_example_that_reads_as_a_paragraph_is_not_called_code(
    tmp_path: Path,
) -> None:
    """markers-r5-5: the text called a pair under a paragraph a pair "in code"."""
    text = f"Example of the markers:\n    {B}\n    quoted\n    {E}\n"

    _, [message] = _held(tmp_path, text)

    assert (
        "A marker example of yours that reads as part of a paragraph holds the "
        "file back the same way, until you change its BEGIN marker line."
    ) in message
    assert " in code" not in message


def test_a_block_your_open_code_block_hides_is_named_and_the_fix_holds(
    sandbox_factory: SandboxFactory, tmp_path: Path
) -> None:
    """lifecycle-1, cmark-2: the install hid its own block and said nothing.

    A code block of yours above the block never closes, and the line that
    closes the rule's code block in Apothem's block closes it: verify failed
    at once, no update refreshed the block, and deleting the block, as the
    fix, said, brought it back. The install now names the code block, and
    its fix changes the block's BEGIN marker line: the next update writes
    Apothem's block at the end of the file, whole, and verify passes.
    """
    box = sandbox_factory("claude-code")
    anchor = _anchor(box)
    anchor.parent.mkdir(parents=True, exist_ok=True)
    anchor.write_bytes(b"# Notes\n\n```bash\nmake test\n")
    profile = _profile(tmp_path, "rules.yaml", ["Run:\n```sh\nnpm test"])

    code, output = box.invoke("install", "--profile", profile, "--json")
    verify, verify_output = box.invoke("verify", "--json")
    lines = anchor.read_bytes().decode("utf-8").split("\n")
    fix = f"Fix A: A1. Change line 6: add a word inside its comment. {_AT_END}"
    anchor.write_bytes(_text_of(_follow(lines[:-1], fix)).encode())
    updated, update_output = box.invoke("update", "--profile", profile)
    fixed, fixed_output = box.invoke("verify")

    assert lines.index(B) == 5, lines[:8]
    assert code == 0, output
    [message] = [
        str(warning["message"])
        for warning in json.loads(output)["warnings"]
        if _names(str(warning["message"]), anchor)
    ]
    assert fix in message
    assert "left the file as it is" not in message
    assert "From the next run on, until you fix these marker lines" in message
    assert verify == 1, verify_output
    [row] = json.loads(verify_output)["results"]
    assert fix in row["stray_begin"]["message"]
    assert updated == 0, update_output
    assert complete_managed_block(anchor.read_bytes().decode("utf-8")) is not None
    assert anchor.read_bytes().count(B.encode()) == 1
    assert fixed == 0, fixed_output


@pytest.mark.parametrize("harness_id", ["codex", "claude-code"])
def test_an_update_below_an_old_block_whose_rule_left_a_code_block_open(
    harness_id: str, sandbox_factory: SandboxFactory, tmp_path: Path
) -> None:
    """The line that opens the code block can be part of the old Apothem text.

    An earlier release's block, whose rule opened a code block it never
    closed, lost its END marker; the update writes its block below, where
    the closing line of a rule's code block closes that code block. The fix
    that changes every BEGIN marker line, followed step by step, changes the
    old BEGIN marker too, and the next update then writes a whole block at
    the end of the file.
    """
    box = sandbox_factory(harness_id)
    old = _profile(tmp_path, "old.yaml", ["Rule one.", _OPEN_RULE])
    new = _profile(tmp_path, "new.yaml", ["Rule two.", "Run:\n```sh\nnpm test\n```"])
    code, output = box.invoke("install", "--profile", old, "--json")
    assert code == 0, output
    anchor = _anchor(box)
    lines = anchor.read_bytes().decode("utf-8").split("\n")
    [(_, end)] = whole_blocks("\n".join(lines))
    # An earlier release wrote no closing line for the rule's code block: drop
    # this release's closing line and the END marker, and add a line of yours.
    assert lines[end - 2] == "```", lines[end - 3 : end]
    anchor.write_bytes(
        "\n".join([*lines[: end - 2], "", "my own line", *lines[end:]]).encode()
    )

    code, output = box.invoke("update", "--profile", new, "--json")
    after = anchor.read_bytes().decode("utf-8").split("\n")
    begin = after.index(B, 1) + 1
    [message] = [
        _flat(str(warning["message"]))
        for warning in json.loads(output)["warnings"]
        if _names(str(warning["message"]), anchor)
    ]
    assert begin > 1
    fix = _fixes(message)[-1][1]
    texts = _follow(after[:-1], fix)
    anchor.write_bytes("".join(f"{line}\n" for line in texts).encode())
    updated, update_output = box.invoke("update", "--profile", new, "--json")
    fixed = anchor.read_bytes().decode("utf-8")
    verify, verify_output = box.invoke("verify")

    assert code == 0, output
    assert after[0] == B
    # The BEGIN marker that starts no pair changes, and no step deletes a line
    # by a number an earlier step moved (markers-r5-2).
    assert "Change line 1: add a word inside its comment." in fix
    assert "Delete" not in fix
    assert updated == 0, update_output
    assert len(whole_blocks(fixed)) == 1
    assert fixed.count(B) == 1
    assert "my own line" in fixed
    assert verify == 0, verify_output


def test_an_update_whose_rule_opens_a_code_block_closes_it_in_the_block(
    sandbox_factory: SandboxFactory, tmp_path: Path
) -> None:
    """markers-4: the block stays whole, and your quote below stays your text.

    Before, the rule's code block ran past Apothem's END marker, so the block
    read as unclear beside your example: no update refreshed it, verify
    failed, and no uninstall took it out.
    """
    box = sandbox_factory("claude-code")
    code, output = box.invoke(
        "install", "--profile", _profile(tmp_path, "one.yaml", ["Rule one."]), "--json"
    )
    assert code == 0, output
    anchor = _anchor(box)
    anchor.write_bytes(anchor.read_bytes() + _QUOTED_BELOW.encode())
    rules = ["Rule one.", _OPEN_RULE]

    code, output = box.invoke(
        "update", "--profile", _profile(tmp_path, "two.yaml", rules), "--json"
    )
    verify, verify_output = box.invoke("verify")

    assert code == 0, output
    lines = anchor.read_bytes().decode("utf-8").split("\n")
    end = lines.index(E)
    assert lines.index("```bash") < end - 1
    assert lines[end - 1] == "```"
    assert anchor.read_bytes().decode("utf-8").endswith(_QUOTED_BELOW)
    assert not [
        warning
        for warning in json.loads(output)["warnings"]
        if _names(str(warning["message"]), anchor)
    ]
    assert verify == 0, verify_output


@pytest.mark.parametrize(
    ("outcome", "warned"), [("updated", False), ("created", False), ("unchanged", True)]
)
def test_the_unclear_warning_follows_what_the_merge_did(
    tmp_path: Path, outcome: str, warned: bool
) -> None:
    """wiring-5, diff-2: in a preview, a quoted pair is named only in a file left.

    The preview of a write that appends a block after the quote gets no
    warning: the real run's file then holds a whole block. A preview reads
    the file before the write, so this is a preview's result; a real run
    reads the file it wrote (see
    ``test_a_write_whose_block_reads_as_code_names_it_and_the_code_block``).
    """
    target = tmp_path / "AGENTS.md"
    target.write_bytes(
        f"# Notes\n\nApothem writes its markers like this:\n\n```md\n{B}\nexample\n"
        f"{E}\n```\n".encode()
    )
    result = install_driver.MaterializationResult(
        outcome=outcome,  # type: ignore[arg-type]
        operation="sentinel_merge",
        path=str(target),
        message="",
    )

    warnings = stray_begin_install_warnings([result], dry_run=True)

    assert bool(warnings) is warned


@pytest.mark.parametrize("harness_id", ["codex", "claude-code"])
def test_a_dry_run_over_a_quoted_pair_previews_no_refusal(
    harness_id: str, sandbox_factory: SandboxFactory
) -> None:
    """diff-2, wiring-5: no record, so the install appends; the preview agrees."""
    box = sandbox_factory(harness_id)
    anchor = _anchor(box)
    anchor.parent.mkdir(parents=True, exist_ok=True)
    anchor.write_bytes(
        f"# Notes\n\nApothem writes its markers like this:\n\n```md\n{B}\nexample\n"
        f"{E}\n```\n".encode()
    )
    profile = str(profile_minimal_path())

    code, output = box.invoke("install", "--profile", profile, "--dry-run", "--json")
    preview = json.loads(output)["warnings"]
    box.install()
    verify, verify_output = box.invoke("verify")

    assert code == 0, output
    assert not [w for w in preview if _names(str(w["message"]), anchor)], preview
    assert anchor.read_bytes().count(B.encode()) == 2
    assert verify == 0, verify_output


def _fence_the_block(anchor: Path) -> tuple[int, int, int]:
    """Put *anchor*'s block, one line edited, in a code block you close below.

    Return the 1-based lines of the BEGIN marker, the END marker and the fence
    that opens the code block.
    """
    text = anchor.read_bytes().decode("utf-8")
    at = text.index(B)
    begin_end = at + len(B) + 1
    text = text[:begin_end] + "a line I added\n" + text[begin_end:]
    head = text[:at] + "My notes:\n\n```\nmake test\n\n"
    fenced = head + text[at:] + "\nMore examples:\n\n```sh\nls\n```\n"
    anchor.write_bytes(fenced.encode())
    lines = fenced.split("\n")
    return lines.index(B) + 1, lines.index(E) + 1, head.count("\n") - 2


def test_a_recorded_block_in_your_code_block_still_reads_as_installed(
    sandbox_factory: SandboxFactory,
) -> None:
    """cmark-1, lifecycle-2, wiring-1, diff-1, tests-1, corpus-1 (codex).

    verify and doctor see the install and name the lines; tests-7 for the note
    and the doctor summary.
    """
    box = sandbox_factory("codex")
    box.install()
    anchor = _anchor(box)
    begin, end, fence = _fence_the_block(anchor)
    box.partial("install", "--profile", str(profile_minimal_path()))

    code, output = box.invoke("verify", "--json")
    result = CliRunner().invoke(main, ["doctor", "--json"])

    assert code == 1, output
    payload = json.loads(output)
    assert payload["installed"] is True
    [row] = payload["results"]
    note = _flat(row["stray_begin"]["message"])
    assert (
        f"The BEGIN marker at line {begin} and the END marker at line {end} sit "
        f"inside a code block that opens at line {fence}."
    ) in note
    assert f"Fix A: A1. Change line {begin}: add a word inside its comment." in note
    assert (
        "Until you fix these marker lines as this text says, install and update "
        "leave this file as it is and end as partial (exit code 2). A marker "
        "example of yours in code holds the file back the same way, until you "
        "change its BEGIN marker line."
    ) in note
    assert result.exit_code == 1, result.output
    [check] = [c for c in json.loads(result.output)["checks"] if c["status"] == "fail"]
    assert check["code"] == "harness.stray_begin"
    assert check["message"] == (
        "codex is installed but does not verify: a file holds Apothem markers to "
        "fix by hand."
    )
    assert _names(check["fix"], anchor)
    assert f"A1. Change line {begin}: add a word inside its comment." in check["fix"]
    assert "add a copy" not in check["fix"]


def test_a_quote_in_a_file_no_install_record_lists_is_no_install(
    tmp_path: Path,
) -> None:
    """A never-installed AGENTS.md that quotes the markers is not an install."""
    root = tmp_path / ".codex"
    anchor = root / "AGENTS.md"
    anchor.parent.mkdir(parents=True)
    anchor.write_bytes(
        f"# Notes\n\nApothem wraps its block like this:\n\n```md\n{B}\n(rules)\n{E}\n"
        "```\n\nMore notes.\n".encode()
    )

    assert not install_driver.detect_install("codex", harness_root=root)


def test_a_recorded_unclear_anchor_counts_as_an_install(tmp_path: Path) -> None:
    """The install record, not an open install alone, makes the pair evidence."""
    root = tmp_path / ".codex"
    anchor = root / "AGENTS.md"
    anchor.parent.mkdir(parents=True)
    anchor.write_bytes(
        f"Intro\n```\ncode\n\n{OLD}New:\n```bash\nnpm ci\n```\n".encode()
    )
    _record("codex", root, anchor)

    assert install_driver.detect_install("codex", harness_root=root)


def _damage_ledger(package_key: str) -> None:
    """Put a line that is not JSON in the middle of *package_key*'s ledger."""
    ledger = install_ledger.ledger_path(package_key)
    lines = ledger.read_bytes().splitlines(keepends=True)
    ledger.write_bytes(b"".join([lines[0], b"{not json\n", *lines]))


def test_an_unreadable_ledger_reads_as_a_record_of_an_unclear_anchor(
    tmp_path: Path,
) -> None:
    """merge-1: an unreadable ledger read as no record, so nothing was installed.

    The pair in code then counted for nothing, and with no other evidence
    the tool read as not installed. Like a BEGIN marker that lost its END,
    whose evidence counts while the ledger cannot say the install was
    closed, the pair now counts while the ledger cannot be read.
    """
    root = tmp_path / ".codex"
    anchor = root / "AGENTS.md"
    anchor.parent.mkdir(parents=True)
    anchor.write_bytes(
        f"Intro\n```\ncode\n\n{OLD}New:\n```bash\nnpm ci\n```\n".encode()
    )
    _record("codex", root, anchor)
    _damage_ledger("codex")

    assert listed_in_record("codex", root, anchor)
    assert install_driver.detect_install("codex", harness_root=root)


def test_an_unreadable_ledger_and_an_unclear_block_do_not_read_as_no_install(
    sandbox_factory: SandboxFactory,
) -> None:
    """merge-1: uninstall said "not installed" and doctor not_installed, exit 0.

    The tool's hooks, agents and Apothem's block stayed loaded, and neither
    named the damaged ledger. The uninstall now reaches the ledger and stops
    on it, as it does for a whole block, and doctor reports the install and
    the ledger.
    """
    box = sandbox_factory("codex")
    box.install()
    anchor = _anchor(box)
    _fence_the_block(anchor)
    before = anchor.read_bytes()
    _damage_ledger("codex")

    code, output = box.invoke("uninstall", "--yes", "--json")
    doctor = CliRunner().invoke(main, ["doctor", "--json"])

    payload = json.loads(output)
    assert code == 1, output
    assert payload["status"] == "error"
    assert "not installed" not in json.dumps(payload["results"])
    assert "is not valid JSON" in json.dumps(payload["results"])
    assert anchor.read_bytes() == before
    assert (box.home / ".codex" / "hooks.json").is_file()
    assert doctor.exit_code == 1, doctor.output
    report = json.loads(doctor.stdout)
    [row] = [row for row in report["harnesses"] if row["name"] == "codex"]
    assert row["installed"] is True
    assert row["status"] != "not_installed"
    assert [c for c in report["checks"] if c["code"] == "ledger.unreadable"]


def test_doctor_reports_a_ledger_it_cannot_open_beside_an_unclear_block(
    sandbox_factory: SandboxFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """doctor stopped with a traceback when it could not open the ledger.

    Another program held the ledger open without read sharing, say. The file
    whose marker pair sits in code then counted as an install, as it does
    for a damaged ledger, so doctor went on to start the tool's hooks, which
    reads the ledger and stopped only a damaged one: the error ended the run
    with no report, where it used to report the tool as not installed.
    doctor now names that ledger in its ledger.unreadable check, with the
    error, and its fix says to make the file readable, not to move a damaged
    file aside.
    """
    box = sandbox_factory("codex")
    box.install()
    _fence_the_block(_anchor(box))
    ledger = install_ledger.ledger_path("codex")
    read_text = Path.read_text

    def held_open(self: Path, *args: object, **kwargs: object) -> str:
        if self == ledger:
            raise PermissionError(13, "Permission denied", str(self))
        return read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", held_open)
    result = CliRunner().invoke(main, ["doctor", "--json"])

    assert isinstance(result.exception, SystemExit), repr(result.exception)
    assert result.exit_code == 1, result.output
    report = json.loads(result.stdout)
    [row] = [row for row in report["harnesses"] if row["name"] == "codex"]
    assert row["installed"] is True
    assert row["status"] != "not_installed"
    [check] = [c for c in report["checks"] if c["code"] == "ledger.unreadable"]
    assert check["status"] == "fail"
    assert check["message"].startswith("codex: the install ledger cannot be read (")
    assert "Permission denied" in check["message"]
    assert check["fix"] == (
        f"Make {ledger} readable (close any program that holds it open, or give "
        "your account read access to it), then run doctor again."
    )


# --- a BEGIN marker whose END marker came back: two whole blocks -------------


def test_the_stray_warning_says_not_to_put_the_end_marker_back(tmp_path: Path) -> None:
    """lifecycle-2: putting the END back leaves two Apothem blocks.

    The verify and doctor note says so only once an install or update has
    written Apothem's block apart from the marker (docs-3): before that,
    putting the END marker back leaves one whole block, a fix that works.
    """
    target = tmp_path / "AGENTS.md"
    target.write_text(
        f"{B}\nold rules\nmy own line\n\n{B}\nnew rules\n{E}\n", encoding="utf-8"
    )
    merged = install_driver.MaterializationResult(
        outcome="updated", operation="sentinel_merge", path=str(target), message=""
    )

    [warning] = stray_begin_install_warnings([merged])
    note = stray_begin_note([target], then="run apothem update")

    back = (
        "Do not add the END marker back instead of changing the marker line: the "
        "file would then hold two Apothem blocks, which install and update leave "
        "as they are."
    )
    assert warning.message.endswith(back)
    assert back in note


def test_a_preview_says_not_to_put_the_end_marker_back_only_once_it_is_written(
    sandbox_factory: SandboxFactory, tmp_path: Path
) -> None:
    """A dry run reads the file before the write, when it holds no whole block.

    Putting the END marker back then leaves one whole block, which the update
    refreshes, and verify passes; the preview said not to. The update that
    wrote its block apart from the marker still says not to put it back.
    """
    box = sandbox_factory("claude-code")
    box.install()
    anchor = _anchor(box)
    original = anchor.read_bytes().decode("utf-8")
    anchor.write_bytes((original.replace(f"{E}\n", "") + "\nmy own line\n").encode())
    changed = _profile_named(tmp_path, "Changed Person")

    code, output = box.invoke("update", "--profile", changed, "--dry-run", "--json")
    anchor.write_bytes(f"{original}\nmy own line\n".encode())
    updated, update_output = box.invoke("update", "--profile", changed)
    after = anchor.read_bytes().decode("utf-8")
    verify, verify_output = box.invoke("verify")
    anchor.write_bytes((after.replace(f"{E}\n", "", 1) + "\nmore of mine\n").encode())
    real, real_output = box.invoke("update", "--profile", changed, "--json")

    [preview] = [
        _flat(str(warning["message"]))
        for warning in json.loads(output)["warnings"]
        if _names(str(warning["message"]), anchor)
    ]
    [written] = [
        _flat(str(warning["message"]))
        for warning in json.loads(real_output)["warnings"]
        if _names(str(warning["message"]), anchor)
    ]
    assert code == 0, output
    assert "write a block of their own apart from it" in preview
    assert preview.endswith(
        "If you add the END marker back instead of changing the marker line, put "
        "no line of yours between the two markers: the next run would replace or "
        "take out every line between them. Once an install or update has written "
        "Apothem's block apart from the marker, do not add it back at all: the "
        "file would then hold two Apothem blocks, which install and update leave "
        "as they are."
    )
    assert updated == 0, update_output
    assert (after.count(B), after.count(E)) == (1, 1)
    assert "Changed Person" in after
    assert verify == 0, verify_output
    assert real == 0, real_output
    assert "write a whole block of their own apart from it" in written
    assert "verify fails for this tool until you change that marker line" in written
    assert written.endswith(
        "Do not add the END marker back instead of changing the marker line: the "
        "file would then hold two Apothem blocks, which install and update leave "
        "as they are."
    )


#: An old block whose END marker came back (lines 2-4) above the block an
#: update appended (lines 8-10).
_TWO_BLOCKS = f"# top\n{B}\nold rules\n{E}\n\nmy own line\n\n{B}\nnew rules\n{E}\n"


@pytest.mark.parametrize(
    ("dry_run", "left"),
    [(False, "so it left"), (True, "so it would leave")],
)
def test_a_file_with_two_whole_blocks_names_each_block(
    tmp_path: Path, dry_run: bool, left: str
) -> None:
    """lifecycle-2: install and update leave it as it is and name both blocks.

    One numbered fix for each block, for the case that it is Apothem's
    block, changes the marker lines of the other block, so a marker pair of
    yours keeps its text; the text says which block is Apothem's in a file
    that starts with Apothem's frontmatter (lifecycle-2, advice-2). No fix
    moves your pair into a code block (lifecycle-r4-1): once Apothem's block
    is not whole, a pair in code holds the file back. Each fix holds.
    """
    target = tmp_path / "AGENTS.md"
    target.write_bytes(_TWO_BLOCKS.encode())
    result = install_driver.MaterializationResult(
        outcome="unchanged", operation="sentinel_merge", path=str(target), message=""
    )

    [warning] = stray_begin_install_warnings([result], dry_run=dry_run)

    assert warning.message.startswith(
        f"{target} holds 2 whole blocks between Apothem's markers (lines 2 to 4, "
        "and lines 8 to 10). Apothem writes one block per file and cannot tell "
        f"which one is its own, {left} the file as it is."
    )
    assert (
        "Fix A, if lines 2 to 4 are Apothem's block: A1. Change line 8: add a "
        "word inside its comment. Lines 2 to 4 are then the one block in the "
        "file. Fix B, if lines 8 to 10 are Apothem's block: B1. Change line 2: "
        "add a word inside its comment. Lines 8 to 10 are then the one block in "
        "the file."
    ) in warning.message
    assert (
        "In a file that starts with Apothem's frontmatter, Apothem's block is the "
        "one right below it. Then run apothem update again. apothem verify fails "
        "for this tool until you fix the file."
    ) in warning.message
    assert "code block" not in warning.message
    assert _holds(_TWO_BLOCKS, warning.message) == 2


@pytest.mark.parametrize(
    ("text", "outcome", "dry_run", "left"),
    [
        pytest.param(_TWO_BLOCKS, "unchanged", False, True, id="two-blocks"),
        pytest.param(_EXAMPLE_ABOVE, "unchanged", False, True, id="unclear"),
        pytest.param(_TWO_BLOCKS, "unchanged", True, False, id="preview"),
        pytest.param(_HIDDEN_BLOCK, "updated", False, False, id="written"),
        pytest.param(f"{B}\nold\n\n{OLD}", "unchanged", False, False, id="stray"),
    ],
)
def test_only_a_file_the_merge_left_for_its_markers_is_marked_left_as_is(
    tmp_path: Path, text: str, outcome: str, dry_run: bool, left: bool
) -> None:
    """lifecycle-r4-5: the CLI reads this detail to report the run as partial.

    A file the merge left as it is because of its markers got no current
    Apothem block. A preview leaves nothing, a write that left the block in
    code wrote it, and a stray BEGIN marker gets a block written apart from
    it, so none of those is marked.
    """
    target = tmp_path / "AGENTS.md"
    target.write_bytes(text.encode())
    result = install_driver.MaterializationResult(
        outcome=outcome, operation="sentinel_merge", path=str(target), message=""
    )

    [warning] = stray_begin_install_warnings([result], dry_run=dry_run)

    assert (warning.detail == {blocks.LEFT_AS_IS: "1"}) is left
    assert bool(warning.detail) is left


def test_the_verify_note_names_both_blocks(tmp_path: Path) -> None:
    target = tmp_path / "AGENTS.md"
    target.write_bytes(_TWO_BLOCKS.encode())

    note = stray_begin_note([target], then="run apothem update")

    assert note.startswith(
        f"{target} holds 2 whole blocks between Apothem's markers (lines 2 to 4, "
        "and lines 8 to 10). Apothem writes one block per file and cannot tell "
        "which one is its own. Each fix below"
    )
    assert note.endswith(" Then run apothem update")
    assert _holds(_TWO_BLOCKS, note) == 2


def _profile_named(tmp_path: Path, name: str) -> str:
    """Write the minimal profile with the operator named *name*; return its path."""
    data = yaml.safe_load(Path(profile_minimal_path()).read_text(encoding="utf-8"))
    data.setdefault("identity", {})["name"] = name
    path = tmp_path / f"{name.replace(' ', '-')}.yaml"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    return str(path)


def test_an_end_marker_put_back_leaves_two_blocks_the_update_does_not_touch(
    sandbox_factory: SandboxFactory, tmp_path: Path
) -> None:
    """lifecycle-2: the update used to refresh the old block and verify passed.

    The block lost its END marker, an update added a fresh block below, and
    the END marker was put back where it was: the file holds two Apothem
    blocks, so the tool loads both. Update now leaves the file as it is and
    names both, and verify and verify --profile fail until one is deleted.
    The update ends as partial, not as a success (lifecycle-r4-5): the file
    got no block from the new profile.
    """
    box = sandbox_factory("claude-code")
    box.install()
    anchor = _anchor(box)
    lines = anchor.read_bytes().decode("utf-8").split("\n")
    at = lines.index(E)
    anchor.write_bytes("\n".join([*lines[:at], *lines[at + 1 :], "my tail"]).encode())
    code, output = box.invoke("update", "--profile", str(profile_minimal_path()))
    assert code == 0, output
    lines = anchor.read_bytes().decode("utf-8").split("\n")
    anchor.write_bytes("\n".join([*lines[:at], E, *lines[at:]]).encode())
    before = anchor.read_bytes()
    changed = _profile_named(tmp_path, "Changed Person")

    payload = box.partial("update", "--profile", changed)
    verify, verify_output = box.invoke("verify", "--json")
    faithful, faithful_output = box.invoke("verify", "--profile", changed)
    result = CliRunner().invoke(main, ["doctor", "--json"])

    assert anchor.read_bytes() == before
    [warning] = [w for w in payload["warnings"] if _names(str(w["message"]), anchor)]
    message = str(warning["message"])
    assert warning["detail"] == {"left_as_is": "1"}
    assert "holds 2 whole blocks between Apothem's markers (lines " in message
    assert verify == 1, verify_output
    [row] = json.loads(verify_output)["results"]
    assert "holds 2 whole blocks" in row["stray_begin"]["message"]
    assert faithful != 0, faithful_output
    [check] = [c for c in json.loads(result.output)["checks"] if c["status"] == "fail"]
    assert check["code"] == "harness.stray_begin"
    assert check["message"] == (
        "claude-code is installed but does not verify: a file holds Apothem "
        "markers to fix by hand."
    )


def test_a_marker_pair_of_yours_above_the_block_is_not_written_over(
    sandbox_factory: SandboxFactory,
) -> None:
    """lifecycle-2: an update used to write Apothem's block over your pair.

    Your marker pair outside code is a whole block too, so the file holds
    two, and the update leaves it as it is. It ended with the success line
    and exit code 0 (lifecycle-r4-5); a line on standard error now names the
    file it left, in place of the success line, and the exit code is 2, also
    under --quiet.
    """
    box = sandbox_factory("codex")
    box.install()
    anchor = _anchor(box)
    mine = f"# Notes\n\nThe markers:\n{B}\nMY EXAMPLE\n{E}\n\n".encode()
    anchor.write_bytes(mine + anchor.read_bytes())
    before = anchor.read_bytes()
    profile = str(profile_minimal_path())

    code, output = box.invoke("update", "--profile", profile)
    quiet = CliRunner().invoke(
        main, ["update", "--harness", "codex", "--profile", profile, "--quiet"]
    )

    assert code == 2, output
    assert anchor.read_bytes() == before
    assert "holds 2 whole blocks" in " ".join(output.split())
    assert "Updated codex" not in output
    line = (
        "✗ codex update left 1 file(s) as they are, without Apothem's current "
        "block, because of their Apothem marker lines; fix those lines as each "
        "warning says, keeping your own text, then run apothem update again"
    )
    named = os.path.normcase(f"{line}\n    {anchor}")
    assert named in os.path.normcase(_flat_lines(output)), output
    assert quiet.exit_code == 2, quiet.output
    assert "Updated codex" not in quiet.output
    assert named in os.path.normcase(_flat_lines(quiet.stderr)), quiet.output


def _flat_lines(text: str) -> str:
    """Return *text* with each line's runs of spaces after its indent made one."""
    return "\n".join(
        line[: len(line) - len(line.lstrip())] + " ".join(line.split())
        for line in text.splitlines()
    )


# --- an uninstall over two blocks: following its text keeps your pair --------

#: A marker pair of yours outside code: how Apothem wraps its rules.
_EXAMPLE = (
    f"My notes: Apothem wraps its rules like this:\n{B}\n(the rules go here)\n{E}\n\n"
)


def _uninstall_warning(box: _Sandbox, anchor: Path) -> tuple[int, str, str, str]:
    """Run the uninstall; return its exit code, output, warning and failure line.

    The warning is the one that names *anchor*; the failure line is the first
    result's message.
    """
    code, output = box.invoke("uninstall", "--yes", "--json")
    payload = json.loads(output)
    [warning] = [
        _flat(str(entry["message"]))
        for entry in payload["warnings"]
        if _names(str(entry["message"]), anchor)
    ]
    return code, output, warning, _flat(str(payload["results"][0]["message"]))


@pytest.mark.parametrize("where", ["above", "below"])
@pytest.mark.parametrize("harness_id", ["codex", "claude-code"])
def test_the_uninstall_puts_a_pair_of_yours_first_and_finishes_once_you_fix_it(
    harness_id: str, where: str, sandbox_factory: SandboxFactory
) -> None:
    """Keeping one block led you to delete Apothem's block and keep your pair.

    Someone uninstalling has no reason to keep Apothem's block, and the retry
    then took out your pair, the one block left. The fix for the case that
    Apothem's block is the one it wrote changes your pair's marker lines and
    keeps its text. Done that way, the uninstall run again finishes and keeps
    your example.
    """
    box = sandbox_factory(harness_id)
    box.install()
    anchor = _anchor(box)
    text = anchor.read_bytes().decode("utf-8")
    shaped = _EXAMPLE + text if where == "above" else f"{text}\n{_EXAMPLE}"
    anchor.write_bytes(shaped.encode())

    code, output, warning, failure = _uninstall_warning(box, anchor)
    kept = anchor.read_bytes()
    unmarked = _EXAMPLE.replace("<!--", "&lt;!--")
    anchor.write_bytes(shaped.replace(_EXAMPLE, unmarked, 1).encode())
    again, again_output = box.invoke("uninstall", "--yes", "--json")
    left = anchor.read_bytes().decode("utf-8")

    assert code == 2, output
    assert kept == shaped.encode()
    assert _holds(shaped, warning, removes=True) == 2
    assert "Delete lines" not in warning
    assert (
        "fix each as its warning says, keeping your own text (follow one of its "
        "numbered fixes, which change marker lines in place), then run apothem "
        "uninstall again"
    ) in failure
    assert "keep one block" not in failure.lower()
    assert again == 0, again_output
    assert left.strip() == unmarked.strip()
    kinds = [r.kind for r in install_ledger.read_records(box.entry.package_key)]
    assert kinds[-1] == "uninstall", kinds


@pytest.mark.parametrize("harness_id", ["codex", "claude-code"])
def test_the_uninstall_names_the_marker_lines_of_yours_around_apothem_s_block(
    harness_id: str, sandbox_factory: SandboxFactory
) -> None:
    """A BEGIN marker above Apothem's block and an END marker below it.

    They make a second block only once Apothem's block is out, and the text
    named no lines: its step to delete an Apothem block from its BEGIN
    marker line to its END marker line, taken on those two lines, deleted
    Apothem's block and your text between them. The warning now names
    Apothem's block and the two marker lines around it, and its fix changes
    the BEGIN marker above it (the END marker below then pairs with nothing);
    once you change those, the uninstall run again finishes and keeps every
    line of yours.
    """
    box = sandbox_factory(harness_id)
    box.install()
    anchor = _anchor(box)
    text = anchor.read_bytes().decode("utf-8")
    shaped = f"my own text above\n{B}\nmy note\n\n{text}\nmy own text below\n{E}\n"
    anchor.write_bytes(shaped.encode())
    lines = shaped.split("\n")
    outer, outer_end = lines.index(B) + 1, len(lines) - 1
    inner, inner_end = lines.index(B, outer) + 1, lines.index(E) + 1

    code, output, warning, _ = _uninstall_warning(box, anchor)
    kept = anchor.read_bytes()
    lines[outer - 1], lines[outer_end - 1] = "BEGIN (my marker)", "END (my marker)"
    anchor.write_bytes("\n".join(lines).encode())
    again, again_output = box.invoke("uninstall", "--yes", "--json")

    assert code == 2, output
    assert kept == shaped.encode()
    assert (
        "holds two different blocks between Apothem's markers: once the block "
        f"from line {inner} to line {inner_end} is out, the BEGIN marker at line "
        f"{outer} and the END marker at line {outer_end} make another."
    ) in warning
    assert (
        f"Do not delete the block from line {inner} to line {inner_end}: the next "
        f"run would then read lines {outer} to {outer_end} as Apothem's block, and "
        "replace or take out what is between them."
    ) in warning
    assert (
        f"Fix A, if lines {inner} to {inner_end} are Apothem's block: A1. Change "
        f"line {outer}: add a word inside its comment. Lines {inner} to "
        f"{inner_end} are then the one block in the file."
    ) in warning
    assert _holds(shaped, warning, removes=True) == 1
    assert again == 0, again_output
    assert anchor.read_bytes().decode("utf-8") == (
        "my own text above\nBEGIN (my marker)\nmy note\n\nmy own text below\n"
        "END (my marker)\n"
    )
    assert "code block" not in warning


#: Where Apothem's reader ends a line: CRLF, a lone CR and LF.
_LINE_END = re.compile(r"(\r\n|\r|\n)")


def _with_line_ends(text: str, ends: str) -> str:
    """Return *text*, written with LF endings, with the line endings *ends* names.

    ``cr``: every line ends with a lone CR. ``one-cr``: the first line holds a
    lone CR of its own (pasted from an old tool, say), so it reads as two
    lines. ``bom-cr``: CR endings after a byte order mark.
    """
    if ends == "cr":
        return text.replace("\n", "\r")
    if ends == "one-cr":
        return text.replace(" ", "\r", 1)
    return "﻿" + text.replace("\n", "\r")


def _reader_lines(path: Path) -> list[str]:
    """Return the lines of *path* as Apothem numbers them in its warnings.

    The file is split at CRLF, a lone CR and LF, and a byte order mark at
    offset 0 is not part of line 1.
    """
    text = path.read_bytes().decode("utf-8").removeprefix("﻿")
    return _LINE_END.split(text)[::2]


def _change_lines(path: Path, changes: dict[int, str]) -> None:
    """Replace the 1-based lines *changes* names, as the reader numbers them.

    Every line ending, and a byte order mark, stays as it is.
    """
    text = path.read_bytes().decode("utf-8")
    bom = "﻿" if text.startswith("﻿") else ""
    parts = _LINE_END.split(text.removeprefix(bom))
    for number, line in changes.items():
        parts[2 * (number - 1)] = line
    path.write_bytes((bom + "".join(parts)).encode("utf-8"))


@pytest.mark.parametrize("ends", ["cr", "one-cr", "bom-cr"])
def test_the_lines_named_around_the_block_count_a_lone_cr_as_a_line_end(
    ends: str, tmp_path: Path
) -> None:
    """markers-r4-1: the lines were counted at LF alone.

    The block between them was found with a lone CR as a line end, so in a
    file with one, the text named the marker lines of Apothem's own block as
    the ones to change. Each line named is now the one the reader numbers so.
    """
    target = tmp_path / "AGENTS.md"
    shaped = f"my own text above\n{B}\nmy note\n\n{OLD}\nmy own text below\n{E}\n"
    target.write_bytes(_with_line_ends(shaped, ends).encode("utf-8"))
    lines = _reader_lines(target)
    outer, outer_end = lines.index(B) + 1, len(lines) - 1
    inner, inner_end = lines.index(B, outer) + 1, lines.index(E) + 1

    message = _flat(blocks.another_block_report(target, then=None))

    assert lines[outer] == "my note"
    assert lines[outer_end - 2] == "my own text below"
    assert (
        f"once the block from line {inner} to line {inner_end} is out, the BEGIN "
        f"marker at line {outer} and the END marker at line {outer_end} make "
        f"another. Apothem writes one block per file and cannot tell which one is "
        "its own, so it left the file as it is. Do not delete the block from line "
        f"{inner} to line {inner_end}: the next run would then read lines {outer} "
        f"to {outer_end} as Apothem's block, and replace or take out what is "
        "between them."
    ) in message
    assert (
        f"A1. Change line {outer}: add a word inside its comment. Lines {inner} "
        f"to {inner_end} are then the one block in the file."
    ) in message


@pytest.mark.parametrize("ends", ["cr", "one-cr", "bom-cr"])
@pytest.mark.parametrize("harness_id", ["codex", "claude-code"])
def test_following_the_marker_line_text_in_a_file_with_lone_crs_keeps_your_lines(
    harness_id: str, ends: str, sandbox_factory: SandboxFactory
) -> None:
    """markers-r4-1: following the text let the next uninstall delete your lines.

    A file with a lone CR line ending, a BEGIN marker above Apothem's block
    and an END marker below it: the uninstall named the marker lines of
    Apothem's own block as the ones to delete or change. Done as it said,
    the BEGIN marker above and the END marker below made a whole block, and
    the next uninstall took it out with your lines between them, exit 0. The
    fix now changes the BEGIN marker line above the block; done as it says,
    the next uninstall finishes and keeps every line of yours, the END marker
    below the block, which then pairs with nothing, included.
    """
    box = sandbox_factory(harness_id)
    box.install()
    anchor = _anchor(box)
    text = anchor.read_bytes().decode("utf-8")
    shaped = f"my own text above\n{B}\nmy note KEEP1\n\n{text}\nmy tail KEEP2\n{E}\n"
    anchor.write_bytes(_with_line_ends(shaped, ends).encode("utf-8"))

    code, output, warning, _ = _uninstall_warning(box, anchor)
    named = re.search(
        r"A1\. Change line (\d+): add a word inside its comment\. Lines", warning
    )
    assert named is not None, warning
    outer = int(named[1])
    _change_lines(anchor, {outer: "BEGIN (my marker)"})
    again, again_output = box.invoke("uninstall", "--yes", "--json")
    left = _reader_lines(anchor)

    assert code == 2, output
    assert again == 0, again_output
    for mine in ("my note KEEP1", "my tail KEEP2", "BEGIN (my marker)", E):
        assert mine in left, left
    assert B not in left
    assert left.index("my note KEEP1") < left.index("my tail KEEP2")


@pytest.mark.parametrize("harness_id", ["codex", "claude-code"])
def test_the_uninstall_leaves_an_end_marker_you_quote_in_code_below_the_block(
    harness_id: str, sandbox_factory: SandboxFactory
) -> None:
    """The END marker below Apothem's block is one you quote in a code example.

    With what is left of an older block above, it makes a second block once
    Apothem's is out, and the text said to delete or change it too, an edit
    to your example that the fix does not need. The text now asks for the
    BEGIN marker alone and says the END marker can stay; done that way, the
    uninstall run again finishes and keeps your example as it is.
    """
    box = sandbox_factory(harness_id)
    box.install()
    anchor = _anchor(box)
    text = anchor.read_bytes().decode("utf-8")
    shaped = (
        f"my own text above\n{B}\nold Apothem rule\n\n{text}How the markers look:"
        f"\n\n```md\n{E}\n```\n\nmy own text below\n"
    )
    anchor.write_bytes(shaped.encode())
    lines = shaped.split("\n")
    outer = lines.index(B) + 1
    inner, inner_end = lines.index(B, outer) + 1, lines.index(E) + 1
    quoted = lines.index(E, inner_end) + 1

    code, output, warning, _ = _uninstall_warning(box, anchor)
    anchor.write_bytes("\n".join(lines[: outer - 1] + lines[outer + 2 :]).encode())
    again, again_output = box.invoke("uninstall", "--yes", "--json")
    left = anchor.read_bytes().decode("utf-8")

    assert code == 2, output
    assert (
        f"Do not delete the block from line {inner} to line {inner_end}: the next "
        f"run would then read lines {outer} to {quoted} as Apothem's block, and "
        "replace or take out what is between them."
    ) in warning
    assert (
        f"Fix A, if lines {inner} to {inner_end} are Apothem's block: A1. Change "
        f"line {outer}: add a word inside its comment. Lines {inner} to "
        f"{inner_end} are then the one block in the file."
    ) in warning
    assert f"Change line {quoted}" not in warning
    assert warning.endswith(" Then run the uninstall again.")
    assert _holds(shaped, warning, removes=True) == 1
    assert again == 0, again_output
    assert f"```md\n{E}\n```\n\nmy own text below\n" in left
    assert "my own text above" in left
    assert B not in left


#: An END marker you quote in code below Apothem's block, then your own text.
_QUOTED_END = f"How the markers look:\n\n```md\n{E}\n```\n\nmy own text below\n"

#: A marker pair of yours outside code, further down.
_PAIR_BELOW = f"\nMy example:\n{B}\nMY EXAMPLE\n{E}\n"


def _below_a_lone_begin(text: str, above: str, below: str = _PAIR_BELOW) -> str:
    """Return *text* (Apothem's block) under a BEGIN marker with *above* below it.

    An END marker quoted in code follows the block, then *below*.
    """
    return f"my own text above\n{B}\n{above}\n\n{text}{_QUOTED_END}{below}"


@pytest.mark.parametrize(
    ("above", "fix"),
    [
        pytest.param("old Apothem rule", "delete", id="older-block"),
        pytest.param("my note", "change", id="yours-changed"),
        pytest.param("my note", "delete", id="yours-deleted"),
    ],
)
@pytest.mark.parametrize("harness_id", ["codex", "claude-code"])
def test_the_uninstall_names_a_pair_of_yours_below_an_end_marker_you_quote(
    harness_id: str, above: str, fix: str, sandbox_factory: SandboxFactory
) -> None:
    """advice-1: the strip went ahead, and its text made your pair Apothem's block.

    A BEGIN marker sits above Apothem's block (what is left of an older
    block, or a line of yours), an END marker is quoted in code below it, and
    a marker pair of yours sits further down. Once Apothem's block is out,
    that BEGIN marker and the quoted END marker read as a pair with yours
    after it, so no block was certain: the uninstall took Apothem's block out
    and named only the BEGIN marker. Deleting it as that text said left your
    pair the one block in the file, and the next install replaced it. The
    uninstall now leaves the file as it is and names both whole blocks; done
    as each warning says, it finishes, and a later install and verify keep
    every line of yours.
    """
    box = sandbox_factory(harness_id)
    box.install()
    anchor = _anchor(box)
    shaped = _below_a_lone_begin(anchor.read_bytes().decode("utf-8"), above)
    anchor.write_bytes(shaped.encode())
    [(inner, inner_end), (mine, mine_end)] = whole_blocks(shaped)
    lines = shaped.split("\n")
    outer = lines.index(B) + 1
    quoted = lines.index(E, inner_end) + 1

    first, first_output, first_warning, _ = _uninstall_warning(box, anchor)
    kept = anchor.read_bytes()
    lines[mine - 1], lines[mine_end - 1] = "BEGIN (my example)", "END (my example)"
    anchor.write_bytes("\n".join(lines).encode())
    second, second_output, second_warning, _ = _uninstall_warning(box, anchor)
    if fix == "change":
        lines[outer - 1] = "(my marker)"
    elif above == "my note":
        del lines[outer - 1]
    else:
        del lines[outer - 1 : outer + 1]  # the BEGIN marker and the old text
    anchor.write_bytes("\n".join(lines).encode())
    third, third_output = box.invoke("uninstall", "--yes", "--json")
    left = anchor.read_bytes().decode("utf-8")
    box.install()
    after = anchor.read_bytes().decode("utf-8")
    verify, verify_output = box.invoke("verify")

    assert first == 2, first_output
    assert kept == shaped.encode()
    assert (
        f" holds 2 whole blocks between Apothem's markers (lines {inner} to "
        f"{inner_end}, and lines {mine} to {mine_end})."
    ) in first_warning
    assert first_warning.endswith(" Then run the uninstall again.")
    assert second == 2, second_output
    assert f"A1. Change line {outer}: add a word inside its comment." in (
        second_warning
    )
    assert f"Change line {quoted}" not in second_warning
    assert second_warning.endswith(" Then run the uninstall again.")
    assert third == 0, third_output
    assert B not in left
    assert f"```md\n{E}\n```" in left
    for line in ("my own text above", "my own text below", "MY EXAMPLE"):
        assert line in after
    assert ("my note" in after) is (above == "my note")
    assert len(whole_blocks(after)) == 1
    assert after.index("MY EXAMPLE") < after.index(B)
    assert verify == 0, verify_output


@pytest.mark.parametrize("harness_id", ["codex", "claude-code"])
def test_the_uninstall_still_strips_a_block_pasted_in_a_second_time(
    harness_id: str, sandbox_factory: SandboxFactory
) -> None:
    """An exact copy of Apothem's block goes with it, and the uninstall finishes.

    Only a whole block that differs from Apothem's own leaves the file as it
    is: a copy pasted in a second time is Apothem's text.
    """
    box = sandbox_factory(harness_id)
    box.install()
    anchor = _anchor(box)
    text = anchor.read_bytes().decode("utf-8")
    anchor.write_bytes(
        f"my own text above\n\n{text}\nmy own text between\n\n{text}\n"
        "my own text below\n".encode()
    )

    code, output = box.invoke("uninstall", "--yes", "--json")

    assert code == 0, output
    assert anchor.read_bytes().decode("utf-8") == (
        "my own text above\n\nmy own text between\n\nmy own text below\n"
    )


@pytest.mark.parametrize("harness_id", ["codex", "claude-code"])
def test_the_uninstall_still_strips_when_your_pair_below_sits_in_code(
    harness_id: str, sandbox_factory: SandboxFactory
) -> None:
    """The same file with your marker pair quoted in code: one whole block.

    The uninstall takes Apothem's block out and names the BEGIN marker it
    leaves. Deleting that line and the old text below it, as the warning
    says, keeps your example through a later install, and verify passes.
    """
    box = sandbox_factory(harness_id)
    box.install()
    anchor = _anchor(box)
    example = f"\nMy example:\n\n```md\n{B}\nMY EXAMPLE\n{E}\n```\n"
    text = anchor.read_bytes().decode("utf-8")
    anchor.write_bytes(_below_a_lone_begin(text, "old Apothem rule", example).encode())

    code, output, warning, _ = _uninstall_warning(box, anchor)
    left = anchor.read_bytes().decode("utf-8")
    anchor.write_bytes(left.replace(f"{B}\nold Apothem rule\n", "", 1).encode())
    box.install()
    after = anchor.read_bytes().decode("utf-8")
    verify, verify_output = box.invoke("verify")

    assert code == 0, output
    assert "still holds a line that reads as the Apothem BEGIN marker" in warning
    assert f"```md\n{B}\nMY EXAMPLE\n{E}\n```" in after
    assert "my own text above\n\nHow the markers look:" in after
    assert len(whole_blocks(after)) == 1
    assert verify == 0, verify_output


#: Apothem's block at line 1, pasted in a second time below a line of yours.
_PASTED = f"{OLD}\nmine\n\n{OLD}"


@pytest.mark.parametrize(
    ("text", "encoding", "another"),
    [
        pytest.param(_PASTED, "utf-8-sig", False, id="copy-behind-a-bom"),
        pytest.param(_PASTED.replace("\n", "\r\n"), "utf-8", False, id="copy-crlf"),
        pytest.param(_PASTED.replace("\n", "\r"), "utf-8", False, id="copy-cr"),
        pytest.param(_below_a_lone_begin(OLD, "old"), "utf-8", True, id="pair-below"),
        pytest.param(
            _below_a_lone_begin(OLD, "old", f"\n```md\n{B}\nMY EXAMPLE\n{E}\n```\n"),
            "utf-8",
            False,
            id="pair-below-in-code",
        ),
    ],
)
def test_another_block_is_any_whole_block_that_is_not_a_copy(
    tmp_path: Path, text: str, encoding: str, another: bool
) -> None:
    """advice-1: only the text left once Apothem's block was out counted.

    A whole block that differs from Apothem's counts even when taking
    Apothem's block out would hide it; a copy pasted in a second time does
    not, whatever its line endings, and with a byte order mark in front of
    the file.
    """
    target = tmp_path / "AGENTS.md"
    target.write_bytes(text.encode(encoding))

    assert blocks.another_block_at(target) is another


@pytest.mark.parametrize("harness_id", ["codex", "claude-code"])
def test_the_two_block_step_keeps_a_line_of_yours_inside_an_older_block(
    harness_id: str, sandbox_factory: SandboxFactory, tmp_path: Path
) -> None:
    """An END marker put back below a line of yours makes it the older block's.

    The step for Apothem's own blocks said to delete each other one from its
    BEGIN marker line to its END marker line, with no word on your own text,
    so that line went with it. It now says to keep any line of yours inside
    it; done that way, the update writes one block and verify passes.
    """
    box = sandbox_factory(harness_id)
    box.install()
    anchor = _anchor(box)
    original = anchor.read_bytes().decode("utf-8")
    anchor.write_bytes((original.replace(f"{E}\n", "") + "my own line\n").encode())
    changed = _profile_named(tmp_path, "Changed Person")
    first, first_output = box.invoke("update", "--profile", changed, "--json")
    lines = anchor.read_bytes().decode("utf-8").split("\n")
    lines.insert(lines.index("my own line") + 1, E)
    anchor.write_bytes("\n".join(lines).encode())

    second, second_output = box.invoke("update", "--profile", changed, "--json")
    [(old, old_end), _] = whole_blocks("\n".join(lines))
    anchor.write_bytes(
        "\n".join([*lines[: old - 1], "my own line", *lines[old_end:]]).encode()
    )
    third, third_output = box.invoke("update", "--profile", changed, "--json")
    after = anchor.read_bytes().decode("utf-8")
    verify, verify_output = box.invoke("verify")

    assert first == 0, first_output
    # Two whole blocks: the update leaves the file as it is, so it is partial.
    assert second == 2, second_output
    assert json.loads(second_output)["status"] == "partial"
    [message] = [
        _flat(str(warning["message"]))
        for warning in json.loads(second_output)["warnings"]
        if _names(str(warning["message"]), anchor)
    ]
    assert f"Fix A, if lines {old} to {old_end} are Apothem's block:" in message
    assert _OLD_TEXT in message
    assert third == 0, third_output
    assert (after.count(B), after.count(E), after.count("my own line")) == (1, 1, 1)
    assert verify == 0, verify_output


# --- with no install record, CLAUDE.md gets the same two-block text -----------

#: How the warning for a file no install record lists ends, after the fix,
#: when its second block shows only once Apothem's is out.
_UNLISTED_END = (
    " Then delete Apothem's block by hand if you no longer want it: no install "
    "record lists the file, so the uninstall leaves it as it is."
)

#: The same when it holds two or more whole blocks: the update and the
#: uninstall that the failure line asks for.
_UNLISTED_AGAIN = " Then run apothem update, then apothem uninstall again."


def _unrecorded_uninstall(
    box: _Sandbox, anchor: Path
) -> tuple[int, str, dict[str, Any], str]:
    """Delete the install ledger, then run the uninstall with no record in place.

    Return its exit code, output, the warning that names *anchor* (flattened
    message) and the failure line.
    """
    install_ledger.ledger_path(box.entry.package_key).unlink()
    code, output = box.invoke("uninstall", "--yes", "--json")
    payload = json.loads(output)
    [warning] = [
        entry for entry in payload["warnings"] if _names(str(entry["message"]), anchor)
    ]
    warning["message"] = _flat(str(warning["message"]))
    return code, output, warning, _flat(str(payload["results"][0]["message"]))


def _update_then_uninstall(box: _Sandbox) -> None:
    """Run the update, then the uninstall, the failure line asks for; both pass."""
    profile = str(profile_minimal_path())
    updated, update_output = box.invoke("update", "--profile", profile, "--json")
    assert updated == 0, update_output
    again, again_output = box.invoke("uninstall", "--yes", "--json")
    assert again == 0, again_output


def test_with_no_record_a_pair_of_yours_in_claude_md_gets_the_two_block_text(
    sandbox_factory: SandboxFactory,
) -> None:
    """The warning said to delete the lines from BEGIN to END by hand.

    With no install record, the uninstall leaves CLAUDE.md as it is and names
    it. Above Apothem's block sits a marker pair of yours, so that step, taken
    from the first BEGIN marker to the next END marker, deleted your pair and
    its text. The warning now names each block and puts your pair first, as
    it does for a recorded file, and ends with the update and the uninstall
    that the failure line asks for (advice-2); the exit code and the failure
    line stay as they were. Done that way, they keep your example.
    """
    box = sandbox_factory("claude-code")
    box.install()
    anchor = _anchor(box)
    shaped = _EXAMPLE + anchor.read_bytes().decode("utf-8")
    anchor.write_bytes(shaped.encode())
    [(begin, end), (block, block_end)] = whole_blocks(shaped)

    code, output, warning, failure = _unrecorded_uninstall(box, anchor)
    kept = anchor.read_bytes()
    unmarked = _EXAMPLE.replace("<!--", "&lt;!--")
    anchor.write_bytes(shaped.replace(_EXAMPLE, unmarked, 1).encode())
    _update_then_uninstall(box)

    assert code == 2, output
    assert kept == shaped.encode()
    assert (
        f" holds 2 whole blocks between Apothem's markers (lines {begin} to {end}, "
        f"and lines {block} to {block_end}). Apothem writes one block per file and "
        "cannot tell which one is its own, so it left the file as it is."
    ) in warning["message"]
    assert (
        f"Fix B, if lines {block} to {block_end} are Apothem's block: B1. "
        in (warning["message"])
    )
    assert warning["message"].endswith(
        f"Apothem's block is the one right below it.{_UNLISTED_AGAIN}"
    )
    assert "delete Apothem's block by hand" not in warning["message"]
    assert "detail" not in warning
    assert "then run apothem update, then apothem uninstall again" in failure
    assert "two different blocks" not in failure
    assert not _names(failure, anchor)
    assert anchor.read_bytes().decode("utf-8").strip() == unmarked.strip()


def test_with_no_record_the_two_block_text_keeps_your_lines_around_the_block(
    sandbox_factory: SandboxFactory,
) -> None:
    """advice-2: its step to delete Apothem's block by hand cost your note.

    With no install record, CLAUDE.md holds a BEGIN marker of yours above
    Apothem's block, an END marker below it, and a marker pair of yours
    further down. The warning names the two whole blocks, and once your pair
    was fixed it said to delete Apothem's block by hand: your BEGIN and END
    markers then made one block, and the next update replaced your note and
    your text between them. The warning now ends with the update and the
    uninstall that the failure line asks for. That uninstall names your two
    marker lines, and done as it says, it finishes and keeps every line.
    """
    box = sandbox_factory("claude-code")
    box.install()
    anchor = _anchor(box)
    text = anchor.read_bytes().decode("utf-8")
    shaped = (
        f"my own text above\n{B}\nmy note\n\n{text}\nmy own text below\n{E}\n"
        f"{_PAIR_BELOW}"
    )
    anchor.write_bytes(shaped.encode())
    [(inner, inner_end), (mine, mine_end)] = whole_blocks(shaped)
    lines = shaped.split("\n")
    outer, outer_end = lines.index(B) + 1, lines.index(E, inner_end) + 1

    code, output, warning, failure = _unrecorded_uninstall(box, anchor)
    lines[mine - 1], lines[mine_end - 1] = "BEGIN (my example)", "END (my example)"
    anchor.write_bytes("\n".join(lines).encode())
    profile = str(profile_minimal_path())
    updated, update_output = box.invoke("update", "--profile", profile, "--json")
    lines = anchor.read_bytes().decode("utf-8").split("\n")
    again, again_output, again_warning, _ = _uninstall_warning(box, anchor)
    lines[outer - 1], lines[outer_end - 1] = "BEGIN (my marker)", "END (my marker)"
    anchor.write_bytes("\n".join(lines).encode())
    last, last_output = box.invoke("uninstall", "--yes", "--json")
    left = anchor.read_bytes().decode("utf-8")

    assert code == 2, output
    assert (
        f" holds 2 whole blocks between Apothem's markers (lines {inner} to "
        f"{inner_end}, and lines {mine} to {mine_end})."
    ) in warning["message"]
    assert warning["message"].endswith(
        f"Apothem's block is the one right below it.{_UNLISTED_AGAIN}"
    )
    assert "then run apothem update, then apothem uninstall again" in failure
    assert updated == 0, update_output
    assert again == 2, again_output
    assert (
        f"A1. Change line {outer}: add a word inside its comment. Lines"
    ) in again_warning
    assert last == 0, last_output
    assert B not in left
    assert E not in left
    for line in ("my own text above", "my note", "my own text below", "MY EXAMPLE"):
        assert line in left


@pytest.mark.parametrize(
    "above",
    [
        pytest.param(f"{B}\nmy note\n", id="your-begin-marker"),
        pytest.param(f"My example:\n\n```md\n{B}\nexample\n{E}\n```\n", id="quoted"),
    ],
)
def test_with_no_record_the_one_block_text_names_apothem_s_block_by_its_lines(
    above: str, sandbox_factory: SandboxFactory
) -> None:
    """advice-3: it said to delete the lines from the BEGIN to the END marker.

    With no install record, CLAUDE.md holds a BEGIN marker of yours above
    Apothem's block, or a marker pair you quote in code there. Taken from the
    first BEGIN marker, that step cut your note or your example. The warning
    now names Apothem's block by its lines, and its fix changes the block's
    BEGIN marker line and yours, which would otherwise read as Apothem's
    once the block is out (advice-4: a numbered delete changed how the lines
    around the block read). Doing those steps keeps every line of yours.
    """
    box = sandbox_factory("claude-code")
    box.install()
    anchor = _anchor(box)
    text = anchor.read_bytes().decode("utf-8")
    shaped = f"my own text above\n{above}\n{text}my own text below\n"
    anchor.write_bytes(shaped.encode())
    [(begin, end)] = whole_blocks(shaped)
    lines = shaped.split("\n")
    mine = [number for number, line in enumerate(lines[: begin - 1], 1) if line == B]

    code, output, warning, _ = _unrecorded_uninstall(box, anchor)
    kept = anchor.read_bytes()
    [(_, fix)] = _fixes(warning["message"])
    anchor.write_bytes(_text_of(_follow(lines[:-1], fix)).encode())

    assert code == 2, output
    assert kept == shaped.encode()
    changes = "".join(
        f" A{step}. Change line {number}: add a word inside its comment."
        for step, number in enumerate(reversed(mine), 2)
    )
    assert warning["message"].startswith(
        f"{anchor} still holds Apothem's managed block (lines {begin} to {end}): "
        "no install record lists the file, so the uninstall leaves it as it is. "
        "If you no longer want the block, take it out by hand. Each fix below"
    )
    assert (
        f"Fix A: A1. Change line {begin}: add a word inside its comment.{changes} "
        "Apothem then finds no block of its own in this file."
    ) in warning["message"]
    fixed = anchor.read_bytes().decode("utf-8")
    assert not whole_blocks(fixed)
    assert not has_stray_begin(fixed)
    assert not uncertain_pairs(fixed)
    assert fixed.replace(" (example) -->", " -->") == shaped


def test_with_no_record_claude_md_names_the_marker_lines_around_apothem_s_block(
    sandbox_factory: SandboxFactory,
) -> None:
    """A BEGIN marker above Apothem's block and an END marker below it.

    With no install record, the step to delete the lines from BEGIN to END by
    hand, taken from the first BEGIN marker to the next END marker, deleted
    your note with Apothem's block and left the END marker below. The warning
    now names Apothem's block and the two marker lines around it, as it does
    for a recorded file; the exit code and the failure line stay as they
    were. Once you change those two lines, the update and the uninstall that
    the failure line asks for keep every line of yours.
    """
    box = sandbox_factory("claude-code")
    box.install()
    anchor = _anchor(box)
    text = anchor.read_bytes().decode("utf-8")
    shaped = f"my own text above\n{B}\nmy note\n\n{text}\nmy own text below\n{E}\n"
    anchor.write_bytes(shaped.encode())
    lines = shaped.split("\n")
    outer, outer_end = lines.index(B) + 1, len(lines) - 1
    inner, inner_end = lines.index(B, outer) + 1, lines.index(E) + 1

    code, output, warning, failure = _unrecorded_uninstall(box, anchor)
    kept = anchor.read_bytes()
    lines[outer - 1], lines[outer_end - 1] = "BEGIN (my marker)", "END (my marker)"
    anchor.write_bytes("\n".join(lines).encode())
    _update_then_uninstall(box)

    assert code == 2, output
    assert kept == shaped.encode()
    assert (
        " holds two different blocks between Apothem's markers: once the block "
        f"from line {inner} to line {inner_end} is out, the BEGIN marker at line "
        f"{outer} and the END marker at line {outer_end} make another."
    ) in warning["message"]
    assert (
        f"Do not delete the block from line {inner} to line {inner_end}: the next "
        f"run would then read lines {outer} to {outer_end} as Apothem's block, and "
        "replace or take out what is between them."
    ) in warning["message"]
    assert (
        f"A1. Change line {outer}: add a word inside its comment. Lines"
    ) in warning["message"]
    assert warning["message"].endswith(_UNLISTED_END)
    assert "detail" not in warning
    assert "then run apothem update, then apothem uninstall again" in failure
    assert "two different blocks" not in failure
    assert not _names(failure, anchor)
    assert anchor.read_bytes().decode("utf-8") == (
        "my own text above\nBEGIN (my marker)\nmy note\n\nmy own text below\n"
        "END (my marker)\n"
    )


# --- what an uninstall says about a BEGIN marker it leaves --------------------


def test_the_uninstall_names_the_old_text_below_a_lone_begin_marker(
    tmp_path: Path,
) -> None:
    """lifecycle-3: no later install, verify or uninstall names the old text.

    The warning names the marker's line, gives the step that changes it, and
    says the old Apothem text below it is yours to keep or delete, since the
    tool still reads it. After an uninstall, verify does not look at the
    file, so the warning does not say it fails until then.
    """
    target = tmp_path / "CLAUDE.md"
    target.write_text(f"# top\n{B}\nold rules\n\nmy own line\n", encoding="utf-8")
    result = install_driver.MaterializationResult(
        outcome="updated",
        operation="surgical_uninstall",
        path=str(target),
        message="",
    )

    [warning] = blocks.stray_begin_warnings([result])

    assert warning.message.startswith(
        f"{target} still holds a line that reads as the Apothem BEGIN marker at "
        f"line 2, with no END marker ({E}) after it, now that Apothem's block is "
        "out: an install keeps it as it is, and the tool still reads the text "
        "below it."
    )
    assert "A1. Change line 2: add a word inside its comment." in warning.message
    assert warning.message.endswith(_OLD_TEXT)
    assert "verify" not in warning.message


# --- a preview says what the run would do --------------------------------------


def _block_file(box: _Sandbox) -> Path:
    """Return the first Markdown file the install record lists as a block file."""
    record = install_ledger.read_records(box.entry.package_key)[-1]
    return next(
        Path(target.path)
        for target in record.targets
        if target.mode == "sentinel_merge" and Path(target.path).suffix == ".md"
    )


@pytest.mark.parametrize("harness_id", ["codex", "claude-code", "hermes"])
def test_a_dry_run_says_it_would_leave_an_unclear_file_as_it_is(
    harness_id: str, sandbox_factory: SandboxFactory
) -> None:
    """lifecycle-5: the preview said Apothem 'left' the file it only previewed."""
    box = sandbox_factory(harness_id)
    box.install()
    anchor = _block_file(box)
    _fence_the_block(anchor)
    profile = str(profile_minimal_path())

    code, output = box.invoke("update", "--profile", profile, "--dry-run", "--json")

    assert code == 0, output
    [message] = [
        str(w["message"])
        for w in json.loads(output)["warnings"]
        if _names(str(w["message"]), anchor)
    ]
    assert "so it would leave the file as it is." in message
    assert "left the file" not in message


# --- a recorded file whose block lost its END above a quoted pair -------------


def test_a_recorded_lost_end_above_a_quoted_pair_names_the_begin_marker_first(
    tmp_path: Path,
) -> None:
    """markers-2, regress-2: the update leaves the file; the BEGIN comes first.

    With an install record, the pair in code may be Apothem's block in a code
    block of yours, so no second block is added. The warning names the BEGIN
    marker that starts no pair, with the old text below it, before the pair.
    """
    text = f"# top\n{B}\nold rules\n\n## Notes\n\n```md\n{B}\nquoted\n{E}\n```\n"
    merged = merge_managed_block(text, "new rules", recorded=True)
    target, [message] = _held(tmp_path, merged)

    assert merged == text
    assert message.startswith(
        f"{target}: Apothem cannot tell whether the marker lines in this file mark "
        "its block or text of yours, so it left the file as it is. The BEGIN marker "
        "at line 2 starts no marker pair: its END marker is gone, or the marker is "
        "yours."
    )
    assert _OLD_TEXT in message
    assert (
        "The BEGIN marker at line 8 and the END marker at line 10 sit inside a code "
        "block that opens at line 7."
    ) in message


# --- a marker example of yours in a recorded file ------------------------------

#: A section of yours that quotes Apothem's two marker lines in a code block.
_DOCUMENTED = (
    "\n## How Apothem marks its block\n\n```md\n"
    f"{B}\n(Apothem's rules)\n{E}\n```\n\nmy closing words\n"
)


def _left(warning: dict[str, Any]) -> bool:
    """Return True when *warning* names a file the run left as it is."""
    return bool(warning.get("detail", {}).get("left_as_is"))


def test_a_file_your_example_holds_back_ends_as_partial_until_you_change_it(
    sandbox_factory: SandboxFactory, tmp_path: Path
) -> None:
    """lifecycle-r4-1: install and update ended as a success and wrote nothing.

    A recorded CLAUDE.md quotes Apothem's marker lines in a code block of
    yours, and Apothem's own block lost its END line. Each update left the
    file as it is (the quoted pair may be Apothem's block in a code block of
    yours), yet ended with "success" and exit code 0, so the tool loaded no
    profile block, and nothing said that the hold lasts until your example
    changes. Each such run now ends as partial and the warning says what ends
    it. Done as each warning says, the next update writes a fresh block,
    keeps your example and every line of yours, and the uninstall finishes.
    """
    box = sandbox_factory("claude-code")
    box.install()
    anchor = _anchor(box)
    text = anchor.read_bytes().decode("utf-8")
    end = text.index(E)
    lost = text[:end] + text[end + len(E) + 1 :] + _DOCUMENTED
    anchor.write_bytes(lost.encode())
    changed = _profile_named(tmp_path, "Changed Person")

    first = box.partial("update", "--profile", changed)
    after_first = anchor.read_bytes()
    # As the first warning says: the BEGIN marker that starts no pair goes,
    # with the old Apothem text below it.
    anchor.write_bytes(lost[lost.index("## How Apothem") :].encode())
    second = box.partial("update", "--profile", changed)
    after_second = anchor.read_bytes()
    # As the second warning says: change the two marker lines of your example.
    example = after_second.decode("utf-8")
    example = example.replace(B, B.replace(" -->", " (example) -->"))
    example = example.replace(E, E.replace(" -->", " (example) -->"))
    anchor.write_bytes(example.encode())
    code, output = box.invoke("update", "--profile", changed, "--json")
    written = anchor.read_bytes().decode("utf-8")
    verify, verify_output = box.invoke("verify", "--profile", changed)
    gone, gone_output = box.invoke("uninstall", "--yes", "--json")
    left = anchor.read_bytes().decode("utf-8")

    assert after_first == lost.encode()
    [held] = [_flat(str(w["message"])) for w in first["warnings"] if _left(w)]
    assert "The BEGIN marker at line 1 starts no marker pair" in held
    assert after_second == lost[lost.index("## How Apothem") :].encode()
    [message] = [_flat(str(w["message"])) for w in second["warnings"] if _left(w)]
    assert (
        "Until you fix these marker lines as this text says, install and update "
        "leave this file as it is and end as partial (exit code 2). A marker "
        "example of yours in code holds the file back the same way, until you "
        "change its BEGIN marker line."
    ) in message
    assert "Fix A: A1. Change line" in message
    assert code == 0, output
    assert json.loads(output)["status"] == "success"
    assert written.startswith(example)
    assert "Changed Person" in written
    assert written.count(B) == 1
    assert verify == 0, verify_output
    assert gone == 0, gone_output
    assert left == example


def test_a_quickstart_over_a_file_it_leaves_ends_as_partial(
    sandbox_factory: SandboxFactory,
) -> None:
    """lifecycle-r4-5: the guided run's summary said success too.

    Its install step leaves a recorded file as it is, so the summary and the
    install step are partial and the exit code is 2.
    """
    box = sandbox_factory("codex")
    box.install()
    anchor = _anchor(box)
    _fence_the_block(anchor)
    before = anchor.read_bytes()

    result = CliRunner().invoke(
        main,
        [
            "quickstart",
            "--harness",
            "codex",
            "--profile",
            str(profile_minimal_path()),
            "--yes",
            "--json",
        ],
    )

    assert result.exit_code == 2, result.output
    payload = json.loads(result.output)
    assert payload["status"] == "partial"
    [step] = [s for s in payload["steps"] if s["step"] == "install"]
    assert step["status"] == "partial"
    assert anchor.read_bytes() == before


def test_a_plain_quickstart_over_a_file_it_leaves_prints_its_next_steps(
    sandbox_factory: SandboxFactory,
) -> None:
    """lifecycle-r5-8: the plain run ended at the install's ✗ line.

    The install exited with code 2 before quickstart printed the verify and
    doctor commands it recommends. The install now hands that exit back, as
    it does under --json: the run prints the ✗ line, then the next steps,
    and exits with code 2.
    """
    box = sandbox_factory("codex")
    box.install()
    anchor = _anchor(box)
    _fence_the_block(anchor)
    before = anchor.read_bytes()

    result = CliRunner().invoke(
        main,
        [
            "quickstart",
            "--harness",
            "codex",
            "--profile",
            str(profile_minimal_path()),
            "--yes",
            "--no-color",
        ],
    )

    output = _flat_lines(result.output)
    assert result.exit_code == 2, result.output
    left = output.find("✗ codex install left 1 file(s) as they are")
    assert -1 < left < output.find("Recommended next step:"), output
    assert (
        "Fix the files it left: follow each file's warning, then run apothem "
        "update --harness codex\n"
    ) in output
    assert "Confirm the install" not in output
    assert "Check system health: apothem doctor" in output
    assert anchor.read_bytes() == before


@pytest.mark.parametrize("left", [True, False], ids=["left", "written"])
def test_a_clean_install_names_the_verify_step_only_when_it_left_no_file(
    left: bool, sandbox_factory: SandboxFactory
) -> None:
    """docs-tests-7: a clean install that left a file said to verify it.

    Its next step said to confirm the fresh install with apothem verify,
    which fails for the file left as it is. Such a run now ends with the ✗
    line and exit code 2, without that step; a clean install that leaves no
    file still prints it.
    """
    box = sandbox_factory("gemini-cli")
    anchor = _anchor(box)
    anchor.write_bytes((_TWO_BLOCKS if left else "# Notes\n").encode())

    code, output = box.invoke(
        "install", "--profile", str(profile_minimal_path()), "--clean", "--yes"
    )

    flat = _flat_lines(output)
    assert code == (2 if left else 0), output
    assert ("✗ gemini-cli install left 1 file(s) as they are" in flat) is left
    step = "Next step: confirm the fresh install with apothem verify"
    assert (step in flat) is not left, output


def test_a_batch_that_leaves_a_file_counts_it_in_the_summary_line(
    sandbox_factory: SandboxFactory, tmp_path: Path
) -> None:
    """docs-tests-7: no test read the summary line of a partial batch.

    Of the two tools an all batch installs, one leaves its file as it is:
    its ✗ line names the file, and the summary line below starts with "!"
    and counts that file. The exit code is 2.
    """
    box = sandbox_factory("codex")
    anchor = _anchor(box)
    anchor.parent.mkdir(parents=True)
    anchor.write_bytes(_TWO_BLOCKS.encode())
    data = yaml.safe_load(Path(profile_minimal_path()).read_text(encoding="utf-8"))
    data["exclude_harnesses"] = [
        entry.public_id
        for entry in HARNESS_REGISTRY
        if entry.public_id not in {"codex", "claude-code"}
    ]
    profile = tmp_path / "two-tools.yaml"
    profile.write_text(yaml.safe_dump(data), encoding="utf-8")

    result = CliRunner().invoke(
        main, ["install", "--harness", "all", "--profile", str(profile)]
    )

    output = _flat_lines(result.output)
    assert result.exit_code == 2, result.output
    summary = re.search(
        r"^! Installed 2 harnesses \(\d+ files written\); 1 file\(s\) left as "
        r"they are, named above\.$",
        output,
        re.MULTILINE,
    )
    assert summary is not None, output
    left = output.find("✗ codex install left 1 file(s) as they are")
    assert -1 < left < summary.start(), output
    assert "✓ Installed claude-code -> " in output
    assert anchor.read_bytes() == _TWO_BLOCKS.encode()


# --- the code block around Apothem's block, closed below it ---------------------


def _code_text(text: str) -> str:
    """Return every line a CommonMark reading of *text* shows as code, joined."""
    from markdown_it import MarkdownIt

    tokens = MarkdownIt("commonmark").parse(text)
    return "".join(t.content for t in tokens if t.type in {"fence", "code_block"})


def _code_line_numbers(text: str) -> set[int]:
    """Return the 0-based lines a CommonMark reading of *text* shows as code."""
    from markdown_it import MarkdownIt

    code: set[int] = set()
    for token in MarkdownIt("commonmark").parse(text):
        if token.type in {"fence", "code_block"} and token.map is not None:
            code.update(range(*token.map))
    return code


#: What follows the line that closes the code block around Apothem's block:
#: your text, and code examples of yours whose opening line carries an info
#: string (```sh), which closes nothing, also right below that line or after
#: a blank line only.
_YOUR_LINES_BELOW = {
    "text": "\nafter fence\n\nmy tail\n",
    "text-then-an-example": "\nafter fence\n\nMore:\n\n```sh\nls\n```\n\nmy tail\n",
    "a-line-then-an-example": "\nsome prose\n\n```sh\nls\n```\n",
    "two-examples": ("\nafter\n\n```sh\nls\n```\n\nmid\n\n```py\nx = 1\n```\n\ntail\n"),
    "an-example-right-below": "```sh\nls\n```\n\nmy tail\n",
    "a-blank-line-then-an-example": "\n```sh\nls\n```\n\nmy tail\n",
}


def _code_blocks_from(text: str, line: int) -> list[tuple[str, str]]:
    """Return the info string and text of each code block *text* opens from *line* on.

    *line* is 0-based; the reading is CommonMark's.
    """
    from markdown_it import MarkdownIt

    return [
        (token.info, token.content)
        for token in MarkdownIt("commonmark").parse(text)
        if token.type in {"fence", "code_block"}
        and token.map is not None
        and token.map[0] >= line
    ]


def _follow_the_step(text: str, message: str) -> tuple[str, int, int]:
    """Return *text* fixed as *message* says, and the lines of the pair it names.

    *message* gives one fix, followed step by step in the order printed.
    """
    lines = text.split("\n")
    [(_, fix)] = _fixes(message)
    named = re.search(
        r"BEGIN marker at line (\d+) and the END marker at line (\d+)", message
    )
    assert named is not None, message
    return _text_of(_follow(lines[:-1], fix)), int(named[1]), int(named[2])


@pytest.mark.parametrize(
    "below", list(_YOUR_LINES_BELOW.values()), ids=list(_YOUR_LINES_BELOW)
)
@pytest.mark.parametrize("harness_id", ["codex", "claude-code"])
def test_following_the_fix_for_a_block_in_your_code_block_leaves_no_code_open(
    harness_id: str, below: str, sandbox_factory: SandboxFactory
) -> None:
    """lifecycle-r4-4, markers-r4-4: done as the text said, your text became code.

    Apothem's block sits in a code block of yours that a closing line below
    the block ends, with your own text after it. The text said to close that
    code block above the BEGIN marker; done that way, the old closing line
    below the block opened a code block that nothing closes, so a Markdown
    viewer showed every line of yours after it as code. The text then said to
    move that closing line up only when that code block ran to the end of
    the file: with a code example of yours further down, whose last line
    closed it, the text still said to add a closing line, and done that way
    your text above that example (and the line that opens it) read as code,
    while the next update and verify passed (r12). With the example right
    below the closing line, or after a blank line only, it still said so, and
    the example showed its opening line as code without its info string
    (r13). Moving that closing line up (markers-r5-1) still changed how lines
    read once the update replaced the block (advice-1). The fix now changes
    the BEGIN marker line in place and moves or adds no line; followed step
    by step, the update writes Apothem's block at the end of the file,
    verify passes, and every line reads as before: your code above the block
    stays code, each line below it reads as code only where it did, each
    code example of yours below it keeps its info string and text, and the
    block written at the end reads as no code. The old Apothem text in your
    code block is yours to delete.
    """
    box = sandbox_factory(harness_id)
    box.install()
    anchor = _anchor(box)
    text = anchor.read_bytes().decode("utf-8")
    wrapped = f"My notes:\n\n```\nmake test\n\n{text}```\n{below}"
    anchor.write_bytes(wrapped.encode())
    profile = str(profile_minimal_path())

    payload = box.partial("update", "--profile", profile)
    [message] = [_flat(str(w["message"])) for w in payload["warnings"] if _left(w)]
    fixed, begin, end = _follow_the_step(wrapped, message)
    anchor.write_bytes(fixed.encode())
    code, output = box.invoke("update", "--profile", profile, "--json")
    verify, verify_output = box.invoke("verify")
    after = anchor.read_bytes().decode("utf-8")

    assert (wrapped.split("\n")[begin - 1], wrapped.split("\n")[end - 1]) == (B, E)
    assert "add a line of" not in message
    assert code == 0, output
    assert json.loads(output)["status"] == "success"
    assert verify == 0, verify_output
    assert after.count(B) == 1
    assert after.startswith(fixed)
    assert "make test" in _code_text(after)
    count = len(wrapped.split("\n")) - 1
    was, now = _code_line_numbers(wrapped), _code_line_numbers(after)
    assert {at for at in now if at < count} == was
    assert not [at for at in now if at >= count]
    closer = wrapped.split("\n").index("```", end) + 1
    assert _code_blocks_from(after, closer) == _code_blocks_from(wrapped, closer)


def test_no_step_deletes_a_closing_line_by_a_number_an_earlier_step_moved(
    tmp_path: Path,
) -> None:
    """markers-r5-2: the fix named the closing line by its first number.

    The code block around the pair opens in the old Apothem text below a
    BEGIN marker that starts no pair. The fix said to delete that opening
    line with the old text, "and delete line 10": read in order, line 10 was
    then a line of yours. The fix now changes both BEGIN marker lines in
    place and moves or deletes no line; followed step by step, it holds.
    """
    text = f"# top\n{B}\nold rules\n```bash\nnpm ci\n\n{OLD}```\n\nmy tail\n"
    _, [message] = _held(tmp_path, text)

    assert (
        "Fix A: A1. Change line 7: add a word inside its comment. A2. Change line "
        f"2: add a word inside its comment. {_AT_END}"
    ) in message
    assert "delete line" not in message.lower()
    assert "Move line" not in message
    assert _holds(text, message) == 1


# --- the record a hold-back reads ---------------------------------------------

#: Apothem's block inside a code block of yours that a later fence closes.
_FENCED = f"Intro\n```\ncode\n\n{OLD}New:\n```bash\nnpm ci\n```\n"


def _link(link: Path, target: Path) -> None:
    """Make *link* lead to the folder *target*, or skip the test when none can."""
    target.mkdir(parents=True, exist_ok=True)
    link.parent.mkdir(parents=True, exist_ok=True)
    try:
        link.symlink_to(target, target_is_directory=True)
        return
    except OSError:
        if sys.platform != "win32":
            pytest.skip("this host cannot make a symbolic link")
    try:
        import _winapi

        _winapi.CreateJunction(str(target), str(link))
    except OSError:
        pytest.skip("this host can make neither a symbolic link nor a junction")


def _spell_home(monkeypatch: pytest.MonkeyPatch, home: Path) -> None:
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))


def test_the_record_under_the_other_spelling_of_the_folder_lists_the_file(
    tmp_path: Path,
) -> None:
    """merge-4: no test read the record through every spelling of the folder.

    The newest record under the link's spelling leaves the file out, and the
    record under the folder's own spelling lists it: the file is listed, as
    the uninstall reads it, so the pair in code there is evidence.
    """
    real, linked = tmp_path / "real-home", tmp_path / "link-home"
    _link(linked, real)
    anchor = real / ".codex" / "AGENTS.md"
    anchor.parent.mkdir(parents=True)
    anchor.write_bytes(_FENCED.encode())
    _record("codex", real / ".codex", anchor)
    _record("codex", linked / ".codex")
    spelled = linked / ".codex" / "AGENTS.md"

    assert current_target("codex", linked / ".codex", spelled) is None
    assert listed_in_record("codex", linked / ".codex", spelled)
    assert install_driver.detect_install("codex", harness_root=linked / ".codex")


def test_an_install_under_another_spelling_holds_a_recorded_file_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """merge-2: the install read only the record under its own spelling.

    Detection and the uninstall read the records under every spelling of the
    folder, so the pair in code counted as Apothem's block there. An install
    under a spelling whose newest record leaves the file out read the same
    pair as your quote, added a second block without a warning, and verify
    then passed. The install now reads the record as the uninstall does: it
    leaves the file as it is and ends as partial.
    """
    real, linked = tmp_path / "real-home", tmp_path / "link-home"
    _link(linked, real)
    profile = str(profile_minimal_path())
    runner = CliRunner()
    for home in (linked, real):
        _spell_home(monkeypatch, home)
        result = runner.invoke(
            main, ["install", "--harness", "codex", "--profile", profile, "--json"]
        )
        assert result.exit_code == 0, result.output
    anchor = real / ".codex" / "AGENTS.md"
    _fence_the_block(anchor)
    before = anchor.read_bytes()
    link_root = linked / ".codex"
    newest = install_ledger.current_install_record("codex", root=link_root)
    assert newest is not None
    install_ledger.append_record(
        LedgerRecord.create(
            harness="codex",
            root=link_root,
            kind="install",
            targets=tuple(
                target
                for target in newest.targets
                if Path(target.path).name != "AGENTS.md"
            ),
        )
    )

    _spell_home(monkeypatch, linked)
    result = runner.invoke(
        main, ["install", "--harness", "codex", "--profile", profile, "--json"]
    )

    assert result.exit_code == 2, result.output
    assert json.loads(result.output)["status"] == "partial"
    assert anchor.read_bytes() == before
    assert before.count(B.encode()) == 1


def test_the_hold_back_reads_an_unreadable_ledger_as_a_record(tmp_path: Path) -> None:
    """merge-2, merge-1: the hold-back read an unreadable ledger as no record.

    The pair in code then read as your quote, and the install added a second
    block beside it. Detection and the uninstall read such a ledger as a
    record, and so does the hold-back now, on both write paths: the
    instruction file of a tool's manifest, and a file such as CLAUDE.md or a
    profile document.
    """
    root = tmp_path / ".codex"
    anchor = root / "AGENTS.md"
    anchor.parent.mkdir(parents=True)
    anchor.write_bytes(_FENCED.encode())
    _record("codex", root, anchor)
    _damage_ledger("codex")
    [entry] = [
        entry
        for entry in _load_rules("codex").install
        if entry.mode == "sentinel_merge" and entry.target.endswith("AGENTS.md")
    ]

    preview = install_driver_merge._operator_owned_preview(
        entry, harness_root=root, project_root=None, harness_name="codex"
    )
    written = install_driver.apply_managed_block_anchor(
        anchor, "new rules", install_root=root, harness_name="codex", dry_run=True
    )

    assert preview is not None
    assert preview.outcome == "unchanged"
    assert written.outcome == "unchanged"


# --- the hold the text claims ---------------------------------------------------

#: The sentence that says install and update leave a file as it is, and the
#: one that says a marker example of yours in code does the same.
_HOLDS = (
    "Until you fix these marker lines as this text says, install and update leave "
    "this file as it is and end as partial (exit code 2)."
)
_EXAMPLE_HOLDS = (
    "A marker example of yours in code holds the file back the same way, until "
    "you change its BEGIN marker line."
)


@pytest.mark.parametrize("recorded", [True, False], ids=["recorded", "no-record"])
@pytest.mark.parametrize("harness_id", ["codex", "gemini-cli"])
def test_verify_and_doctor_say_the_file_is_left_as_it_is_only_when_it_is(
    harness_id: str, recorded: bool, sandbox_factory: SandboxFactory, tmp_path: Path
) -> None:
    """The verify note and the doctor fix said so for a file no record lists.

    Apothem's block sits in a code block of yours and the install ledger is
    gone. The text said install and update leave the file as it is until you
    fix its marker lines, but with no record the merge reads the pair in code
    as text of yours: the next update ended as a success and wrote a block
    of its own. The text now says so only where the merge holds the file
    back, as it does while an install record lists the file. Without a
    record, Codex shows no other sign of the install, so doctor reports it
    as not installed; a project keeps its .apothem folder, so doctor checks
    the Gemini CLI install there.
    """
    box = sandbox_factory(harness_id)
    box.install()
    anchor = _anchor(box)
    _fence_the_block(anchor)
    if not recorded:
        install_ledger.ledger_path(box.entry.package_key).unlink()
    changed = _profile_named(tmp_path, "Changed Person")

    code, output = box.invoke("verify", "--json")
    doctor = CliRunner().invoke(main, ["doctor", "--json", *box.scope()])
    update, update_output = box.invoke("update", "--profile", changed, "--json")

    assert code == 1, output
    [row] = json.loads(output)["results"]
    texts = [_flat(row["stray_begin"]["message"])]
    texts += [
        _flat(str(check["fix"]))
        for check in json.loads(doctor.stdout)["checks"]
        if check["code"] == "harness.stray_begin"
    ]
    assert len(texts) == (1 if harness_id == "codex" and not recorded else 2)
    for text in texts:
        assert _names(text, anchor)
        assert "Fix A: A1. Change line" in text
        assert (_HOLDS in text) is recorded
        assert (_EXAMPLE_HOLDS in text) is recorded
    assert update == (2 if recorded else 0), update_output


def test_the_note_says_a_file_is_left_as_it_is_only_where_the_merge_does(
    tmp_path: Path,
) -> None:
    """A pair in code holds a file back only while an install record lists it.

    The pair rule 3 fired on holds the file back with or without a record, so
    the note says install and update leave that file as it is either way, but
    says that a marker example of yours in code does the same only while a
    record lists the file.
    """
    quoted = tmp_path / "quoted.md"
    quoted_text = f"# Notes\n\n```md\n{B}\nexample\n{E}\n```\n"
    quoted.write_bytes(quoted_text.encode())
    split = tmp_path / "split.md"
    split_text = _RESIDUAL + _QUOTED_BELOW
    split.write_bytes(split_text.encode())

    def listed(path: Path) -> bool:
        return True

    unlisted = {
        path: _flat(stray_begin_note([path], then="x")) for path in (quoted, split)
    }
    recorded = {
        path: _flat(stray_begin_note([path], then="x", listed=listed))
        for path in (quoted, split)
    }

    assert merge_managed_block(quoted_text, "new body") != quoted_text
    assert merge_managed_block(split_text, "new body") == split_text
    assert _HOLDS not in unlisted[quoted]
    assert _HOLDS in unlisted[split]
    assert _EXAMPLE_HOLDS not in unlisted[split]
    for text in recorded.values():
        assert f"{_HOLDS} {_EXAMPLE_HOLDS}" in text
