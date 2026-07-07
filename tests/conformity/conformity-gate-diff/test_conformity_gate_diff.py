# SPDX-License-Identifier: MIT

"""Self-tests for the conformity-gate differential helpers.

Why these tests exist. The conformity-gate orchestrator distinguishes
between a fresh write (no pre-content) and an Edit (pre-content available).
For Edits, the gate runs every grep against the pre-edit body AND the
post-edit body and suppresses any finding present in BOTH passes — only
findings introduced by the edit surface to the operator. This protects
the cross-cluster Edit cascade from being blocked by pre-existing
violations the edit does not touch.

The helpers under test:
  - _finding_signature: canonicalises a finding for pre/post equality
    while ignoring position fields (line, column, occurrences) so the
    same defect is recognized across the edit even when the line moves.
  - _diff_invocations: pairs pre / post grep results and suppresses
    pre-existing findings from the post set.
  - _orchestrator_diff_report: end-to-end differential pass — runs the
    orchestrator on pre-content, runs it on post-content, and returns a
    differential report.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Final

_REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[3]
_GATE_PATH: Final[Path] = _REPO_ROOT / "src" / "apothem" / "conformity" / "gate.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("conformity_gate", _GATE_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["conformity_gate"] = module
    spec.loader.exec_module(module)
    return module


_MOD: Final[ModuleType] = _load()


def test_finding_signature_ignores_line_field() -> None:
    f1 = {"value": "x", "line": 7, "rule": "demo"}
    f2 = {"value": "x", "line": 99, "rule": "demo"}
    assert _MOD._finding_signature(f1) == _MOD._finding_signature(f2)


def test_finding_signature_ignores_occurrences_field() -> None:
    f1 = {"value": "x", "occurrences": [1, 2], "rule": "demo"}
    f2 = {"value": "x", "occurrences": [40, 50, 60], "rule": "demo"}
    assert _MOD._finding_signature(f1) == _MOD._finding_signature(f2)


def test_finding_signature_distinguishes_distinct_findings() -> None:
    f1 = {"value": "x", "rule": "demo"}
    f2 = {"value": "y", "rule": "demo"}
    assert _MOD._finding_signature(f1) != _MOD._finding_signature(f2)


def test_diff_invocations_suppresses_pre_existing_findings() -> None:
    pre = [
        _MOD.GrepInvocation(
            grep="demo-grep",
            passed=False,
            findings=[{"value": "x", "rule": "demo"}],
            elapsed_seconds=0.0,
            over_budget=False,
        )
    ]
    post = [
        _MOD.GrepInvocation(
            grep="demo-grep",
            passed=False,
            findings=[{"value": "x", "rule": "demo"}],
            elapsed_seconds=0.0,
            over_budget=False,
        )
    ]
    diffed = _MOD._diff_invocations(pre, post)
    assert len(diffed) == 1
    assert diffed[0].passed
    assert diffed[0].findings == []


def test_diff_invocations_retains_new_findings() -> None:
    pre = [
        _MOD.GrepInvocation(
            grep="demo-grep",
            passed=False,
            findings=[{"value": "x", "rule": "demo"}],
            elapsed_seconds=0.0,
            over_budget=False,
        )
    ]
    post = [
        _MOD.GrepInvocation(
            grep="demo-grep",
            passed=False,
            findings=[
                {"value": "x", "rule": "demo"},
                {"value": "y", "rule": "demo"},
            ],
            elapsed_seconds=0.0,
            over_budget=False,
        )
    ]
    diffed = _MOD._diff_invocations(pre, post)
    assert len(diffed) == 1
    assert not diffed[0].passed
    retained_values = {f["value"] for f in diffed[0].findings}
    assert retained_values == {"y"}


def test_diff_invocations_passes_when_post_is_clean() -> None:
    pre = [
        _MOD.GrepInvocation(
            grep="demo-grep",
            passed=False,
            findings=[{"value": "x", "rule": "demo"}],
            elapsed_seconds=0.0,
            over_budget=False,
        )
    ]
    post = [
        _MOD.GrepInvocation(
            grep="demo-grep",
            passed=True,
            findings=[],
            elapsed_seconds=0.0,
            over_budget=False,
        )
    ]
    diffed = _MOD._diff_invocations(pre, post)
    assert len(diffed) == 1
    assert diffed[0].passed


def test_orchestrator_diff_report_passes_when_pre_and_post_share_findings() -> None:
    fixture_dir = _REPO_ROOT / "tests" / "conformity" / "magic-number-grep"
    body = (fixture_dir / "fail.py").read_text(encoding="utf-8")
    target = fixture_dir / "fail.py"
    report = _MOD._orchestrator_diff_report(
        body, body, target, only="magic_number_grep"
    )
    assert report.passed
    for inv in report.invocations:
        assert inv.findings == []


def test_orchestrator_diff_report_flags_only_new_findings_from_edit() -> None:
    fixture_dir = _REPO_ROOT / "tests" / "conformity" / "magic-number-grep"
    pre_body = (fixture_dir / "pass.py").read_text(encoding="utf-8")
    fail_body = (fixture_dir / "fail.py").read_text(encoding="utf-8")
    target = fixture_dir / "pass.py"
    report = _MOD._orchestrator_diff_report(
        pre_body, fail_body, target, only="magic_number_grep"
    )
    assert not report.passed


def test_plan_suite_path_short_circuits_to_pass() -> None:
    plan_path = (
        _REPO_ROOT
        / ".apothem"
        / "plans"
        / "any-suite"
        / "phases"
        / "01-x"
        / "REPORT.md"
    )
    body = "any content with literal 99 and 99 inline"
    report = _MOD.run_orchestrator(body, plan_path)
    assert report.passed
