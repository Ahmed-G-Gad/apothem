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
from apothem.lib.harness_registry import HARNESS_REGISTRY, HarnessRegistryEntry
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
