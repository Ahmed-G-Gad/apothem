# SPDX-License-Identifier: MIT

"""Lifecycle acceptance matrix over every registered adapter, driven by the CLI.

For each of the registered harnesses, on a clean HOME (and a clean project
directory for project-scope harnesses):

* ``install`` then ``uninstall`` leaves HOME and the project exactly as they
  were: no file and no empty directory the install created remains;
* ``install`` then ``rollback`` of that install does the same.

The install ledger and the backup root live outside HOME (the suite-wide
autouse fixtures redirect them), so the snapshots compare only what the
harness itself sees.
"""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from click.testing import CliRunner

from apothem.cli import main
from apothem.harnesses._shared import install_driver
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


def _snapshot(*roots: Path) -> dict[str, str]:
    """Map every path under *roots* to a content hash (``dir`` for directories)."""
    state: dict[str, str] = {}
    for root in roots:
        for path in sorted(root.rglob("*")):
            key = f"{root.name}/{path.relative_to(root)}"
            state[key] = (
                "dir"
                if path.is_dir()
                else hashlib.sha256(path.read_bytes()).hexdigest()
            )
    return state


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

    def run(self, *args: str) -> dict[str, Any]:
        result = CliRunner().invoke(
            main, [*args, "--harness", self.entry.public_id, *self.scope(), "--json"]
        )
        assert result.exit_code == 0, result.output
        payload: dict[str, Any] = json.loads(result.output)
        return payload

    def install(self, *extra: str) -> dict[str, Any]:
        return self.run("install", "--profile", str(profile_minimal_path()), *extra)

    def snapshot(self) -> dict[str, str]:
        return _snapshot(self.home, self.project)


SandboxFactory = Callable[[str], "_Sandbox"]


@pytest.fixture
def sandbox_factory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> SandboxFactory:
    def make(harness_id: str) -> _Sandbox:
        entry = next(e for e in HARNESS_REGISTRY if e.public_id == harness_id)
        return _Sandbox(entry, tmp_path, monkeypatch)

    return make


@pytest.mark.parametrize("harness_id", _IDS)
def test_install_then_uninstall_restores_the_clean_state(
    harness_id: str, sandbox_factory: SandboxFactory
) -> None:
    sandbox = sandbox_factory(harness_id)
    before = sandbox.snapshot()

    sandbox.install()
    sandbox.run("uninstall", "--yes")

    after = sandbox.snapshot()
    assert after == before, sorted(set(after) ^ set(before))[:20]


@pytest.mark.parametrize("harness_id", _IDS)
def test_install_then_rollback_restores_the_clean_state(
    harness_id: str, sandbox_factory: SandboxFactory
) -> None:
    sandbox = sandbox_factory(harness_id)
    before = sandbox.snapshot()

    sandbox.install()
    sandbox.run("rollback", "--last", "--yes")

    after = sandbox.snapshot()
    assert after == before, sorted(set(after) ^ set(before))[:20]


def _norm(path: str) -> Path:
    return Path(os.path.normpath(path))


@pytest.mark.parametrize("harness_id", _IDS)
def test_dry_run_plans_every_path_the_install_writes(
    harness_id: str, sandbox_factory: SandboxFactory
) -> None:
    sandbox = sandbox_factory(harness_id)
    before = sandbox.snapshot()

    plan = sandbox.install("--dry-run")

    assert sandbox.snapshot() == before  # a dry run writes nothing
    planned = [
        _norm(str(result["path"]))
        for result in plan["results"]
        if result["outcome"] in {"created", "updated"}
    ]
    written = [_norm(path) for path in sandbox.install()["files_written"]]
    unplanned = [
        str(path)
        for path in written
        if not any(path == entry or entry in path.parents for entry in planned)
    ]
    assert not unplanned, unplanned[:10]


