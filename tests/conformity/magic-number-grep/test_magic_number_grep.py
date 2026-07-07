# SPDX-License-Identifier: MIT

"""Self-tests for the magic-number-grep validator."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Final

_REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[3]
_GREP_PATH: Final[Path] = (
    _REPO_ROOT / "src" / "apothem" / "conformity" / "magic_number_grep.py"
)
_FIXTURE_DIR: Final[Path] = Path(__file__).resolve().parent


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("magic_number_grep", _GREP_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["magic_number_grep"] = module
    spec.loader.exec_module(module)
    return module


_MOD: Final[ModuleType] = _load()
_PASS_BODY: Final[str] = (_FIXTURE_DIR / "pass.py").read_text(encoding="utf-8")
_FAIL_BODY: Final[str] = (_FIXTURE_DIR / "fail.py").read_text(encoding="utf-8")


def test_pass_fixture_passes() -> None:
    result = _MOD.check(_PASS_BODY, _FIXTURE_DIR / "pass.py")
    assert result.passed
    assert result.findings == []


def test_fail_fixture_flags_repeated_unnamed_literals() -> None:
    result = _MOD.check(_FAIL_BODY, _FIXTURE_DIR / "fail.py")
    assert not result.passed
    flagged_values = {f.value for f in result.findings}
    assert "30" in flagged_values


def test_markdown_path_is_skipped() -> None:
    result = _MOD.check(_FAIL_BODY, Path("README.md"))
    assert result.passed


def test_yaml_path_is_skipped() -> None:
    result = _MOD.check(_FAIL_BODY, Path("config.yaml"))
    assert result.passed


def test_toml_path_is_skipped() -> None:
    result = _MOD.check(_FAIL_BODY, Path("pyproject.toml"))
    assert result.passed


def test_json_path_is_skipped() -> None:
    result = _MOD.check(_FAIL_BODY, Path("settings.json"))
    assert result.passed


def test_srcinfo_basename_is_skipped() -> None:
    result = _MOD.check(_FAIL_BODY, Path(".SRCINFO"))
    assert result.passed


def test_finding_records_every_occurrence_line() -> None:
    result = _MOD.check(_FAIL_BODY, _FIXTURE_DIR / "fail.py")
    assert not result.passed
    finding_30 = next(f for f in result.findings if f.value == "30")
    assert len(finding_30.occurrences) >= 2


# --- C5: base-prefixed literals match as whole literals (docstring truth-up)


def test_hex_literal_matches_whole_value() -> None:
    body = "mask = 0xFF\nother = compute(0xFF)\n"
    result = _MOD.check(body, Path("bits.py"))
    assert not result.passed
    assert "0xFF" in {f.value for f in result.findings}


def test_binary_literal_matches_whole_value() -> None:
    body = "flags = 0b1010\nmore = 0b1010\n"
    result = _MOD.check(body, Path("bits.py"))
    assert "0b1010" in {f.value for f in result.findings}


def test_octal_literal_matches_whole_value() -> None:
    body = "mode = 0o17\nalso = 0o17\n"
    result = _MOD.check(body, Path("bits.py"))
    assert "0o17" in {f.value for f in result.findings}


def test_hex_literal_not_split_into_bare_zero() -> None:
    # Regression: the prior pattern captured only the leading `0` of `0xFF`.
    body = "a = 0xFF\nb = 0xFF\n"
    result = _MOD.check(body, Path("bits.py"))
    assert "0" not in {f.value for f in result.findings}


# --- C5: binary-minus symmetry ---------------------------------------------


def test_binary_minus_is_symmetric_across_spacing() -> None:
    spaced = "a = x - 30\nb = y - 30\n"
    tight = "a = x-30\nb = y-30\n"
    spaced_values = {f.value for f in _MOD.check(spaced, Path("s.py")).findings}
    tight_values = {f.value for f in _MOD.check(tight, Path("t.py")).findings}
    assert spaced_values == tight_values == {"30"}


def test_unary_sign_is_preserved() -> None:
    body = "a = -30\nb = -30\n"
    result = _MOD.check(body, Path("neg.py"))
    assert "-30" in {f.value for f in result.findings}


def test_unary_keyword_context_keeps_sign() -> None:
    body = "def f():\n    return -30\n\ndef g():\n    return -30\n"
    result = _MOD.check(body, Path("neg.py"))
    assert "-30" in {f.value for f in result.findings}
