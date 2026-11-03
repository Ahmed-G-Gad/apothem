# SPDX-License-Identifier: MIT

"""Fail when the built docs site sends a reader to the wrong language or to a dead fragment.

Why this check exists. ``check_site_anchor_links.py`` reads page sources, but
two things it relies on happen only when the site is built: a body link on a
translated page is pointed at the translated copy of its target while the page
renders (``site/components/localized-link.tsx``, from the content loader's table
of contents), and a heading's id is whatever the build gives it. A Fumadocs
upgrade that changes the table of contents would leave every translated link on
the English page, and nothing in the sources would show it. This check reads the
built HTML.

Checks, over the body (the first ``div.prose`` inside ``main``) of every built
page:

- a translated page has no link to ``/docs/<page>`` when its language has its
  own copy of ``<page>``;
- a link to ``/<locale>/docs/<page>`` opens a page that language translated;
- a link with a ``#fragment``, and each link to the page itself, lands on an
  element id of the built page it opens, by the browser's rule: the id as
  written or percent-decoded.

Run it after ``npm run build`` in ``site/``: ``python
scripts/dev/check_built_docs_links.py site/dist``. ``docs-build`` in CI does.

Exit codes: ``0`` when clean, ``1`` on any finding, ``2`` when the built tree,
the docs tree or the routed-locale list cannot be read.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from collections.abc import Sequence
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote

sys.path.insert(0, str(Path(__file__).resolve().parent))

from check_site_anchor_links import (
    DEFAULT_LOCALE,
    DOCS_ROOT,
    I18N_TS,
    REPO_ROOT,
    Finding,
    Page,
    PageKey,
    docs_target,
    load_pages,
    relative,
    routed_locales,
)

DEFAULT_DIST = REPO_ROOT / "site" / "dist"
_HEADINGS = frozenset({"h1", "h2", "h3", "h4", "h5", "h6"})
_CHUNK = 1 << 16  # a page's body ends well inside its first few of these


class Body(HTMLParser):
    """The links and element ids in a built page's body: its first ``div.prose``."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.depth = 0
        self.seen = False
        self.in_heading = False
        self.links: list[str] = []
        self.ids: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {name: value or "" for name, value in attrs}
        if tag == "div":
            if self.depth:
                self.depth += 1
            elif not self.seen and "prose" in attributes.get("class", "").split():
                self.depth = 1
                self.seen = True
        if not self.depth:
            return
        if tag in _HEADINGS:
            self.in_heading = True
        if attributes.get("id"):
            self.ids.add(attributes["id"])
        if tag == "a":
            if attributes.get("name"):
                self.ids.add(attributes["name"])
            # The self-link the heading component puts in a heading is not a body link.
            if attributes.get("href") and not self.in_heading:
                self.links.append(attributes["href"])

    def handle_endtag(self, tag: str) -> None:
        if tag in _HEADINGS:
            self.in_heading = False
        if tag == "div" and self.depth:
            self.depth -= 1


def read_body(path: Path) -> Body | None:
    """Parse the body of a built page, reading no further than ``</main>``."""
    if not path.is_file():
        return None
    chunks: list[bytes] = []
    with path.open("rb") as handle:
        while chunk := handle.read(_CHUNK):
            chunks.append(chunk)
            if b"</main>" in b"".join(chunks[-2:]):
                break
    text = b"".join(chunks).decode("utf-8", "replace")
    start = text.find("<main")
    if start == -1:
        return None
    end = text.find("</main>", start)
    body = Body()
    body.feed(text[start : end if end != -1 else len(text)])
    return body


def built_path(dist: Path, key: PageKey) -> Path:
    """Where the static export writes the page at ``(locale, slug)``."""
    locale, slug = key
    base = dist if locale == DEFAULT_LOCALE else dist / locale
    return base / ("docs.html" if not slug else "/".join(("docs", *slug)) + ".html")


class _Checker:
    """Check the links of every built page against the pages they open."""

    def __init__(
        self, pages: dict[PageKey, Page], locales: Sequence[str], dist: Path
    ) -> None:
        self.pages = pages
        self.locales = locales
        self.dist = dist
        self.findings: list[Finding] = []
        self.counts: Counter[str] = Counter()
        self._bodies: dict[PageKey, Body | None] = {}

    def body(self, key: PageKey) -> Body | None:
        if key not in self._bodies:
            self._bodies[key] = read_body(built_path(self.dist, key))
        return self._bodies[key]

    def run(self) -> None:
        for key, page in self.pages.items():
            built = self.body(key)
            if built is None:
                self._fail(page, "", "built-missing", "the build wrote no page for it")
                continue
            self.counts["pages"] += 1
            for href in built.links:
                self._check(page, built, href)

    def _fail(self, page: Page, href: str, rule: str, message: str) -> None:
        self.findings.append(
            Finding(relative(page.path), 0, unquote(href), rule, message)
        )

    def _check(self, page: Page, built: Body, href: str) -> None:
        path, _, fragment = href.partition("#")
        wanted = unquote(fragment)
        if not path and fragment:
            self.counts["anchored"] += 1
            if wanted not in built.ids and fragment not in built.ids:
                self._fail(
                    page, href, "built-fragment", "no element on the page has that id"
                )
            return
        target = docs_target(path.split("?", 1)[0], self.locales)
        if target is None:
            return
        locale, slug = target
        self.counts["docs-links"] += 1
        translated = (page.locale, slug) in self.pages
        if page.locale != DEFAULT_LOCALE and locale == DEFAULT_LOCALE and translated:
            self._fail(
                page,
                href,
                "built-unlocalized",
                f"{page.locale} has its own copy of this page, so the link should open /{page.locale}/docs/...",
            )
            return
        if locale != DEFAULT_LOCALE:
            self.counts["localized"] += 1
            if (locale, slug) not in self.pages:
                self._fail(
                    page,
                    href,
                    "built-fallback",
                    f"{locale} has not translated this page",
                )
                return
        if fragment:
            self.counts["anchored"] += 1
            served = self.body(target)
            if served is None:
                self._fail(
                    page, href, "built-missing", "the page it opens is not in the build"
                )
            elif wanted not in served.ids and fragment not in served.ids:
                self._fail(
                    page,
                    href,
                    "built-fragment",
                    "no element on the page it opens has that id",
                )


def check_dist(
    dist: Path, pages: dict[PageKey, Page], locales: Sequence[str]
) -> tuple[list[Finding], Counter[str]]:
    """Check the built site under *dist* against the pages it was built from."""
    checker = _Checker(pages, locales, dist)
    checker.run()
    return checker.findings, checker.counts


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Returns the process exit code."""
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("dist", type=Path, nargs="?", default=DEFAULT_DIST)
    parser.add_argument("--docs-root", type=Path, default=DOCS_ROOT)
    parser.add_argument("--i18n", type=Path, default=I18N_TS)
    args = parser.parse_args(argv)
    try:
        if not args.dist.is_dir():
            raise ValueError(
                f"{args.dist}: no built site; run `npm run build` in site/ first"
            )
        locales = routed_locales(args.i18n)
        pages = load_pages(args.docs_root, locales)
        findings, counts = check_dist(args.dist, pages, locales)
    except (OSError, ValueError) as error:
        print(f"check_built_docs_links: {error}", file=sys.stderr)
        return 2
    print(
        f"{counts['pages']} built pages; {counts['docs-links']} docs links, "
        f"{counts['localized']} of them to a translated page; {counts['anchored']} anchored links"
    )
    for finding in findings:
        print(finding.render())
    if findings:
        print(f"{len(findings)} findings in the built site")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