@pytest.mark.parametrize("harness_id", _IDS)
def test_diff_is_empty_and_reinstall_is_a_noop_after_install(
    harness_id: str, sandbox_factory: SandboxFactory
) -> None:
    sandbox = sandbox_factory(harness_id)
    sandbox.install()

    diff = sandbox.run("diff", "--profile", str(profile_minimal_path()))
    pending = [
        (result["operation"], result["path"])
        for result in diff["results"]
        if result["outcome"] not in {"unchanged", "warning"}
    ]
    assert not pending, pending[:10]

    backups_before = sorted(install_driver.BACKUP_ROOT.rglob("*"))
    again = sandbox.install()
    assert again["files_written"] == []
    assert sorted(install_driver.BACKUP_ROOT.rglob("*")) == backups_before


def _recorded_anchors(harness_id: str) -> list[Path]:
    """Return the managed-block files the latest install of *harness_id* wrote."""
    record = install_ledger.read_records(package_key_for_public_id(harness_id))[-1]
    anchors = [
        Path(target.path)
        for target in record.targets
        if target.mode == "sentinel_merge" and Path(target.path).is_file()
    ]
    if not anchors:
        pytest.skip(f"{harness_id} writes no managed block on a clean install")
    return anchors


def _verify(box: _Sandbox) -> int:
    result = CliRunner().invoke(
        main, ["verify", "--harness", box.entry.public_id, *box.scope(), "--json"]
    )
    return result.exit_code


@pytest.mark.parametrize("harness_id", _IDS)
def test_an_install_keeps_your_text_after_a_begin_with_no_end(
    harness_id: str, sandbox_factory: SandboxFactory
) -> None:
    """Install and update never cut the text after a BEGIN marker with no END.

    Each managed block the install wrote loses its END marker and gains a line
    of the operator's. A preview and the next install name each file; the
    install keeps every byte and writes one whole block of its own; verify
    fails until the stray marker goes.
    """
    box = sandbox_factory(harness_id)
    box.install()
    anchors = _recorded_anchors(harness_id)
    for anchor in anchors:
        text = anchor.read_text(encoding="utf-8").replace(APOTHEM_BLOCK_END, "")
        anchor.write_bytes((text + "my own line\n").encode())
    before = {anchor: anchor.read_bytes() for anchor in anchors}

    preview = box.install("--dry-run")
    payload = box.run("update", "--profile", str(profile_minimal_path()))
    again = box.install()
    status = CliRunner().invoke(
        main,
        ["status", *box.scope(), "--profile", str(profile_minimal_path()), "--json"],
    )
    damaged = _verify(box)
    after = {anchor: anchor.read_bytes() for anchor in anchors}
    for anchor in anchors:
        # Delete only the stray marker: the one outside the whole block.
        text = anchor.read_text(encoding="utf-8")
        block = complete_managed_block(text) or ""
        at = text.index(block)
        kept = [
            part.replace(APOTHEM_BLOCK_BEGIN, "")
            for part in (text[:at], text[at + len(block) :])
        ]
        anchor.write_bytes((kept[0] + block + kept[1]).encode())
    repaired = _verify(box)

    for anchor in anchors:
        stray = before[anchor][before[anchor].index(APOTHEM_BLOCK_BEGIN.encode()) :]
        assert stray in after[anchor]
        assert after[anchor].count(APOTHEM_BLOCK_END.encode()) == 1
    for envelope in (preview, payload):
        named = [
            str(w["message"])
            for w in envelope["warnings"]
            if APOTHEM_BLOCK_END in str(w["message"])
        ]
        assert len(named) == len(anchors), envelope["warnings"]
    assert again["files_written"] == []
    names = {harness_id, package_key_for_public_id(harness_id)}
    [row] = [r for r in json.loads(status.output)["results"] if r["harness"] in names]
    assert row["drift"] == "drift", row
    assert damaged != 0
    assert repaired == 0


