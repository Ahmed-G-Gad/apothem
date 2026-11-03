# SPDX-License-Identifier: MIT

"""Fail when an anchored docs link does not land on a heading id of the page it opens.

Why this check exists. A link such as ``/docs/install#choose-a-channel`` only
scrolls when the page it opens has a heading whose id is ``choose-a-channel``.
When no heading has that id the browser opens the page at the top, with no
error. Translated pages made this likely: Fumadocs slugs each page's headings
from that page's own text, so a translated page's ids are translated, and 252
cross-page links on translated pages carried the translated id of a page that
the site then served in English, where it matches nothing. No check saw it:
``link_check`` strips the fragment before it resolves a link, and nothing reads
heading ids before the site is built.

The site now sends a body link on a translated page to the translated copy of
its target and maps the fragment by heading position
(``site/components/localized-link.tsx``). So a cross-page fragment in a
translated page's source is the ENGLISH id, and its same-page fragments are the
translated page's own ids.

Checks, over every page under ``site/content/docs``:

- ``#id`` on its own: an id on the page itself;
- ``/docs/<page>#id`` on an English page: an id on the English ``<page>``;
- ``/docs/<page>#id`` on a translated page: an id on the English ``<page>``
  and, where the language has its own copy of ``<page>``, the fragment the site
  maps it to is an id on that copy;
- ``/<locale>/docs/<page>#id``: an id on the page that route serves;
- a translated page that records the current English text (its ``sourceHash``
  matches) has the English page's heading structure, because the mapping
  compares the two;
- no component such as ``<Card href="/docs/...">`` carries an in-site docs
  href, because only markdown links and ``<a>`` pass through the localization.

An id is a markdown heading's github-slugger id (``github_slugger.py``), a
heading's ``[#id]`` marker, or an ``id`` attribute in the page's HTML or JSX.
Only ATX headings (``## Title``) are read. The check reads page sources, not the
built site, so a heading whose text the flattener below cannot reproduce
exactly should set its id with ``[#id]``.

Reported but not failed: a translated page that records older English text and
whose heading structure differs. Its inbound anchored links open the English
page until the translation is refreshed.

``check_built_docs_links.py`` repeats the link checks on the built site, where
the localization has actually happened.

Exit codes: ``0`` when clean, ``1`` on any finding, ``2`` when the docs tree or
the routed-locale list cannot be read.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import re
import sys
from collections import Counter
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import NamedTuple
from urllib.parse import unquote

sys.path.insert(0, str(Path(__file__).resolve().parent))

from github_slugger import Slugger

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCS_ROOT = REPO_ROOT / "site" / "content" / "docs"
I18N_TS = REPO_ROOT / "site" / "lib" / "i18n.ts"
DEFAULT_LOCALE = "en"

_ROUTED_LOCALES = re.compile(
    r"export const ROUTED_LOCALES\b[^=]*=\s*\[(?P<list>[^\]]*)\]"
)
_FRONTMATTER = re.compile(r"\A---\n.*?\n---\n", re.DOTALL)
_SOURCE_HASH = re.compile(r"^sourceHash: \"?(?P<hash>[0-9a-f]+)\"?\s*$", re.MULTILINE)
_COMMENT = re.compile(r"\{/\*.*?\*/\}", re.DOTALL)
_FENCE = re.compile(r"^[ \t]*(`{3,}|~{3,})")
_ATX = re.compile(r"^[ \t]*(#{1,6})(?:[ \t]+(.*?))?(?:[ \t]+#+)?[ \t]*$")
_CUSTOM_ID = re.compile(r"\s*\[#(?P<id>[\s\S]+?)]\s*$")
_CODE_SPAN = re.compile(r"(`+)(?!`).+?(?<!`)\1(?!`)", re.DOTALL)
_TABLE_ROW = re.compile(r"^[ \t]*\|")
_CELL_SEPARATOR = re.compile(r"(?<!\\)\|")
_INLINE_LINK = re.compile(
    r"(?<![!\\])\[(?:[^\[\]\\]|\\.|\[(?:[^\[\]\\]|\\.)*\])*\]"
    r"\(\s*(?P<dest><[^<>\n]*>|(?:[^()\s\\]|\\.|\((?:[^()\s\\]|\\.)*\))*)"
    r"(?:\s+(?:\"(?:[^\"\\]|\\.)*\"|'(?:[^'\\]|\\.)*'|\((?:[^()\\]|\\.)*\)))?\s*\)"
)
_DEFINITION = re.compile(
    r"^[ \t]{0,3}\[(?!\^)[^\]\n]+\]:[ \t]*(?P<dest><[^<>\n]*>|\S+)", re.MULTILINE
)
_HREF = re.compile(
    r"""<(?P<tag>[A-Za-z][\w.]*)\b[^<>]*?\bhref\s*=\s*(?:"(?P<dq>[^"]*)"|'(?P<sq>[^']*)')"""
)
_TAG_ID = re.compile(
    r"""<[A-Za-z][^<>]*?\sid\s*=\s*(?:"(?P<dq>[^"]+)"|'(?P<sq>[^']+)')"""
)
_ANCHOR_NAME = re.compile(
    r"""<a\s[^<>]*?\bname\s*=\s*(?:"(?P<dq>[^"]+)"|'(?P<sq>[^']+)')"""
)

