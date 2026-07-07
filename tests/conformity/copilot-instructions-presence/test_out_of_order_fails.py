# SPDX-License-Identifier: MIT

"""Validator emits COPILOT_SECTION_OUT_OF_ORDER when canonical order breaks."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from types import ModuleType


def test_out_of_order_fails(
    grep_module: ModuleType,
    build_body: Callable[[tuple[str, ...]], str],
    write_target: Callable[[str], Path],
) -> None:
    """A surface that swaps two canonical sections produces a
    COPILOT_SECTION_OUT_OF_ORDER finding."""
    swapped_sections = (
        "Coding Conventions",  # swapped with "Project Context"
        "Project Context",
        "File Headers",
        "Plans Discipline",
        "Structured Inquiry Behavior",
        "Forbidden Patterns",
        "Output Format",
        "Review Checklist",
        "Pointers",
    )
    body = build_body(swapped_sections)
    fixture = write_target(body)

    result = grep_module.check(body, fixture)

    assert result.passed is False
    rules = {f.rule for f in result.findings}
    assert "COPILOT_SECTION_OUT_OF_ORDER" in rules
