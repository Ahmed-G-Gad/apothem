# SPDX-License-Identifier: MIT

"""Regression tests for the conformity-gate harness runtime-state exemption.

Background. The conformity gate is wired into ``~/.claude/settings.json`` as a
``PreToolUse`` Write/Edit hook (``python -m apothem.conformity.gate --hook``).
Its default scope is the whole ``~/.claude`` (and ``~/.codex``) harness root, so
it fired on the harness's OWN per-project state under
``~/.claude/projects/<hash>/memory/``. A ``MEMORY.md`` index there is
frontmatter-less and provenance-less by the auto-memory convention, so
``orphan-output-grep`` / ``frontmatter-grep`` flagged it and the gate exited
non-zero with the report on stdout and an empty stderr --- the harness fail-
closed the write and surfaced only "No stderr output".

These tests assert the two-part fix and its diagnostics:

1. ``_is_harness_state_path`` recognises the ``projects/`` and ``memory/``
   runtime-state subtrees under a configured scope, and rejects apothem-managed
   config subtrees (``rules/`` / ``skills/``), ``None``, and out-of-scope paths.
2. ``--hook`` mode silent-passes (exit 0, empty matcher set) on a ``MEMORY.md``
   write under the per-project tree, the global memory tier, and any path fully
   outside scope --- while still running the matcher chain (and blocking with a
   non-empty stderr diagnostic) on an apothem-managed config write.
3. ``run_orchestrator`` fails open on a matcher that raises: the error is
   recorded on the invocation rather than crashing the whole gate (no fail-
   close from one matcher's internal bug).
"""

from __future__ import annotations

import importlib.util
import io
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Final

import pytest

_REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[2]
_GATE_PATH: Final[Path] = _REPO_ROOT / "src" / "apothem" / "conformity" / "gate.py"