@pytest.mark.parametrize("harness_id", _IDS)
def test_a_block_that_lost_its_end_marker_is_left_as_it_is(
    harness_id: str, sandbox_factory: SandboxFactory
) -> None:
    """Uninstall never removes text below a BEGIN marker that has no END.

    Each managed block the install wrote loses its END marker and gains a line
    of the operator's; the uninstall leaves each file byte for byte, names it
    in a warning, and the harness then reads as not installed.
    """
    box = sandbox_factory(harness_id)
    box.install()
    anchors = _recorded_anchors(harness_id)
    for anchor in anchors:
        text = anchor.read_text(encoding="utf-8").replace(APOTHEM_BLOCK_END, "")
        anchor.write_text(text + "my own line\n", encoding="utf-8")
    before = {anchor: anchor.read_bytes() for anchor in anchors}

    payload = box.run("uninstall", "--yes")
    again = box.run("uninstall", "--yes")

    assert {anchor: anchor.read_bytes() for anchor in anchors} == before
    named = [
        str(warning["message"])
        for warning in payload["warnings"]
        if APOTHEM_BLOCK_END in str(warning["message"])
    ]
    assert len(named) == len(anchors), payload["warnings"]
    for anchor in anchors:
        where = os.path.normcase(str(anchor))
        assert any(where in os.path.normcase(m) for m in named), (where, named)
    assert [result["outcome"] for result in again["results"]] == ["skipped"]


def _codex_anchor(box: _Sandbox) -> Path:
    box.install()
    return box.home / ".codex" / "AGENTS.md"


def test_a_block_without_its_end_counts_when_the_ledger_knows_nothing(
    sandbox_factory: SandboxFactory,
) -> None:
    """With no record at all (an install from before the ledger, a lost ledger),
    an END-less block still shows the install, so an uninstall runs instead of
    reporting the tool as not installed."""
    from apothem.harnesses.codex import CodexAdapter

    anchor = _codex_anchor(sandbox_factory("codex"))
    install_ledger.ledger_path("codex").unlink()
    anchor.write_bytes(anchor.read_bytes().replace(APOTHEM_BLOCK_END.encode(), b""))

    assert CodexAdapter().is_installed() is True


def test_a_non_utf8_byte_in_a_managed_anchor_does_not_break_is_installed(
    sandbox_factory: SandboxFactory,
) -> None:
    from apothem.harnesses.codex import CodexAdapter

    anchor = _codex_anchor(sandbox_factory("codex"))
    anchor.write_bytes(anchor.read_bytes() + b"\nmine \xff\n")

    assert CodexAdapter().is_installed() is True


def test_a_block_without_its_end_counts_when_the_ledger_cannot_be_read(
    sandbox_factory: SandboxFactory,
) -> None:
    from apothem.harnesses.codex import CodexAdapter

    anchor = _codex_anchor(sandbox_factory("codex"))
    # Bytes that are not UTF-8 make the ledger raise (a line that is not
    # JSON is only skipped).
    install_ledger.ledger_path("codex").write_bytes(b"\xff\xfe not utf-8\n")
    anchor.write_bytes(anchor.read_bytes().replace(APOTHEM_BLOCK_END.encode(), b""))

    assert CodexAdapter().is_installed() is True


def test_a_block_pasted_in_twice_is_taken_out_whole(
    sandbox_factory: SandboxFactory,
) -> None:
    from apothem.harnesses.codex import CodexAdapter

    box = sandbox_factory("codex")
    anchor = _codex_anchor(box)
    anchor.write_bytes(anchor.read_bytes() + b"\n" + anchor.read_bytes())

    box.run("uninstall", "--yes")

    assert APOTHEM_BLOCK_END.encode() not in (
        anchor.read_bytes() if anchor.exists() else b""
    )
    assert CodexAdapter().is_installed() is False


def test_status_reads_a_profile_anchor_with_a_non_utf8_byte(
    sandbox_factory: SandboxFactory,
) -> None:
    anchor = _codex_anchor(sandbox_factory("codex"))
    anchor.write_bytes(anchor.read_bytes() + b"\nmine \xff\n")

    result = CliRunner().invoke(
        main,
        [
            "status",
            "--profile",
            str(profile_minimal_path()),
            "--json",
        ],
    )

    payload = json.loads(result.output)
    assert payload["error"] is None, payload["error"]
    [row] = [r for r in payload["results"] if r.get("harness") == "codex"]
    assert row["drift"] != "error", row
