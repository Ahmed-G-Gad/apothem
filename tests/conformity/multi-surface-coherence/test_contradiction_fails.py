# SPDX-License-Identifier: MIT

"""Validator emits COHERENCE_CONTRADICTION when surfaces disagree on a claim."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from types import ModuleType


def test_contradiction_fails(
    grep_module: ModuleType,
    write_surface: Callable[[str, str], Path],
) -> None:
    """A non-canonical surface that negates the canonical claim's tokens
    produces a COHERENCE_CONTRADICTION error finding."""
    affirmative = (
        "# Stub Surface\n\n"
        "Every applicable new file begins with the canonical banner.\n"
    )
    # Each token sits in a leading-negation window so the validator's
    # contradiction analysis fires deterministically.
    negated = (
        "# Stub Surface\n\n"
        "This surface never adds the canonical banner;"
        " never marks applicable scope;"
        " never tags new file emission.\n"
    )
    write_surface("AGENTS.md", affirmative)
    write_surface("CLAUDE.md", affirmative)
    write_surface(".github/copilot-instructions.md", negated)

    result = grep_module.check("", None)

    rules = {f.rule for f in result.findings if f.severity == "error"}
    assert result.passed is False
    assert "COHERENCE_CONTRADICTION" in rules
