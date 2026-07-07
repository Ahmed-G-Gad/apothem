# SPDX-License-Identifier: MIT

"""Regression baseline for the performance-benchmark drivers.

These tests turn ``src/apothem/benchmarks/bench_*`` from a one-shot audit into
a release-gating regression baseline (per the per-class budgets in
``rules/performance-discipline.md``). The drivers previously resolved their
measurement targets against a mis-computed repository root, so a missing target
silently produced a sub-budget reading from a process that never ran the real
code — a false PASS. Two test classes guard against regressions:

* target-resolution: each driver's resolved target constant points at a real
  on-disk file/directory, and a genuine run exits 0 within budget;
* false-PASS prevention: when a target is missing, the driver exits non-zero
  (loud failure) rather than reporting a spurious sub-budget pass.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from apothem.benchmarks import (
    bench_agents,
    bench_hooks,
    bench_tests,
    bench_validate_ecosystem,
)


class TestTargetResolution:
    """The measured targets resolve to real on-disk artifacts."""

    def test_dispatcher_target_exists(self) -> None:
        assert bench_hooks._DISPATCHER.is_file()

    def test_validator_target_exists(self) -> None:
        assert bench_validate_ecosystem._VALIDATOR.is_file()

    def test_tests_dir_exists(self) -> None:
        assert bench_tests._TESTS_DIR.is_dir()


@pytest.mark.benchmark
class TestDriversMeasureAndGate:
    """Each driver genuinely measures and reports a within-budget pass.

    Marked ``benchmark``: these drivers spawn real subprocesses and assert
    against wall-clock budgets, so a loaded CI runner can deselect them with
    ``-m "not benchmark"`` and route them to a dedicated performance lane. A
    plain ``pytest tests/unit`` run still executes them.
    """

    def test_bench_hooks_passes_within_budget(self) -> None:
        assert bench_hooks.main(["--event=PreToolUse"]) == 0

    def test_bench_validate_ecosystem_passes_within_budget(self) -> None:
        assert bench_validate_ecosystem.main(["--check", "option-annotation"]) == 0

    def test_bench_agents_scaffold_exits_zero(self) -> None:
        # Agent spawn is a harness-level operation not measurable headlessly;
        # the scaffold is a recorded, justified budget amendment, so it exits 0
        # with an honest SCAFFOLD marker rather than a spurious PASS.
        assert bench_agents.main(["--pattern", "research"]) == 0


@pytest.mark.benchmark
class TestMissingTargetFailsLoudly:
    """A missing target FAILs (exit != 0) instead of false-PASSing.

    Marked ``benchmark``: shares the subprocess-driving benchmark drivers with
    ``TestDriversMeasureAndGate`` and is deselectable with ``-m "not
    benchmark"`` on loaded runners.
    """

    def test_bench_hooks_missing_dispatcher(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            bench_hooks, "_DISPATCHER", Path("does/not/exist/dispatch.py")
        )
        assert bench_hooks.main(["--event=PreToolUse"]) == 2

    def test_bench_validate_ecosystem_missing_validator(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            bench_validate_ecosystem,
            "_VALIDATOR",
            Path("does/not/exist/validate_ecosystem.py"),
        )
        assert bench_validate_ecosystem.main(["--check", "option-annotation"]) == 2

    def test_bench_tests_missing_module(self) -> None:
        assert bench_tests.main(["--module", "tests/unit/_no_such_module_.py"]) == 2


@pytest.mark.benchmark
class TestInnerFailureFailsLoudly:
    """A target that exists but whose run exits non-zero FAILs (exit != 0).

    Without the returncode guard these drivers timed a broken run and reported a
    spurious sub-budget PASS — a bogus ``--check`` argparse-errors in well under
    budget, a pytest collection error exits fast. The benchmark must report the
    failure, never attest budget compliance for a run that never executed.
    """

    def test_bench_validate_ecosystem_nonzero_run_fails(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        class _Fake:
            returncode = 2

        monkeypatch.setattr(
            bench_validate_ecosystem.subprocess, "run", lambda *a, **k: _Fake()
        )
        assert bench_validate_ecosystem.main(["--check", "option-annotation"]) == 2

    def test_bench_tests_nonzero_pytest_fails(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        class _Fake:
            returncode = 1

        monkeypatch.setattr(bench_tests.subprocess, "run", lambda *a, **k: _Fake())
        assert bench_tests.main([]) == 2
