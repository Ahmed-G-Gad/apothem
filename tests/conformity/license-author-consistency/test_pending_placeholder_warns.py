# SPDX-License-Identifier: MIT

"""Validator passes with LICENSE_PENDING warning on the pending placeholder."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from types import ModuleType


def test_pending_placeholder_warns(
    grep_module: ModuleType,
    write_license: Callable[[str], Path],
) -> None:
    """A LICENSE carrying the canonical pending placeholder produces a
    warning-severity LICENSE_PENDING finding; the verdict is PASS."""
    write_license("<USER-CONFIRM:license-pending>\n")

    result = grep_module.check("", None)

    assert result.passed is True
    rules = [(f.rule, f.severity) for f in result.findings]
    assert ("LICENSE_PENDING", "warning") in rules
