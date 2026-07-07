# SPDX-License-Identifier: MIT

"""Validator returns passed=True on a canonical-header file."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from types import ModuleType


def test_canonical_passes(
    grep_module: ModuleType,
    canonical_block: str,
    write_fixture: Callable[[str, str], Path],
) -> None:
    """A Python file whose first lines match the canonical hash-form
    block plus mandatory trailing blank line passes the validator."""
    body = canonical_block + "def example() -> None:\n    return None\n"
    fixture = write_fixture("src/example.py", body)

    result = grep_module.check(body, fixture)

    assert result.passed is True
    assert result.findings == []


def test_canonical_passes_with_shebang(
    grep_module: ModuleType,
    canonical_block: str,
    write_fixture: Callable[[str, str], Path],
) -> None:
    """A shebang on line 1 pushes the canonical block to line 2; the
    validator's insertion-index logic handles this case."""
    body = "#!/usr/bin/env python3\n" + canonical_block + 'print("hello")\n'
    fixture = write_fixture("scripts/example.py", body)

    result = grep_module.check(body, fixture)

    assert result.passed is True
