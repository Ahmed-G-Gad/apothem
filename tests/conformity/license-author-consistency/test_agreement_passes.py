# SPDX-License-Identifier: MIT

"""Validator passes when the LICENSE carries a parseable author line."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from types import ModuleType


def test_agreement_passes(
    grep_module: ModuleType,
    write_license: Callable[[str], Path],
) -> None:
    """A LICENSE whose copyright line names an author passes the
    validator with zero findings."""
    write_license(
        "MIT License\n\nCopyright (c) 2026 Ahmed G. Gad\n\n"
        "Permission is hereby granted...\n"
    )

    result = grep_module.check("", None)

    assert result.passed is True
    assert result.findings == []
