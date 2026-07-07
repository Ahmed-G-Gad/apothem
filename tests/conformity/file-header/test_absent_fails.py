# SPDX-License-Identifier: MIT

"""Validator returns passed=False with HEADER_ABSENT on a body whose
scan window contains no AUTHOR_MARK."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from types import ModuleType


def test_absent_fails(
    grep_module: ModuleType,
    write_fixture: Callable[[str, str], Path],
) -> None:
    """A Python file with no banner at all reports HEADER_ABSENT."""
    body = (
        '"""Module docstring without authorship banner."""\n'
        "\n"
        "def example() -> None:\n    return None\n"
    )
    fixture = write_fixture("src/example.py", body)

    result = grep_module.check(body, fixture)

    assert result.passed is False
    assert len(result.findings) == 1
    assert result.findings[0].rule == grep_module.RULE_ABSENT
    assert result.findings[0].match == ""
