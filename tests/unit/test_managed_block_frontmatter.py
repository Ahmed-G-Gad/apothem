# SPDX-License-Identifier: MIT

# REUSE-IgnoreStart
"""Frontmatter-carrying rule files keep their frontmatter at byte 0.

Cursor, Kiro, Trae, CodeBuddy and Windsurf read a rule file's activation mode
from YAML frontmatter that must be the first content in the file (Kiro:
https://kiro.dev/docs/steering/ "The inclusion configuration must be the first
content in the file"; Cursor: https://cursor.com/docs/context/rules, both
retrieved 2026-10-02). The managed-block merge therefore emits a frontmatter-
carrying body as frontmatter first, then the BEGIN sentinel, the body and the
END sentinel, and the merge and remove paths recognise that shape.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from apothem.lib.harness_materializer import (
    APOTHEM_BLOCK_BEGIN,
    APOTHEM_BLOCK_END,
    merge_managed_block,
    remove_managed_block,
)
from apothem.lib.harness_registry import get_harness_entry, load_adapter_class

_FM = '---\nalwaysApply: true\ndescription: "Apothem rules"\n---\n'
_BODY = _FM + "\n<!-- SPDX-License-Identifier: MIT -->\n\n# Apothem\n\nGovernance.\n"


def _strict_frontmatter(text: str) -> dict[str, object]:
    """Parse frontmatter that must open at byte 0 (no blank line or comment first)."""
    assert text.startswith("---\n"), f"first line is {text.splitlines()[0]!r}"
    end = text.index("\n---\n", 4)
    loaded = yaml.safe_load(text[4:end])
    assert isinstance(loaded, dict)
    return loaded


def test_split_frontmatter_requires_byte_zero() -> None:
    from apothem.lib.frontmatter import split_frontmatter

    parts = split_frontmatter(_BODY)
    assert parts is not None
    assert parts[0] == _FM
    assert parts[0] + parts[1] == _BODY
    assert split_frontmatter("<!-- c -->\n" + _BODY) is None
    assert split_frontmatter("\n" + _BODY) is None


def test_fresh_merge_emits_frontmatter_first() -> None:
    merged = merge_managed_block("", _BODY)
    assert _strict_frontmatter(merged) == {
        "alwaysApply": True,
        "description": "Apothem rules",
    }
    after_fm = merged[len(_FM) :]
    assert after_fm.startswith(APOTHEM_BLOCK_BEGIN)
    assert merged.count(APOTHEM_BLOCK_BEGIN) == 1
    assert merged.count("---\n") == 2
    assert "# Apothem" in merged


def test_merge_is_idempotent() -> None:
    once = merge_managed_block("", _BODY)
    assert merge_managed_block(once, _BODY) == once


def test_remove_deletes_frontmatter_and_block() -> None:
    assert remove_managed_block(merge_managed_block("", _BODY)) == ""


def test_update_replaces_frontmatter_and_keeps_operator_prose() -> None:
    installed = merge_managed_block("", _BODY) + "\n# Operator notes\n\nMine.\n"
    new_body = _BODY.replace("alwaysApply: true", "alwaysApply: false")
    updated = merge_managed_block(installed, new_body)
    assert _strict_frontmatter(updated)["alwaysApply"] is False
    assert updated.count("---\n") == 2
    assert updated.count(APOTHEM_BLOCK_BEGIN) == 1
    assert updated.endswith("# Operator notes\n\nMine.\n")
    assert remove_managed_block(updated) == "# Operator notes\n\nMine.\n"


def test_legacy_sentinel_first_install_migrates_to_frontmatter_first() -> None:
    legacy = f"{APOTHEM_BLOCK_BEGIN}\n{_BODY.strip()}\n{APOTHEM_BLOCK_END}\n"
    migrated = merge_managed_block(legacy, _BODY)
    assert _strict_frontmatter(migrated)["alwaysApply"] is True
    assert migrated == merge_managed_block("", _BODY)


def test_operator_prose_without_frontmatter_moves_below_block() -> None:
    operator = "# Operator rules\n\nKeep mine.\n"
    merged = merge_managed_block(operator, _BODY)
    _strict_frontmatter(merged)
    assert merged.endswith(operator)
    assert remove_managed_block(merged) == operator


def test_operator_frontmatter_governs_its_own_file() -> None:
    operator = '---\nalwaysApply: false\nglobs: "*.py"\n---\n\n# Mine\n'
    merged = merge_managed_block(operator, _BODY)
    assert merged.startswith(operator)
    assert merged.count("---\n") == 2
    assert _strict_frontmatter(merged)["globs"] == "*.py"
    assert remove_managed_block(merged) == operator


def test_body_without_frontmatter_keeps_sentinel_first_shape() -> None:
    body = "# Plain\n\nText.\n"
    merged = merge_managed_block("", body)
    assert merged.startswith(APOTHEM_BLOCK_BEGIN)
    assert remove_managed_block(merged) == ""


_RULE_FILE_HARNESSES = ("cursor", "kiro", "trae", "codebuddy", "windsurf")


@pytest.mark.parametrize("harness", _RULE_FILE_HARNESSES)
def test_installed_rule_file_opens_with_frontmatter(
    harness: str, tmp_path: Path
) -> None:
    adapter_cls = load_adapter_class(get_harness_entry(harness))
    adapter = adapter_cls()
    adapter.install({}, project=tmp_path)  # type: ignore[attr-defined]
    target = adapter.resolve_output_path(tmp_path)  # type: ignore[attr-defined]
    text = target.read_text(encoding="utf-8")
    assert _strict_frontmatter(text)
    assert text.count(APOTHEM_BLOCK_BEGIN) == 1
    # Re-install is a no-op and uninstall leaves nothing behind.
    adapter.install({}, project=tmp_path)  # type: ignore[attr-defined]
    assert target.read_text(encoding="utf-8") == text
    adapter.uninstall(project=tmp_path)  # type: ignore[attr-defined]
    assert not target.exists() or not target.read_text(encoding="utf-8").strip()


# REUSE-IgnoreEnd
