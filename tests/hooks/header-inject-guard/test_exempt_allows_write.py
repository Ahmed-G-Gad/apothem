# SPDX-License-Identifier: MIT

"""A Write of a path matching an exception glob (e.g., a `.json` file)
passes the hook even though JSON has no banner syntax. The Edit-tool
analog holds for the same exemption logic."""

from __future__ import annotations

from pathlib import Path
from types import ModuleType


def test_exempt_json_allows_write(
    grep_module: ModuleType,
    tmp_path: Path,
) -> None:
    body = '{"key": "value"}\n'
    target = tmp_path / "config" / "settings.json"
    target.parent.mkdir(parents=True)
    target.write_text(body, encoding="utf-8")

    result = grep_module.check(body, target)

    assert result.passed is True


def test_edit_guard_documents_corner_cases(edit_guard_path: Path) -> None:
    """The Edit-route guard documents the create-via-edit and
    header-removal corner cases — these are the only Edit scenarios the
    hook reacts to; pure modifications of canonical files are
    pass-through."""
    text = edit_guard_path.read_text(encoding="utf-8")

    assert "create-via-edit" in text
    assert "header-removal" in text.lower() or "header removal" in text.lower()
    assert "Pass-through" in text or "pass-through" in text.lower()
