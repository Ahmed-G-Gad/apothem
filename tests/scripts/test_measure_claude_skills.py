# SPDX-License-Identifier: MIT

"""scripts/dev/measure_claude_skills.py reports the real emission."""

from __future__ import annotations

import dataclasses
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

from apothem.harnesses._shared import install_driver
from apothem.lib.plugin_tree import assemble_plugin_tree

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT = _REPO_ROOT / "scripts" / "dev" / "measure_claude_skills.py"

_spec = importlib.util.spec_from_file_location("measure_claude_skills", _SCRIPT)
assert _spec is not None
assert _spec.loader is not None
measure_mod: ModuleType = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = measure_mod  # dataclasses resolves its module here
_spec.loader.exec_module(measure_mod)


@pytest.fixture(scope="module")
def plugin_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return assemble_plugin_tree(
        _REPO_ROOT / "src" / "apothem",
        tmp_path_factory.mktemp("plugin") / "claude-code",
    )


@pytest.fixture(scope="module")
def engine_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("home") / ".claude"
    install_driver.run_install("claude_code", harness_root=root)
    return root


def test_measure_covers_every_command_and_flags_the_shadowed_two() -> None:
    rows = measure_mod.measure()
    assert len(rows) == 45
    assert sorted(r.name for r in rows if r.shadowed) == ["projectify", "workflow"]
    assert [r.name for r in rows] == sorted(r.name for r in rows)


def test_numbers_equal_the_emitted_file_sizes(
    plugin_root: Path, engine_root: Path
) -> None:
    rows = [r for r in measure_mod.measure(install_root=engine_root) if not r.shadowed]
    assert len(rows) == 43
    for row in rows:
        plugin_dir = plugin_root / "skills" / row.name
        engine_dir = engine_root / "skills" / row.name
        assert (plugin_dir / "SKILL.md").stat().st_size == row.plugin_bytes, row.name
        assert (engine_dir / "SKILL.md").stat().st_size == row.engine_bytes, row.name
        references = sorted((plugin_dir / "references").glob("*.md"))
        assert len(references) == row.reference_count, row.name
        assert sum(p.stat().st_size for p in references) == row.reference_bytes, (
            row.name
        )
        assert (
            len([p for p in references if p.name.startswith("step-")]) == row.step_files
        )


def test_every_row_passes_its_own_invariants() -> None:
    for row in measure_mod.measure():
        assert row.restore_ok, row.name
        assert row.unfold_ok, row.name
        assert row.headroom_bytes == row.budget_bytes - row.plugin_bytes
        assert row.engine_bytes > row.plugin_bytes
        assert row.fits_cap == (row.engine_bytes <= measure_mod.SKILL_MD_CAP_BYTES)
        assert row.lines <= 500


def test_check_passes_on_the_committed_corpus(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert measure_mod.main(["--check"]) == 0
    out = capsys.readouterr().out
    assert "PROBLEM" not in out
    assert "research-suite" in out
    assert "PINNED" in out


def test_check_fails_when_the_cap_drops(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(measure_mod, "SKILL_MD_CAP_BYTES", 10_000)
    assert measure_mod.main(["--check"]) == 1
    assert "PROBLEM" in capsys.readouterr().out
    assert measure_mod.main([]) == 0


def test_json_output_has_the_documented_schema(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert measure_mod.main(["--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert set(payload) == {
        "cap_bytes",
        "budget_bytes",
        "note_reserve_bytes",
        "install_root",
        "bytes_per_token",
        "commands",
        "native_skills",
        "problems",
    }
    assert payload["install_root"] == "/home/user/.claude"
    assert payload["problems"] == []
    assert len(payload["commands"]) == 45
    row_fields = {f.name for f in dataclasses.fields(measure_mod.Row)}
    assert all(set(row) == row_fields for row in payload["commands"])
    pinned = [n for n in payload["native_skills"] if n["ceiling"] is not None]
    assert [n["name"] for n in pinned] == ["research-suite"]


def test_cap_flag_resplits_at_the_given_budget(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert measure_mod.main(["--json", "--cap", "13000"]) in {0, 1}
    payload = json.loads(capsys.readouterr().out)
    assert payload["cap_bytes"] == 13_000
    assert payload["budget_bytes"] == 13_000 - payload["note_reserve_bytes"]
    default = {r.name: r for r in measure_mod.measure()}
    tighter = {c["name"]: c for c in payload["commands"]}
    assert tighter["plan-execute"]["step_files"] >= default["plan-execute"].step_files
    assert (
        tighter["plan-execute"]["plugin_bytes"] <= default["plan-execute"].plugin_bytes
    )
