# SPDX-License-Identifier: MIT

"""Every translated docs page records which English text it was translated from.

Why this guard exists. Locale pages drifted from their English sources: 55
locale pages were older than the English page they translate, with stale CLI
synopses, and nothing recorded which English revision a translation came from.
Each locale page now carries a ``sourceHash`` frontmatter field, the hash of the
English page it was translated from (``site/lib/translation-source.mjs``). The
docs site compares it with the current English page at build time and marks a
stale translation on the page. A locale page without the field cannot be
checked, so this test requires it on every locale page; ``node
site/scripts/translation-sources.mjs --stamp <locale>/<path>`` records it after a
translation is refreshed.
"""

from __future__ import annotations

import pathlib
import re

_DOCS_ROOT = pathlib.Path(__file__).resolve().parents[3] / "site" / "content" / "docs"
_LOCALES = ("ar", "de", "es", "fr", "hi", "id", "ja", "ko", "pt-br", "ru", "zh-cn")
_FRONTMATTER = re.compile(r"\A---\n(?P<body>.*?)\n---\n", re.DOTALL)
_SOURCE_HASH = re.compile(r"^sourceHash: \"?(?P<hash>[^\"\n]*)\"?$", re.MULTILINE)


def _locale_pages() -> list[pathlib.Path]:
    pages: list[pathlib.Path] = []
    for locale in _LOCALES:
        pages.extend(sorted((_DOCS_ROOT / locale).rglob("*.mdx")))
    return pages


def test_every_locale_page_records_a_source_hash() -> None:
    """Each locale page's frontmatter carries a 16-hex-digit ``sourceHash``."""
    pages = _locale_pages()
    # Anti-vacuous anchor: eleven locales of the English page set.
    assert len(pages) >= 11 * 190
    problems = []
    for path in pages:
        match = _FRONTMATTER.match(path.read_text(encoding="utf-8"))
        if match is None:
            problems.append(f"{path.relative_to(_DOCS_ROOT)}: no frontmatter")
            continue
        recorded = _SOURCE_HASH.search(match.group("body"))
        if recorded is None or not re.fullmatch(
            r"[0-9a-f]{16}", recorded.group("hash")
        ):
            problems.append(
                f"{path.relative_to(_DOCS_ROOT)}: missing or malformed sourceHash"
            )
    assert problems == [], f"{len(problems)} locale pages: {problems[:5]}"


def test_every_locale_page_translates_an_existing_english_page() -> None:
    """A locale page with no English source would have nothing to compare against."""
    orphans = []
    for path in _locale_pages():
        rel = path.relative_to(_DOCS_ROOT)
        english = _DOCS_ROOT.joinpath(*rel.parts[1:])
        if not english.is_file():
            orphans.append(str(rel))
    assert orphans == []
