# SPDX-License-Identifier: MIT

"""Behavior contract for ``src/apothem/conformity/dynamism_grep.py``.

Tests cover the locale-aware documentation-blog exclusion. The matcher
treats the documentation blog as out-of-scope because it records
historical releases by literal version (dated release-announcement
posts). That exclusion MUST cover both the English-root blog at
``site/content/docs/blog/`` and every locale mirror at
``site/content/docs/<locale>/blog/`` — the original implementation only
covered the English-root prefix, so the 12 locale blog mirrors were
scanned and their legitimate literal versions surfaced as false
positives. These tests regression-guard the locale-aware fix:

(a) ``_is_in_scope`` excludes a locale blog page;
(b) ``_is_in_scope`` excludes the English-root blog page;
(c) ``_is_in_scope`` keeps a normal locale docs page in scope; and
(d) a full ``check`` run flags a literal version on a normal locale docs
    page while a literal version on a locale blog page is skipped.
"""

from __future__ import annotations

from pathlib import Path

from apothem.conformity.dynamism_grep import _is_in_scope, check


def test_locale_blog_page_is_out_of_scope() -> None:
    """A ``<locale>/blog/`` page is excluded exactly like the EN-root blog."""
    root = Path("/repo")
    locale_blog = root / "site/content/docs/ar/blog/posts/v0-1-0-release.mdx"
    assert _is_in_scope(locale_blog, root) is False


def test_english_root_blog_page_is_out_of_scope() -> None:
    """The English-root ``blog/`` page remains excluded after the fix."""
    root = Path("/repo")
    en_blog = root / "site/content/docs/blog/posts/v0-1-0-release.mdx"
    assert _is_in_scope(en_blog, root) is False


def test_normal_locale_docs_page_is_in_scope() -> None:
    """A non-blog locale docs page stays in scope so it is still swept."""
    root = Path("/repo")
    locale_page = root / "site/content/docs/ar/install/index.mdx"
    assert _is_in_scope(locale_page, root) is True


def test_locale_blog_skipped_while_locale_docs_page_flagged(tmp_path: Path) -> None:
    """A literal version on a locale docs page is flagged; the blog is skipped.

    Builds a minimal docs tree: one locale blog post carrying a literal
    ``v0.1.0`` (a dated release announcement, legitimately out of scope)
    and one normal locale docs page carrying a literal ``1.2.3`` (a
    drift-prone surface that MUST be flagged). The check run reports the
    docs-page finding and never the blog one — proving the exclusion is
    locale-aware and does not suppress the in-scope sweep.
    """
    blog_post = tmp_path / "site/content/docs/ar/blog/posts/v0-1-0-release.mdx"
    blog_post.parent.mkdir(parents=True, exist_ok=True)
    blog_post.write_text(
        "# Apothem v0.1.0 release\n\nApothem v0.1.0 is now available.\n",
        encoding="utf-8",
    )

    docs_page = tmp_path / "site/content/docs/ar/install/index.mdx"
    docs_page.parent.mkdir(parents=True, exist_ok=True)
    docs_page.write_text(
        "# Install\n\nThe pinned release is 1.2.3.\n",
        encoding="utf-8",
    )

    result = check(tmp_path)

    assert result.passed is False
    flagged_paths = {Path(f.path).as_posix() for f in result.findings}
    assert docs_page.as_posix() in flagged_paths
    assert blog_post.as_posix() not in flagged_paths
    # The blog mirror was excluded from the sweep, but the in-scope docs
    # page was still scanned — the exclusion is targeted, not vacuous.
    assert result.scanned_count == 1
