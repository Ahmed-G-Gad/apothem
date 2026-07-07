# SPDX-License-Identifier: MIT

"""Self-tests for the plans-discipline-language-grep validator."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Final

_REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[3]
_GREP_PATH: Final[Path] = (
    _REPO_ROOT / "src" / "apothem" / "conformity" / "plans_discipline_language_grep.py"
)


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "plans_discipline_language_grep", _GREP_PATH
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["plans_discipline_language_grep"] = module
    spec.loader.exec_module(module)
    return module


_MOD: Final[ModuleType] = _load()

_FIXTURE_TEXT = (
    "Planning artifacts are written to <project-root>/.plans/, "
    "never to any harness configuration directory (for example ~/.codex/ "
    "or ~/.claude/) and never to a global location. "
    "This rule is non-negotiable; cite §3 of the project spec on "
    "every related decision."
)


def _scaffold(root: Path, *, fixture: bool = True) -> None:
    """Create the canonical surface tree under root."""
    fixture_dir = root / "tests" / "fixtures"
    fixture_dir.mkdir(parents=True, exist_ok=True)
    if fixture:
        (fixture_dir / "plans-discipline.txt").write_text(
            _FIXTURE_TEXT, encoding="utf-8"
        )
    (root / "output-styles").mkdir(parents=True, exist_ok=True)
    (root / ".github").mkdir(parents=True, exist_ok=True)


def test_all_surfaces_byte_exact_passes(tmp_path: Path) -> None:
    _scaffold(tmp_path)
    for surface in _MOD.REQUIRED_SURFACES:
        target = tmp_path / surface
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(f"# header\n\n{_FIXTURE_TEXT}\n", encoding="utf-8")
    result = _MOD.check(tmp_path)
    assert result.passed is True
    assert result.fixture_present is True
    assert all(s.mode == "byte-exact" for s in result.surfaces)


def test_paraphrase_passes_above_floor(tmp_path: Path) -> None:
    """A paraphrase that hits the canonical token set above the floor admits."""
    _scaffold(tmp_path)
    paraphrase = (
        "Plans live at <project-root>/.plans/ and never at ~/.claude/.plans/; "
        "writing to a global location violates the Plans Discipline."
    )
    for surface in _MOD.REQUIRED_SURFACES:
        target = tmp_path / surface
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(paraphrase, encoding="utf-8")
    result = _MOD.check(tmp_path)
    assert result.passed is True
    assert all(s.mode == "paraphrase" for s in result.surfaces)
    assert all(s.coverage >= _MOD.COVERAGE_FLOOR for s in result.surfaces)


def test_missing_surface_is_finding(tmp_path: Path) -> None:
    """A surface file absent at its canonical path is a finding."""
    _scaffold(tmp_path)
    # Author the core surfaces but skip copilot-instructions.
    for surface in ("AGENTS.md", "CLAUDE.md", "src/apothem/output-styles/default.md"):
        target = tmp_path / surface
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(_FIXTURE_TEXT, encoding="utf-8")
    result = _MOD.check(tmp_path)
    assert result.passed is False
    absent = [
        f for f in result.findings if f.surface == ".github/copilot-instructions.md"
    ]
    assert len(absent) == 1
    assert "absent" in absent[0].detail


def test_below_floor_paraphrase_is_finding(tmp_path: Path) -> None:
    """A surface mentioning .plans/ once but missing other tokens fails."""
    _scaffold(tmp_path)
    weak_text = "Plans go somewhere; we'll figure it out later.\n"
    for surface in _MOD.REQUIRED_SURFACES:
        target = tmp_path / surface
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(weak_text, encoding="utf-8")
    result = _MOD.check(tmp_path)
    assert result.passed is False
    assert len(result.findings) == 4
    assert all(f.coverage < _MOD.COVERAGE_FLOOR for f in result.findings)


def test_missing_fixture_is_finding(tmp_path: Path) -> None:
    """When the fixture file itself is absent, byte-exact admission is
    disabled and a finding records the absence."""
    _scaffold(tmp_path, fixture=False)
    for surface in _MOD.REQUIRED_SURFACES:
        target = tmp_path / surface
        target.parent.mkdir(parents=True, exist_ok=True)
        # Author paraphrase that still admits via tokens.
        target.write_text(
            "<project-root>/.plans/ ~/.codex/ ~/.claude/.plans/ never global Plans Discipline",
            encoding="utf-8",
        )
    result = _MOD.check(tmp_path)
    assert result.passed is False
    assert result.fixture_present is False
    fixture_findings = [f for f in result.findings if f.surface == _MOD.FIXTURE_PATH]
    assert len(fixture_findings) == 1


def test_main_cli_returns_exit_zero_on_pass(tmp_path: Path) -> None:
    _scaffold(tmp_path)
    for surface in _MOD.REQUIRED_SURFACES:
        target = tmp_path / surface
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(_FIXTURE_TEXT, encoding="utf-8")
    rc = _MOD._main([str(_GREP_PATH), str(tmp_path)])
    assert rc == _MOD.EXIT_PASS


def test_main_cli_returns_exit_two_on_findings(tmp_path: Path) -> None:
    _scaffold(tmp_path, fixture=False)
    rc = _MOD._main([str(_GREP_PATH), str(tmp_path)])
    assert rc == _MOD.EXIT_FAIL
