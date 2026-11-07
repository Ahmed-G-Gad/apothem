# SPDX-License-Identifier: MIT

"""Tests for scripts/dev/check_built_docs_links.py.

The checker reads the static export of the docs site next to the page sources
it came from. These tests build a small source tree and a small export under
``tmp_path`` and pin its verdicts: the links of a translated page point at the
translated copy of their target, and a fragment lands on an element id of the
built page it opens. The export of the committed site is checked by the
``docs-build`` job, after ``npm run build``.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "dev"))

import check_built_docs_links as built  # noqa: E402

I18N = "export const ROUTED_LOCALES: readonly string[] = ['en', 'de'] as const;\n"
SOURCES = {
    "index.mdx": "## Home\n",
    "guide.mdx": "## Setup steps\n\n## Shared roots\n",
    "pipeline/plan.mdx": "## Usage\n",
    "de/index.mdx": "## Start\n",
    "de/guide.mdx": "## Einrichtung\n\n## Gemeinsame Wurzeln\n",
}


def _html(body: str) -> str:
    """A built page: a sidebar and a footer outside the body, the body in div.prose."""
    return (
        "<html><body><aside><a href='/docs/guide#setup-steps'>sidebar</a></aside>"
        f"<main><article><div class='prose'>{body}</div></article>"
        "<footer><a href='/docs/footer#x'>next</a></footer></main></body></html>"
    )


def _site(root: Path, pages: dict[str, str]) -> tuple[Path, Path, Path]:
    """Write the sources and a built site; return the docs root, i18n file and dist."""
    for relative, text in SOURCES.items():
        path = root / "content" / "docs" / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")
    i18n = root / "i18n.ts"
    i18n.write_text(I18N, encoding="utf-8", newline="\n")
    dist = root / "dist"
    for relative, body in pages.items():
        path = dist / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_html(body), encoding="utf-8", newline="\n")
    return root / "content" / "docs", i18n, dist


HEADING = (
    "<h2 id='{id}'><a data-card='' href='#{id}'>{id}</a><button>copy</button></h2>"
)
BUILT = {
    "docs.html": HEADING.format(id="home"),
    "docs/guide.html": HEADING.format(id="setup-steps")
    + HEADING.format(id="shared-roots"),
    "docs/pipeline/plan.html": HEADING.format(id="usage"),
    "de/docs.html": HEADING.format(id="start")
    + "<a href='/de/docs/guide#gemeinsame-wurzeln'>roots</a>"
    + "<a href='/docs/pipeline/plan#usage'>untranslated</a>"
    + "<a href='#start'>here</a>"
    + "<a href='https://example.com/docs/guide'>elsewhere</a>",
    "de/docs/guide.html": HEADING.format(id="einrichtung")
    + HEADING.format(id="gemeinsame-wurzeln"),
}


def _check(root: Path, pages: dict[str, str]) -> list[built.Finding]:
    docs_root, i18n, dist = _site(root, pages)
    locales = built.routed_locales(i18n)
    findings, _ = built.check_dist(dist, built.load_pages(docs_root, locales), locales)
    return findings


def test_a_correctly_localized_site_has_no_findings(tmp_path: Path) -> None:
    """Translated links, links to untranslated pages and live anchors are all fine."""
    docs_root, i18n, dist = _site(tmp_path, BUILT)
    locales = built.routed_locales(i18n)
    findings, counts = built.check_dist(
        dist, built.load_pages(docs_root, locales), locales
    )
    assert findings == []
    assert counts["pages"] == 5
    assert counts["localized"] == 1
    assert counts["anchored"] == 3


def test_a_link_left_on_the_english_route_is_found(tmp_path: Path) -> None:
    """A translated page that links /docs/guide although the language has it is a finding."""
    pages = {
        **BUILT,
        "de/docs.html": BUILT["de/docs.html"] + "<a href='/docs/guide'>x</a>",
    }
    findings = _check(tmp_path, pages)
    assert [(f.rule, f.url) for f in findings] == [("built-unlocalized", "/docs/guide")]
    assert findings[0].page.endswith("de/index.mdx")


def test_a_locale_link_to_an_untranslated_page_is_found(tmp_path: Path) -> None:
    """A locale route for a page the language never translated would be an English duplicate."""
    pages = {
        **BUILT,
        "de/docs.html": BUILT["de/docs.html"]
        + "<a href='/de/docs/pipeline/plan'>x</a>",
    }
    assert [f.rule for f in _check(tmp_path, pages)] == ["built-fallback"]


def test_a_dead_fragment_is_found_on_any_page(tmp_path: Path) -> None:
    """A fragment with no element id on the built page it opens fails, in any language."""
    pages = {
        **BUILT,
        "docs.html": BUILT["docs.html"]
        + "<a href='/docs/guide#gone'>x</a><a href='#nothing'>y</a>",
        "de/docs.html": BUILT["de/docs.html"] + "<a href='/de/docs/guide#gone'>z</a>",
    }
    findings = _check(tmp_path, pages)
    assert sorted((f.rule, f.url) for f in findings) == [
        ("built-fragment", "#nothing"),
        ("built-fragment", "/de/docs/guide#gone"),
        ("built-fragment", "/docs/guide#gone"),
    ]


def test_a_fragment_matches_an_id_as_written_or_percent_decoded(tmp_path: Path) -> None:
    """The browser looks the fragment up decoded, and the raw id as a fallback."""
    pages = {
        **BUILT,
        "de/docs/guide.html": BUILT["de/docs/guide.html"] + HEADING.format(id="raíces"),
        "de/docs.html": BUILT["de/docs.html"]
        + "<a href='/de/docs/guide#ra%C3%ADces'>a</a><a href='/de/docs/guide#raíces'>b</a>",
    }
    assert _check(tmp_path, pages) == []


def test_links_outside_the_body_and_heading_self_links_are_ignored(
    tmp_path: Path,
) -> None:
    """The sidebar and footer links, and the self-link inside a heading, are not body links."""
    assert _check(tmp_path, BUILT) == []


def test_a_page_the_build_did_not_write_is_found(tmp_path: Path) -> None:
    """A source page with no built file means the export is incomplete."""
    pages = {name: body for name, body in BUILT.items() if name != "de/docs/guide.html"}
    findings = _check(tmp_path, pages)
    assert [f.rule for f in findings] == ["built-missing", "built-missing"]
    # The missing page itself, and the German index whose link opens it.
    assert sorted(f.page.split("content/docs/", 1)[-1] for f in findings) == [
        "de/guide.mdx",
        "de/index.mdx",
    ]


def test_read_body_needs_a_main_element(tmp_path: Path) -> None:
    """A file that is not a page has no body; one that is read stops at </main>."""
    stub = tmp_path / "stub.html"
    stub.write_text("<html><body>redirect</body></html>", encoding="utf-8")
    assert built.read_body(stub) is None
    assert built.read_body(tmp_path / "missing.html") is None
    page = tmp_path / "page.html"
    page.write_text(
        _html("<a href='/docs/a'>a</a>")
        + "<div class='prose'><a href='/docs/b'>b</a></div>"
    )
    body = built.read_body(page)
    assert body is not None
    assert body.links == ["/docs/a"]


def test_built_path_follows_the_static_export_layout(tmp_path: Path) -> None:
    """English pages sit under dist/docs, translations under dist/<locale>/docs."""
    assert built.built_path(tmp_path, ("en", ())) == tmp_path / "docs.html"
    assert built.built_path(tmp_path, ("en", ("a", "b"))) == tmp_path / "docs/a/b.html"
    assert built.built_path(tmp_path, ("de", ("a",))) == tmp_path / "de/docs/a.html"


def test_main_exit_codes(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """0 for a clean site, 1 with findings, 2 when there is no build."""
    docs_root, i18n, dist = _site(tmp_path, BUILT)
    args = [str(dist), "--docs-root", str(docs_root), "--i18n", str(i18n)]
    assert built.main(args) == 0
    assert "5 built pages" in capsys.readouterr().out
    (dist / "de/docs.html").write_text(
        _html("<a href='/docs/guide'>x</a>"), encoding="utf-8"
    )
    assert built.main(args) == 1
    assert "built-unlocalized" in capsys.readouterr().out
    assert (
        built.main(
            [
                str(tmp_path / "nowhere"),
                "--docs-root",
                str(docs_root),
                "--i18n",
                str(i18n),
            ]
        )
        == 2
    )
    assert "no built site" in capsys.readouterr().err


def test_a_fragment_link_the_site_cannot_map_stays_on_the_english_page(
    tmp_path: Path,
) -> None:
    """An older translation with other headings keeps its anchored link on the English route."""
    pages = {
        **BUILT,
        "de/docs.html": BUILT["de/docs.html"]
        + "<a href='/docs/guide#shared-roots'>x</a>",
    }
    docs_root, i18n, dist = _site(tmp_path, pages)
    (docs_root / "de" / "guide.mdx").write_text("## Einrichtung\n", encoding="utf-8")
    locales = built.routed_locales(i18n)
    findings, counts = built.check_dist(
        dist, built.load_pages(docs_root, locales), locales
    )
    assert findings == []
    assert counts["kept-english"] == 1


def test_a_fragment_link_the_site_should_map_but_did_not_is_found(
    tmp_path: Path,
) -> None:
    """With the same headings, an English-route link with an English id should be localized."""
    pages = {
        **BUILT,
        "de/docs.html": BUILT["de/docs.html"]
        + "<a href='/docs/guide#shared-roots'>x</a>",
    }
    findings = _check(tmp_path, pages)
    assert [(f.rule, f.url) for f in findings] == [
        ("built-unlocalized", "/docs/guide#shared-roots")
    ]


def test_a_page_without_a_body_wrapper_is_a_finding(tmp_path: Path) -> None:
    """A layout change that drops div.prose must not turn the check into a no-op."""
    pages = {**BUILT, "docs.html": BUILT["docs.html"]}
    docs_root, i18n, dist = _site(tmp_path, pages)
    (dist / "docs.html").write_text(
        "<html><body><main><article><a href='/docs/guide#gone'>x</a></article></main></body></html>",
        encoding="utf-8",
    )
    locales = built.routed_locales(i18n)
    findings, _ = built.check_dist(dist, built.load_pages(docs_root, locales), locales)
    assert [f.rule for f in findings] == ["built-no-body"]
