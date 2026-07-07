# SPDX-License-Identifier: MIT

"""Validator treats files matching an exception glob as exempt and
returns passed=True regardless of banner presence."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from types import ModuleType


def test_exempt_glob_match_passes(
    grep_module: ModuleType,
    write_fixture: Callable[[str, str], Path],
) -> None:
    """A `.json` file matches the test exception list (`**/*.json`) so
    the validator treats it as exempt even though JSON has no comment
    syntax for a banner."""
    body = '{"key": "value"}\n'
    fixture = write_fixture("config/settings.json", body)

    result = grep_module.check(body, fixture)

    assert result.passed is True
    assert result.findings == []


def test_exempt_unknown_variant_passes(
    grep_module: ModuleType,
    write_fixture: Callable[[str, str], Path],
) -> None:
    """A file whose suffix maps to no known variant family (e.g., no
    suffix at all and no basename match) is exempt by construction."""
    body = "raw text\n"
    fixture = write_fixture("data/raw", body)

    result = grep_module.check(body, fixture)

    assert result.passed is True
