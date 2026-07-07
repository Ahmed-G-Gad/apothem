# SPDX-License-Identifier: MIT

"""Validator passes when every required surface affirms the same claim."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from types import ModuleType


def test_pair_pass(
    grep_module: ModuleType,
    write_surface: Callable[[str, str], Path],
) -> None:
    """All required surfaces carrying the same affirmative claim language
    produce no error-severity findings; the verdict is PASS."""
    affirmative_body = (
        "# Stub Surface\n\n"
        "Every applicable new file begins with the canonical banner.\n"
    )
    write_surface("AGENTS.md", affirmative_body)
    write_surface("CLAUDE.md", affirmative_body)
    write_surface(".github/copilot-instructions.md", affirmative_body)

    result = grep_module.check("", None)

    error_findings = [f for f in result.findings if f.severity == "error"]
    assert result.passed is True
    assert error_findings == []
