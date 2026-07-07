# SPDX-License-Identifier: MIT

"""A Write whose proposed content already carries the canonical banner
passes the hook unchanged."""

from __future__ import annotations

from pathlib import Path
from types import ModuleType


def test_canonical_allows_write(
    grep_module: ModuleType,
    canonical_block: str,
    tmp_path: Path,
) -> None:
    body = canonical_block + "x = 1\n"
    target = tmp_path / "src" / "canonical.py"
    target.parent.mkdir(parents=True)
    target.write_text(body, encoding="utf-8")

    result = grep_module.check(body, target)

    assert result.passed is True
    assert result.findings == []