# Inline markdown inside a heading, flattened the way Fumadocs' ``flattenNode``
# does: text and code spans keep their characters, everything else keeps only
# its children.
_HEADING_CODE_SPAN = re.compile(r"(`+)(.+?)(?<!`)\1(?!`)")
_IMAGE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
_LINK = re.compile(r"\[((?:[^\[\]]|\[[^\]]*\])*)\]\((?:[^()]|\([^)]*\))*\)")
_JSX_TAG = re.compile(r"</?[A-Za-z][\w.:-]*(?:\s+[^<>]*?)?/?>")
_ESCAPE = re.compile(r"\\([!-/:-@\[-`{-~])")
_STAR_EMPHASIS = re.compile(r"(\*{1,3})(?=\S)(.+?)(?<=\S)\1")
_UNDERSCORE_EMPHASIS = re.compile(r"(?<![\w])(_{1,3})(?=\S)(.+?)(?<=\S)\1(?![\w])")
_STRIKETHROUGH = re.compile(r"(~~)(?=\S)(.+?)(?<=\S)\1")
_PLACEHOLDER = re.compile("\x00(\\d+)\x00")

# ``site/lib/translation-source.mjs``: the text a ``sourceHash`` covers leaves
# these generated blocks out.
_GENERATED_REGIONS = (
    (
        "{/* apothem:generated-reference:start */}",
        "{/* apothem:generated-reference:end */}",
    ),
    ("{/* apothem:changelog:start */}", "{/* apothem:changelog:end */}"),
)
# What JavaScript's ``trim`` strips, which Python's ``strip`` does not match.
_JS_WHITESPACE = "".join(
    map(
        chr,
        (
            *range(0x09, 0x0E),
            0x20,
            0xA0,
            0x1680,
            *range(0x2000, 0x200B),
            0x2028,
            0x2029,
            0x202F,
            0x205F,
            0x3000,
            0xFEFF,
        ),
    )
)

PageKey = tuple[str, tuple[str, ...]]


class Heading(NamedTuple):
    """One markdown heading: its line, depth and the id the site gives it."""

    line: int
    depth: int
    id: str


class Link(NamedTuple):
    """One link destination found in a page, with the line it starts on."""

    line: int
    url: str


class Scanned(NamedTuple):
    """What a page's source holds that the check needs."""

    headings: tuple[Heading, ...]
    extra_ids: frozenset[str]
    links: tuple[Link, ...]
    component_links: tuple[Link, ...]


@dataclass(frozen=True)
class Page:
    """A docs page as the check sees it."""

    locale: str
    slug: tuple[str, ...]
    path: Path
    scanned: Scanned
    text_hash: str
    recorded_hash: str | None

    @property
    def headings(self) -> tuple[Heading, ...]:
        """The page's markdown headings, in order."""
        return self.scanned.headings

    @property
    def links(self) -> tuple[Link, ...]:
        """The page's link destinations."""
        return self.scanned.links

    @property
    def ids(self) -> frozenset[str]:
        """Every fragment that lands on this page."""
        return frozenset(h.id for h in self.headings) | self.scanned.extra_ids

    @property
    def route(self) -> str:
        """The URL the site serves this page at."""
        prefix = "/docs" if self.locale == DEFAULT_LOCALE else f"/{self.locale}/docs"
        return "/".join([prefix, *self.slug])

    @property
    def shape(self) -> tuple[int, ...]:
        """The heading depths in order, which the fragment mapping compares."""
        return tuple(heading.depth for heading in self.headings)


