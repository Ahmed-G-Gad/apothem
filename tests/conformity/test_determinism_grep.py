# SPDX-License-Identifier: MIT

"""Unit tests for the determinism-grep output-shape harness.

These tests exercise the harness against committed fixtures: a
conformant `pass.md` whose structural signature is stable and whose
output shape is complete, and a deliberately perturbed `fail.md` whose
terminal next-step block has been removed. The perturbed fixture must
fail the harness — the regression guarantee task the harness exists for.
"""

from __future__ import annotations

from pathlib import Path

from apothem.conformity import determinism_grep as dg

_FIXTURES = Path(__file__).resolve().parent / "determinism-grep"
_PASS = _FIXTURES / "pass.md"
_FAIL = _FIXTURES / "fail.md"


def test_signature_is_stable_across_repeated_reads() -> None:
    """Identical input yields an identical signature on every recomputation."""
    body = _PASS.read_text(encoding="utf-8")
    signatures = {dg._signature(body) for _ in range(dg.RECOMPUTE_RUNS)}
    assert len(signatures) == 1


def test_pass_fixture_has_complete_deterministic_shape() -> None:
    """The conformant fixture produces zero findings."""
    findings = dg._classify_surface(_PASS)
    assert findings == [], [str(f) for f in findings]


def test_fail_fixture_missing_next_step_is_flagged() -> None:
    """The perturbed fixture fails with an incomplete-shape finding."""
    findings = dg._classify_surface(_FAIL)
    kinds = {f.kind for f in findings}
    assert "incomplete-shape" in kinds
    details = " ".join(f.detail for f in findings)
    assert "next step" in details.lower()


def test_pass_fixture_shape_dimensions() -> None:
    """The structural shape captures the expected output-shape dimensions."""
    shape = dg._structural_shape(_PASS.read_text(encoding="utf-8"))
    assert shape["spdx"] is True
    assert shape["nextstep_form"] == "singular"
    assert shape["recommended_postfix_count"] >= 1
    assert "Recommended Next Step" in shape["h2_sequence"]


def test_check_passes_for_conformant_temp_root(tmp_path: Path) -> None:
    """check() passes when every surface under the root is conformant."""
    commands = tmp_path / "src" / "apothem" / "commands"
    skills = tmp_path / "src" / "apothem" / "skills" / "sample"
    commands.mkdir(parents=True)
    skills.mkdir(parents=True)
    (commands / "sample.md").write_text(
        _PASS.read_text(encoding="utf-8"), encoding="utf-8"
    )
    (skills / "SKILL.md").write_text(
        _PASS.read_text(encoding="utf-8"), encoding="utf-8"
    )
    result = dg.check(tmp_path)
    assert result.passed, [str(f) for f in result.findings]
    assert result.files_inspected == 2


def test_check_fails_when_a_surface_is_perturbed(tmp_path: Path) -> None:
    """check() fails when any surface violates the output-shape floor."""
    commands = tmp_path / "src" / "apothem" / "commands"
    skills = tmp_path / "src" / "apothem" / "skills"
    commands.mkdir(parents=True)
    skills.mkdir(parents=True)
    (commands / "broken.md").write_text(
        _FAIL.read_text(encoding="utf-8"), encoding="utf-8"
    )
    result = dg.check(tmp_path)
    assert not result.passed
    assert any(f.kind == "incomplete-shape" for f in result.findings)
