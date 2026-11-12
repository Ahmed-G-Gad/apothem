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
the lines of its markers and where they read, and a fix for each case that
says what follows from it. Install gives that text only when the merge left
the file as it is, and a recorded file in that state still counts as an
install.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from click.testing import CliRunner

import apothem
from apothem.cli import main
from apothem.cli._stray_begin_report import stray_begin_note
from apothem.harnesses._shared import install_driver
from apothem.harnesses._shared import install_driver_blocks as blocks
from apothem.harnesses._shared.install_driver_blocks import (
    stray_begin_files,
    stray_begin_install_warnings,
)
from apothem.harnesses._shared.install_driver_evidence import _carries_managed_block
from apothem.lib import install_ledger
from apothem.lib.harness_materializer import (
    APOTHEM_BLOCK_BEGIN,
    APOTHEM_BLOCK_END,
    wrap_managed_block,
)
from apothem.lib.harness_registry import HARNESS_REGISTRY, HarnessRegistryEntry
from apothem.lib.install_ledger import LedgerRecord, LedgerTarget
from apothem.schemas import profile_minimal_path


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
    assert "delete that marker line" in row["message"]
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
    assert "delete that marker line" in note


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
    assert "delete that marker line" in check["fix"]
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


def test_the_install_warning_says_to_delete_the_marker_and_the_old_text(
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
    assert "Delete that marker line by hand" in warning.message
    assert "the old Apothem text below it" in warning.message
    assert "keep your own lines" in warning.message


def test_the_note_names_every_file() -> None:
    files = [Path("one.md"), Path("two.md"), Path("three.md")]

    note = stray_begin_note(files, then="run apothem verify again")

    assert note.startswith("one.md, two.md and three.md each have")
    assert note.endswith("then run apothem verify again")


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


def _flat(text: str) -> str:
    return " ".join(text.split())


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
    """docs-1, cmark-3, diff-3, oracle-2: the example is not the only pair named."""
    target, [message] = _held(tmp_path, _EXAMPLE_ABOVE)

    assert message.startswith(
        f"{target}: Apothem cannot tell whether the marker lines in this file "
        "mark its block or text of yours, so it left the file as it is."
    )
    for begin, end, fence in ((4, 6, 3), (14, 16, 11)):
        assert (
            f"The BEGIN marker at line {begin} and the END marker at line {end} sit "
            f"inside a code block that opens at line {fence}. If lines {begin} to "
            f"{end} are Apothem's block, close that code block above line {begin}: "
            "the next update then replaces those lines. If they are text of yours, "
            "change or delete those two marker lines."
        ) in message
    assert message.endswith(
        "Then run apothem update again. apothem verify fails for this tool until "
        "you fix the file."
    )


def test_the_rule_3_warning_names_the_begin_and_the_later_pair(
    tmp_path: Path,
) -> None:
    """lifecycle-3, tests-6, oracle-2: no unconditional fix that cuts your text."""
    _, [message] = _held(tmp_path, _RESIDUAL)

    assert (
        "The BEGIN marker at line 1 is outside code, but its END marker at line 4 "
        "sits inside a code block that opens at line 3, and the marker pair from "
        "line 8 to line 10 comes after them: that pair may be Apothem's block."
    ) in message
    assert (
        "If the BEGIN marker at line 1 is yours, delete or change it: the next "
        "update then replaces lines 8 to 10."
    ) in message
    assert (
        "If lines 1 to 4 are Apothem's block, the code block that opens at line 3 "
        "comes from a rule in your profile: close it above line 4 and fix that "
        "rule; the next update then replaces those lines."
    ) in message
    assert "close that code block above the END marker" not in message


@pytest.mark.parametrize(
    ("text", "where", "fix"),
    [
        pytest.param(
            f"Start marker:\n```\n{B}\n```\nEnd marker:\n```\n{E}\n```\n",
            "The BEGIN marker at line 3 sits inside a code block that opens at line "
            "2, and the END marker at line 7 sits inside a code block that opens at "
            "line 6.",
            "If lines 3 to 7 are Apothem's block, delete them by hand, keeping your "
            "own text.",
            id="two-code-blocks",
        ),
        pytest.param(
            f"Intro\n\n    {B}\n    old\n    {E}\n",
            "The BEGIN marker at line 3 and the END marker at line 5 sit in indented "
            "code.",
            "If lines 3 to 5 are Apothem's block, start lines 3 and 5 at the left "
            "margin: the next update then replaces those lines.",
            id="indented",
        ),
        pytest.param(
            f"Example of the markers:\n    {B}\n    quoted\n    {E}\n",
            "The BEGIN marker at line 2 and the END marker at line 4 read as part of "
            "the paragraph above them.",
            "If lines 2 to 4 are Apothem's block, start lines 2 and 4 at the left "
            "margin: the next update then replaces those lines.",
            id="paragraph",
        ),
        pytest.param(
            f"{B}\n    {E}\n\n{OLD}",
            "The BEGIN marker at line 1 is outside code, but its END marker at line "
            "2 sits in indented code, and the marker pair from line 4 to line 6 "
            "comes after them: that pair may be Apothem's block.",
            "If lines 1 to 2 are Apothem's block, start line 2 at the left margin: "
            "the next update then replaces those lines.",
            id="rule-3-indented-end",
        ),
    ],
)
def test_each_shape_gets_its_own_place_and_fix(
    tmp_path: Path, text: str, where: str, fix: str
) -> None:
    """docs-4, oracle-4, diff-6, tests-7: no shape is called indented code wrongly."""
    _, [message] = _held(tmp_path, text)

    assert where in message
    assert fix in message


def test_the_uninstall_warning_says_to_delete_whichever_pair_is_apothems(
    tmp_path: Path,
) -> None:
    """docs-1: every pair is named, so the operator can find Apothem's block."""
    target = tmp_path / "AGENTS.md"
    target.write_bytes(_EXAMPLE_ABOVE.encode())

    warning = blocks.unclear_block_warning(target, "surgical_uninstall")

    assert warning is not None
    assert warning.detail == {"kept_reason": "unclear-block", "marker_left": "1"}
    assert warning.message.endswith(
        "If one of these pairs is Apothem's block (lines 4 to 6, or lines 14 to "
        "16), delete it by hand, keeping your own text."
    )
    assert "sit inside a code block that opens at line 11" in warning.message


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
    assert "If lines 14 to 16 are Apothem's block" in note
    assert note.endswith(" Then run apothem update and apothem verify again")


@pytest.mark.parametrize(
    ("outcome", "warned"), [("updated", False), ("created", False), ("unchanged", True)]
)
def test_the_unclear_warning_follows_what_the_merge_did(
    tmp_path: Path, outcome: str, warned: bool
) -> None:
    """wiring-5, diff-2: only a file the merge left as it is gets the warning."""
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

    warnings = stray_begin_install_warnings([result])

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
    box.install()

    code, output = box.invoke("verify", "--json")
    result = CliRunner().invoke(main, ["doctor", "--json"])

    assert code == 1, output
    payload = json.loads(output)
    assert payload["installed"] is True
    [row] = payload["results"]
    note = row["stray_begin"]["message"]
    assert (
        f"The BEGIN marker at line {begin} and the END marker at line {end} sit "
        f"inside a code block that opens at line {fence}."
    ) in note
    assert f"If lines {begin} to {end} are Apothem's block" in note
    assert result.exit_code == 1, result.output
    [check] = [c for c in json.loads(result.output)["checks"] if c["status"] == "fail"]
    assert check["code"] == "harness.stray_begin"
    assert check["message"] == (
        "codex is installed but does not verify: a file holds Apothem markers to "
        "fix by hand."
    )
    assert _names(check["fix"], anchor)
    assert f"close that code block above line {begin}" in check["fix"]


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
