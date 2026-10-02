# SPDX-License-Identifier: MIT

"""ROADMAP.md is the single roadmap; the site page mirrors it.

Two hand-written roadmaps had drifted: seven items appeared in only one of
them, and both sent requests to GitHub Discussions, which is not enabled. The
site page is now a shell whose body ``site/scripts/update-reference-inventory.mjs``
copies from ROADMAP.md between roadmap markers, the same way the changelog
page mirrors CHANGELOG.md, and requests go to the issue tracker.
"""

from __future__ import annotations

import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SOURCE = _REPO_ROOT / "ROADMAP.md"
_PAGE = _REPO_ROOT / "site" / "content" / "docs" / "community" / "roadmap.mdx"
_START = "{/* apothem:roadmap:start */}"
_END = "{/* apothem:roadmap:end */}"


def _source_body() -> str:
    raw = _SOURCE.read_text(encoding="utf-8")
    raw = re.sub(r"^\s*<!--[\s\S]*?-->\s*", "", raw)
    raw = re.sub(r"^# [^\n]*\n", "", raw)
    return raw.strip()


def _page_parts() -> tuple[str, str, str]:
    text = _PAGE.read_text(encoding="utf-8")
    assert text.count(_START) == 1, "roadmap page lacks its start marker"
    assert text.count(_END) == 1, "roadmap page lacks its end marker"
    before, rest = text.split(_START, 1)
    block, after = rest.split(_END, 1)
    return before, block.strip(), after


def test_site_page_mirrors_roadmap_md() -> None:
    _, block, _ = _page_parts()
    assert block == _source_body(), (
        "site roadmap drifted from ROADMAP.md; run "
        "node site/scripts/update-reference-inventory.mjs"
    )


def test_site_page_carries_no_roadmap_items_of_its_own() -> None:
    before, _, after = _page_parts()
    outside = before.split("---", 2)[-1] + after
    assert not re.search(r"^\s*(?:##|[-*]|\|)", outside, re.MULTILINE), (
        "roadmap items belong in ROADMAP.md, not around the generated block"
    )


def test_requests_go_to_the_issue_tracker_not_discussions() -> None:
    text = _SOURCE.read_text(encoding="utf-8")
    assert "github.com/ahmed-g-gad/apothem/discussions" not in text
    assert "github.com/ahmed-g-gad/apothem/issues" in text


def test_links_resolve_on_both_surfaces() -> None:
    """Relative links work on GitHub but break once mirrored into the site."""
    for target in re.findall(r"\]\(([^)]+)\)", _SOURCE.read_text(encoding="utf-8")):
        assert target.startswith("https://"), f"ROADMAP.md link {target!r} is relative"
