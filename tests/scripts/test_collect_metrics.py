# SPDX-License-Identifier: MIT

"""Unit tests for the CI metrics collector, ``scripts/dev/collect_metrics.py``.

The collector writes the per-commit metrics artifact: line + branch coverage per
package with floors, the always-on instruction bytes each harness loads at
launch after an isolated install, CLI cold start, and end-to-end hook latency.
The tests pin the parts whose mistakes would be silent: the coverage arithmetic
and package attribution, the floor check, each harness's launch-surface rule
(which files count, which do not), the mapping of hook-benchmark results to
values or recorded null reasons, and the artifact's key set.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPTS_DEV = _REPO_ROOT / "scripts" / "dev"
if str(_SCRIPTS_DEV) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DEV))

import collect_metrics as cm  # noqa: E402

from apothem.lib.harness_registry import SUPPORTED_HARNESS_IDS  # noqa: E402

# The collector reads pyproject.toml with the stdlib TOML reader (3.11+); the
# CI metrics job runs on 3.12. The pure helpers below run on every Python.
_needs_tomllib = pytest.mark.skipif(
    sys.version_info < (3, 11), reason="tomllib is stdlib from Python 3.11"
)


def _write(root: Path, files: dict[str, str]) -> None:
    for rel, text in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text.encode("utf-8"))


def _size(text: str) -> int:
    return len(text.encode("utf-8"))


# --------------------------------------------------------------------------
# Coverage per package
# --------------------------------------------------------------------------


def _summary(lines: int, covered: int, branches: int, covered_branches: int) -> dict:
    return {
        "summary": {
            "num_statements": lines,
            "covered_lines": covered,
            "num_branches": branches,
            "covered_branches": covered_branches,
        }
    }


def test_coverage_per_package_uses_lines_plus_branches() -> None:
    report = {
        "files": {
            "src/apothem/cli/main.py": _summary(80, 70, 20, 10),
            "src/apothem/lib/x.py": _summary(20, 20, 0, 0),
            "src/apothem/conformity/gate.py": _summary(50, 40, 10, 5),
            "src/apothem/audit/scan.py": _summary(10, 1, 0, 0),
            "src/apothem/benchmarks/bench_hooks.py": _summary(10, 0, 0, 0),
        }
    }
    packages = {
        "engine": ("src/apothem/cli", "src/apothem/lib"),
        "conformity": ("src/apothem/conformity",),
        "audit": ("src/apothem/audit",),
    }

    result = cm.coverage_by_package(report, packages)

    assert result == {
        "engine": round(100 * (70 + 10 + 20) / (80 + 20 + 20), 2),
        "conformity": round(100 * (40 + 5) / (50 + 10), 2),
        "audit": 10.0,
    }


def test_statement_only_coverage_ignores_branches() -> None:
    report = {"files": {"src/apothem/audit/a.py": _summary(10, 8, 10, 0)}}
    packages = {"audit": ("src/apothem/audit",)}

    assert cm.coverage_by_package(report, packages) == {"audit": 40.0}
    assert cm.coverage_by_package(report, packages, branches=False) == {"audit": 80.0}


def test_coverage_accepts_absolute_and_windows_paths() -> None:
    report = {"files": {"C:\\w\\src\\apothem\\audit\\a.py": _summary(4, 2, 0, 0)}}
    assert cm.coverage_by_package(report, {"audit": ("src/apothem/audit",)}) == {
        "audit": 50.0
    }


def test_package_with_no_measured_files_is_none() -> None:
    assert cm.coverage_by_package({"files": {}}, {"audit": ("src/apothem/audit",)}) == {
        "audit": None
    }


@_needs_tomllib
def test_floors_come_from_pyproject() -> None:
    packages, floors = cm.coverage_config(_REPO_ROOT / "pyproject.toml")

    assert set(packages) == {"engine", "conformity", "audit"}
    assert "src/apothem/cli" in packages["engine"]
    assert packages["conformity"] == ("src/apothem/conformity",)
    assert floors["engine"] == 80
    assert set(floors) == {"engine", "conformity", "audit"}


def test_floor_violations_name_the_package() -> None:
    violations = cm.floor_violations(
        {"engine": 90.0, "conformity": 83.9, "audit": None},
        {"engine": 80, "conformity": 84, "audit": 73},
    )
    assert violations == ["conformity 83.9 < floor 84", "audit not measured (floor 73)"]


# --------------------------------------------------------------------------
# Always-on launch surfaces
# --------------------------------------------------------------------------


def test_every_registered_harness_has_a_documented_rule() -> None:
    assert set(cm.LAUNCH_SURFACES) == set(SUPPORTED_HARNESS_IDS)
    for harness, (rule, _surfaces) in cm.LAUNCH_SURFACES.items():
        assert rule.strip(), harness


def test_claude_code_counts_unscoped_rules_and_claude_md(tmp_path: Path) -> None:
    home, project = tmp_path / "home", tmp_path / "project"
    always = '---\nname: "a"\nalwaysApply: true\n---\nbody\n'
    scoped = '---\nname: "b"\npaths:\n  - "src/**"\n---\nbody\n'
    _write(
        home,
        {
            ".claude/CLAUDE.md": "managed block\n",
            ".claude/rules/a.md": always,
            ".claude/rules/b.md": scoped,
            ".claude/skills/x/SKILL.md": "not loaded in full\n",
        },
    )
    project.mkdir()

    size, files = cm.measure_surfaces("claude-code", home, project)

    assert files == 2
    assert size == _size("managed block\n") + _size(always)


def test_cursor_counts_always_apply_rules_only(tmp_path: Path) -> None:
    home, project = tmp_path / "home", tmp_path / "project"
    on = "<!-- BEGIN -->\n---\nalwaysApply: true\n---\nbody\n"
    off = "---\nalwaysApply: false\nglobs: '*.py'\n---\nbody\n"
    _write(project, {".cursor/rules/on.mdc": on, ".cursor/rules/off.mdc": off})
    home.mkdir()

    assert cm.measure_surfaces("cursor", home, project) == (_size(on), 1)


def test_zed_reads_only_the_first_matching_instruction_file(tmp_path: Path) -> None:
    home, project = tmp_path / "home", tmp_path / "project"
    _write(project, {".rules": "first\n", "AGENTS.md": "shadowed\n"})
    home.mkdir()

    assert cm.measure_surfaces("zed", home, project) == (_size("first\n"), 1)


def test_opencode_resolves_instruction_globs(tmp_path: Path) -> None:
    home, project = tmp_path / "home", tmp_path / "project"
    config = {"instructions": ["~/.config/opencode/support/rules/*.md"]}
    _write(
        home,
        {
            ".config/opencode/opencode.json": json.dumps(config),
            ".config/opencode/support/rules/a.md": "aaaa\n",
            ".config/opencode/support/rules/b.md": "bb\n",
            ".config/opencode/support/other.md": "not matched\n",
        },
    )
    project.mkdir()

    assert cm.measure_surfaces("opencode", home, project) == (_size("aaaa\nbb\n"), 2)


def test_qwen_uses_the_configured_context_file_name(tmp_path: Path) -> None:
    home, project = tmp_path / "home", tmp_path / "project"
    _write(
        home,
        {
            ".qwen/settings.json": json.dumps({"context": {"fileName": ["CTX.md"]}}),
            ".qwen/CTX.md": "context\n",
            ".qwen/QWEN.md": "not the configured name\n",
        },
    )
    project.mkdir()

    assert cm.measure_surfaces("qwen-code", home, project) == (_size("context\n"), 1)


def test_unloaded_support_trees_count_zero(tmp_path: Path) -> None:
    home, project = tmp_path / "home", tmp_path / "project"
    _write(home, {".hermes/apothem/rules/00-apothem-profile.md": "profile rule\n"})
    project.mkdir()

    assert cm.measure_surfaces("hermes", home, project) == (0, 0)


# --------------------------------------------------------------------------
# Hook latency mapping
# --------------------------------------------------------------------------


def test_hook_results_map_to_values_or_null_reasons() -> None:
    report = {
        "chains": {
            "PreToolUse:Write": {
                "status": "pass",
                "median_sum_ms": 412.5,
                "injected_chars": 7779,
                "detail": "ok",
            },
            "Stop": {
                "status": "error",
                "median_sum_ms": None,
                "injected_chars": None,
                "detail": "exit 126 (not executable) running as registered",
            },
        }
    }
    nulls: dict[str, str] = {}

    latency, injected = cm.hook_metrics(report, nulls)

    assert latency == {"PreToolUse:Write": 412.5, "Stop": None}
    assert injected == {"PreToolUse:Write": 7779, "Stop": None}
    assert nulls == {
        "hook_e2e_ms.Stop": "exit 126 (not executable) running as registered"
    }


# --------------------------------------------------------------------------
# The artifact
# --------------------------------------------------------------------------


@_needs_tomllib
@pytest.mark.skipif(sys.platform == "win32", reason="isolated POSIX install run")
def test_artifact_carries_every_key_with_a_value_or_a_reason(tmp_path: Path) -> None:
    out = tmp_path / "metrics.json"

    code = cm.main(
        ["--harness", "cursor", "--skip-hooks", "--skip-coldstart", "--out", str(out)]
    )

    assert code == 0
    metrics = json.loads(out.read_text(encoding="utf-8"))
    assert metrics["schema_version"] == 1
    assert set(metrics["coverage"]) == {"engine", "conformity", "audit"}
    assert set(metrics["coverage_lines"]) == {"engine", "conformity", "audit"}
    assert set(metrics["always_on_bytes"]) == set(SUPPORTED_HARNESS_IDS)
    assert metrics["always_on_bytes"]["cursor"] > 0
    assert metrics["always_on_files"]["cursor"] == 1
    assert metrics["always_on_bytes"]["codex"] is None
    assert "always_on_bytes.codex" in metrics["nulls"]
    assert metrics["cli_coldstart_ms"] is None
    assert "cli_coldstart_ms" in metrics["nulls"]
    assert metrics["hook_e2e_ms"] == {}
    assert "hook_e2e_ms" in metrics["nulls"]
    assert "coverage.engine" in metrics["nulls"]
    assert set(metrics["rules"]["always_on_bytes"]) == set(SUPPORTED_HARNESS_IDS)
