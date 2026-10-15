# SPDX-License-Identifier: MIT

"""Validator behavior for Markdown frontmatter and the MDX variant.

The file-header validator must place the canonical block the way the injector
does: after a YAML frontmatter block for Markdown and MDX, and at the file head
for every other family. Expected header text is built through the validator's
own render helpers so this file carries no literal license tag.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from apothem.conformity import file_header_grep as fhg


def _canonical_text(variant: str) -> str:
    """Return the canonical block for *variant*, trailing blank included."""
    hash_form_line, spdx_text = fhg._load_banner()
    return (
        "\n".join(fhg._render_canonical_block(hash_form_line, spdx_text, variant))
        + "\n"
    )


@pytest.fixture
def anchored_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Anchor the validator's repo root at *tmp_path* so paths resolve under it."""
    root = tmp_path.resolve()
    monkeypatch.setattr(fhg, "ECOSYSTEM_ROOT", root)
    return root


def test_markdown_frontmatter_then_canonical_block_passes(anchored_root: Path) -> None:
    """A canonical block placed after frontmatter is the correct position."""
    body = "---\ntitle: Page\n---\n" + _canonical_text(fhg.VARIANT_HTML) + "# Page\n"
    result = fhg.check(body, anchored_root / "docs" / "page.md")
    assert result.passed is True
    assert result.findings == []


def test_markdown_frontmatter_without_header_is_absent_after_the_fence(
    anchored_root: Path,
) -> None:
    """A missing header is reported at the line after the closing fence."""
    body = "---\ntitle: Page\n---\n# Page\n"
    result = fhg.check(body, anchored_root / "docs" / "page.md")
    assert result.passed is False
    assert len(result.findings) == 1
    assert result.findings[0].rule == fhg.RULE_ABSENT
    assert result.findings[0].line == 4


def test_frontmatter_shaped_python_file_is_not_skipped(anchored_root: Path) -> None:
    """Frontmatter skipping is limited to the html and mdx variants."""
    body = "---\na: b\n---\n" + _canonical_text(fhg.VARIANT_HASH) + "x = 1\n"
    result = fhg.check(body, anchored_root / "src" / "example.py")
    assert result.passed is False
    assert result.findings[0].rule == fhg.RULE_ABSENT
    assert result.findings[0].line == 1


def test_mdx_canonical_block_after_frontmatter_passes(anchored_root: Path) -> None:
    """The MDX comment form after frontmatter, with the blank line, passes."""
    body = "---\ntitle: Page\n---\n\n" + _canonical_text(fhg.VARIANT_MDX) + "# Page\n"
    result = fhg.check(body, anchored_root / "docs" / "page.mdx")
    assert result.passed is True


def test_mdx_without_any_header_is_absent(anchored_root: Path) -> None:
    """An MDX file with no comment form at the head is reported as absent."""
    body = "# Page\n\nBody text.\n"
    result = fhg.check(body, anchored_root / "docs" / "page.mdx")
    assert result.passed is False
    assert result.findings[0].rule == fhg.RULE_ABSENT
    assert result.findings[0].line == 1


def test_mdx_with_html_comment_wrapper_is_malformed(anchored_root: Path) -> None:
    """The html comment wrapper is the wrong family for an MDX file."""
    hash_form_line, spdx_text = fhg._load_banner()
    wrong_wrapper = fhg._render_variant(hash_form_line, spdx_text, fhg.VARIANT_HTML)[0]
    body = "---\ntitle: Page\n---\n\n" + wrong_wrapper + "\n\n# Page\n"
    result = fhg.check(body, anchored_root / "docs" / "page.mdx")
    assert result.passed is False
    assert result.findings[0].rule == fhg.RULE_MALFORMED
    assert result.findings[0].line == 5


def test_mdx_suffix_resolves_to_mdx_variant() -> None:
    """The validator's suffix table maps .mdx to the MDX variant."""
    assert fhg._variant_family_for(Path("docs/page.mdx")) == fhg.VARIANT_MDX
    assert fhg._variant_family_for(Path("docs/page.MDX")) == fhg.VARIANT_MDX
