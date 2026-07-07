# SPDX-License-Identifier: MIT

"""Self-tests for the unpinned-action-grep validator."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Final

_REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[3]
_GREP_PATH: Final[Path] = (
    _REPO_ROOT / "src" / "apothem" / "conformity" / "unpinned_action_grep.py"
)
_FIXTURE_DIR: Final[Path] = Path(__file__).resolve().parent


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("unpinned_action_grep", _GREP_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["unpinned_action_grep"] = module
    spec.loader.exec_module(module)
    return module


_MOD: Final[ModuleType] = _load()
_PASS_BODY: Final[str] = (_FIXTURE_DIR / "pass.yml").read_text(encoding="utf-8")
_FAIL_BODY: Final[str] = (_FIXTURE_DIR / "fail.yml").read_text(encoding="utf-8")


def test_pass_fixture_passes() -> None:
    result = _MOD.check(_PASS_BODY, _FIXTURE_DIR / "pass.yml")
    assert result.passed
    assert result.findings == []


def test_fail_fixture_flags_floating_tag_refs() -> None:
    result = _MOD.check(_FAIL_BODY, _FIXTURE_DIR / "fail.yml")
    assert not result.passed
    flagged_refs = {f.ref for f in result.findings}
    # Includes major-tag, branch, latest, and semver-pinned non-SHA forms.
    assert "v4" in flagged_refs
    assert "main" in flagged_refs
    assert "latest" in flagged_refs


def test_local_action_path_is_exempt() -> None:
    body = "jobs:\n  build:\n    steps:\n      - uses: ./local/action\n"
    result = _MOD.check(body)
    assert result.passed


def test_inline_exemption_marker_honoured() -> None:
    body = (
        "jobs:\n"
        "  release:\n"
        "    steps:\n"
        "      - uses: slsa-framework/slsa-github-generator/.github/workflows/generator_generic_slsa3.yml@v2.0.0  # action-pinning-exempt: SLSA reusable workflow trust-anchored on per-tag attestation\n"
    )
    result = _MOD.check(body)
    assert result.passed


def test_inline_exemption_without_reason_is_not_honoured() -> None:
    body = (
        "jobs:\n"
        "  release:\n"
        "    steps:\n"
        "      - uses: actions/checkout@v4  # action-pinning-exempt:\n"
    )
    result = _MOD.check(body)
    assert not result.passed


def test_action_with_subpath_is_recognised() -> None:
    body = (
        "jobs:\n"
        "  build:\n"
        "    steps:\n"
        "      - uses: actions/cache/save@b4ffde65f46336ab88eb53be808477a3936bae11\n"
    )
    result = _MOD.check(body)
    assert result.passed


def test_finding_records_action_and_ref_per_occurrence() -> None:
    result = _MOD.check(_FAIL_BODY, _FIXTURE_DIR / "fail.yml")
    actions = {f.action for f in result.findings}
    assert "actions/checkout" in actions
    assert "actions/setup-python" in actions


def test_clean_workflow_with_only_run_steps_passes() -> None:
    body = (
        "jobs:\n"
        "  test:\n"
        "    steps:\n"
        "      - run: pytest -q\n"
        "      - run: ruff check .\n"
    )
    result = _MOD.check(body)
    assert result.passed