@dataclass(frozen=True)
class Finding:
    """One defect: an anchored link that does not land, or a page the mapping cannot use."""

    page: str
    line: int
    url: str
    rule: str
    message: str

    def render(self) -> str:
        """The finding as one ``path:line: rule: url: message`` line."""
        subject = f" {self.url}:" if self.url else ""
        place = f"{self.page}:{self.line}" if self.line else self.page
        return f"{place}: {self.rule}:{subject} {self.message}"


@dataclass
class Report:
    """What a run found and counted."""

    findings: list[Finding] = field(default_factory=list)
    counts: Counter[str] = field(default_factory=Counter)
    structure_drift: list[str] = field(default_factory=list)


def routed_locales(i18n_ts: Path = I18N_TS) -> tuple[str, ...]:
    """The routed non-default locales, read from the site's own locale table."""
    match = _ROUTED_LOCALES.search(i18n_ts.read_text(encoding="utf-8"))
    if match is None:
        raise ValueError(f"{i18n_ts}: no ROUTED_LOCALES list")
    names = re.findall(r"""['"]([^'"]+)['"]""", match.group("list"))
    return tuple(name for name in names if name != DEFAULT_LOCALE)


def translatable_hash(source: str) -> str:
    """The ``sourceHash`` of an English page: ``site/lib/translation-source.mjs`` in Python."""
    text = re.sub(r"\r\n?", "\n", source)
    for start, end in _GENERATED_REGIONS:
        position = 0
        while True:
            opened = text.find(start, position)
            if opened == -1:
                break
            closed = text.find(end, opened + len(start))
            if closed == -1:
                break
            text = text[: opened + len(start)] + text[closed:]
            position = opened + len(start) + len(end)
    lines = (line.rstrip(_JS_WHITESPACE) for line in text.split("\n"))
    text = "\n".join(lines).strip(_JS_WHITESPACE)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _blank(text: str, pattern: re.Pattern[str]) -> str:
    """Replace every match with spaces, keeping newlines so line numbers hold."""
    return pattern.sub(lambda m: re.sub(r"[^\n]", " ", m.group(0)), text)


def _blank_code_spans(block: str) -> str:
    """Blank a block's inline code spans.

    A table row is split into cells before its inline markdown is read, so a
    code span never crosses a cell: an unclosed backtick in one cell does not
    pair with a backtick in the next.
    """
    out: list[str] = []
    paragraph: list[str] = []

    def flush() -> None:
        if paragraph:
            out.extend(_blank("\n".join(paragraph), _CODE_SPAN).split("\n"))
            paragraph.clear()

    for line in block.split("\n"):
        if _TABLE_ROW.match(line):
            flush()
            cells = _CELL_SEPARATOR.split(line)
            out.append("|".join(_blank(cell, _CODE_SPAN) for cell in cells))
        else:
            paragraph.append(line)
    flush()
    return "\n".join(out)


def _flatten(heading_text: str) -> str:
    """The text Fumadocs slugs for a heading: its inline markdown, flattened."""
    spans: list[str] = []

    def keep(match: re.Match[str]) -> str:
        content = match.group(2)
        if len(content) >= 2 and content[0] == content[-1] == " " and content.strip():
            content = content[1:-1]
        spans.append(content)
        return f"\x00{len(spans) - 1}\x00"

    text = _HEADING_CODE_SPAN.sub(keep, heading_text)
    text = _IMAGE.sub("", text)
    for _ in range(3):
        text = _LINK.sub(lambda m: m.group(1), text)
    text = _JSX_TAG.sub("", text)
    text = _STRIKETHROUGH.sub(lambda m: m.group(2), text)
    for _ in range(2):
        text = _STAR_EMPHASIS.sub(lambda m: m.group(2), text)
        text = _UNDERSCORE_EMPHASIS.sub(lambda m: m.group(2), text)
    text = _ESCAPE.sub(lambda m: m.group(1), text)
    text = html.unescape(text)
    return _PLACEHOLDER.sub(lambda m: spans[int(m.group(1))], text)


