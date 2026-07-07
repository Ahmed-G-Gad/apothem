# SPDX-License-Identifier: MIT

"""Self-tests for the plan-suite-structure-grep validator.

The validator walks every ``<root>/.apothem/plans/<suite>/`` directory and asserts
the suite-locality, closed-vocabulary, numeric-prefix, and phase-coherence
invariants. These tests build minimal suite fixtures under ``tmp_path`` and
assert pass / fail per invariant, mirroring the standalone-grep test shape
used across ``tests/conformity/``.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Final

_REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[3]
_GREP_PATH: Final[Path] = (
    _REPO_ROOT / "src" / "apothem" / "conformity" / "plan_suite_structure_grep.py"
)


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "plan_suite_structure_grep", _GREP_PATH
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["plan_suite_structure_grep"] = module
    spec.loader.exec_module(module)
    return module


_MOD: Final[ModuleType] = _load()


def _make_conformant_suite(root: Path, name: str = "demo-suite") -> Path:
    """Build a minimal fully-conformant plan suite under ``root/.apothem/plans/``."""
    suite = root / ".apothem" / "plans" / name
    (suite / "_spec").mkdir(parents=True)
    (suite / "_spec" / "spec.md").write_text("# spec\n", encoding="utf-8")
    (suite / "_inputs").mkdir()
    (suite / "_inputs" / "forge.md").write_text("# forge\n", encoding="utf-8")
    (suite / "_inputs" / "review-findings.md").write_text("# notes\n", encoding="utf-8")
    (suite / "_outputs").mkdir()
    (suite / "_outputs" / "audit-report-2026-06-16.md").write_text(
        "# audit\n", encoding="utf-8"
    )
    (suite / "_outputs" / "i18n-gap.md").write_text("# gap\n", encoding="utf-8")
    phase = suite / "phases" / "01-discovery"
    phase.mkdir(parents=True)
    (phase / "PHASE.md").write_text("# phase\n", encoding="utf-8")
    (phase / "REPORT.md").write_text("# report\n", encoding="utf-8")
    # Suite-root singletons carry NO numeric prefix.
    (suite / "MASTER-PLAN.md").write_text("# plan\n", encoding="utf-8")
    (suite / "PROGRESS.md").write_text("# progress\n", encoding="utf-8")
    return suite


# --- Pass cases -------------------------------------------------------------


def test_no_plans_dir_passes_vacuously(tmp_path: Path) -> None:
    """A root carrying no .plans/ directory passes with zero suites."""
    (tmp_path / "src").mkdir()
    result = _MOD.check(tmp_path)
    assert result.passed is True
    assert result.findings == []
    assert result.suite_count == 0


def test_conformant_suite_passes(tmp_path: Path) -> None:
    """A fully-conformant suite returns passed=True with one suite counted."""
    _make_conformant_suite(tmp_path)
    result = _MOD.check(tmp_path)
    assert result.passed is True
    assert result.findings == []
    assert result.suite_count == 1


def test_subphase_folder_conformant_passes(tmp_path: Path) -> None:
    """A conformant NNL-subtopic sub-phase folder does not trip a finding."""
    suite = _make_conformant_suite(tmp_path)
    sub = suite / "phases" / "01-discovery" / "01A-subtopic"
    sub.mkdir()
    (sub / "PHASE.md").write_text("# sub\n", encoding="utf-8")
    result = _MOD.check(tmp_path)
    assert result.passed is True, [str(f) for f in result.findings]


def test_underscore_dir_outside_vocab_not_flagged(tmp_path: Path) -> None:
    """A working dir outside the closed vocab (e.g. _notes/) is NOT flagged."""
    suite = _make_conformant_suite(tmp_path)
    (suite / "_notes").mkdir()
    (suite / "_notes" / "scratch.md").write_text("# scratch\n", encoding="utf-8")
    result = _MOD.check(tmp_path)
    assert result.passed is True, [str(f) for f in result.findings]


# --- Suite-locality fail cases ----------------------------------------------


def test_artifact_dir_at_plans_root_fails(tmp_path: Path) -> None:
    """A _spec/ directly under .apothem/plans/ (not in a suite) is a finding."""
    _make_conformant_suite(tmp_path)
    (tmp_path / ".apothem" / "plans" / "_spec").mkdir()
    result = _MOD.check(tmp_path)
    assert result.passed is False
    issues = {f.issue for f in result.findings}
    assert "artifact-class directory at .apothem/plans root" in issues


def test_nested_artifact_dir_fails(tmp_path: Path) -> None:
    """A _spec/ nested inside a phase folder is a suite-locality violation."""
    suite = _make_conformant_suite(tmp_path)
    nested = suite / "phases" / "01-discovery" / "_spec"
    nested.mkdir()
    result = _MOD.check(tmp_path)
    assert result.passed is False
    issues = {f.issue for f in result.findings}
    assert "nested artifact-class directory" in issues


# --- Disjoint-vocabulary fail cases -----------------------------------------


def test_spec_md_in_inputs_fails(tmp_path: Path) -> None:
    """A spec.md inside _inputs/ is cross-vocabulary contamination."""
    suite = _make_conformant_suite(tmp_path)
    (suite / "_inputs" / "spec.md").write_text("# spec\n", encoding="utf-8")
    result = _MOD.check(tmp_path)
    assert result.passed is False
    detail = " ".join(f.detail for f in result.findings)
    assert "disjoint" in detail


def test_forge_md_in_spec_fails(tmp_path: Path) -> None:
    """A forge.md inside _spec/ is cross-vocabulary contamination."""
    suite = _make_conformant_suite(tmp_path)
    (suite / "_spec" / "forge.md").write_text("# forge\n", encoding="utf-8")
    result = _MOD.check(tmp_path)
    assert result.passed is False
    issues = {f.issue for f in result.findings}
    assert "purpose-vocabulary contamination" in issues


def test_non_singleton_spec_file_fails(tmp_path: Path) -> None:
    """A non-spec.md file at the _spec/ root is a finding."""
    suite = _make_conformant_suite(tmp_path)
    (suite / "_spec" / "extra.md").write_text("# extra\n", encoding="utf-8")
    result = _MOD.check(tmp_path)
    assert result.passed is False
    issues = {f.issue for f in result.findings}
    assert "non-singleton _spec file" in issues


def test_spec_allowed_subdir_passes(tmp_path: Path) -> None:
    """The allowed _spec/ subdirs (supporting/diagrams/citations) pass."""
    suite = _make_conformant_suite(tmp_path)
    (suite / "_spec" / "diagrams").mkdir()
    (suite / "_spec" / "diagrams" / "arch.md").write_text("d\n", encoding="utf-8")
    result = _MOD.check(tmp_path)
    assert result.passed is True, [str(f) for f in result.findings]


def test_spec_disallowed_subdir_fails(tmp_path: Path) -> None:
    """An out-of-vocab _spec/ subdirectory is a finding."""
    suite = _make_conformant_suite(tmp_path)
    (suite / "_spec" / "scratch").mkdir()
    result = _MOD.check(tmp_path)
    assert result.passed is False
    issues = {f.issue for f in result.findings}
    assert "non-vocab _spec subdirectory" in issues


# --- _outputs purpose fail cases --------------------------------------------


def test_outputs_kebab_topic_passes(tmp_path: Path) -> None:
    """A free-form kebab-topic _outputs/ filename is admitted."""
    suite = _make_conformant_suite(tmp_path)
    (suite / "_outputs" / "mcp-transport-map.md").write_text("m\n", encoding="utf-8")
    result = _MOD.check(tmp_path)
    assert result.passed is True, [str(f) for f in result.findings]


def test_outputs_non_kebab_name_fails(tmp_path: Path) -> None:
    """A non-kebab, non-purpose _outputs/ filename is a finding."""
    suite = _make_conformant_suite(tmp_path)
    (suite / "_outputs" / "Bad_Name.md").write_text("b\n", encoding="utf-8")
    result = _MOD.check(tmp_path)
    assert result.passed is False
    issues = {f.issue for f in result.findings}
    assert "non-vocab _outputs filename" in issues


# --- Numeric-prefix fail cases ----------------------------------------------


def test_phase_folder_without_prefix_fails(tmp_path: Path) -> None:
    """A phase folder not matching NN-topic is a finding."""
    suite = _make_conformant_suite(tmp_path)
    bad = suite / "phases" / "discovery"
    bad.mkdir()
    (bad / "PHASE.md").write_text("# p\n", encoding="utf-8")
    result = _MOD.check(tmp_path)
    assert result.passed is False
    issues = {f.issue for f in result.findings}
    assert "phase folder not NN-topic" in issues


def test_phase_missing_phase_md_fails(tmp_path: Path) -> None:
    """A phase folder with no PHASE.md is a phase-coherence finding."""
    suite = _make_conformant_suite(tmp_path)
    bare = suite / "phases" / "02-followup"
    bare.mkdir()
    (bare / "REPORT.md").write_text("# r\n", encoding="utf-8")
    result = _MOD.check(tmp_path)
    assert result.passed is False
    issues = {f.issue for f in result.findings}
    assert "phase missing PHASE.md" in issues


def test_subphase_folder_bad_shape_fails(tmp_path: Path) -> None:
    """A sub-phase folder not matching NNL-subtopic is a finding."""
    suite = _make_conformant_suite(tmp_path)
    bad_sub = suite / "phases" / "01-discovery" / "sub-a"
    bad_sub.mkdir()
    result = _MOD.check(tmp_path)
    assert result.passed is False
    issues = {f.issue for f in result.findings}
    assert "sub-phase folder not NNL-subtopic" in issues


def test_decorative_root_prefix_fails(tmp_path: Path) -> None:
    """A lone NN-prefixed suite-root file (no NN- sibling) is a finding."""
    suite = _make_conformant_suite(tmp_path)
    (suite / "00-overview.md").write_text("# overview\n", encoding="utf-8")
    result = _MOD.check(tmp_path)
    assert result.passed is False
    issues = {f.issue for f in result.findings}
    assert "decorative numeric prefix on suite-root file" in issues


def test_root_prefix_with_sibling_sequence_passes(tmp_path: Path) -> None:
    """Two NN-prefixed root files sharing a topic tail form a sequence (no finding)."""
    suite = _make_conformant_suite(tmp_path)
    (suite / "01-step.md").write_text("a\n", encoding="utf-8")
    (suite / "02-step.md").write_text("b\n", encoding="utf-8")
    result = _MOD.check(tmp_path)
    # The sequence is allowed; no decorative-prefix finding.
    issues = {f.issue for f in result.findings}
    assert "decorative numeric prefix on suite-root file" not in issues


# --- CLI entry-point cases --------------------------------------------------


def test_main_cli_returns_exit_zero_on_pass(tmp_path: Path) -> None:
    """The CLI entry point returns EXIT_PASS (0) on a conformant suite."""
    _make_conformant_suite(tmp_path)
    rc = _MOD._main([str(_GREP_PATH), str(tmp_path)])
    assert rc == _MOD.EXIT_PASS


def test_main_cli_returns_exit_two_on_findings(tmp_path: Path) -> None:
    """The CLI entry point returns EXIT_FAIL (2) on a structural violation."""
    suite = _make_conformant_suite(tmp_path)
    (suite / "_inputs" / "spec.md").write_text("# spec\n", encoding="utf-8")
    rc = _MOD._main([str(_GREP_PATH), str(tmp_path)])
    assert rc == _MOD.EXIT_FAIL
