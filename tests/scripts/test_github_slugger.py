# SPDX-License-Identifier: MIT

"""Tests for scripts/dev/github_slugger.py, the port of github-slugger 2.0.0.

The expected ids below were produced by github-slugger 2.0.0 itself (the
package the docs site builds its heading ids with), so a port that drifts from
it fails here. The removal table the port reads is checked against the
installed package too, whenever ``site/node_modules`` exists.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "dev"))

import github_slugger  # noqa: E402

SITE = REPO_ROOT / "site"
INSTALLED_SLUGGER = SITE / "node_modules" / "github-slugger" / "package.json"

# Inputs that need a code point the file would hide or the editor would rewrite.
SINGLE = [
    ("Hello World", "hello-world"),
    ("Install: the quick way!", "install-the-quick-way"),
    ("C++ & C#", "c--c"),
    ("snake_case and kebab-case", "snake_case-and-kebab-case"),
    ("1.2.3 release", "123-release"),
    ("  padded  ", "--padded--"),
    ("Привет, мир!", "привет-мир"),
    ("الجذور المشتركة", "الجذور-المشتركة"),
    ("共有ルート", "共有ルート"),
    ("Raíces compartidas", "raíces-compartidas"),
    ("Straße", "straße"),
    ("😄 Smile", "-smile"),
    ("`code` and *emphasis*", "code-and-emphasis"),
    ("Tab\there", "tabhere"),
    ("ΑΣ", "ας"),
    ("मूल जड़ें", "मूल-जड़ें"),
    ("한국어 제목", "한국어-제목"),
    ("Ünïcödé — dash", "ünïcödé--dash"),
    ("What's new?", "whats-new"),
    ("a/b\\c", "abc"),
    ("Q&A (FAQ)", "qa-faq"),
    ("100% sure", "100-sure"),
    ("Café au lait", "café-au-lait"),
    ("١٢ Arabic-Indic digits", "١٢-arabic-indic-digits"),
    ("ǅ title", "ǆ-title"),
    ("İstanbul", "i" + chr(0x307) + "stanbul"),
    ("x" + chr(0xA0) + "y", "xy"),
]


@pytest.mark.parametrize(("text", "expected"), SINGLE)
def test_slug_matches_github_slugger(text: str, expected: str) -> None:
    """One heading's id equals what github-slugger 2.0.0 makes of its text."""
    assert github_slugger.slug(text) == expected


def test_repeated_headings_get_numbered_suffixes() -> None:
    """A page that repeats an id numbers the repeats, and a numbered id can repeat too."""
    slugger = github_slugger.Slugger()
    made = [
        slugger.slug(text)
        for text in ("foo", "foo", "foo-1", "foo", "Foo", "bar", "foo-2")
    ]
    assert made == ["foo", "foo-1", "foo-1-1", "foo-2", "foo-3", "bar", "foo-2-1"]


def test_each_slugger_counts_its_own_page() -> None:
    """Two pages that share a heading text both start from the plain id."""
    assert github_slugger.Slugger().slug("Intro") == "intro"
    assert github_slugger.Slugger().slug("Intro") == "intro"


def test_the_table_keeps_letters_marks_digits_space_and_hyphen() -> None:
    """The removal table drops punctuation, symbols and unassigned code points only."""
    for kept in ("a", "Z", "é", "ж", "ع", "你", "5", "_", "-", " ", chr(0x301)):
        assert not github_slugger.is_removed(ord(kept)), repr(kept)
    for removed in ("!", "(", "/", "+", "😄", "—", chr(0x0), chr(0x10FFFF)):
        assert github_slugger.is_removed(ord(removed)), repr(removed)


@pytest.mark.skipif(
    not INSTALLED_SLUGGER.is_file() or shutil.which("node") is None,
    reason="needs node and site/node_modules (the docs-build job runs the same check)",
)
def test_the_table_matches_the_installed_github_slugger() -> None:
    """Regenerating the table from the installed package changes nothing."""
    result = subprocess.run(
        ["node", "scripts/github-slugger-table.mjs", "--check"],
        cwd=SITE,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert result.returncode == 0, result.stderr