def _destination(raw: str) -> str:
    """A link destination without its ``<>``, escapes or character references."""
    if raw.startswith("<") and raw.endswith(">"):
        raw = raw[1:-1]
    return html.unescape(_ESCAPE.sub(lambda m: m.group(1), raw))


def _prose_and_headings(text: str) -> tuple[list[str], list[Heading]]:
    """Split a page into its prose lines (fences emptied) and its headings."""
    slugger = Slugger()
    prose: list[str] = []
    headings: list[Heading] = []
    fence: str | None = None
    for number, line in enumerate(text.split("\n"), 1):
        opening = _FENCE.match(line)
        if fence is not None:
            if (
                opening is not None
                and opening.group(1)[0] == fence[0]
                and len(opening.group(1)) >= len(fence)
                and not line.strip()[len(opening.group(1)) :].strip()
            ):
                fence = None
            prose.append("")
            continue
        if opening is not None:
            fence = opening.group(1)
            prose.append("")
            continue
        prose.append(line)
        atx = _ATX.match(line)
        if atx is None or atx.group(2) is None:
            continue
        custom = _CUSTOM_ID.search(atx.group(2))
        heading_id = (
            custom.group("id") if custom else slugger.slug(_flatten(atx.group(2)))
        )
        headings.append(Heading(number, len(atx.group(1)), heading_id))
    return prose, headings


def _blocks(prose: list[str]) -> Iterator[tuple[int, str]]:
    """Yield ``(first line number, text)`` for each run of non-blank lines."""
    start = 0
    for index, line in enumerate([*prose, ""]):
        if line.strip():
            continue
        if index > start:
            yield start + 1, "\n".join(prose[start:index])
        start = index + 1


def scan(text: str) -> Scanned:
    """Return a page's headings, extra ids and links from its MDX source."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    if text.startswith("---\n"):
        text = _blank(text, _FRONTMATTER)
    text = _blank(text, _COMMENT)
    prose, headings = _prose_and_headings(text)

    extra_ids: set[str] = set()
    links: list[Link] = []
    component_links: list[Link] = []
    for first_line, block in _blocks(prose):
        block = _blank_code_spans(block)

        def line_of(
            offset: int, first_line: int = first_line, block: str = block
        ) -> int:
            return first_line + block.count("\n", 0, offset)

        for found in _INLINE_LINK.finditer(block):
            links.append(
                Link(line_of(found.start()), _destination(found.group("dest")))
            )
        for found in _DEFINITION.finditer(block):
            links.append(
                Link(line_of(found.start()), _destination(found.group("dest")))
            )
        for found in _HREF.finditer(block):
            url = html.unescape(found.group("dq") or found.group("sq") or "")
            link = Link(line_of(found.start()), url)
            (links if found.group("tag") == "a" else component_links).append(link)
        for pattern in (_TAG_ID, _ANCHOR_NAME):
            for found in pattern.finditer(block):
                extra_ids.add(found.group("dq") or found.group("sq"))
    return Scanned(
        tuple(headings), frozenset(extra_ids), tuple(links), tuple(component_links)
    )


def load_pages(docs_root: Path, locales: Sequence[str]) -> dict[PageKey, Page]:
    """Read every docs page, keyed by ``(locale, slug)``; English is ``en``."""
    pages: dict[PageKey, Page] = {}
    for path in sorted(docs_root.rglob("*")):
        if path.suffix not in (".md", ".mdx") or not path.is_file():
            continue
        parts = list(path.relative_to(docs_root).with_suffix("").parts)
        locale = parts.pop(0) if parts[0] in locales else DEFAULT_LOCALE
        if parts[-1] == "index":
            parts.pop()
        text = path.read_text(encoding="utf-8")
        recorded = _SOURCE_HASH.search(text.split("\n---\n", 1)[0])
        pages[(locale, tuple(parts))] = Page(
            locale,
            tuple(parts),
            path,
            scan(text),
            translatable_hash(text),
            recorded.group("hash") if recorded else None,
        )
    return pages


def map_fragment(
    fragment: str, english: Sequence[Heading], local: Sequence[Heading]
) -> str | None:
    """The id of the translated heading a site link to ``#fragment`` lands on.

    Mirrors ``localizeDocsHref`` in ``site/lib/locale-links.ts``: the fragment
    is an English id and the translated page has the same heading structure, so
    the heading at the same position is the target. ``None`` means the site
    keeps the English page.
    """
    wanted = unquote(fragment)
    position = next((i for i, h in enumerate(english) if h.id == wanted), None)
    if position is None or len(english) != len(local):
        return None
    if any(a.depth != b.depth for a, b in zip(english, local, strict=True)):
        return None
    return local[position].id


def _split(url: str) -> tuple[str, str] | None:
    """``(path, fragment)`` for a link that carries a fragment, else ``None``."""
    path, hash_, fragment = url.partition("#")
    fragment = fragment.strip()
    if not hash_ or not fragment:
        return None
    return path.split("?", 1)[0], fragment


def _is_external(path: str) -> bool:
    return (
        path.startswith("//")
        or re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", path) is not None
    )


def docs_target(path: str, locales: Sequence[str]) -> PageKey | None:
    """``(locale, slug)`` for a ``/docs`` or ``/<locale>/docs`` path, else ``None``."""
    if not path.startswith("/"):
        return None
    segments = [segment for segment in path.split("/") if segment]
    locale = DEFAULT_LOCALE
    if segments and segments[0] in locales:
        locale = segments.pop(0)
    if not segments or segments[0] != "docs":
        return None
    return locale, tuple(unquote(segment) for segment in segments[1:])


def _translated_id_hint(fragment: str, english: Page, local: Page | None) -> str:
    """Name the English id when the fragment is the translated heading's id."""
    if local is None:
        return ""
    wanted = unquote(fragment)
    for position, heading in enumerate(local.headings):
        if heading.id == wanted and position < len(english.headings):
            english_id = english.headings[position].id
            return f" (that is the translated id; the English id is #{english_id})"
    return ""


