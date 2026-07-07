# SPDX-License-Identifier: MIT

"""Behaviour contract for the plan-next-step-consistency-grep validator.

The validator walks ``<root>/.apothem/plans/`` and flags any infra file whose
``## Recommended Next Step`` footer names a pipeline stage that disagrees with
the suite's recorded next stage. It reads that recorded stage from PROGRESS.md
in two formats — the meta-pipeline-tracking variant (``## Pipeline Tracker`` +
``- **Next action (imperative):** Run `/plan-X```) and the canonical template
(``## Phase Tracker`` + ``**Next action:** ...`` field). It is advisory: the
CLI exits 0 by default and only exits 2 under ``--strict``.

Tests build ephemeral ``.apothem/plans/<suite>/`` fixtures under ``tmp_path`` so the
behaviour is exercised deterministically, independent of any live plan suite.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Final

_REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[3]
_CONFORMITY_DIR: Final[Path] = _REPO_ROOT / "src" / "apothem" / "conformity"
_GREP_PATH: Final[Path] = _CONFORMITY_DIR / "plan_next_step_consistency_grep.py"
_GATE_PATH: Final[Path] = _CONFORMITY_DIR / "gate.py"


def _load(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


_MOD: Final[ModuleType] = _load("plan_next_step_consistency_grep", _GREP_PATH)


def _progress(*, tracker_next: str, next_action: str, footer: str) -> str:
    """Render a PROGRESS.md in the meta-pipeline tracker format."""
    return (
        "# PROGRESS — sample\n\n"
        "## Pipeline Tracker\n\n"
        "| Stage | Status | Artifact |\n"
        "|-------|--------|----------|\n"
        "| `/plan-review` | ✅ **COMPLETE** | scorecards |\n"
        f"| `{tracker_next}` | ⏭️ **NEXT** | architecture questions |\n"
        "| `/plan-execute` | pending | — |\n\n"
        "## Resumption Contract\n\n"
        "- **Status:** review complete.\n"
        f"- **Next action (imperative):** Run **`{next_action}`** to resolve\n"
        "  the architecture questions; then `/plan-execute` Phase 00A.\n\n"
        "## Recommended Next Step\n\n"
        f"**Run `{footer}`** to resolve the architecture questions.\n"
    )


def _infra(footer: str) -> str:
    """Render an infra file (MASTER-PLAN-shaped) with a footer stage."""
    return (
        "# MASTER-PLAN — sample\n\n"
        "## Phases\n\nPhase index body.\n\n"
        "## Recommended Next Step\n\n"
        f"**Run `{footer}`** to resolve the architecture questions.\n"
    )


def _write_suite(
    root: Path,
    name: str,
    *,
    progress: str | None,
    infra: dict[str, str] | None = None,
) -> Path:
    """Create ``<root>/.apothem/plans/<name>/`` with the supplied files; return it."""
    suite = root / ".apothem" / "plans" / name
    suite.mkdir(parents=True)
    if progress is not None:
        (suite / "PROGRESS.md").write_text(progress, encoding="utf-8")
    for filename, body in (infra or {}).items():
        (suite / filename).write_text(body, encoding="utf-8")
    return suite


def test_consistent_suite_passes(tmp_path: Path) -> None:
    """Every footer agreeing with the recorded next stage is a clean pass."""
    _write_suite(
        tmp_path,
        "sample",
        progress=_progress(
            tracker_next="/plan-design",
            next_action="/plan-design",
            footer="/plan-design",
        ),
        infra={
            "MASTER-PLAN.md": _infra("/plan-design"),
            "MASTER-INDEX.md": _infra("/plan-design"),
            "TRACE-MATRIX.md": _infra("/plan-design"),
        },
    )
    result = _MOD.check(tmp_path)
    assert result.passed is True
    assert result.findings == []
    assert result.notes == []
    assert result.suites_inspected == 1
    assert result.files_inspected == 4
    assert result.advisory is True


def test_legacy_space_stage_form_recognized(tmp_path: Path) -> None:
    """Both written stage forms normalize to the canonical ``/plan-<stage>``.

    The recorded next stage is written in the legacy space-separated dispatch
    form ``/plan <stage>`` and the footer in the canonical hyphenated command
    form ``/plan-<stage>``. Both must normalize to the same token, so a
    mismatching stage is flagged with the canonical hyphenated form in the
    detail regardless of which written form authored it.
    """
    _write_suite(
        tmp_path,
        "sample",
        progress=_progress(
            tracker_next="/plan design",
            next_action="/plan design",
            footer="/plan design",
        ),
        infra={"MASTER-PLAN.md": _infra("/plan-review")},
    )
    result = _MOD.check(tmp_path)
    assert result.passed is False
    assert len(result.findings) == 1
    assert "/plan-review" in result.findings[0].detail
    assert "/plan-design" in result.findings[0].detail


def test_stale_infra_footer_flagged(tmp_path: Path) -> None:
    """A MASTER-PLAN footer pointing at an already-complete stage is flagged."""
    _write_suite(
        tmp_path,
        "sample",
        progress=_progress(
            tracker_next="/plan-design",
            next_action="/plan-design",
            footer="/plan-design",
        ),
        infra={"MASTER-PLAN.md": _infra("/plan-review")},
    )
    result = _MOD.check(tmp_path)
    assert result.passed is False
    assert len(result.findings) == 1
    finding = result.findings[0]
    assert finding.surface.endswith("MASTER-PLAN.md")
    assert finding.suite == "sample"
    assert "/plan-review" in finding.detail
    assert "/plan-design" in finding.detail


def test_progress_self_contradiction_flagged(tmp_path: Path) -> None:
    """PROGRESS.md's own footer contradicting its Tracker + Next action."""
    _write_suite(
        tmp_path,
        "sample",
        progress=_progress(
            tracker_next="/plan-design",
            next_action="/plan-design",
            footer="/plan-review",
        ),
    )
    result = _MOD.check(tmp_path)
    assert result.passed is False
    assert len(result.findings) == 1
    finding = result.findings[0]
    assert finding.surface.endswith("PROGRESS.md")
    assert "/plan-review" in finding.detail
    assert "/plan-design" in finding.detail


