# SPDX-License-Identifier: MIT

"""Third-party names and colors carry a trademark and non-affiliation notice.

The docs color fifteen harness nodes "to match their primary brand identity"
and the README names every supported tool, with no statement that the names
are their owners' trademarks or that Apothem is independent of them. The brand
page also claimed the Apothem mark renders Google's four brand hues, which no
shipped mark SVG contains.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_BRAND = _REPO_ROOT / "site" / "content" / "docs" / "brand" / "harness-colors.mdx"
_NOTICE_PHRASES = ("trademarks of their respective owners", "not affiliated with")


@pytest.mark.parametrize(
    "path", [_REPO_ROOT / "README.md", _BRAND], ids=["readme", "brand"]
)
def test_notice_is_present(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    for phrase in _NOTICE_PHRASES:
        assert phrase in text, f"{path.name} lacks {phrase!r}"


def test_brand_page_claims_only_colors_the_mark_contains() -> None:
    mark_colors: set[str] = set()
    for svg in [
        *_REPO_ROOT.glob("assets/*.svg"),
        *_REPO_ROOT.glob("site/public/*.svg"),
    ]:
        mark_colors.update(
            c.lower()
            for c in re.findall(r"#[0-9A-Fa-f]{6}", svg.read_text(encoding="utf-8"))
        )
    for line in _BRAND.read_text(encoding="utf-8").splitlines():
        if "Apothem mark" not in line:
            continue
        for color in re.findall(r"#[0-9A-Fa-f]{6}", line):
            assert color.lower() in mark_colors, (
                f"the mark contains no {color}: {line[:120]}"
            )