def relative(path: Path) -> str:
    try:
        return path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _first_difference(english: Page, local: Page) -> str:
    """Say where two pages' heading structures first differ."""
    for position, (a, b) in enumerate(zip(english.shape, local.shape, strict=False), 1):
        if a != b:
            return f"heading {position} is level {b} here and level {a} in English"
    return f"it has {len(local.shape)} headings and the English page has {len(english.shape)}"


class _Checker:
    """Check each anchored link of each page against the pages it opens."""

    def __init__(self, pages: dict[PageKey, Page], locales: Sequence[str]) -> None:
        self.pages = pages
        self.locales = locales
        self.report = Report()

    def run(self) -> Report:
        for page in self.pages.values():
            self._check_structure(page)
            for link in page.scanned.component_links:
                self._check_component_link(page, link)
            for link in page.links:
                parts = _split(link.url)
                if parts is not None and not _is_external(parts[0]):
                    self._check(page, link, *parts)
        return self.report

    def _fail(self, page: Page, line: int, url: str, rule: str, message: str) -> None:
        self.report.findings.append(
            Finding(relative(page.path), line, url, rule, message)
        )

    def _check_structure(self, page: Page) -> None:
        english = self.pages.get((DEFAULT_LOCALE, page.slug))
        if page.locale == DEFAULT_LOCALE or english is None:
            return
        current = page.recorded_hash == english.text_hash
        if current:
            self.report.counts["current-translations"] += 1
        if page.shape == english.shape:
            return
        if current:
            self._fail(
                page,
                1,
                "",
                "structure",
                "this translation records the current English text but "
                f"{_first_difference(english, page)}; the site opens a translated "
                "section only when both pages have the same headings",
            )
        else:
            self.report.structure_drift.append(relative(page.path))

    def _check_component_link(self, page: Page, link: Link) -> None:
        if link.url == "/docs" or link.url.startswith(("/docs/", "/docs#", "/docs?")):
            self._fail(
                page,
                link.line,
                link.url,
                "component-link",
                "a component's href is not localized on translated pages; "
                "write a markdown link instead",
            )

    def _check(self, page: Page, link: Link, path: str, fragment: str) -> None:
        counts = self.report.counts
        if path == "":
            counts["same-page"] += 1
            if unquote(fragment) not in page.ids:
                self._fail(
                    page,
                    link.line,
                    link.url,
                    "same-page",
                    "no heading on this page has that id",
                )
            return
        target = docs_target(path, self.locales)
        if target is None:
            if not path.startswith("/"):
                self._fail(
                    page,
                    link.line,
                    link.url,
                    "relative",
                    "a relative link with a fragment cannot be checked; "
                    "use an absolute /docs/ path",
                )
            return
        locale, slug = target
        english = self.pages.get((DEFAULT_LOCALE, slug))
        opened = self.pages.get((locale, slug)) or english
        if opened is None or english is None:
            self._fail(
                page,
                link.line,
                link.url,
                "missing-page",
                f"/docs/{'/'.join(slug)} is not a docs page",
            )
            return
        if locale != DEFAULT_LOCALE or page.locale == DEFAULT_LOCALE:
            counts["cross-page"] += 1
            if unquote(fragment) not in opened.ids:
                self._fail(
                    page,
                    link.line,
                    link.url,
                    "fragment",
                    f"no heading on {opened.route} has that id",
                )
            return
        self._check_translated(page, link, fragment, english)

    def _check_translated(
        self, page: Page, link: Link, fragment: str, english: Page
    ) -> None:
        """A translated page's link to ``english`` by its English route."""
        counts = self.report.counts
        counts["translated-cross-page"] += 1
        own = self.pages.get((page.locale, english.slug))
        if unquote(fragment) not in english.ids:
            hint = _translated_id_hint(fragment, english, own)
            self._fail(
                page,
                link.line,
                link.url,
                "english-fragment",
                f"no heading on {english.route} has that id; a cross-page fragment "
                f"on a translated page is the English id{hint}",
            )
            return
        mapped = (
            None
            if own is None
            else map_fragment(fragment, english.headings, own.headings)
        )
        if mapped is None:
            counts["stays-english"] += 1
        elif own is not None and mapped in own.ids:
            counts["localized"] += 1
        else:
            self._fail(
                page,
                link.line,
                link.url,
                "mapping",
                f"the site maps it to #{mapped}, which no heading has",
            )


