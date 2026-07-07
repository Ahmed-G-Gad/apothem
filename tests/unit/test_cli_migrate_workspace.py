# SPDX-License-Identifier: MIT

"""CLI tests for ``apothem migrate-workspace``."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from apothem.cli import main
from apothem.lib.data_home import DataHome, resolve_shared_data_home
from apothem.lib.memory import MemoryRecord, MemoryStore


def _seed_legacy_home(base: Path, package_key: str) -> None:
    """Seed a legacy per-harness data home with one memory record."""
    root = base / ".apothem" / package_key
    home = DataHome(
        root=root,
        plans=root / "plans",
        memory=root / "memory",
        contexts=root / "contexts",
        learning=root / "learning",
    ).ensure()
    MemoryStore(home).add(
        MemoryRecord(
            id="rec-1",
            title="a fact",
            body="A durable fact.",
            kind="fact",
            created="2026-06-24T00:00:00Z",
        )
    )


def test_dry_run_detects_legacy_layout(runner: CliRunner, tmp_path: Path) -> None:
    _seed_legacy_home(tmp_path, "claude_code")

    result = runner.invoke(
        main,
        ["migrate-workspace", "--project", str(tmp_path), "--dry-run", "--json"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["legacy_layout_detected"] is True
    assert payload["dry_run"] is True
    # Dry-run writes nothing: the legacy home survives.
    assert (tmp_path / ".apothem" / "claude_code" / "memory").is_dir()


def test_migrate_collapses_into_shared_home(runner: CliRunner, tmp_path: Path) -> None:
    _seed_legacy_home(tmp_path, "claude_code")
    _seed_legacy_home(tmp_path, "zed")

    result = runner.invoke(
        main, ["migrate-workspace", "--project", str(tmp_path), "--json"]
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["status"] == "success"
    assert payload["migrated"] is True
    shared = resolve_shared_data_home(base=tmp_path)
    assert MemoryStore(shared).contains("rec-1")
    assert not (tmp_path / ".apothem" / "claude_code").exists()


def test_no_legacy_layout_is_clean_success(runner: CliRunner, tmp_path: Path) -> None:
    result = runner.invoke(
        main, ["migrate-workspace", "--project", str(tmp_path), "--json"]
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["status"] == "success"
    assert payload["migrated"] is False


def test_missing_project_root_is_expected_error(
    runner: CliRunner, tmp_path: Path
) -> None:
    result = runner.invoke(
        main,
        ["migrate-workspace", "--project", str(tmp_path / "absent"), "--json"],
    )

    assert result.exit_code != 0
