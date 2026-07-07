# SPDX-License-Identifier: MIT

"""Tests for the conformity-gate orchestrator's plan-suite exemption.

provenance: cluster-1 hardening (commit lineage from `17e0d9f` settings.json
refit). The conformity-gate at ``src/apothem/conformity/gate.py``
short-circuits on plan-suite paths so per-Write hooks do not block plan-suite
emissions whose Markdown enumerations (dates, version identifiers, phase
identifiers, kebab-case directory paths) trigger structural false positives on
matchers designed for codebase content. The exemption is anchored at the
``src/apothem/schemas/header-exceptions.txt`` ``.apothem/**`` exception class
(the sole canonical plans tree is ``.apothem/plans/``).

Tests assert four behaviors:

1. ``_is_plan_suite_path`` returns True for paths under an ``.apothem/plans/``
   subtree.
2. ``_is_plan_suite_path`` returns False for non-plan paths and None.
3. ``run_orchestrator`` short-circuits to a synthetic empty PASS on plan paths.
4. ``run_orchestrator`` runs the full matcher set on non-plan paths.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parents[2]
ORCHESTRATOR_PATH = REPO_ROOT / "src" / "apothem" / "conformity" / "gate.py"


def _load_orchestrator() -> ModuleType:
    """Load the orchestrator via importlib (the file uses hyphens)."""
    safe_name = "conformity_gate"
    spec = importlib.util.spec_from_file_location(safe_name, ORCHESTRATOR_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[safe_name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(safe_name, None)
        raise
    return module


def test_is_plan_suite_path_recognises_plans_subtree() -> None:
    orchestrator = _load_orchestrator()
    posix_plan_path = Path("/home/user/project/.apothem/plans/some-suite/PROGRESS.md")
    win_plan_path = Path(
        "C:/Users/username/project/.apothem/plans/some-suite/REPORT.md"
    )
    assert orchestrator._is_plan_suite_path(posix_plan_path) is True
    assert orchestrator._is_plan_suite_path(win_plan_path) is True


def test_is_plan_suite_path_rejects_non_plan_and_none() -> None:
    orchestrator = _load_orchestrator()
    code_path = Path("/home/user/.claude/src/apothem/conformity/gate.py")
    rule_path = Path("/home/user/.claude/rules/some-rule.md")
    # A legacy project-local .plans/ path is no longer a recognized plan-suite
    # path — the sole canonical tree is .apothem/plans/.
    legacy_path = Path("/home/user/project/.plans/some-suite/PROGRESS.md")
    # A non-plans child of .apothem (operator data) is not a plan-suite path.
    data_path = Path("/home/user/project/.apothem/memory/records.json")
    assert orchestrator._is_plan_suite_path(code_path) is False
    assert orchestrator._is_plan_suite_path(rule_path) is False
    assert orchestrator._is_plan_suite_path(legacy_path) is False
    assert orchestrator._is_plan_suite_path(data_path) is False
    assert orchestrator._is_plan_suite_path(None) is False


def test_run_orchestrator_short_circuits_on_plan_path() -> None:
    """Plan-suite paths return a synthetic empty-invocations PASS report."""
    orchestrator = _load_orchestrator()
    plan_path = Path("C:/Users/username/project/.apothem/plans/some-suite/PROGRESS.md")
    content = "## Some Heading\n\nDates and identifiers do not trip the gate here.\n"
    report = orchestrator.run_orchestrator(content, plan_path)
    assert report.passed is True
    assert report.grep_count == 0
    assert report.pass_count == 0
    assert report.fail_count == 0
    assert report.invocations == []


def test_run_orchestrator_runs_matchers_on_non_plan_path() -> None:
    """Non-plan paths run the full matcher set; grep_count is the catalog size."""
    orchestrator = _load_orchestrator()
    benign_content = "# title\n\nThe quick brown fox jumps over the lazy dog.\n"
    code_path = Path("C:/Users/username/.claude/src/apothem/conformity/some_file.txt")
    report = orchestrator.run_orchestrator(benign_content, code_path)
    assert report.grep_count == len(orchestrator.GREP_MODULES)
    assert report.grep_count > 0
