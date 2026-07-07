# SPDX-License-Identifier: MIT

"""Tests for the freshness-token narrative matcher.

The matcher proves zero freshness-narrative phrases (AI-disclosure, legacy /
replacement, deferral, fix-and-refinement story-of-becoming) on shipped public
surfaces — the repository ``README.md`` and the ``site/content/docs`` tree.
These tests cover denylist loading, the in-scope pass/fail paths, the
acceptance fixture (a planted "this replaces the legacy v0 behavior" line in
README), scope correctness (out-of-scope developer surfaces are never flagged),
fenced-code-block exclusion, and the advisory JSON flag.
"""

from __future__ import annotations

import json
from pathlib import Path

from apothem.conformity import freshness_token_grep as ftg

_FIXTURE_DIR = Path(__file__).resolve().parent / "freshness-token-grep"


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_denylist_loads_and_is_non_empty() -> None:
    tokens = ftg._load_tokens()
    assert tokens, "denylist parsed to an empty token list"
    # Comment lines and the SPDX header must be excluded.
    assert all(not t.startswith("#") for t in tokens)
    # High-precision phrases only — no bare common words that have legit uses.
    assert "legacy" not in tokens
    assert "deprecated" not in tokens
    assert "placeholder" not in tokens
    # Present-tense feature/policy facts are not story-of-becoming — absent so a
    # truthful current-version surface is never falsely flagged.
    assert "backward-compatible" not in tokens
    assert "no longer supported" not in tokens
    # The AI-disclosure token-class is plain-language-grep's on this same scope;
    # freshness-token-grep carries none of it (strictly non-overlapping).
    assert "ai-generated" not in tokens


def test_clean_readme_passes(tmp_path: Path) -> None:
    clean = (_FIXTURE_DIR / "pass.md").read_text(encoding="utf-8")
    _write(tmp_path / "README.md", clean)
    result = ftg.check(tmp_path)
    assert result.passed
    assert result.findings == []
    assert result.files_inspected == 1


def test_planted_replacement_narrative_in_readme_fails(tmp_path: Path) -> None:
    # The phase 67.3 acceptance fixture.
    _write(
        tmp_path / "README.md",
        "# Apothem\n\nThis release replaces the legacy v0 behavior.\n",
    )
    result = ftg.check(tmp_path)
    assert not result.passed
    assert len(result.findings) >= 1
    finding = result.findings[0]
    assert finding.surface == "README.md"
    assert finding.kind == "freshness-token"


def test_fail_fixture_in_site_docs_flags(tmp_path: Path) -> None:
    leaky = (_FIXTURE_DIR / "fail.md").read_text(encoding="utf-8")
    _write(tmp_path / "site" / "content" / "docs" / "page.md", leaky)
    result = ftg.check(tmp_path)
    assert not result.passed
    # Multiple distinct narrative phrases in the fixture.
    assert len(result.findings) >= 4


def test_out_of_scope_developer_surface_passes(tmp_path: Path) -> None:
    # The same phrases on a developer-only surface are NOT flagged — process
    # vocabulary is load-bearing off the shipped facade.
    leaky = (_FIXTURE_DIR / "fail.md").read_text(encoding="utf-8")
    _write(tmp_path / "src" / "apothem" / "rules" / "x.md", leaky)
    _write(tmp_path / "site" / "src" / "content" / "blog-draft.md", leaky)
    result = ftg.check(tmp_path)
    assert result.passed
    assert result.findings == []


def test_fenced_code_block_is_excluded(tmp_path: Path) -> None:
    # A forbidden phrase quoted inside a code fence is a sample, not narrative.
    fenced = "# Apothem\n\n```\nthis replaces the legacy v0 behavior\n```\n"
    _write(tmp_path / "README.md", fenced)
    result = ftg.check(tmp_path)
    assert result.passed
    assert result.findings == []


def test_advisory_flag_present_in_json(tmp_path: Path) -> None:
    _write(tmp_path / "README.md", "# Apothem\n\nCurrent and fresh.\n")
    result = ftg.check(tmp_path)
    payload = json.loads(result.to_json())
    assert payload["advisory"] is True
    assert payload["grep"] == "freshness-token-grep"


def test_case_insensitive_match(tmp_path: Path) -> None:
    _write(tmp_path / "README.md", "# Apothem\n\nMore docs are COMING SOON.\n")
    result = ftg.check(tmp_path)
    assert not result.passed
