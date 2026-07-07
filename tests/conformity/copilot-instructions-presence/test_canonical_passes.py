# SPDX-License-Identifier: MIT

"""Validator returns passed=True on a well-formed Copilot surface."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from types import ModuleType


def test_canonical_body_passes(
    grep_module: ModuleType,
    canonical_body: str,
    write_target: Callable[[str], Path],
) -> None:
    """A surface with the canonical banner and all nine sections in order
    passes the validator with zero findings."""
    fixture = write_target(canonical_body)

    result = grep_module.check(canonical_body, fixture)

    assert result.passed is True
    assert result.findings == []
