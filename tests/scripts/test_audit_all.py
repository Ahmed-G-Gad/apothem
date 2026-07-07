# SPDX-License-Identifier: MIT

"""Unit tests for the one-shot quality orchestrator.

``scripts/dev/audit_all.py`` runs the ruff / mypy / pytest / validator / chaos
stages in order, honoring a fail-fast policy (overridable with
``--continue-on-error``) and per-stage ``--no-<slug>`` skips. The orchestration
logic -- stage selection, the fail-fast vs run-all policy, suite-aware command
extension, and exit-code aggregation -- is what carries the risk, so it is
tested directly with ``subprocess.run`` mocked (no stage ever executes).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPTS_DEV = _REPO_ROOT / "scripts" / "dev"
if str(_SCRIPTS_DEV) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DEV))

import audit_all as aa  # noqa: E402


class _FakeProc:
    def __init__(self, returncode: int) -> None:
        self.returncode = returncode


def _stage(slug: str, *, suite_aware: bool = False) -> aa.Stage:
    return aa.Stage(slug=slug, title=slug, command=("true",), suite_aware=suite_aware)


class TestStageResult:
    def test_passed_is_true_only_on_zero(self) -> None:
        assert aa.StageResult(_stage("x"), 0).passed is True
        assert aa.StageResult(_stage("x"), 1).passed is False


class TestStageSlugs:
    def test_lists_all_canonical_stage_slugs(self) -> None:
        slugs = aa._stage_slugs()
        assert "ruff-check" in slugs
        assert "pytest" in slugs
        assert "validate-ecosystem" in slugs
        assert len(slugs) == len(aa._STAGES)


class TestRunStage:
    def test_returns_result_from_subprocess_returncode(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(aa.subprocess, "run", lambda *a, **k: _FakeProc(3))
        result = aa.run_stage(_stage("mypy"), tmp_path)
        assert result.returncode == 3
        assert result.passed is False

    def test_suite_aware_stage_appends_suite_flag(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        captured: list[list[str]] = []

        def fake_run(command: list[str], **kwargs: object) -> _FakeProc:
            captured.append(list(command))
            return _FakeProc(0)

        monkeypatch.setattr(aa.subprocess, "run", fake_run)
        aa.run_stage(_stage("validate", suite_aware=True), tmp_path, suite_name="alpha")

        assert captured[0][-2:] == ["--suite", "alpha"]

    def test_non_suite_aware_stage_ignores_suite_name(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        captured: list[list[str]] = []
        monkeypatch.setattr(
            aa.subprocess,
            "run",
            lambda command, **k: captured.append(list(command)) or _FakeProc(0),
        )
        aa.run_stage(_stage("ruff", suite_aware=False), tmp_path, suite_name="alpha")

        assert "--suite" not in captured[0]

    def test_suite_aware_without_suite_name_skips_flag(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        captured: list[list[str]] = []
        monkeypatch.setattr(
            aa.subprocess,
            "run",
            lambda command, **k: captured.append(list(command)) or _FakeProc(0),
        )
        aa.run_stage(_stage("validate", suite_aware=True), tmp_path, suite_name=None)

        assert "--suite" not in captured[0]


class TestRunPolicy:
    def _patch_run_stage(
        self, monkeypatch: pytest.MonkeyPatch, codes: dict[str, int]
    ) -> list[str]:
        """Replace run_stage with a deterministic stub; record what ran."""
        ran: list[str] = []

        def fake_run_stage(
            stage: aa.Stage, cwd: Path, suite_name: str | None = None
        ) -> aa.StageResult:
            ran.append(stage.slug)
            return aa.StageResult(stage=stage, returncode=codes.get(stage.slug, 0))

        monkeypatch.setattr(aa, "run_stage", fake_run_stage)
        return ran

    def test_fail_fast_stops_after_first_failure(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        stages = [_stage("a"), _stage("b"), _stage("c")]
        ran = self._patch_run_stage(monkeypatch, {"b": 1})

        results = aa.run(stages, cwd=tmp_path, continue_on_error=False, suite_name=None)

        # 'b' fails -> 'c' never runs.
        assert ran == ["a", "b"]
        assert len(results) == 2

    def test_continue_on_error_runs_all_stages(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        stages = [_stage("a"), _stage("b"), _stage("c")]
        ran = self._patch_run_stage(monkeypatch, {"b": 1})

        results = aa.run(stages, cwd=tmp_path, continue_on_error=True, suite_name=None)

        assert ran == ["a", "b", "c"]
        assert len(results) == 3


class TestReport:
    def test_zero_when_all_pass(self) -> None:
        results = [aa.StageResult(_stage("a"), 0), aa.StageResult(_stage("b"), 0)]
        assert aa.report(results) == 0

    def test_one_when_any_fail(self) -> None:
        results = [aa.StageResult(_stage("a"), 0), aa.StageResult(_stage("b"), 2)]
        assert aa.report(results) == 1


class TestSelectStages:
    def test_selects_all_by_default(self) -> None:
        args = aa.parse_args([])
        assert len(aa._select_stages(args)) == len(aa._STAGES)

    def test_no_slug_flag_skips_that_stage(self) -> None:
        args = aa.parse_args(["--no-mypy", "--no-pytest"])
        slugs = [s.slug for s in aa._select_stages(args)]
        assert "mypy" not in slugs
        assert "pytest" not in slugs
        assert "ruff-check" in slugs


class TestMain:
    def test_no_stages_selected_returns_zero(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Skip every stage -> nothing to do -> exit 0.
        argv = [f"--no-{slug}" for slug in aa._stage_slugs()]
        assert aa.main(argv) == 0

    def test_aggregates_stage_results_into_exit_code(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def fake_run_stage(
            stage: aa.Stage, cwd: Path, suite_name: str | None = None
        ) -> aa.StageResult:
            # Make the pytest stage fail; everything else passes.
            return aa.StageResult(stage, 1 if stage.slug == "pytest" else 0)

        monkeypatch.setattr(aa, "run_stage", fake_run_stage)
        assert aa.main(["--root", str(tmp_path), "--continue-on-error"]) == 1
