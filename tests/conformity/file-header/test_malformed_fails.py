# SPDX-License-Identifier: MIT

# REUSE-IgnoreStart
"""Validator returns passed=False with HEADER_MALFORMED on a banner that
contains the AUTHOR_MARK but is not in canonical form."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from types import ModuleType


def test_malformed_fails(
    grep_module: ModuleType,
    write_fixture: Callable[[str, str], Path],
) -> None:
    """A banner that carries the author signature but uses a different
    comment marker (e.g., a `# ` prefix without the trailing `#`) is
    classified MALFORMED."""
    body = (
        "# Copyright (c) Ahmed G. Gad\n"
        "# Website: https://ahmedgad.com\n"
        "# Email: me@ahmedgad.com\n"
        "# Github: https://github.com/ahmed-g-gad\n"
        "# All rights reserved\n"
        "\n"
        "def example() -> None:\n    return None\n"
    )
    fixture = write_fixture("src/example.py", body)

    result = grep_module.check(body, fixture)

    assert result.passed is False
    assert len(result.findings) == 1
    assert result.findings[0].rule == grep_module.RULE_MALFORMED
    assert "Copyright (c) Ahmed G. Gad" in result.findings[0].match


def test_wrong_comment_family_is_malformed(
    grep_module: ModuleType,
    write_fixture: Callable[[str, str], Path],
) -> None:
    """A present SPDX line in the wrong comment family for the variant
    (``//`` in a hash-variant ``.py``) is MALFORMED, not ABSENT."""
    body = (
        "// SPDX-License-Identifier: MIT\n\ndef example() -> None:\n    return None\n"
    )
    fixture = write_fixture("src/example.py", body)

    result = grep_module.check(body, fixture)

    assert result.passed is False
    assert len(result.findings) == 1
    assert result.findings[0].rule == grep_module.RULE_MALFORMED
    assert result.findings[0].line == 1
    assert "SPDX-License-Identifier:" in result.findings[0].match


def test_wrong_license_is_malformed(
    grep_module: ModuleType,
    write_fixture: Callable[[str, str], Path],
) -> None:
    """A present SPDX line carrying a non-canonical license is MALFORMED."""
    body = (
        "# SPDX-License-Identifier: Apache-2.0\n\n"
        "def example() -> None:\n    return None\n"
    )
    fixture = write_fixture("src/example.py", body)

    result = grep_module.check(body, fixture)

    assert result.passed is False
    assert len(result.findings) == 1
    assert result.findings[0].rule == grep_module.RULE_MALFORMED
    assert result.findings[0].line == 1
    assert "Apache-2.0" in result.findings[0].match


def test_missing_trailing_blank_is_malformed(
    grep_module: ModuleType,
    write_fixture: Callable[[str, str], Path],
) -> None:
    """A canonical SPDX line lacking the mandatory trailing blank is MALFORMED:
    the header marker is present but the block is not canonical."""
    body = "# SPDX-License-Identifier: MIT\ndef example() -> None:\n    return None\n"
    fixture = write_fixture("src/example.py", body)

    result = grep_module.check(body, fixture)

    assert result.passed is False
    assert len(result.findings) == 1
    assert result.findings[0].rule == grep_module.RULE_MALFORMED


def test_genuinely_headerless_file_stays_absent(
    grep_module: ModuleType,
    write_fixture: Callable[[str, str], Path],
) -> None:
    """A file with no SPDX marker at all stays ABSENT — the SPDX-at-insertion
    branch must not relabel a truly headerless file as MALFORMED."""
    body = "def example() -> None:\n    return None\n"
    fixture = write_fixture("src/example.py", body)

    result = grep_module.check(body, fixture)

    assert result.passed is False
    assert len(result.findings) == 1
    assert result.findings[0].rule == grep_module.RULE_ABSENT


# REUSE-IgnoreEnd
