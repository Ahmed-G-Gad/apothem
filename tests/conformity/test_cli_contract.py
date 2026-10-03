# SPDX-License-Identifier: MIT

"""Command-line contract shared by every conformity entry point.

Every module under ``apothem.conformity`` that runs as a script answers
``--help`` with usage text and exit 0, and treats an unknown flag as a usage
error: a one-line message and exit 3 (``EXIT_USAGE``), never a traceback.
Every standalone (root-based) validator treats a root that does not exist as
the same usage error, resolves a relative root exactly like its absolute form,
and reports how many targets it inspected; a validator that inspected nothing
cannot pass unless it declares that an empty scope is expected.

The ``--help`` / unknown-flag sweep runs each module in-process through
``runpy`` (fast); the gate's own process-level behaviour, which the CI and the
pre-commit hooks see, is pinned with real subprocesses.
"""

from __future__ import annotations

import io
import json
import os
import runpy
import subprocess
import sys
from pathlib import Path

import pytest

from apothem.conformity import _grep_base, gate

_REPO_ROOT = Path(__file__).resolve().parents[2]
_CONFORMITY_DIR = _REPO_ROOT / "src" / "apothem" / "conformity"

# Every conformity module that runs as a script. ``gate`` is pinned separately
# with subprocesses because its ``__main__`` block reconfigures the process
# streams, which an in-process run would apply to pytest's capture.
_SCRIPT_MODULES: tuple[str, ...] = tuple(
    sorted(
        path.stem
        for path in _CONFORMITY_DIR.glob("*.py")
        if path.stem != "gate"
        and 'if __name__ == "__main__"' in path.read_text(encoding="utf-8")
    )
)

# Standalone validators whose empty scope is legitimate on a clean checkout:
# plan suites live under the gitignored ``.apothem/plans/`` tree.
_EMPTY_SCOPE_EXPECTED_ON_CHECKOUT: frozenset[str] = frozenset(
    {"plan-suite-structure-grep", "plan-next-step-consistency-grep"}
)


def _run_module(module: str, args: list[str], monkeypatch: pytest.MonkeyPatch) -> int:
    """Run ``apothem.conformity.<module>`` as ``__main__``; return its exit code."""
    monkeypatch.setattr(sys, "argv", [module, *args])
    monkeypatch.setattr(sys, "stdin", io.StringIO(""))
    # Drop a cached import so runpy executes a fresh copy as ``__main__``.
    monkeypatch.delitem(sys.modules, f"apothem.conformity.{module}", raising=False)
    try:
        runpy.run_module(f"apothem.conformity.{module}", run_name="__main__")
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 0
    return 0  # a module whose __main__ returned without exiting


def _gate(*args: str, cwd: Path = _REPO_ROOT) -> subprocess.CompletedProcess[str]:
    """Run the gate as a real process, the way CI and pre-commit invoke it."""
    env = dict(os.environ, PYTHONPATH=str(_REPO_ROOT / "src"))
    env.pop("APOTHEM_CONFORMITY_STRICT", None)
    return subprocess.run(
        [sys.executable, "-m", "apothem.conformity.gate", *args],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
        timeout=600,
    )


def test_script_modules_discovered() -> None:
    """The sweep sees every scripted matcher, not an empty set."""
    assert len(_SCRIPT_MODULES) >= 50


