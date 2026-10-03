# SPDX-License-Identifier: MIT

"""Regression baseline for the performance-benchmark drivers.

These tests turn ``src/apothem/benchmarks/bench_*`` from a one-shot audit into
a release-gating regression baseline (per the per-class budgets in
``rules/performance-discipline.md``). The drivers previously resolved their
measurement targets against a mis-computed repository root, so a missing target
silently produced a sub-budget reading from a process that never ran the real
code — a false PASS. The guards here:

* target-resolution: each driver's resolved target constant points at a real
  on-disk file/directory;
* real measurement: ``bench_hooks`` runs the registered hook chain on a real
  event payload (not ``--help``), so the dispatcher, the handler and the
  message emission are all on the measured path;
* false-PASS prevention: a missing target, a hook command that cannot run, a
  handler that skips itself, or invalid hook output exits non-zero instead of
  reporting a spurious sub-budget pass;
* honest scaffolds: a driver with nothing wired reports NOT MEASURED with its
  own exit code, never a PASS-shaped zero.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pytest

from apothem.benchmarks import (
    bench_agents,
    bench_hooks,
    bench_tests,
    bench_validate_ecosystem,
)

_needs_bash = pytest.mark.skipif(
    shutil.which("bash") is None or sys.platform == "win32",
    reason="the registered hook chain runs bash commands (shell: bash entries)",
)

# A registered chain that runs the real bootstrap and dispatcher through bash
# explicitly, so the fixture does not depend on the script's file mode.
_BOOTSTRAP = '"${CLAUDE_PLUGIN_ROOT}/src/apothem/hooks/lib/bootstrap.sh"'
_MESSAGES = "${CLAUDE_PLUGIN_ROOT}/src/apothem/hooks/messages"
_DEPENDENCY_GUARD = (
    f'bash {_BOOTSTRAP} PreToolUse "{_MESSAGES}/pretooluse-dependency-guard.md"'
)


def _hooks_json(tmp_path: Path, chains: dict[str, dict[str, list[str]]]) -> Path:
    """Write a hooks.json registering ``chains[event][matcher] = [commands]``."""
    hooks: dict[str, list[dict[str, object]]] = {}
    for event, matchers in chains.items():
        hooks[event] = [
            {
                "matcher": matcher,
                "hooks": [
                    {
                        "type": "command",
                        "command": command,
                        "timeout": 10,
                        "shell": "bash",
                    }
                    for command in commands
                ]
                + [
                    {
                        "type": "command",
                        "command": "pwsh -NoProfile -File ignored.ps1",
                        "timeout": 10,
                        "shell": "powershell",
                    }
                ],
            }
            for matcher, commands in matchers.items()
        ]
    path = tmp_path / "hooks.json"
    path.write_text(json.dumps({"hooks": hooks}), encoding="utf-8")
    return path


class TestTargetResolution:
    """The measured targets resolve to real on-disk artifacts."""

    def test_dispatcher_target_exists(self) -> None:
        assert bench_hooks._DISPATCHER.is_file()

    def test_registered_hooks_manifest_exists(self) -> None:
        assert bench_hooks._HOOKS_JSON.is_file()

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

    @_needs_bash
    def test_bench_hooks_measures_real_write_payload(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        manifest = _hooks_json(tmp_path, {"PreToolUse": {"Write": [_DEPENDENCY_GUARD]}})
        monkeypatch.setattr(bench_hooks, "_HOOKS_JSON", manifest)

        code = bench_hooks.main(["--event=PreToolUse", "--runs=1", "--json"])

        assert code == 0
        report = json.loads(capsys.readouterr().out)
        chain = report["chains"]["PreToolUse:Write"]
        assert chain["status"] == "pass"
        assert chain["commands"] == 1
        assert chain["median_sum_ms"] > 0
        # The benchmark writes a benign app.py. The dependency guard speaks
        # only when a write targets a manifest or lockfile, so a real run of
        # the registered chain injects nothing for this payload: the benign
        # cost the guard-precision change set out to remove.
        assert chain["injected_chars"] == 0

    def test_bench_validate_ecosystem_passes_within_budget(self) -> None:
        assert bench_validate_ecosystem.main(["--check", "option-annotation"]) == 0

    def test_bench_agents_reports_not_measured(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # Agent spawn is a harness-level operation that cannot be measured
        # headlessly without a model call. The driver says so with its own exit
        # code instead of exiting 0 like a pass.
        code = bench_agents.main(["--pattern", "research"])
        assert code == bench_agents.EXIT_NOT_MEASURED
        assert code not in (0, 1, 2)
        assert "NOT MEASURED" in capsys.readouterr().out


@pytest.mark.benchmark
class TestHookChainVerdicts:
    """bench_hooks verdicts beyond a clean pass."""

    @_needs_bash
    def test_over_budget_chain_fails(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        manifest = _hooks_json(tmp_path, {"PreToolUse": {"Write": [_DEPENDENCY_GUARD]}})
        monkeypatch.setattr(bench_hooks, "_HOOKS_JSON", manifest)
        monkeypatch.setitem(bench_hooks._BUDGETS, "PreToolUse", 0.0)

        assert bench_hooks.main(["--event=PreToolUse", "--runs=1"]) == 1

    def test_unregistered_event_is_not_measured(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        manifest = _hooks_json(tmp_path, {"PreToolUse": {"Write": [_DEPENDENCY_GUARD]}})
        monkeypatch.setattr(bench_hooks, "_HOOKS_JSON", manifest)

        code = bench_hooks.main(["--event=UserPromptSubmit"])

        assert code == bench_hooks.EXIT_NOT_MEASURED
        assert "NOT MEASURED" in capsys.readouterr().out

    @_needs_bash
    def test_command_that_cannot_run_is_an_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        missing = '"${CLAUDE_PLUGIN_ROOT}/does/not/exist.sh" PreToolUse'
        manifest = _hooks_json(tmp_path, {"PreToolUse": {"Write": [missing]}})
        monkeypatch.setattr(bench_hooks, "_HOOKS_JSON", manifest)

        assert bench_hooks.main(["--event=PreToolUse", "--runs=1"]) == 2

    @_needs_bash
    def test_handler_that_skips_itself_is_an_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The bootstrap is fail-open: with no event name it prints a diagnostic
        # envelope and exits 0. A benchmark that timed that would report a pass
        # for a handler that never ran.
        skipped = f"bash {_BOOTSTRAP}"
        manifest = _hooks_json(tmp_path, {"PreToolUse": {"Write": [skipped]}})
        monkeypatch.setattr(bench_hooks, "_HOOKS_JSON", manifest)

        assert bench_hooks.main(["--event=PreToolUse", "--runs=1"]) == 2

    @_needs_bash
    def test_invalid_hook_output_is_an_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        manifest = _hooks_json(tmp_path, {"PreToolUse": {"Write": ["echo not-json"]}})
        monkeypatch.setattr(bench_hooks, "_HOOKS_JSON", manifest)

        assert bench_hooks.main(["--event=PreToolUse", "--runs=1"]) == 2


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

    def test_bench_hooks_missing_manifest(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(bench_hooks, "_HOOKS_JSON", Path("does/not/exist.json"))
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
            """Completed-process double carrying a failing return code."""

            returncode = 2

        monkeypatch.setattr(
            bench_validate_ecosystem.subprocess, "run", lambda *a, **k: _Fake()
        )
        assert bench_validate_ecosystem.main(["--check", "option-annotation"]) == 2

    def test_bench_tests_nonzero_pytest_fails(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        class _Fake:
            """Completed-process double carrying a failing return code."""

            returncode = 1

        monkeypatch.setattr(bench_tests.subprocess, "run", lambda *a, **k: _Fake())
        assert bench_tests.main([]) == 2
