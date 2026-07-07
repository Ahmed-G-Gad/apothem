# SPDX-License-Identifier: MIT

"""Self-tests for the bare-except-grep validator.

Covers the fixture pair (`pass.py` passes, `fail.py` is flagged) plus the
inline-re-raise regression: a broad ``except`` whose re-raise sits inline on
the ``except`` line itself (``except Exception: raise``) is a faithful
re-raise, not a swallow, and must not be flagged.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Final

_REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[3]
_GREP_PATH: Final[Path] = (
    _REPO_ROOT / "src" / "apothem" / "conformity" / "bare_except_grep.py"
)
_FIXTURE_DIR: Final[Path] = Path(__file__).resolve().parent


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("bare_except_grep", _GREP_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["bare_except_grep"] = module
    spec.loader.exec_module(module)
    return module


_MOD: Final[ModuleType] = _load()
_PASS_BODY: Final[str] = (_FIXTURE_DIR / "pass.py").read_text(encoding="utf-8")
_FAIL_BODY: Final[str] = (_FIXTURE_DIR / "fail.py").read_text(encoding="utf-8")


def test_pass_fixture_passes() -> None:
    result = _MOD.check(_PASS_BODY, _FIXTURE_DIR / "pass.py")
    assert result.passed
    assert result.findings == []


def test_fail_fixture_is_flagged() -> None:
    result = _MOD.check(_FAIL_BODY, _FIXTURE_DIR / "fail.py")
    assert not result.passed
    assert result.findings


def test_inline_reraise_is_not_flagged() -> None:
    # Regression: the re-raise sits inline on the `except` line itself.
    body = "try:\n    work()\nexcept Exception: raise\n"
    result = _MOD.check(body)
    assert result.passed
    assert result.findings == []


def test_inline_reraise_after_statement_is_not_flagged() -> None:
    body = "try:\n    work()\nexcept Exception: log(); raise\n"
    result = _MOD.check(body)
    assert result.passed


def test_multiline_reraise_is_not_flagged() -> None:
    body = "try:\n    work()\nexcept Exception:\n    raise\n"
    result = _MOD.check(body)
    assert result.passed


def test_inline_swallow_is_flagged() -> None:
    # A broad except whose inline body is not a re-raise is still a swallow.
    body = "try:\n    work()\nexcept Exception: return None\n"
    result = _MOD.check(body)
    assert not result.passed


def test_bare_except_with_inline_raise_is_still_flagged() -> None:
    # A bare `except:` is always a finding regardless of an inline re-raise.
    body = "try:\n    work()\nexcept: raise\n"
    result = _MOD.check(body)
    assert not result.passed


def test_broad_tuple_without_reraise_is_flagged() -> None:
    # Regression: a broad type inside a tuple (`except (ValueError, Exception):`)
    # is a broad swallow, not a narrow catch.
    body = "try:\n    work()\nexcept (ValueError, Exception):\n    return None\n"
    result = _MOD.check(body)
    assert not result.passed
    assert result.findings


def test_broad_tuple_with_reraise_is_not_flagged() -> None:
    body = "try:\n    work()\nexcept (ValueError, Exception):\n    raise\n"
    result = _MOD.check(body)
    assert result.passed


def test_broad_tuple_with_as_binding_is_flagged() -> None:
    body = (
        "try:\n    work()\nexcept (OSError, BaseException) as err:\n    return None\n"
    )
    result = _MOD.check(body)
    assert not result.passed


def test_narrow_tuple_is_not_flagged() -> None:
    # A tuple with no broad root type is a precise catch and is permitted.
    body = "try:\n    work()\nexcept (ValueError, KeyError):\n    return None\n"
    result = _MOD.check(body)
    assert result.passed
    assert result.findings == []


# --- C5: multi-line tuple clauses ------------------------------------------


def test_multiline_broad_tuple_without_reraise_is_flagged() -> None:
    body = (
        "try:\n    work()\nexcept (\n    ValueError,\n"
        "    Exception,\n):\n    return None\n"
    )
    result = _MOD.check(body)
    assert not result.passed
    assert result.findings
    assert result.findings[0].line == 3  # the opening `except (` line


def test_multiline_broad_tuple_with_reraise_is_not_flagged() -> None:
    body = (
        "try:\n    work()\nexcept (\n    ValueError,\n    Exception,\n):\n    raise\n"
    )
    result = _MOD.check(body)
    assert result.passed


def test_multiline_narrow_tuple_is_not_flagged() -> None:
    body = (
        "try:\n    work()\nexcept (\n    ValueError,\n"
        "    KeyError,\n):\n    return None\n"
    )
    result = _MOD.check(body)
    assert result.passed
    assert result.findings == []


# --- C5: PEP 654 except* exception groups -----------------------------------


def test_except_star_broad_without_reraise_is_flagged() -> None:
    body = "try:\n    work()\nexcept* Exception:\n    return None\n"
    result = _MOD.check(body)
    assert not result.passed


def test_except_star_broad_with_reraise_is_not_flagged() -> None:
    body = "try:\n    work()\nexcept* Exception:\n    raise\n"
    result = _MOD.check(body)
    assert result.passed


def test_bare_except_star_is_flagged() -> None:
    body = "try:\n    work()\nexcept*:\n    pass\n"
    result = _MOD.check(body)
    assert not result.passed


# --- C5: `except:` quoted inside a string is not a clause -------------------


def test_except_inside_single_line_string_is_not_flagged() -> None:
    body = 'msg = "prefer a typed except: over a bare one"\n'
    result = _MOD.check(body)
    assert result.passed
    assert result.findings == []


def test_except_inside_triple_quoted_string_is_not_flagged() -> None:
    body = 'DOC = """\nexcept Exception:\n    return None\n"""\n'
    result = _MOD.check(body)
    assert result.passed


def test_real_clause_after_string_mention_is_still_flagged() -> None:
    # The string mention is ignored, but a real bare clause below still fires.
    body = 'note = "an except: example"\ntry:\n    work()\nexcept:\n    pass\n'
    result = _MOD.check(body)
    assert not result.passed
    assert any(f.form == "bare except:" for f in result.findings)