def test_internal_tracker_resumption_drift_flagged(tmp_path: Path) -> None:
    """Tracker NEXT and Resumption 'Next action' disagreeing is itself a find."""
    _write_suite(
        tmp_path,
        "sample",
        progress=_progress(
            tracker_next="/plan-execute",
            next_action="/plan-design",
            footer="/plan-design",
        ),
    )
    result = _MOD.check(tmp_path)
    assert result.passed is False
    assert len(result.findings) == 1
    assert "internal drift" in result.findings[0].detail
    assert "/plan-execute" in result.findings[0].detail
    assert "/plan-design" in result.findings[0].detail


def test_tracker_only_state_used_when_no_next_action(tmp_path: Path) -> None:
    """When the Resumption Contract names no stage, Tracker NEXT is canonical."""
    progress = (
        "# PROGRESS — sample\n\n"
        "## Pipeline Tracker\n\n"
        "| Stage | Status | Artifact |\n"
        "|-------|--------|----------|\n"
        "| `/plan-design` | ⏭️ **NEXT** | questions |\n\n"
        "## Resumption Contract\n\n"
        "- **Status:** review complete; ready to proceed.\n\n"
        "## Recommended Next Step\n\n"
        "**Run `/plan-review`** again before proceeding.\n"
    )
    _write_suite(tmp_path, "sample", progress=progress)
    result = _MOD.check(tmp_path)
    assert result.passed is False
    assert len(result.findings) == 1
    assert "Pipeline/Phase Tracker NEXT" in result.findings[0].detail


def test_phase_tracker_heading_parsed(tmp_path: Path) -> None:
    """The canonical template's ``## Phase Tracker`` heading is parsed too."""
    progress = (
        "# PROGRESS — sample\n\n"
        "## Phase Tracker\n\n"
        "| Stage | Status | Artifact |\n"
        "|-------|--------|----------|\n"
        "| `/plan-design` | ⏭️ **NEXT** | questions |\n\n"
        "## Resumption Contract\n\n"
        "**Status:** ready.\n\n"
        "## Recommended Next Step\n\n"
        "**Run `/plan-review`** before proceeding.\n"
    )
    _write_suite(tmp_path, "sample", progress=progress)
    result = _MOD.check(tmp_path)
    assert result.passed is False
    assert len(result.findings) == 1
    assert "/plan-review" in result.findings[0].detail
    assert "/plan-design" in result.findings[0].detail


