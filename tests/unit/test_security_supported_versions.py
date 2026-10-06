# SPDX-License-Identifier: MIT

"""SECURITY.md must list the current release line as supported.

The policy says the latest minor always receives security fixes and that an
unlisted minor is unsupported. When 1.1.0 shipped, the table still listed only
1.0.x, so the policy formally told reporters on the current release to upgrade
to a supported version. This test ties the table to ``pyproject.toml``'s
``MAJOR.MINOR`` so the next minor cannot ship with the same contradiction;
``scripts/release/bump_version.py`` adds the row.
"""

from __future__ import annotations

import re
from pathlib import Path

from apothem import __version__

_REPO_ROOT = Path(__file__).resolve().parents[2]
_ROW = re.compile(r"^\|\s*(\d+)\.(\d+)\.x\s*\|\s*([^|]*?)\s*\|", re.MULTILINE)


def _supported_rows() -> dict[tuple[int, int], str]:
    text = (_REPO_ROOT / "SECURITY.md").read_text(encoding="utf-8")
    section = text.split("## Supported versions", 1)[1].split("\n## ", 1)[0]
    return {(int(m[1]), int(m[2])): m[3] for m in _ROW.finditer(section)}


def test_current_minor_is_listed_as_supported() -> None:
    major, minor = (int(part) for part in __version__.split(".")[:2])
    rows = _supported_rows()
    assert (major, minor) in rows, (
        f"SECURITY.md has no {major}.{minor}.x row; the current release line "
        "must be listed (bump_version.py adds it)"
    )
    assert rows[(major, minor)] == "✓", (
        f"SECURITY.md marks {major}.{minor}.x as {rows[(major, minor)]!r}; "
        "the latest minor is always fully supported"
    )


def test_no_listed_minor_is_newer_than_the_release() -> None:
    current = tuple(int(part) for part in __version__.split(".")[:2])
    newer = [row for row in _supported_rows() if row > current]
    assert not newer, f"SECURITY.md lists unreleased minors: {newer}"