def _load_gate() -> ModuleType:
    """Load the gate orchestrator from the tree under test (install-independent).

    The editable install may resolve ``apothem`` to a different checkout (e.g.
    a sibling worktree's main repo), so the gate is loaded directly from the
    tree this test file lives in, mirroring the existing gate-test fixtures.
    """
    spec = importlib.util.spec_from_file_location(
        "conformity_gate_under_test", _GATE_PATH
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["conformity_gate_under_test"] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop("conformity_gate_under_test", None)
        raise
    return module


@pytest.fixture(scope="module")
def gate() -> ModuleType:
    """Return the loaded conformity-gate orchestrator module under test."""
    return _load_gate()


@pytest.fixture(autouse=True)
def _clear_scope_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure no ambient scope env var pollutes the default-scope resolution."""
    monkeypatch.delenv("APOTHEM_CONFORMITY_SCOPE", raising=False)
    monkeypatch.delenv("CODEX_HOME", raising=False)


def _run_hook(
    gate: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    file_path: str,
    content: str,
    *,
    extra_argv: tuple[str, ...] = (),
) -> tuple[int, dict, str]:
    """Drive ``gate.main(['gate', '--hook', *extra_argv])`` with a Write payload.

    Returns ``(exit_code, parsed_stdout_report, stderr)``.
    """
    payload = {
        "tool_name": "Write",
        "tool_input": {"file_path": file_path, "content": content},
    }
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    exit_code = gate.main(["gate", "--hook", *extra_argv])
    captured = capsys.readouterr()
    return exit_code, json.loads(captured.out), captured.err


# --- _is_harness_state_path unit tests --------------------------------------


def test_is_harness_state_path_recognises_project_memory_subtree(
    gate: ModuleType,
) -> None:
    scope = Path.home() / ".claude"
    target = scope / "projects" / "C--some-hash" / "memory" / "MEMORY.md"
    assert gate._is_harness_state_path(target, (scope.resolve(),)) is True


def test_is_harness_state_path_recognises_global_memory_tier(gate: ModuleType) -> None:
    scope = Path.home() / ".claude"
    target = scope / "memory" / "MEMORY.md"
    assert gate._is_harness_state_path(target, (scope.resolve(),)) is True


def test_is_harness_state_path_rejects_managed_config_subtree(gate: ModuleType) -> None:
    """apothem-managed config (rules/, skills/) is NOT exempt --- the gate runs."""
    scope = (Path.home() / ".claude").resolve()
    assert gate._is_harness_state_path(scope / "rules" / "r.md", (scope,)) is False
    assert (
        gate._is_harness_state_path(scope / "skills" / "s" / "SKILL.md", (scope,))
        is False
    )


def test_is_harness_state_path_rejects_none_and_out_of_scope(
    gate: ModuleType, tmp_path: Path
) -> None:
    scope = (Path.home() / ".claude").resolve()
    assert gate._is_harness_state_path(None, (scope,)) is False
    # A `projects/memory/` tree in an unrelated workspace (not under the
    # configured scope) is NOT exempted.
    outside = tmp_path / "projects" / "memory" / "MEMORY.md"
    assert gate._is_harness_state_path(outside, (scope,)) is False


# --- --hook end-to-end behaviour --------------------------------------------


def test_hook_silent_passes_memory_index_under_projects(
    gate: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The reported bug: a MEMORY.md write under the per-project tree no longer blocks."""
    target = str(
        Path.home() / ".claude" / "projects" / "C--hash" / "memory" / "MEMORY.md"
    )
    content = "# Memory Index\n\n- [topic](topic-file.md) - a stable fact\n"

    exit_code, report, stderr = _run_hook(gate, monkeypatch, capsys, target, content)

    assert exit_code == gate.EXIT_PASS
    assert report["passed"] is True
    assert report["grep_count"] == 0
    assert stderr == ""


def test_hook_silent_passes_global_memory_tier(
    gate: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    target = str(Path.home() / ".claude" / "memory" / "MEMORY.md")

    exit_code, report, stderr = _run_hook(
        gate, monkeypatch, capsys, target, "# Memory Index\n\n- [x](y.md) - fact\n"
    )

    assert exit_code == gate.EXIT_PASS
    assert report["grep_count"] == 0
    assert stderr == ""


def test_hook_silent_passes_path_outside_apothem_scope(
    gate: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    """A write to a path outside every configured harness root is a silent pass."""
    target = str(tmp_path / "unrelated-repo" / "MEMORY.md")

    exit_code, report, stderr = _run_hook(
        gate, monkeypatch, capsys, target, "anything\n"
    )

    assert exit_code == gate.EXIT_PASS
    assert report["grep_count"] == 0
    assert stderr == ""


def test_hook_advisory_surfaces_findings_without_blocking(
    gate: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """An in-scope managed-config write with findings is advisory by default:
    the write proceeds (exit 0) and the findings are surfaced on stderr ---
    never a silent block on the operator."""
    target = str(Path.home() / ".claude" / "rules" / "orphan-no-provenance.md")
    content = "# Plain artifact\n\nNo frontmatter, no provenance, no bindings.\n"

    exit_code, report, stderr = _run_hook(gate, monkeypatch, capsys, target, content)

    assert exit_code == gate.EXIT_PASS
    assert report["passed"] is False
    assert report["grep_count"] > 0
    assert stderr != ""
    assert "advisory" in stderr


def test_hook_strict_exits_non_zero_on_managed_config_findings(
    gate: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """With the opt-in --strict flag, the same write exits non-zero (the CI /
    pre-commit gating signal) and surfaces the reason on stderr. The shipped
    PreToolUse hook never passes --strict, so this gating bites at merge time,
    not at the runtime tool call."""
    target = str(Path.home() / ".claude" / "rules" / "orphan-no-provenance.md")
    content = "# Plain artifact\n\nNo frontmatter, no provenance, no bindings.\n"

    exit_code, report, stderr = _run_hook(
        gate, monkeypatch, capsys, target, content, extra_argv=("--strict",)
    )

    assert exit_code == gate.EXIT_FAIL
    assert report["passed"] is False
    assert report["grep_count"] > 0
    assert "exits non-zero" in stderr
    assert "fail the CI / pre-commit step" in stderr
    # The strict summary must NOT claim a runtime write was blocked --- the
    # shipped advisory wiring never blocks the tool call.
    assert "blocked the write" not in stderr


# --- fail-open isolation -----------------------------------------------------


def test_run_orchestrator_fails_open_on_matcher_error(
    gate: ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A matcher that raises is recorded as a fail-open invocation, not a crash."""
    original = gate._load_check

    def patched(name: str):  # type: ignore[no-untyped-def]
        if name == "orphan_output_grep":

            def _boom(content: str, path: Path | None = None):  # type: ignore[no-untyped-def]
                raise RuntimeError("simulated matcher bug")

            return _boom
        return original(name)

    monkeypatch.setattr(gate, "_load_check", patched)

    report = gate.run_orchestrator(
        "# x\n", tmp_path / "x.md", only="orphan_output_grep"
    )

    assert report.grep_count == 1
    invocation = report.invocations[0]
    assert invocation.grep == "orphan_output_grep"
    assert invocation.passed is True
    assert invocation.error is not None
    assert "simulated matcher bug" in invocation.error
    assert report.passed is True
