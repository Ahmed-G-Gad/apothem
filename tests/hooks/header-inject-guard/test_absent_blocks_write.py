# SPDX-License-Identifier: MIT

"""A Write of an applicable file without the canonical banner triggers
the header-inject-guard via the conformity-gate's HEADER_ABSENT verdict.
"""

from __future__ import annotations

from pathlib import Path
from types import ModuleType


def test_absent_blocks_write(
    grep_module: ModuleType,
    tmp_path: Path,
    write_guard_path: Path,
) -> None:
    """The grep module flags HEADER_ABSENT; the operator-facing context
    message is loaded from disk and references the corrective action."""
    body = 'def example() -> None:\n    """No banner here."""\n'
    target = tmp_path / "src" / "example.py"
    target.parent.mkdir(parents=True)
    target.write_text(body, encoding="utf-8")

    result = grep_module.check(body, target)

    assert result.passed is False
    assert len(result.findings) == 1
    assert result.findings[0].rule == grep_module.RULE_ABSENT

    # The corresponding hook context message exists and names the
    # corrective surface (structured-inquiry channel, the canonical fixture).
    text = write_guard_path.read_text(encoding="utf-8")
    assert "structured-inquiry channel" in text
    assert "src/apothem/schemas/authorship-header.txt" in text
    # The corrective option labels (accept-corrected / ...) live in the
    # canonical Authorship-Header option-set the message delegates to,
    # rather than inline in the hook message.
    assert "interactive-questions-canonical-shapes.md" in text
    assert "5.10" in text
