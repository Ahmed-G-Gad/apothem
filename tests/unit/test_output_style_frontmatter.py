# SPDX-License-Identifier: MIT

"""Output-style frontmatter keeps Claude Code's coding instructions.

Claude Code drops its built-in software-engineering instructions (how to scope
changes, write comments, verify work) for any custom output style unless the
style sets ``keep-coding-instructions: true`` (default ``false``), per
https://code.claude.com/docs/en/output-styles (retrieved 2026-10-02). Every
Apothem style shapes how engineering work is presented, not whether it is done,
so each one must keep those instructions.
"""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest
import yaml

_PKG = Path(__file__).resolve().parents[2] / "src" / "apothem"
_STYLES_DIR = _PKG / "output-styles"
_SCHEMA = _PKG / "schemas" / "output-style.schema.json"
_STYLES = sorted(p for p in _STYLES_DIR.glob("*.md") if p.name != "README.md")


def _frontmatter(path: Path) -> dict[str, object]:
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n"), f"{path.name}: frontmatter must open at byte 0"
    block = text.split("---", 2)[1]
    loaded = yaml.safe_load(block)
    assert isinstance(loaded, dict)
    return loaded


def test_style_corpus_is_present() -> None:
    assert len(_STYLES) == 4


@pytest.mark.parametrize("style", _STYLES, ids=lambda p: p.stem)
def test_style_keeps_coding_instructions(style: Path) -> None:
    assert _frontmatter(style).get("keep-coding-instructions") is True


@pytest.mark.parametrize("style", _STYLES, ids=lambda p: p.stem)
def test_style_frontmatter_validates_against_schema(style: Path) -> None:
    schema = json.loads(_SCHEMA.read_text(encoding="utf-8"))
    jsonschema.validate(_frontmatter(style), schema)


def test_schema_types_keep_coding_instructions_as_boolean() -> None:
    schema = json.loads(_SCHEMA.read_text(encoding="utf-8"))
    bad = {"name": "X", "description": "Y", "keep-coding-instructions": "yes"}
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(bad, schema)
