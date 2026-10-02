# SPDX-License-Identifier: MIT

"""Cohort-wide advisory exit-contract test.

The conformity gate classifies a standalone validator as *advisory* when its
``to_json()`` payload declares ``"advisory": true`` (``gate._advisory_verdict``).
The gate's contract for that class is explicit (``gate._run_all`` docstring):

    Advisory validators exit 0 even when they report findings, so the overall
    gate stays green; their inner verdict is surfaced per-validator ...

An advisory validator that exits non-zero on findings breaks that contract: the
``gate --all`` run flips to a FAIL the orchestrator never intended, because the
verdict is meant to ride the JSON ``passed`` field, not the process exit code.

This test enumerates every advisory validator dynamically — no hand-maintained
list — and asserts that each one's ``_main`` exits ``EXIT_PASS`` even when its
``check`` reports findings. The enumeration walks ``gate.STANDALONE_MODULES`` and
selects the modules whose ``GrepResult.to_json`` emits the advisory flag, so a
newly-added advisory validator is covered automatically and a regression (an
advisory validator wired to exit 2 on findings) fails here.
"""

from __future__ import annotations

import importlib
import inspect
import json
from pathlib import Path
from types import ModuleType
from typing import ClassVar

import pytest

from apothem.conformity import gate


def _emits_advisory_flag(module: ModuleType) -> bool:
    """Return True iff the module's ``GrepResult.to_json`` declares advisory:true.

    The advisory posture is expressed as a literal ``"advisory": True`` entry in
    the payload dict built inside ``to_json`` — the same shape
    ``gate._advisory_verdict`` reads at runtime. Inspecting the source is a
    static, side-effect-free way to classify the validator without a root walk.
    """
    grep_result = getattr(module, "GrepResult", None)
    to_json = getattr(grep_result, "to_json", None)
    if to_json is None:
        return False
    try:
        src = inspect.getsource(to_json)
    except (OSError, TypeError):
        return False
    return '"advisory": True' in src or "'advisory': True" in src


def _advisory_modules() -> list[str]:
    """Enumerate the underscored module names of every advisory standalone."""
    names: list[str] = []
    for canonical in gate.STANDALONE_MODULES:
        module_name = canonical.replace("-", "_")
        try:
            module = importlib.import_module(f"apothem.conformity.{module_name}")
        except ImportError:
            continue
        if _emits_advisory_flag(module):
            names.append(module_name)
    return names


_ADVISORY_MODULES = _advisory_modules()


class _FailingResult:
    """Minimal stand-in whose ``to_json`` mimics a failing advisory verdict.

    ``_main`` on an advisory validator only consumes ``result.to_json()``; the
    verdict must travel in the JSON, never the exit code. This stand-in carries a
    ``passed: false`` advisory payload with a non-empty ``findings`` list so the
    test proves the exit-0 contract holds *with findings present*, not just on a
    clean run.
    """

    passed: ClassVar[bool] = False
    # A scan that reports findings has inspected targets; each advisory
    # validator reads its own count field, so the stub carries all of them.
    files_inspected: ClassVar[int] = 1
    folders_inspected: ClassVar[int] = 1

    def to_json(self) -> str:
        return json.dumps(
            {
                "grep": "stub",
                "passed": False,
                "findings": [{"detail": "planted advisory finding"}],
                "advisory": True,
            }
        )


def test_advisory_cohort_is_non_empty() -> None:
    """The enumeration finds the known advisory validators.

    A guard against a silent regression where the detection heuristic stops
    matching (e.g. the payload key is renamed) and the parametrized test below
    would otherwise vacuously pass with zero cases.
    """
    assert "freshness_token_grep" in _ADVISORY_MODULES
    assert "reference_token_grep" in _ADVISORY_MODULES
    assert "agents_md_coverage_grep" in _ADVISORY_MODULES


@pytest.mark.parametrize("module_name", _ADVISORY_MODULES)
def test_advisory_main_exits_zero_on_findings(
    module_name: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    """Each advisory validator's ``_main`` exits 0 even when findings are present."""
    module = importlib.import_module(f"apothem.conformity.{module_name}")
    assert hasattr(module, "_main"), f"{module_name} exposes no _main entry point"

    # Force the sweep to report findings without depending on a per-validator
    # fixture: the advisory ``_main`` reads only ``result.to_json()``.
    def _failing_check(*_args: object, **_kwargs: object) -> _FailingResult:
        return _FailingResult()

    monkeypatch.setattr(module, "check", _failing_check)

    exit_code = module._main([module_name, str(tmp_path)])
    assert exit_code == module.EXIT_PASS, (
        f"{module_name}._main returned {exit_code} on findings; advisory "
        f"validators must exit EXIT_PASS ({module.EXIT_PASS}) per the gate's "
        f"advisory contract (gate._run_all: 'Advisory validators exit 0 even "
        f"when they report findings')"
    )

    # The verdict must ride the JSON: advisory:true with the failing inner
    # verdict, exactly the shape gate._advisory_verdict consumes.
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert payload["advisory"] is True
    assert payload["passed"] is False
    assert payload["findings"], "advisory findings must be surfaced in the JSON"
