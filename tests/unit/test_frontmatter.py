# SPDX-License-Identifier: MIT

# REUSE-IgnoreStart
"""Unit tests for the lib/frontmatter probing utility.

The Hypothesis property suite (tests/property/test_frontmatter_properties.py)
exercises round-trip invariants; these targeted unit tests cover the specific
branches it does not reach directly: the unreadable-file OSError path, the
unquoted-scalar return, and the ``has_field`` / ``has_all_fields`` presence
helpers, plus the leading-authorship-comment skip and the quoted-value dequote.
"""

from __future__ import annotations

from pathlib import Path

from apothem.lib import frontmatter as fm


def _write(tmp_path: Path, body: str, name: str = "doc.md") -> Path:
    target = tmp_path / name
    target.write_text(body, encoding="utf-8")
    return target


class TestExtractFrontmatter:
    """Extracting the leading YAML block.

    Covers the normal extraction, the skip past a leading authorship comment,
    and the two none cases: no frontmatter, and an unreadable path.
    """

    def test_extracts_the_yaml_block(self, tmp_path: Path) -> None:
        path = _write(tmp_path, '---\nname: "x"\ndescription: "y"\n---\nbody\n')
        assert fm.extract_frontmatter(path) == 'name: "x"\ndescription: "y"'

    def test_no_frontmatter_returns_none(self, tmp_path: Path) -> None:
        path = _write(tmp_path, "# Just a heading, no frontmatter\n")
        assert fm.extract_frontmatter(path) is None

    def test_skips_leading_authorship_comment(self, tmp_path: Path) -> None:
        path = _write(
            tmp_path, "<!-- SPDX-License-Identifier: MIT -->\n---\nname: x\n---\nbody"
        )
        assert fm.extract_frontmatter(path) == "name: x"

    def test_unreadable_path_returns_none(self, tmp_path: Path) -> None:
        # A nonexistent path raises FileNotFoundError (an OSError) -> None.
        assert fm.extract_frontmatter(tmp_path / "absent.md") is None


class TestFieldValue:
    """Reading one field out of the frontmatter.

    Covers dequoting of double- and single-quoted values, an unquoted value
    returned raw, and an absent field returning none.
    """

    def test_double_quoted_value_is_dequoted(self, tmp_path: Path) -> None:
        path = _write(tmp_path, '---\nname: "Ahmed"\n---\n')
        assert fm.field_value(path, "name") == "Ahmed"

    def test_single_quoted_value_is_dequoted(self, tmp_path: Path) -> None:
        path = _write(tmp_path, "---\nname: 'Ahmed'\n---\n")
        assert fm.field_value(path, "name") == "Ahmed"

    def test_unquoted_value_returned_raw(self, tmp_path: Path) -> None:
        path = _write(tmp_path, "---\nalwaysApply: true\n---\n")
        assert fm.field_value(path, "alwaysApply") == "true"

    def test_absent_field_returns_none(self, tmp_path: Path) -> None:
        path = _write(tmp_path, "---\nname: x\n---\n")
        assert fm.field_value(path, "missing") is None

    def test_no_frontmatter_returns_none(self, tmp_path: Path) -> None:
        path = _write(tmp_path, "no frontmatter here")
        assert fm.field_value(path, "name") is None


class TestPresenceHelpers:
    """Field-presence predicates.

    Covers the single-field check in both directions and the all-fields check,
    which is false when even one field is absent.
    """

    def test_has_field_true_when_present(self, tmp_path: Path) -> None:
        path = _write(tmp_path, "---\nname: x\n---\n")
        assert fm.has_field(path, "name") is True

    def test_has_field_false_when_absent(self, tmp_path: Path) -> None:
        path = _write(tmp_path, "---\nname: x\n---\n")
        assert fm.has_field(path, "description") is False

    def test_has_all_fields_true_when_all_present(self, tmp_path: Path) -> None:
        path = _write(tmp_path, "---\nname: x\ndescription: y\n---\n")
        assert fm.has_all_fields(path, ["name", "description"]) is True

    def test_has_all_fields_false_when_one_absent(self, tmp_path: Path) -> None:
        path = _write(tmp_path, "---\nname: x\n---\n")
        assert fm.has_all_fields(path, ["name", "description"]) is False


# REUSE-IgnoreEnd
