# SPDX-License-Identifier: MIT

"""Validator emits LICENSE_AUTHOR_ABSENT when a present, non-pending
LICENSE carries no parseable copyright author line.

Under the narrowed authorship-header contract the historical
banner-vs-LICENSE mismatch check is retired; the single remaining failure
mode is a LICENSE that exists and is not pending yet names no author."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from types import ModuleType


def test_author_absent_fails(
    grep_module: ModuleType,
    write_license: Callable[[str], Path],
) -> None:
    """A LICENSE with body text but no ``Copyright (c) <name>`` line
    produces a LICENSE_AUTHOR_ABSENT error finding and a False verdict."""
    write_license("MIT License\n\nPermission is hereby granted, free of charge...\n")

    result = grep_module.check("", None)

    assert result.passed is False
    rules = {f.rule for f in result.findings}
    assert "LICENSE_AUTHOR_ABSENT" in rules
