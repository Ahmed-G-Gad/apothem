# SPDX-License-Identifier: MIT

"""Validator emits COPILOT_SECTION_ABSENT when a canonical section is missing."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from types import ModuleType


def test_missing_section_fails(
    grep_module: ModuleType,
    build_body: Callable[[tuple[str, ...]], str],
    write_target: Callable[[str], Path],
) -> None:
    """Dropping a single canonical section produces a COPILOT_SECTION_ABSENT
    finding naming that section."""
    sections = (
        "Project Context",
        "Coding Conventions",
        "File Headers",
        # "Plans Discipline" intentionally omitted.
        "Structured Inquiry Behavior",
        "Forbidden Patterns",
        "Output Format",
        "Review Checklist",
        "Pointers",
    )
    body = build_body(sections)
    fixture = write_target(body)

    result = grep_module.check(body, fixture)

    assert result.passed is False
    rules = {f.rule for f in result.findings}
    assert "COPILOT_SECTION_ABSENT" in rules
    contexts = " ".join(f.context for f in result.findings)
    assert "Plans Discipline" in contexts