def test_field_format_next_action_with_stage(tmp_path: Path) -> None:
    """The template's ``**Next action:**`` field form yields a stage."""
    progress = (
        "# PROGRESS — sample\n\n"
        "## Resumption Contract\n\n"
        "**Next action:** Run `/plan-design` to resolve the questions.\n"
        "**Blockers:** none\n\n"
        "## Recommended Next Step\n\n"
        "**Run `/plan-review`** before proceeding.\n"
    )
    _write_suite(tmp_path, "sample", progress=progress)
    result = _MOD.check(tmp_path)
    assert result.passed is False
    assert len(result.findings) == 1
    assert "/plan-review" in result.findings[0].detail
    assert "/plan-design" in result.findings[0].detail


def test_execution_imperative_next_action_no_false_positive(
    tmp_path: Path,
) -> None:
    """An execution-imperative Next action does not borrow a later stage token.

    The Next action is "Execute Phase 05" (no ``/plan-<stage>``); a ``/plan-review``
    appears only in a later field and in ``### Active Decisions``. The bounded
    parse must not pick those up, so the recorded next stage is indeterminate:
    the footer is left unvalidated (no false finding) and surfaced as a note.
    """
    progress = (
        "# PROGRESS — sample\n\n"
        "## Phase Tracker\n\n"
        "| # | Phase | Status |\n"
        "|---|-------|--------|\n"
        "| 05 | rate limiting | 🔄 In Progress |\n\n"
        "## Resumption Contract\n\n"
        "**Next action:** Execute Phase 05 Task 05.3: implement the\n"
        "rate limiting middleware.\n"
        "**Blockers:** none — but revisit the `/plan-review` scorecards.\n\n"
        "### Active Decisions\n"
        "- D-3: adopted a `/plan-review` cadence of two cycles.\n\n"
        "## Recommended Next Step\n\n"
        "**Run `/plan-review`** again — stale footer.\n"
    )
    _write_suite(tmp_path, "sample", progress=progress)
    result = _MOD.check(tmp_path)
    assert result.passed is True
    assert result.findings == []
    assert len(result.notes) == 1
    assert "indeterminate" in result.notes[0]
    assert "PROGRESS.md" in result.notes[0]


def test_prose_next_in_pending_row_not_matched(tmp_path: Path) -> None:
    """A pending row whose prose contains 'next' is not the NEXT row.

    Only the bolded ``**NEXT**`` status row supplies the stage; if the loose
    match leaked, the pending ``/plan-execute`` row would win and the
    ``/plan-execute`` footer would pass — asserting a finding proves the real
    ``/plan-design`` NEXT row was chosen.
    """
    progress = (
        "# PROGRESS — sample\n\n"
        "## Pipeline Tracker\n\n"
        "| Stage | Status | Artifact |\n"
        "|-------|--------|----------|\n"
        "| `/plan-execute` | pending | run next after design |\n"
        "| `/plan-design` | ⏭️ **NEXT** | questions |\n\n"
        "## Resumption Contract\n\n"
        "**Status:** ready.\n\n"
        "## Recommended Next Step\n\n"
        "**Run `/plan-execute`** now.\n"
    )
    _write_suite(tmp_path, "sample", progress=progress)
    result = _MOD.check(tmp_path)
    assert result.passed is False
    assert len(result.findings) == 1
    assert "/plan-execute" in result.findings[0].detail
    assert "/plan-design" in result.findings[0].detail


def test_plain_next_steps_todo_not_treated_as_footer(tmp_path: Path) -> None:
    """A ``## Next Steps`` phase-todo list (no Recommended) is not a footer."""
    todo = (
        "# MASTER-PLAN — sample\n\n"
        "## Next Steps\n\n"
        "1. [ ] Execute Phase 02\n"
        "2. [ ] Re-run `/plan-review` later if findings reopen\n"
    )
    _write_suite(
        tmp_path,
        "sample",
        progress=_progress(
            tracker_next="/plan-design",
            next_action="/plan-design",
            footer="/plan-design",
        ),
        infra={"MASTER-PLAN.md": todo},
    )
    result = _MOD.check(tmp_path)
    assert result.passed is True
    assert result.findings == []


