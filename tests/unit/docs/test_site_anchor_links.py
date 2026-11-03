# SPDX-License-Identifier: MIT

"""Every anchored docs link lands on a heading id of the page it opens.

Why this guard exists. A docs link with a ``#fragment`` only scrolls when the
page it opens has a heading with that id; otherwise the page opens at the top
with no error. On translated pages that went wrong 252 times, because Fumadocs
slugs each page's headings from that page's own text and the links carried the
translated id of a page the site served in English. Translated pages now link
across pages by the English id, and the site maps it onto the translated
heading by position (``site/components/localized-link.tsx``). This test reads
every page under ``site/content/docs`` with ``scripts/dev/check_site_anchor_links.py``
and fails on any anchored link that would not land, any translation that
records the current English text but changed its heading structure, and any
component that carries an in-site docs href past the localization.

It is the required form of the guard: it runs in the ``quality`` matrix and in
``coverage`` with Python alone, so it needs neither ``site/node_modules`` nor a
site build. ``site/scripts/github-slugger-table.mjs`` keeps the slug table it
relies on in step with the installed github-slugger.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "dev"))

import check_site_anchor_links as checker  # noqa: E402
import github_slugger  # noqa: E402


def test_every_anchored_link_lands_on_a_heading_id() -> None:
    """No page has an anchored link, a structure change or a component link the site cannot use."""
    report = checker.run()
    counts = report.counts
    # Anti-vacuous anchors: the corpus when the guard was written, 213 English
    # pages and 197 in each of eleven languages, with 600 same-page anchors and
    # 264 anchored cross-page links on translated pages.
    assert counts["pages"] >= 2300
    assert counts["locales"] == 11
    assert counts["same-page"] >= 500
    assert counts["cross-page"] >= 20
    assert counts["translated-cross-page"] >= 200
    # The structure rule only fires for a translation that records the current
    # English text, so the hash port must recognise most of them as current.
    assert counts["current-translations"] >= 1500
    lines = [finding.render() for finding in report.findings]
    shown = "\n".join(lines[:15])
    assert lines == [], (
        f"{len(lines)} findings (first {min(len(lines), 15)}):\n{shown}\n"
        "A cross-page #fragment on a translated page is the ENGLISH id; a same-page "
        "#fragment is the translated page's own id. "
        "Run `python scripts/dev/check_site_anchor_links.py` for the full list."
    )


def test_the_slug_table_belongs_to_the_locked_github_slugger() -> None:
    """The removal table records the github-slugger version that package-lock.json locks."""
    lock = json.loads(
        (REPO_ROOT / "site" / "package-lock.json").read_text(encoding="utf-8")
    )
    locked = lock["packages"]["node_modules/github-slugger"]["version"]
    header = github_slugger.TABLE_PATH.read_text(encoding="utf-8").split("\n\n", 1)[0]
    recorded = re.search(r"github-slugger (\d+\.\d+\.\d+) removes", header)
    assert recorded is not None, "github-slugger-removed.txt does not name a version"
    assert recorded.group(1) == locked, (
        f"site/package-lock.json locks github-slugger {locked} but the removal table "
        f"was generated from {recorded.group(1)}; run `node scripts/github-slugger-table.mjs` "
        "from site/ (after `npm ci`), review the table's diff and the guard's results, and commit it"
    )
