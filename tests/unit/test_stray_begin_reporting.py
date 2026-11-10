# SPDX-License-Identifier: MIT

"""verify and doctor name the file a stray Apothem BEGIN marker fails them in.

A BEGIN marker that starts no whole block (its END marker is gone) fails verify
for the tool whose managed-block file holds it, and install and update keep it,
so re-running them does not help. A failed verify row and doctor's failed check
name each such file and say to delete the marker line; the plain verify line
then leaves out the adapter's output path, which can be another file. Only the
files a tool's install keeps a block in count: a project's own CLAUDE.md does
not fail a project-scope tool's verify.
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
from apothem.harnesses._shared.install_driver_written import (
    stray_begin_files,
    stray_begin_install_warnings,
)
from apothem.lib import install_ledger
from apothem.lib.harness_materializer import APOTHEM_BLOCK_BEGIN, APOTHEM_BLOCK_END
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