def test_footer_without_stage_not_flagged(tmp_path: Path) -> None:
    """A footer naming no pipeline stage is not compared (no false positive)."""
    _write_suite(
        tmp_path,
        "sample",
        progress=_progress(
            tracker_next="/plan-design",
            next_action="/plan-design",
            footer="/plan-design",
        ),
        infra={
            "MASTER-PLAN.md": (
                "# MASTER-PLAN — sample\n\n"
                "## Recommended Next Step\n\n"
                "**Promote the converged plan to an ADR** — no pipeline stage "
                "remains.\n"
            ),
        },
    )
    result = _MOD.check(tmp_path)
    assert result.passed is True
    assert result.findings == []
    assert result.files_inspected == 2


def test_multi_action_recommended_matches_passes(tmp_path: Path) -> None:
    """A `## Next Steps` block whose Recommended line matches state passes."""
    next_steps = (
        "# MASTER-PLAN — sample\n\n"
        "## Next Steps\n\n"
        "1. **Run `/plan-design`** — **Recommended**. Resolve the questions.\n"
        "2. Re-read `/plan-review` scorecards when revisiting findings.\n"
    )
    _write_suite(
        tmp_path,
        "sample",
        progress=_progress(
            tracker_next="/plan-design",
            next_action="/plan-design",
            footer="/plan-design",
        ),
        infra={"MASTER-PLAN.md": next_steps},
    )
    result = _MOD.check(tmp_path)
    assert result.passed is True
    assert result.findings == []


def test_multi_action_recommended_stale_flagged(tmp_path: Path) -> None:
    """A `## Next Steps` block whose Recommended line is stale is flagged."""
    next_steps = (
        "# MASTER-PLAN — sample\n\n"
        "## Next Steps\n\n"
        "1. **Run `/plan-review`** — **Recommended**. Re-audit before moving.\n"
        "2. Then run `/plan-design` to resolve the questions.\n"
    )
    _write_suite(
        tmp_path,
        "sample",
        progress=_progress(
            tracker_next="/plan-design",
            next_action="/plan-design",
            footer="/plan-design",
        ),
        infra={"MASTER-PLAN.md": next_steps},
    )
    result = _MOD.check(tmp_path)
    assert result.passed is False
    assert len(result.findings) == 1
    assert "/plan-review" in result.findings[0].detail


def test_suite_without_progress_skipped(tmp_path: Path) -> None:
    """A suite carrying no PROGRESS.md has no recorded state; it is skipped."""
    _write_suite(
        tmp_path,
        "sample",
        progress=None,
        infra={"MASTER-PLAN.md": _infra("/plan-review")},
    )
    result = _MOD.check(tmp_path)
    assert result.passed is True
    assert result.findings == []
    assert result.suites_inspected == 0


def test_no_plans_directory_passes(tmp_path: Path) -> None:
    """A project root without a .plans/ tree inspects nothing and passes."""
    (tmp_path / "README.md").write_text("# repo\n", encoding="utf-8")
    result = _MOD.check(tmp_path)
    assert result.passed is True
    assert result.findings == []
    assert result.suites_inspected == 0
    assert result.files_inspected == 0


def test_multiple_suites_each_inspected(tmp_path: Path) -> None:
    """Every suite under .plans/ is inspected independently."""
    _write_suite(
        tmp_path,
        "alpha",
        progress=_progress(
            tracker_next="/plan-design",
            next_action="/plan-design",
            footer="/plan-design",
        ),
    )
    _write_suite(
        tmp_path,
        "beta",
        progress=_progress(
            tracker_next="/plan-design",
            next_action="/plan-design",
            footer="/plan-review",
        ),
    )
    result = _MOD.check(tmp_path)
    assert result.suites_inspected == 2
    assert len(result.findings) == 1
    assert result.findings[0].suite == "beta"


def test_to_json_carries_advisory_and_notes(tmp_path: Path) -> None:
    """The serialized report round-trips and carries advisory + notes keys."""
    _write_suite(
        tmp_path,
        "sample",
        progress=_progress(
            tracker_next="/plan-design",
            next_action="/plan-design",
            footer="/plan-review",
        ),
    )
    payload = json.loads(_MOD.check(tmp_path).to_json())
    assert payload["advisory"] is True
    assert payload["passed"] is False
    assert payload["grep"] == "plan-next-step-consistency-grep"
    assert len(payload["findings"]) == 1
    assert payload["notes"] == []


