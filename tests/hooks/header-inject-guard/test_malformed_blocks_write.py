# SPDX-License-Identifier: MIT

"""A Write whose banner contains the AUTHOR_MARK but is not in canonical
form triggers the header-inject-guard via HEADER_MALFORMED."""

from __future__ import annotations

from pathlib import Path
from types import ModuleType


def test_malformed_blocks_write(
    grep_module: ModuleType,
    tmp_path: Path,
) -> None:
    body = (
        "# Copyright (c) Ahmed G. Gad\n"
        "# Website: https://ahmedgad.com\n"
        "# Email: me@ahmedgad.com\n"
        "# Github: https://github.com/ahmed-g-gad\n"
        "# All rights reserved\n"
        "\n"
        "x = 1\n"
    )
    target = tmp_path / "src" / "example.py"
    target.parent.mkdir(parents=True)
    target.write_text(body, encoding="utf-8")

    result = grep_module.check(body, target)

    assert result.passed is False
    assert len(result.findings) == 1
    assert result.findings[0].rule == grep_module.RULE_MALFORMED
