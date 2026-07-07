# SPDX-License-Identifier: MIT

"""Unit tests for ``tools.lib.frontmatter`` regex-based YAML probing."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_TOOLS_LIB = _REPO_ROOT / "src" / "apothem" / "lib"
if str(_TOOLS_LIB) not in sys.path:
    sys.path.insert(0, str(_TOOLS_LIB))

from frontmatter import (  # noqa: E402
    extract_frontmatter,
    field_value,
    has_all_fields,
    has_field,
)


def _write(tmp_path: Path, name: str, body: str) -> Path:
    path = tmp_path / name
    path.write_text(body, encoding="utf-8")
    return path


_SAMPLE = """---
name: "example"
version: "1.0.0"
updated: "2026-04-20"
description: "sample artifact for tests"
scope: always-on
portability: 'universal'
---

# Body

Content below frontmatter.
"""


def test_extract_frontmatter_returns_block_between_markers(
    tmp_path: Path,
) -> None:
    path = _write(tmp_path, "a.md", _SAMPLE)

    block = extract_frontmatter(path)

    assert block is not None
    assert 'name: "example"' in block
    assert "Body" not in block


def test_extract_frontmatter_returns_none_without_markers(
    tmp_path: Path,
) -> None:
    path = _write(tmp_path, "b.md", "# Just a heading\n\nNo frontmatter.\n")

    assert extract_frontmatter(path) is None


def test_extract_frontmatter_returns_none_for_missing_file(
    tmp_path: Path,
) -> None:
    assert extract_frontmatter(tmp_path / "nope.md") is None


@pytest.mark.parametrize(
    ("field", "expected"),
    [
        ("name", "example"),
        ("version", "1.0.0"),
        ("description", "sample artifact for tests"),
        ("scope", "always-on"),
        ("portability", "universal"),
    ],
)
def test_field_value_dequotes_single_and_double_quotes(
    tmp_path: Path, field: str, expected: str
) -> None:
    path = _write(tmp_path, "c.md", _SAMPLE)

    assert field_value(path, field) == expected


def test_field_value_returns_none_when_field_absent(tmp_path: Path) -> None:
    path = _write(tmp_path, "d.md", _SAMPLE)

    assert field_value(path, "absent") is None


def test_field_value_returns_none_when_no_frontmatter(tmp_path: Path) -> None:
    path = _write(tmp_path, "e.md", "no frontmatter here\n")

    assert field_value(path, "name") is None


def test_has_field_mirrors_field_value_presence(tmp_path: Path) -> None:
    path = _write(tmp_path, "f.md", _SAMPLE)

    assert has_field(path, "name") is True
    assert has_field(path, "missing") is False


def test_has_all_fields_requires_every_name(tmp_path: Path) -> None:
    path = _write(tmp_path, "g.md", _SAMPLE)

    assert has_all_fields(path, ["name", "version", "description"]) is True
    assert has_all_fields(path, ["name", "not-there"]) is False


def test_field_value_keeps_empty_string_when_quoted_empty(
    tmp_path: Path,
) -> None:
    body = '---\nname: ""\n---\n'
    path = _write(tmp_path, "h.md", body)

    assert field_value(path, "name") == ""


def test_field_value_trims_whitespace(tmp_path: Path) -> None:
    body = "---\nname:    spaced-out    \n---\n"
    path = _write(tmp_path, "i.md", body)

    assert field_value(path, "name") == "spaced-out"
