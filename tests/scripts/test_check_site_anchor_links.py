# SPDX-License-Identifier: MIT

"""Tests for scripts/dev/check_site_anchor_links.py.

The checker reads docs page sources and decides, for every link that carries a
fragment, whether the page the link opens has a heading with that id. These
tests pin how it reads a page (headings, ids, links), how it maps a fragment
onto a translated page, and its verdicts on small trees built under
``tmp_path``. The committed docs tree is checked in
``tests/unit/docs/test_site_anchor_links.py``.
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "dev"))

import check_site_anchor_links as checker  # noqa: E402

I18N = """\
// The routed locales: ROUTED_LOCALES is the list below, not this sentence.
export const ROUTED_LOCALES: readonly string[] = ['en', 'de', 'ar'] as const;
export const ROUTED_NON_DEFAULT_LOCALES: readonly string[] = ROUTED_LOCALES.filter(
  (code) => code !== 'en',
);
"""

SCANNED = """\
---
title: Sample
description: "A [link](/docs/in-frontmatter#nope) that is not content"
---

{/* a comment with a [link](/docs/in-comment#nope) */}

## Setup steps

Back to [the top](#setup-steps) or [another page](/docs/other#part-two "Title").

```bash
# Not a heading
echo "[not a link](/docs/in-fence#nope)"
```

## Setup steps

### Run `apothem install` <bdi>now</bdi> [#custom-run]

| Name | Notes | Link |
| --- | --- | --- |
| `x` | an unclosed `tick | [`src/a.md`](https://example.com/a.md#frag) |

Inline `[not a link](/docs/in-code#nope)`, an ![image](/docs/img#nope), an escaped \\[bracket](/docs/esc#nope)
and <a href="/docs/by-href#frag">markup</a> with <a name="named-anchor">a name</a> and <div id="boxed">a box</div>.

<Card title="Card" href="/docs/by-card#frag" />

[ref]: /docs/by-definition#frag
"""


def _tree(root: Path, pages: dict[str, str]) -> tuple[Path, Path]:
    """Write *pages* under ``root/content/docs`` and an ``i18n.ts``; return both."""
    for relative, text in pages.items():
        path = root / "content" / "docs" / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")
    i18n = root / "i18n.ts"
    i18n.write_text(I18N, encoding="utf-8", newline="\n")
    return root / "content" / "docs", i18n


def _run(root: Path, pages: dict[str, str]) -> checker.Report:
    docs_root, i18n = _tree(root, pages)
    return checker.run(docs_root, i18n)


GUIDE = "## Setup steps\n\n## Shared roots\n\nSee [setup](#setup-steps).\n"
GUIDE_DE = (
    "## Einrichtung\n\n## Gemeinsame Wurzeln\n\nSiehe [Einrichtung](#einrichtung).\n"
)


def test_routed_locales_come_from_the_site_table(tmp_path: Path) -> None:
    """The locale list is read from ROUTED_LOCALES, minus the default language."""
    _, i18n = _tree(tmp_path, {})
    assert checker.routed_locales(i18n) == ("de", "ar")
    real = checker.routed_locales()
    assert {"ar", "de", "pt-br", "zh-cn"} <= set(real)
    assert "en" not in real


def test_a_table_without_routed_locales_is_an_error(tmp_path: Path) -> None:
    """A locale file with no ROUTED_LOCALES list cannot be read."""
    empty = tmp_path / "i18n.ts"
    empty.write_text("export const OTHER = [];\n", encoding="utf-8")
    with pytest.raises(ValueError, match="no ROUTED_LOCALES"):
        checker.routed_locales(empty)


def test_scan_reads_headings_ids_and_links() -> None:
    """Headings get github-slugger ids; links skip code, comments and images."""
    scanned = checker.scan(SCANNED)
    assert [(h.line, h.depth, h.id) for h in scanned.headings] == [
        (8, 2, "setup-steps"),
        (17, 2, "setup-steps-1"),
        (19, 3, "custom-run"),
    ]
    assert [link.url for link in scanned.links] == [
        "#setup-steps",
        "/docs/other#part-two",
        "https://example.com/a.md#frag",
        "/docs/by-href#frag",
        "/docs/by-definition#frag",
    ]
    assert scanned.extra_ids == {"named-anchor", "boxed"}
    assert [link.url for link in scanned.component_links] == ["/docs/by-card#frag"]


def test_scan_numbers_links_by_the_line_they_start_on() -> None:
    """A link's line is where it starts, also inside a wrapped paragraph."""
    scanned = checker.scan(
        "First line\nthen a [wrapped\nlink](/docs/a#b).\n\n[late](#c)\n"
    )
    assert [(link.line, link.url) for link in scanned.links] == [
        (2, "/docs/a#b"),
        (5, "#c"),
    ]


@pytest.mark.parametrize(
    ("heading", "expected"),
    [
        ("Run `apothem install`", "run-apothem-install"),
        ("Call a model <bdi>python -m</bdi>", "call-a-model-python--m"),
        ("The **bold** and _italic_ way", "the-bold-and-italic-way"),
        ("A [link](/docs/x#y) inside", "a-link-inside"),
        ("Escaped \\*stars\\*", "escaped-stars"),
        ("Fish &amp; chips", "fish--chips"),
        ("Trailing hashes ##", "trailing-hashes"),
        ("Custom id [#my-id]", "my-id"),
    ],
)
def test_heading_ids_follow_the_sites_slugging(heading: str, expected: str) -> None:
    """The ids Fumadocs would give headings with inline markup."""
    assert [h.id for h in checker.scan(f"## {heading}\n").headings] == [expected]


def test_scan_reads_windows_line_endings() -> None:
    """A CRLF page gives the same headings and lines as an LF page."""
    text = "---\ntitle: T\n---\n\n## One\n\n[a](#one)\n"
    assert checker.scan(text.replace("\n", "\r\n")) == checker.scan(text)


def _headings(*pairs: tuple[int, str]) -> list[checker.Heading]:
    return [
        checker.Heading(index + 1, depth, id_)
        for index, (depth, id_) in enumerate(pairs)
    ]


def test_map_fragment_follows_the_heading_position() -> None:
    """An English id maps to the translated heading at the same position."""
    english = _headings((2, "setup"), (2, "shared-roots"), (3, "detail"))
    local = _headings((2, "einrichtung"), (2, "gemeinsame-wurzeln"), (3, "detail"))
    assert checker.map_fragment("shared-roots", english, local) == "gemeinsame-wurzeln"
    assert checker.map_fragment("detail", english, local) == "detail"


def test_map_fragment_prefers_the_english_position_over_a_matching_translated_id() -> (
    None
):
    """A translated id equal to another heading's English id does not capture the link."""
    english = _headings((2, "overview"), (2, "plugin"))
    local = _headings((2, "plugin"), (2, "uebersicht"))
    assert checker.map_fragment("overview", english, local) == "plugin"
    assert checker.map_fragment("plugin", english, local) == "uebersicht"


def test_map_fragment_decodes_percent_escapes() -> None:
    """A percent-encoded fragment names the same heading as its raw form."""
    english = _headings((2, "raíces"), (2, "other"))
    local = _headings((2, "root"), (2, "andere"))
    assert checker.map_fragment("ra%C3%ADces", english, local) == "root"


def test_map_fragment_gives_up_when_the_structure_differs() -> None:
    """A page with another heading structure keeps the link on the English page."""
    english = _headings((2, "a"), (2, "b"))
    assert checker.map_fragment("b", english, _headings((2, "x"))) is None
    assert checker.map_fragment("b", english, _headings((2, "x"), (3, "y"))) is None


def test_map_fragment_only_maps_english_ids() -> None:
    """A fragment that is not an English id is never mapped, translated id or not."""
    english = _headings((2, "a"), (2, "b"))
    local = _headings((2, "x"), (2, "y"))
    assert checker.map_fragment("y", english, local) is None
    assert checker.map_fragment("missing", english, local) is None


def test_translatable_hash_ignores_generated_regions_and_line_endings() -> None:
    """The hash is the sourceHash of site/lib/translation-source.mjs."""
    plain = "---\ntitle: T\n---\n\nText\n"
    assert checker.translatable_hash(plain) == checker.translatable_hash(
        plain.replace("\n", "\r\n") + "\n\n"
    )
    start = "{/* apothem:generated-reference:start */}"
    end = "{/* apothem:generated-reference:end */}"
    with_block = f"{plain}\n{start}\nrows {1}\n{end}\n"
    other_block = f"{plain}\n{start}\nrows {2} and more\n{end}\n"
    assert checker.translatable_hash(with_block) == checker.translatable_hash(
        other_block
    )
    assert checker.translatable_hash(plain) != checker.translatable_hash(
        plain + "More.\n"
    )
    assert len(checker.translatable_hash(plain)) == 16


def test_a_clean_tree_has_no_findings(tmp_path: Path) -> None:
    """Live same-page, cross-page and translated links produce no finding."""
    report = _run(
        tmp_path,
        {
            "index.mdx": "## Home\n\n[roots](/docs/guide#shared-roots) and [here](#home)\n",
            "guide.mdx": GUIDE,
            "de/index.mdx": "## Start\n\n[Wurzeln](/docs/guide#shared-roots) und [hier](#start)\n",
            "de/guide.mdx": GUIDE_DE,
        },
    )
    assert report.findings == []
    assert report.counts["same-page"] == 4
    assert report.counts["cross-page"] == 1
    assert report.counts["translated-cross-page"] == 1
    assert report.counts["localized"] == 1
    assert report.structure_drift == []


def test_an_english_link_to_a_missing_heading_is_found(tmp_path: Path) -> None:
    """A fragment that names no heading on the English page is a finding."""
    report = _run(
        tmp_path,
        {
            "index.mdx": "## Home\n\n[gone](/docs/guide#no-such-heading)\n",
            "guide.mdx": GUIDE,
        },
    )
    assert [(f.rule, f.line, f.url) for f in report.findings] == [
        ("fragment", 3, "/docs/guide#no-such-heading")
    ]
    assert "/docs/guide" in report.findings[0].message
    assert report.findings[0].render().endswith(report.findings[0].message)


def test_a_translated_id_on_a_translated_page_is_found_with_the_english_id(
    tmp_path: Path,
) -> None:
    """A translated page must link by the English id, and the finding names it."""
    report = _run(
        tmp_path,
        {
            "guide.mdx": GUIDE,
            "de/guide.mdx": GUIDE_DE,
            "de/index.mdx": "## Start\n\n[Wurzeln](/docs/guide#gemeinsame-wurzeln)\n",
            "index.mdx": "## Home\n",
        },
    )
    assert [f.rule for f in report.findings] == ["english-fragment"]
    assert "the English id is #shared-roots" in report.findings[0].message


def test_a_translated_same_page_link_uses_the_translated_id(tmp_path: Path) -> None:
    """On a translated page a same-page link takes the page's own id, not the English one."""
    report = _run(
        tmp_path,
        {
            "guide.mdx": GUIDE,
            "de/guide.mdx": "## Einrichtung\n\n## Gemeinsame Wurzeln\n\n[a](#setup-steps)\n",
        },
    )
    assert [(f.rule, f.url) for f in report.findings] == [("same-page", "#setup-steps")]


def test_a_translation_with_other_structure_keeps_the_english_page(
    tmp_path: Path,
) -> None:
    """When the headings differ the link is still valid, opens English, and is reported."""
    report = _run(
        tmp_path,
        {
            "index.mdx": "## Home\n",
            "guide.mdx": GUIDE,
            "de/index.mdx": "## Start\n\n[Wurzeln](/docs/guide#shared-roots)\n",
            "de/guide.mdx": "## Einrichtung\n",
        },
    )
    assert report.findings == []
    assert report.counts["stays-english"] == 1
    assert report.counts["localized"] == 0
    assert report.structure_drift == [
        checker.relative(tmp_path / "content/docs/de/guide.mdx")
    ]


def _stamped(text: str, english: str) -> str:
    """A translated page that records *english* as the text it translates."""
    return f'---\ntitle: T\nsourceHash: "{checker.translatable_hash(english)}"\n---\n\n{text}'


def test_a_current_translation_must_keep_the_english_structure(tmp_path: Path) -> None:
    """A translation that records the current English text and drops a heading is a defect."""
    report = _run(
        tmp_path,
        {
            "index.mdx": "## Home\n",
            "guide.mdx": GUIDE,
            "de/guide.mdx": _stamped("## Einrichtung\n", GUIDE),
        },
    )
    assert [f.rule for f in report.findings] == ["structure"]
    assert report.findings[0].url == ""
    assert "it has 1 headings and the English page has 2" in report.findings[0].message
    assert report.structure_drift == []


def test_a_current_translation_with_another_heading_level_names_the_heading(
    tmp_path: Path,
) -> None:
    """The structure finding names the first heading whose level differs."""
    report = _run(
        tmp_path,
        {
            "guide.mdx": GUIDE,
            "de/guide.mdx": _stamped(
                "## Einrichtung\n\n### Gemeinsame Wurzeln\n", GUIDE
            ),
        },
    )
    assert [f.rule for f in report.findings] == ["structure"]
    assert (
        "heading 2 is level 3 here and level 2 in English" in report.findings[0].message
    )


def test_an_older_translation_with_other_structure_is_only_reported(
    tmp_path: Path,
) -> None:
    """After an English edit the copy is older, so a structure difference waits for the refresh."""
    older = _stamped(
        "## Einrichtung\n", GUIDE + "\nA paragraph the translation lacks.\n"
    )
    report = _run(
        tmp_path,
        {"index.mdx": "## Home\n", "guide.mdx": GUIDE, "de/guide.mdx": older},
    )
    assert report.findings == []
    assert len(report.structure_drift) == 1


def test_a_component_href_to_the_docs_is_found(tmp_path: Path) -> None:
    """Only markdown links and ``<a>`` are localized, so a component's docs href is a defect."""
    report = _run(
        tmp_path,
        {
            "index.mdx": (
                '## Home\n\n<Card title="Guide" href="/docs/guide" />\n\n'
                '<Card title="Out" href="https://example.com/x" />\n\n'
                '<a href="/docs/guide#setup-steps">plain anchor</a>\n'
            ),
            "guide.mdx": GUIDE,
        },
    )
    assert [(f.rule, f.url) for f in report.findings] == [
        ("component-link", "/docs/guide")
    ]
    assert report.counts["cross-page"] == 1


def test_a_finding_renders_on_one_line() -> None:
    """A finding without a link leaves the link out of its line."""
    assert checker.Finding("a/b.mdx", 3, "", "structure", "m").render() == (
        "a/b.mdx:3: structure: m"
    )
    assert checker.Finding("a/b.mdx", 4, "/docs/x#y", "fragment", "m").render() == (
        "a/b.mdx:4: fragment: /docs/x#y: m"
    )


def test_a_link_to_an_untranslated_page_checks_the_english_ids(tmp_path: Path) -> None:
    """A page the language has not translated is checked against the English page."""
    report = _run(
        tmp_path,
        {
            "index.mdx": "## Home\n",
            "guide.mdx": GUIDE,
            "de/index.mdx": "## Start\n\n[ok](/docs/guide#setup-steps) [bad](/docs/guide#nope)\n",
        },
    )
    assert [f.url for f in report.findings] == ["/docs/guide#nope"]
    assert report.counts["stays-english"] == 1


def test_a_link_with_a_locale_prefix_is_checked_against_that_languages_page(
    tmp_path: Path,
) -> None:
    """``/de/docs/...`` opens the German copy, so it takes the German id."""
    report = _run(
        tmp_path,
        {
            "index.mdx": "## Home\n\n[de](/de/docs/guide#einrichtung) [en-id](/de/docs/guide#setup-steps)\n",
            "guide.mdx": GUIDE,
            "de/guide.mdx": GUIDE_DE,
        },
    )
    assert [f.url for f in report.findings] == ["/de/docs/guide#setup-steps"]
    assert report.findings[0].rule == "fragment"


def test_percent_encoded_fragments_match_raw_ids(tmp_path: Path) -> None:
    """The browser decodes a fragment before it looks for the id, and so does the check."""
    report = _run(
        tmp_path,
        {"index.mdx": "## Raíces\n\n[a](#ra%C3%ADces) [b](#raíces)\n"},
    )
    assert report.findings == []


def test_links_the_check_cannot_judge_are_skipped_or_flagged(tmp_path: Path) -> None:
    """External, fragment-less and non-docs links are skipped; a relative one is flagged."""
    report = _run(
        tmp_path,
        {
            "index.mdx": (
                "## Home\n\n[a](https://example.com/x#y) [b](/docs/guide) [c](/#features) "
                "[d](mailto:me@example.com#x) [e](#) [f](./guide#setup-steps) [g](/docs/nope#x)\n"
            ),
            "guide.mdx": GUIDE,
        },
    )
    assert [(f.rule, f.url) for f in report.findings] == [
        ("relative", "./guide#setup-steps"),
        ("missing-page", "/docs/nope#x"),
    ]


def test_the_docs_index_is_a_target(tmp_path: Path) -> None:
    """``/docs#id`` opens the docs index page."""
    report = _run(
        tmp_path,
        {
            "index.mdx": "## Home\n\n[a](/docs#home) [b](/docs/#nope)\n",
            "guide.mdx": GUIDE,
        },
    )
    assert [f.url for f in report.findings] == ["/docs/#nope"]


def test_main_reports_findings_and_exits_nonzero(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The CLI prints one line per finding and exits 1; a clean tree exits 0."""
    docs_root, i18n = _tree(
        tmp_path, {"index.mdx": "## Home\n\n[x](#nope)\n", "guide.mdx": GUIDE}
    )
    args = ["--docs-root", str(docs_root), "--i18n", str(i18n)]
    assert checker.main(args) == 1
    out = capsys.readouterr().out
    assert "same-page: #nope" in out
    assert "1 findings" in out

    (docs_root / "index.mdx").write_text("## Home\n", encoding="utf-8")
    assert checker.main([*args, "--structure"]) == 0
    assert "findings" not in capsys.readouterr().out


def test_main_exits_two_when_the_locale_table_is_unreadable(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A missing locale table is a usage error, distinct from a finding."""
    docs_root, _ = _tree(tmp_path, {"index.mdx": "## Home\n"})
    code = checker.main(
        ["--docs-root", str(docs_root), "--i18n", str(tmp_path / "none.ts")]
    )
    assert code == 2
    assert "check_site_anchor_links:" in capsys.readouterr().err


def test_a_line_that_starts_with_inline_code_does_not_open_a_fence() -> None:
    """Backticks after the first three on the line make it inline code, not a fence."""
    scanned = checker.scan(
        "```json``` files are listed here.\n\n## After\n\n[a](#after)\n"
    )
    assert [h.id for h in scanned.headings] == ["after"]
    assert [link.url for link in scanned.links] == ["#after"]


def test_each_fence_closes_on_its_own_marker() -> None:
    """A tilde fence and a longer backtick fence hide what is inside them."""
    text = "~~~\n## no\n~~~\n\n````\n```\n## not either\n```\n````\n\n## Real\n"
    assert [h.id for h in checker.scan(text).headings] == ["real"]


def test_headings_inside_list_items_and_quotes_are_read() -> None:
    """Markdown makes a heading of ``- ## x``, ``> ## x`` and ``1. ### x``."""
    scanned = checker.scan("- ## In a list\n> ## In a quote\n1. ### Numbered\n")
    assert [(h.depth, h.id) for h in scanned.headings] == [
        (2, "in-a-list"),
        (2, "in-a-quote"),
        (3, "numbered"),
    ]


def test_heading_forms_the_scanner_cannot_place_are_reported() -> None:
    """A setext heading and an empty one shift positions; a thematic break does not."""
    text = (
        "Title\n=====\n\nOther\n-----\n\n##\n\n---\n\n| a |\n| --- |\n\n- item\n---\n"
    )
    scanned = checker.scan(text)
    assert [line for line, _ in scanned.unsupported] == [2, 5, 7]
    assert scanned.headings == ()


def test_an_unsupported_heading_form_is_a_finding(tmp_path: Path) -> None:
    """The check says so when it cannot see a heading, instead of guessing positions."""
    report = _run(tmp_path, {"index.mdx": "Title\n=====\n"})
    assert [(f.rule, f.line) for f in report.findings] == [("unsupported-heading", 2)]


def test_a_locale_route_to_an_untranslated_page_is_a_finding(tmp_path: Path) -> None:
    """``/de/docs/<page>`` for a page German never translated is an English duplicate."""
    report = _run(
        tmp_path,
        {
            "index.mdx": "## Home\n\n[a](/de/docs/pipeline/plan) [b](/de/docs/guide#einrichtung)\n",
            "guide.mdx": GUIDE,
            "de/guide.mdx": GUIDE_DE,
            "pipeline/plan.mdx": "## Usage\n",
        },
    )
    assert [(f.rule, f.url) for f in report.findings] == [
        ("fallback-route", "/de/docs/pipeline/plan")
    ]


def test_main_prints_ids_a_console_cannot_show(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A finding with a non-ASCII id must not crash a console that cannot print it."""
    docs_root, i18n = _tree(
        tmp_path, {"index.mdx": "## Home\n\n[x](#" + chr(0x440) + "az)\n"}
    )
    buffer = io.BytesIO()
    stream = io.TextIOWrapper(buffer, encoding="ascii", errors="strict")
    monkeypatch.setattr(sys, "stdout", stream)
    assert checker.main(["--docs-root", str(docs_root), "--i18n", str(i18n)]) == 1
    stream.flush()
    assert "\\u0440az" in buffer.getvalue().decode("ascii")