def test_main_advisory_exit_zero_despite_findings(tmp_path: Path, capsys) -> None:
    """Default (advisory) CLI exits 0 even when inconsistencies are found."""
    _write_suite(
        tmp_path,
        "sample",
        progress=_progress(
            tracker_next="/plan-design",
            next_action="/plan-design",
            footer="/plan-review",
        ),
    )
    rc = _MOD._main([str(_GREP_PATH), str(tmp_path)])
    assert rc == _MOD.EXIT_PASS
    payload = json.loads(capsys.readouterr().out)
    assert payload["passed"] is False
    assert payload["advisory"] is True


def test_main_strict_exit_two_on_findings(tmp_path: Path) -> None:
    """--strict CLI exits 2 when inconsistencies are found."""
    _write_suite(
        tmp_path,
        "sample",
        progress=_progress(
            tracker_next="/plan-design",
            next_action="/plan-design",
            footer="/plan-review",
        ),
    )
    rc = _MOD._main([str(_GREP_PATH), "--strict", str(tmp_path)])
    assert rc == _MOD.EXIT_FAIL


def test_main_strict_exit_zero_on_clean(tmp_path: Path) -> None:
    """--strict CLI exits 0 when the suite is consistent."""
    _write_suite(
        tmp_path,
        "sample",
        progress=_progress(
            tracker_next="/plan-design",
            next_action="/plan-design",
            footer="/plan-design",
        ),
    )
    rc = _MOD._main([str(_GREP_PATH), "--strict", str(tmp_path)])
    assert rc == _MOD.EXIT_PASS


def test_gate_check_resolves_standalone_validator() -> None:
    """`gate --check` resolves this standalone validator (and its siblings).

    Guards against a hyphen/underscore mismatch that would make every
    standalone validator unreachable via ``--check``.
    """
    gate = _load("gate", _GATE_PATH)
    assert gate._resolve_validator("plan-next-step-consistency-grep") == (
        "plan-next-step-consistency-grep",
        True,
    )
    assert gate._resolve_validator("naming-grep") == ("naming-grep", True)
    # Underscore form resolves too; per-Write greps still resolve.
    assert gate._resolve_validator("naming_grep") == ("naming-grep", True)
    assert gate._resolve_validator("hedging-grep") == ("hedging_grep", False)


def test_advisory_verdict_parsing() -> None:
    """`gate._advisory_verdict` extracts an advisory validator's inner verdict."""
    gate = _load("gate", _GATE_PATH)
    adv_fail = json.dumps(
        {"advisory": True, "passed": False, "findings": [{"surface": "x"}]}
    )
    assert gate._advisory_verdict(adv_fail) == {
        "passed": False,
        "findings": [{"surface": "x"}],
    }
    adv_pass = json.dumps({"advisory": True, "passed": True, "findings": []})
    assert gate._advisory_verdict(adv_pass) == {"passed": True, "findings": []}
    # A non-advisory validator's output is not an advisory verdict.
    assert gate._advisory_verdict(json.dumps({"passed": False, "findings": []})) is None
    # Non-JSON output (e.g. a script error string) is not an advisory verdict.
    assert gate._advisory_verdict("naming-grep: some error") is None


def test_gate_surfaces_advisory_findings_while_exit_stays_green(
    tmp_path: Path,
) -> None:
    """The gate keeps the advisory exit green but propagates the inner verdict.

    A stale footer makes the validator report ``passed: false`` while it still
    exits 0 (advisory). The gate's per-validator exit verdict therefore stays
    green, but ``_advisory_verdict`` recovers the drift from the JSON so the
    gate report can surface it.
    """
    gate = _load("gate", _GATE_PATH)
    _write_suite(
        tmp_path,
        "sample",
        progress=_progress(
            tracker_next="/plan-design",
            next_action="/plan-design",
            footer="/plan-review",
        ),
    )
    passed, output = gate._run_standalone("plan-next-step-consistency-grep", tmp_path)
    # Advisory: the subprocess exits 0, so the gate's exit verdict is green.
    assert passed is True
    # But the inner advisory verdict surfaces the drift.
    verdict = gate._advisory_verdict(output)
    assert verdict is not None
    assert verdict["passed"] is False
    assert len(verdict["findings"]) == 1
