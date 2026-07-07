# SPDX-License-Identifier: MIT

"""Unit tests for ``tools.lib.reporter.Reporter``."""

from __future__ import annotations

import io
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_TOOLS_LIB = _REPO_ROOT / "src" / "apothem" / "lib"
if str(_TOOLS_LIB) not in sys.path:
    sys.path.insert(0, str(_TOOLS_LIB))

from reporter import Reporter  # noqa: E402


@pytest.fixture
def rep() -> Reporter:
    return Reporter(stream=io.StringIO())


def test_ok_increments_passed_and_emits_pass_marker(rep: Reporter) -> None:
    rep.ok("alpha")

    assert rep.passed == 1
    assert rep.failed == 0
    assert rep.warned == 0
    assert "[PASS] alpha" in rep.stream.getvalue()


def test_fail_increments_failed_records_error_and_emits_fail_marker(
    rep: Reporter,
) -> None:
    rep.fail("boom")

    assert rep.failed == 1
    assert rep.errors == ["boom"]
    assert "[FAIL] boom" in rep.stream.getvalue()


def test_warn_and_info_do_not_affect_pass_fail_counters(
    rep: Reporter,
) -> None:
    rep.warn("caution")
    rep.info("note")

    assert rep.warned == 1
    assert rep.passed == 0
    assert rep.failed == 0
    text = rep.stream.getvalue()
    assert "[WARN] caution" in text
    assert "[INFO] note" in text


def test_section_writes_bracketed_header(rep: Reporter) -> None:
    rep.section("Header")

    assert "\n=== Header ===" in rep.stream.getvalue()


def test_summary_lists_all_three_counters(rep: Reporter) -> None:
    rep.ok("a")
    rep.ok("b")
    rep.fail("c")
    rep.warn("d")

    rep.summary()

    text = rep.stream.getvalue()
    assert "Passed: 2" in text
    assert "Failed: 1" in text
    assert "Warnings: 1" in text


def test_exit_code_zero_when_no_failures(rep: Reporter) -> None:
    rep.ok("a")
    rep.warn("b")

    assert rep.exit_code == 0


def test_exit_code_nonzero_after_failure(rep: Reporter) -> None:
    rep.ok("a")
    rep.fail("b")

    assert rep.exit_code == 1


def test_multiple_failures_are_tracked_in_order(rep: Reporter) -> None:
    rep.fail("first")
    rep.fail("second")
    rep.fail("third")

    assert rep.failed == 3
    assert rep.errors == ["first", "second", "third"]
