# SPDX-License-Identifier: MIT

"""Behavioral pass+fail coverage for the semver-stability matcher.

The matcher's public-surface comparison (``compare_surfaces`` over the
inventories from ``extract_public_surface``) is version-independent and
carries the breaking-change logic; the v1.0.0 gate sits above it. These
tests drive that core directly: a stable surface produces zero findings,
an unstable surface (removed symbol / added required parameter / dropped
``__all__`` entry) produces findings. A separate test confirms the
``--staged`` path swallows a git ``TimeoutExpired`` rather than raising,
using the ``GIT_TIMEOUT_SECONDS`` bound the module added.

The cohort-contract tests assert the package exit/payload shape the matcher
was brought onto: a JSON ``GrepResult`` payload on stdout, ``EXIT_FAIL == 2``
(not the legacy ``1``) on findings, ``EXIT_PASS == 0`` on a clean surface,
and the ``_main(argv)`` entry point.
"""

from __future__ import annotations

import dataclasses
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Final, NoReturn

import pytest

_REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[3]
_GREP_PATH: Final[Path] = (
    _REPO_ROOT / "src" / "apothem" / "conformity" / "semver_stability_grep.py"
)


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("semver_stability_grep", _GREP_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["semver_stability_grep"] = module
    spec.loader.exec_module(module)
    return module


_MOD: Final[ModuleType] = _load()

_STABLE_SRC: Final[str] = "\n".join(
    [
        "__all__ = ['public_fn', 'PublicClass']",
        "",
        "def public_fn(a, b=1):",
        "    return a + b",
        "",
        "class PublicClass:",
        "    def method(self):",
        "        return 1",
    ]
)


def test_identical_surface_passes() -> None:
    old = _MOD.extract_public_surface(_STABLE_SRC)
    new = _MOD.extract_public_surface(_STABLE_SRC)
    assert old is not None
    assert new is not None
    findings = _MOD.compare_surfaces(old, new, "src/apothem/x.py")
    assert findings == []


def test_backward_compatible_addition_passes() -> None:
    # Adding an optional-defaulted parameter and a new function is not breaking.
    new_src = (
        _STABLE_SRC.replace("def public_fn(a, b=1):", "def public_fn(a, b=1, c=2):")
        + "\n\ndef brand_new_fn():\n    return 0\n"
    )
    old = _MOD.extract_public_surface(_STABLE_SRC)
    new = _MOD.extract_public_surface(new_src)
    assert old is not None
    assert new is not None
    findings = _MOD.compare_surfaces(old, new, "src/apothem/x.py")
    assert findings == []


def test_removed_public_function_fails() -> None:
    new_src = _STABLE_SRC.replace("def public_fn(a, b=1):\n    return a + b\n", "")
    old = _MOD.extract_public_surface(_STABLE_SRC)
    new = _MOD.extract_public_surface(new_src)
    assert old is not None
    assert new is not None
    findings = _MOD.compare_surfaces(old, new, "src/apothem/x.py")
    assert findings, "removing a public function must be a breaking change"
    assert any("public_fn" in f.message and "removed" in f.message for f in findings)


def test_added_required_parameter_fails() -> None:
    new_src = _STABLE_SRC.replace("def public_fn(a, b=1):", "def public_fn(a, z, b=1):")
    old = _MOD.extract_public_surface(_STABLE_SRC)
    new = _MOD.extract_public_surface(new_src)
    assert old is not None
    assert new is not None
    findings = _MOD.compare_surfaces(old, new, "src/apothem/x.py")
    assert findings
    assert any("required parameter" in f.message for f in findings)


def test_removed_all_entry_fails() -> None:
    new_src = _STABLE_SRC.replace(
        "__all__ = ['public_fn', 'PublicClass']", "__all__ = ['public_fn']"
    )
    old = _MOD.extract_public_surface(_STABLE_SRC)
    new = _MOD.extract_public_surface(new_src)
    assert old is not None
    assert new is not None
    findings = _MOD.compare_surfaces(old, new, "src/apothem/x.py")
    assert findings
    assert any("__all__" in f.message for f in findings)


def test_check_staged_handles_git_timeout_gracefully(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Force the v1.0.0 gate open so check_staged reaches the git call,
    # then make the git invocation raise TimeoutExpired. The module's
    # timeout=GIT_TIMEOUT_SECONDS bound must be caught, not propagated.
    monkeypatch.setattr(_MOD, "current_version", lambda: "1.2.3")

    def _raise_timeout(*args: object, **kwargs: object) -> NoReturn:
        assert kwargs.get("timeout") == _MOD.GIT_TIMEOUT_SECONDS
        raise subprocess.TimeoutExpired(cmd="git", timeout=_MOD.GIT_TIMEOUT_SECONDS)

    monkeypatch.setattr(_MOD.subprocess, "run", _raise_timeout)
    # Must not raise; the matcher degrades to an empty finding list.
    assert _MOD.check_staged() == []


def test_exit_constants_follow_the_cohort_contract() -> None:
    # The cohort exit contract is EXIT_PASS == 0, EXIT_FAIL == 2 — the legacy
    # `return 1` on findings is retired.
    assert _MOD.EXIT_PASS == 0
    assert _MOD.EXIT_FAIL == 2


def test_grep_result_emits_json_payload() -> None:
    findings = [_MOD.Finding("HIGH", "M15", "src/apothem/x.py", "removed foo")]
    result = _MOD.GrepResult(grep=_MOD.GREP_NAME, passed=False, findings=findings)
    payload = json.loads(result.to_json())
    assert payload["grep"] == "semver-stability-grep"
    assert payload["passed"] is False
    assert payload["findings"][0]["severity"] == "HIGH"
    assert payload["findings"][0]["message"] == "removed foo"


def test_dataclasses_are_frozen() -> None:
    # The Finding and PublicSurface dataclasses are frozen per the cohort
    # convention; mutating an instance raises FrozenInstanceError.
    finding = _MOD.Finding("HIGH", "M15", "src/apothem/x.py", "msg")
    with pytest.raises(dataclasses.FrozenInstanceError):
        finding.severity = "LOW"  # type: ignore[misc]


def test_main_exits_fail_two_on_findings(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # `_main(argv)` on the --staged path emits a JSON GrepResult and exits
    # EXIT_FAIL (2), not the legacy plain-text-to-stderr `return 1`.
    monkeypatch.setattr(
        _MOD,
        "check_staged",
        lambda: [_MOD.Finding("HIGH", "M15", "src/apothem/x.py", "removed foo")],
    )
    exit_code = _MOD._main(["semver_stability_grep", "--staged"])
    assert exit_code == _MOD.EXIT_FAIL
    payload = json.loads(capsys.readouterr().out)
    assert payload["passed"] is False
    assert payload["findings"]


def test_main_exits_pass_zero_on_clean_surface(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(_MOD, "check_staged", list)
    exit_code = _MOD._main(["semver_stability_grep", "--staged"])
    assert exit_code == _MOD.EXIT_PASS
    payload = json.loads(capsys.readouterr().out)
    assert payload["passed"] is True
    assert payload["findings"] == []


def test_async_function_stored_in_surface() -> None:
    # An async public coroutine is inventoried under functions; the widened
    # dict[str, FunctionDef | AsyncFunctionDef] type covers it.
    src = "async def public_coro():\n    return 1\n"
    surface = _MOD.extract_public_surface(src)
    assert surface is not None
    assert "public_coro" in surface.functions