def check_pages(pages: dict[PageKey, Page], locales: Sequence[str]) -> Report:
    """Check every anchored link on every page."""
    report = _Checker(pages, locales).run()
    report.counts["pages"] = len(pages)
    report.counts["locales"] = len(locales)
    return report


def run(docs_root: Path = DOCS_ROOT, i18n_ts: Path = I18N_TS) -> Report:
    """Load the pages under *docs_root* and check them."""
    locales = routed_locales(i18n_ts)
    return check_pages(load_pages(docs_root, locales), locales)


def _summary(report: Report) -> list[str]:
    counts = report.counts
    lines = [
        f"{counts['pages']} pages in {counts['locales'] + 1} languages; anchored links: "
        f"{counts['same-page']} to their own page, {counts['cross-page']} across pages, "
        f"{counts['translated-cross-page']} across pages on translated pages "
        f"({counts['localized']} open the translation, {counts['stays-english']} stay on English)"
    ]
    if report.structure_drift:
        lines.append(
            f"{len(report.structure_drift)} older translations differ from English in "
            "heading structure, so anchored links to them open the English page"
        )
    return lines


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Returns the process exit code."""
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--docs-root", type=Path, default=DOCS_ROOT)
    parser.add_argument("--i18n", type=Path, default=I18N_TS)
    parser.add_argument(
        "--structure",
        action="store_true",
        help="also list the older translations whose heading structure differs",
    )
    args = parser.parse_args(argv)
    try:
        report = run(args.docs_root, args.i18n)
    except (OSError, ValueError) as error:
        print(f"check_site_anchor_links: {error}", file=sys.stderr)
        return 2
    for line in _summary(report):
        print(line)
    if args.structure:
        for page in sorted(report.structure_drift):
            print(f"structure: {page}")
    for finding in report.findings:
        print(finding.render())
    if report.findings:
        print(
            f"{len(report.findings)} findings: anchored links or pages the site cannot use"
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
