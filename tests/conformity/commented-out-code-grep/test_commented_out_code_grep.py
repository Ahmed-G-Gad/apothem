# SPDX-License-Identifier: MIT

"""Self-tests for the commented-out-code-grep validator.

Covers the fixture pair plus the C5 precision fix: a prose comment run that
trips only a single code-shape axis (an incidental English keyword or a
prose parenthetical) is no longer a false positive, while a multi-line run
of genuinely commented-out code — where each line clears at least two
distinct code-shape axes — is still flagged.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Final

_REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[3]
_GREP_PATH: Final[Path] = (
    _REPO_ROOT / "src" / "apothem" / "conformity" / "commented_out_code_grep.py"
)
_FIXTURE_DIR: Final[Path] = Path(__file__).resolve().parent


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("commented_out_code_grep", _GREP_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["commented_out_code_grep"] = module
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


# --- C5 precision: prose runs (single-axis) are not commented-out code ------


def test_prose_run_with_incidental_keywords_passes() -> None:
    # Each line trips at most one axis: a lone English keyword (`use`/`if`/
    # `from`) or a prose parenthetical `(see below)` — never two.
    body = "\n".join(
        [
            "# We use the profile (see below) to derive the config.",
            "# If the value is set, return early from the loop.",
            "# The import path for this type is documented above.",
        ]
    )
    result = _MOD.check(body, Path("note.py"))
    assert result.passed, [(f.start_line, f.end_line) for f in result.findings]


def test_prose_parenthetical_alone_is_not_a_call() -> None:
    # A space before `(` marks a prose parenthetical, not a call; the run
    # therefore never clears the two-axis bar.
    body = "\n".join(
        [
            "# This function (as noted) computes the ratio.",
            "# For each entry in the table we scan the row.",
            "# Return the summary once the scan completes here.",
        ]
    )
    result = _MOD.check(body, Path("note.py"))
    assert result.passed


# --- C5 precision: real commented-out code (multi-axis) is still flagged ----


def test_real_commented_code_block_is_flagged() -> None:
    # Every line clears two axes: assignment+call, comparison+block-colon,
    # definition-keyword+call.
    body = "\n".join(
        [
            "# response = requests.get(url, timeout=30)",
            "# if response.status_code != 200:",
            '#     raise RuntimeError(f"unexpected {response.status_code}")',
        ]
    )
    result = _MOD.check(body, Path("client.py"))
    assert not result.passed
    assert result.findings


def test_real_commented_code_with_json_load_is_flagged() -> None:
    body = "\n".join(
        [
            "# def handler(event):",
            "#     payload = json.loads(event.body)",
            "#     return respond(payload)",
        ]
    )
    result = _MOD.check(body, Path("handler.py"))
    assert not result.passed


def test_slash_comment_block_is_flagged() -> None:
    body = "\n".join(
        [
            "// const url = buildUrl(base, path);",
            "// if (response.status !== 200) {",
            "//   throw new Error(response.statusText);",
        ]
    )
    result = _MOD.check(body, Path("client.ts"))
    assert not result.passed


def test_two_line_code_run_is_below_block_threshold() -> None:
    # Two qualifying lines is under MIN_BLOCK_LINES; not a definitive block.
    body = "# x = compute(a, b)\n# y = compute(b, c)\n"
    result = _MOD.check(body, Path("calc.py"))
    assert result.passed