@pytest.mark.parametrize("module", _SCRIPT_MODULES)
def test_help_prints_usage_and_exits_zero(
    module: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``--help`` prints usage text and exits 0 (never a traceback or a scan)."""
    code = _run_module(module, ["--help"], monkeypatch)
    out = capsys.readouterr().out
    assert code == 0
    assert out.lower().startswith("usage:")


@pytest.mark.parametrize("module", _SCRIPT_MODULES)
def test_unknown_flag_is_a_usage_error(
    module: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """An unknown flag exits ``EXIT_USAGE`` with a one-line error on stderr."""
    code = _run_module(module, ["--no-such-flag"], monkeypatch)
    err = capsys.readouterr().err
    assert code == _grep_base.EXIT_USAGE
    assert "--no-such-flag" in err


@pytest.mark.parametrize("name", gate.STANDALONE_MODULES)
def test_standalone_missing_root_is_a_usage_error(
    name: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    """A standalone validator handed a nonexistent root exits ``EXIT_USAGE``.

    A typo'd path in a CI step or a pre-commit hook must not read as a pass.
    """
    missing = tmp_path / "no-such-dir"
    code = _run_module(name.replace("-", "_"), [str(missing)], monkeypatch)
    capsys.readouterr()
    assert code == _grep_base.EXIT_USAGE


def test_gate_help_exits_zero() -> None:
    """``gate --help`` prints usage and exits 0."""
    completed = _gate("--help")
    assert completed.returncode == 0
    assert completed.stdout.lower().startswith("usage:")
    assert "Traceback" not in completed.stderr


@pytest.mark.parametrize(
    "args",
    [
        pytest.param(("--bogus",), id="unknown-flag"),
        pytest.param((".",), id="directory-as-file"),
        pytest.param(("no/such/file.md",), id="missing-file"),
        pytest.param(
            ("--check", "hedging-grep", "no/such/file.md"), id="check-missing-file"
        ),
        pytest.param(("--all", "no/such/dir"), id="all-missing-root"),
        pytest.param(("--all-perwrite", "no/such/dir"), id="all-perwrite-missing-root"),
        pytest.param(
            ("--check", "naming-grep", "no/such/dir"), id="standalone-missing-root"
        ),
        pytest.param(("--list", "--all"), id="conflicting-modes"),
    ],
)
def test_gate_usage_errors_exit_three_without_traceback(args: tuple[str, ...]) -> None:
    """Every gate usage error exits 3 with a message and no traceback."""
    completed = _gate(*args)
    assert completed.returncode == gate.EXIT_USAGE, completed.stderr
    assert "Traceback" not in completed.stderr
    assert completed.stderr.strip()


def test_gate_all_missing_root_lists_no_passing_validator() -> None:
    """``gate --all <missing> --strict`` passes nothing: it is a usage error."""
    completed = _gate("--all", "/no/such/dir", "--strict")
    assert completed.returncode == gate.EXIT_USAGE
    assert '"passed": true' not in completed.stdout


@pytest.fixture(scope="module")
def all_report() -> dict[str, object]:
    """One ``gate --all .`` run from the repository root (the CI form)."""
    completed = _gate("--all", ".")
    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert isinstance(payload, dict)
    return payload


def _results(report: dict[str, object]) -> dict[str, dict[str, object]]:
    results = report["results"]
    assert isinstance(results, list)
    return {str(entry["validator"]): entry for entry in results}


def test_gate_all_resolves_relative_root(all_report: dict[str, object]) -> None:
    """``--all .`` reports the absolute repository root it actually scanned."""
    assert all_report["root"] == str(_REPO_ROOT)


@pytest.mark.parametrize("name", gate.STANDALONE_MODULES)
def test_gate_all_reports_inspected_count(
    name: str, all_report: dict[str, object]
) -> None:
    """Every standalone validator reports ``inspected: N`` with N > 0 here.

    Only the plan-suite validators may inspect nothing on a clean checkout,
    and they must say so (``empty_scope_expected``) rather than pass silently.
    """
    entry = _results(all_report)[name]
    inspected = entry.get("inspected")
    assert isinstance(inspected, int), entry
    if name in _EMPTY_SCOPE_EXPECTED_ON_CHECKOUT and inspected == 0:
        assert entry.get("empty_scope_expected") is True
    else:
        assert inspected > 0, entry


def test_naming_grep_inspects_components_from_relative_root(
    all_report: dict[str, object],
) -> None:
    """The CI form ``gate --all .`` makes naming-grep walk the corpus."""
    entry = _results(all_report)["naming-grep"]
    output = json.loads(str(entry["output"]))
    assert output["components_inspected"] > 0


def test_relative_and_absolute_roots_agree(tmp_path: Path) -> None:
    """``--check <v> .`` and ``--check <v> <abs>`` inspect the same targets."""
    relative = _gate("--check", "naming-grep", ".")
    absolute = _gate("--check", "naming-grep", str(_REPO_ROOT))
    rel_payload = json.loads(relative.stdout)
    abs_payload = json.loads(absolute.stdout)
    assert rel_payload["inspected"] == abs_payload["inspected"] > 0


def test_empty_root_is_not_a_pass(tmp_path: Path) -> None:
    """A validator that inspected nothing reports a failure, not a pass."""
    completed = _gate("--check", "agnosticism-grep", str(tmp_path), "--strict")
    payload = json.loads(completed.stdout)
    assert payload["inspected"] == 0
    assert payload["passed"] is False
    assert payload["empty_scope_expected"] is False
    assert completed.returncode == gate.EXIT_FAIL


def test_declared_empty_scope_still_passes(tmp_path: Path) -> None:
    """A validator whose empty scope is documented passes and says so."""
    completed = _gate("--check", "plan-suite-structure-grep", str(tmp_path), "--strict")
    payload = json.loads(completed.stdout)
    assert payload["inspected"] == 0
    assert payload["empty_scope_expected"] is True
    assert payload["passed"] is True
    assert completed.returncode == gate.EXIT_PASS
