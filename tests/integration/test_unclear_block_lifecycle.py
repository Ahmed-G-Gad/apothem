# SPDX-License-Identifier: MIT

"""A recorded managed block that a code block of the operator's now holds.

For every adapter that writes a Markdown managed block, through the real CLI
on a clean HOME (and project): install, then put the block inside a code block
of the operator's that a later fence closes, as an operator who left a fence
open above it and added an example below would. No rule can say whether that
marker pair is Apothem's block or a quote of the operator's, so:

* a re-install changes no byte of the file, adds no second block, and names
  the file and the line of the code block in a warning;
* verify fails until the operator fixes the file;
* uninstall keeps every byte of the operator's text.

That holds only when the merge sees the file's install record, so a harness
whose record is kept under another root than the one the merge reads would
show up here as a second block. A stray BEGIN marker whose END marker is
quoted in code above the real block, and an anchor saved with CR line endings,
are run through the CLI the same way.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from click.testing import CliRunner

from apothem.cli import main
from apothem.lib import install_ledger
from apothem.lib.harness_materializer import (
    APOTHEM_BLOCK_BEGIN,
    APOTHEM_BLOCK_END,
    complete_managed_block,
)
from apothem.lib.harness_registry import (
    HARNESS_REGISTRY,
    HarnessRegistryEntry,
    package_key_for_public_id,
)
from apothem.schemas import profile_minimal_path

_IDS = [entry.public_id for entry in HARNESS_REGISTRY]
_PROFILE = str(profile_minimal_path())


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
        mp.delenv("OPENCLAW_WORKSPACE_DIR", raising=False)
        if entry.public_id == "open-claw":
            # A workspace OpenClaw has set up, so the install writes its rules
            # file there.
            workspace = self.home / ".openclaw" / "workspace"
            workspace.mkdir(parents=True)
            (workspace / "AGENTS.md").write_bytes(b"# My agent\n")
            (workspace / "SOUL.md").write_bytes(b"soul\n")

    def scope(self) -> list[str]:
        if self.entry.scope == "project":
            return ["--project", str(self.project)]
        return []

    def invoke(self, *args: str) -> tuple[int, str]:
        result = CliRunner().invoke(
            main, [*args, "--harness", self.entry.public_id, *self.scope()]
        )
        return result.exit_code, result.output

    def run(self, *args: str) -> dict[str, Any]:
        code, output = self.invoke(*args, "--json")
        assert code == 0, output
        payload: dict[str, Any] = json.loads(output)
        return payload

    def install(self) -> dict[str, Any]:
        return self.run("install", "--profile", _PROFILE)


SandboxFactory = Callable[[str], _Sandbox]


@pytest.fixture
def sandbox_factory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> SandboxFactory:
    def make(harness_id: str) -> _Sandbox:
        entry = next(e for e in HARNESS_REGISTRY if e.public_id == harness_id)
        return _Sandbox(entry, tmp_path, monkeypatch)

    return make


def _recorded_anchors(harness_id: str) -> list[Path]:
    """Return the managed-block files the latest install of *harness_id* wrote."""
    record = install_ledger.read_records(package_key_for_public_id(harness_id))[-1]
    anchors = [
        Path(target.path)
        for target in record.targets
        if target.mode == "sentinel_merge"
        and Path(target.path).suffix in {".md", ".mdc", ""}
        and Path(target.path).is_file()
    ]
    if not anchors:
        pytest.skip(f"{harness_id} writes no managed block on a clean install")
    return anchors


def _fence_around_the_block(anchor: Path, *, edit: bool) -> int:
    """Put *anchor*'s block in a code block the operator closes below it.

    With *edit*, a line inside the block is the operator's too, so the block no
    longer reads as the one an install writes: only the install record keeps
    the next install from adding a second block. Returns the 1-based line of
    the fence that opens the code block.
    """
    text = anchor.read_bytes().decode("utf-8")
    block = complete_managed_block(text)
    assert block is not None, text[:200]
    at = text.index(block)
    if edit:
        begin_end = at + len(APOTHEM_BLOCK_BEGIN) + 1
        text = text[:begin_end] + "a line I added\n" + text[begin_end:]
    head = text[:at] + "My notes:\n\n```\nmake test\n\n"
    tail = text[at:] + "\nMore examples:\n\n```sh\nls\n```\n"
    anchor.write_bytes((head + tail).encode("utf-8"))
    return head.count("\n") - 2


def _warnings_naming(payload: dict[str, Any], anchor: Path, line: int) -> list[str]:
    return [
        str(warning["message"])
        for warning in payload["warnings"]
        if anchor.name in str(warning["message"])
        and f"code block that opens at line {line}" in str(warning["message"])
    ]


@pytest.mark.parametrize(
    ("harness_id", "edit"),
    [
        *[(harness_id, True) for harness_id in _IDS],
        ("codex", False),
        ("claude-code", False),
    ],
)
def test_a_recorded_block_inside_an_operator_code_block_is_left_alone(
    harness_id: str, edit: bool, sandbox_factory: SandboxFactory
) -> None:
    box = sandbox_factory(harness_id)
    box.install()
    anchors = _recorded_anchors(harness_id)
    lines = {anchor: _fence_around_the_block(anchor, edit=edit) for anchor in anchors}
    before = {anchor: anchor.read_bytes() for anchor in anchors}

    again = box.install()
    after_install = {anchor: anchor.read_bytes() for anchor in anchors}
    verify, verify_output = box.invoke("verify", "--json")
    box.invoke("uninstall", "--yes", "--json")
    after_uninstall = {anchor: anchor.read_bytes() for anchor in anchors}

    assert after_install == before
    for anchor in anchors:
        assert after_install[anchor].count(APOTHEM_BLOCK_BEGIN.encode()) == 1
        assert _warnings_naming(again, anchor, lines[anchor]), again["warnings"]
    assert verify != 0, verify_output
    assert after_uninstall == before


@pytest.mark.parametrize("harness_id", ["codex", "claude-code"])
def test_a_stray_begin_whose_end_is_quoted_in_code_cuts_nothing(
    harness_id: str, sandbox_factory: SandboxFactory
) -> None:
    """residual-1: re-install and uninstall keep every line; verify fails."""
    box = sandbox_factory(harness_id)
    box.install()
    [anchor] = _recorded_anchors(harness_id)
    stray = (
        f"{APOTHEM_BLOCK_BEGIN}\nop text A\n```\n{APOTHEM_BLOCK_END}\n```\n"
        "op text B\n\n"
    ).encode()
    anchor.write_bytes(stray + anchor.read_bytes())
    before = anchor.read_bytes()

    again = box.install()
    after_install = anchor.read_bytes()
    verify, verify_output = box.invoke("verify", "--json")
    box.invoke("uninstall", "--yes", "--json")

    assert after_install == before
    assert _warnings_naming(again, anchor, 3), again["warnings"]
    assert verify != 0, verify_output
    assert anchor.read_bytes() == before


def test_an_anchor_saved_with_cr_endings_shows_no_drift(
    sandbox_factory: SandboxFactory,
) -> None:
    """cr-5: line endings do not count, CR alone included."""
    box = sandbox_factory("codex")
    box.install()
    [anchor] = _recorded_anchors("codex")
    anchor.write_bytes(
        anchor.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r")
    )

    code, output = box.invoke("verify", "--profile", _PROFILE)
    box.install()
    again, again_output = box.invoke("verify", "--profile", _PROFILE)

    assert code == 0, output
    assert again == 0, again_output
