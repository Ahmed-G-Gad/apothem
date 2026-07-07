# SPDX-License-Identifier: MIT

"""Validator emits COPILOT_BANNER_ABSENT when the Markdown banner is missing."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from types import ModuleType


def test_banner_absent_fails(
    grep_module: ModuleType,
    canonical_body: str,
    write_target: Callable[[str], Path],
) -> None:
    """Stripping the banner block from the head emits COPILOT_BANNER_ABSENT."""
    # Drop the leading 7 banner lines plus the blank separator.
    lines = canonical_body.splitlines()
    body = "\n".join(lines[8:]) + "\n"
    fixture = write_target(body)

    result = grep_module.check(body, fixture)

    assert result.passed is False
    rules = {f.rule for f in result.findings}
    assert "COPILOT_BANNER_ABSENT" in rules
