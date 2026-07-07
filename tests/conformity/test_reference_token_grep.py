# SPDX-License-Identifier: MIT

"""Tests for the reference-token leak matcher.

The matcher proves zero reference-platform branding leaks across authored
in-scope surfaces (rules, commands, skills, agents, docs, assets). These
tests cover denylist loading, the in-scope pass/fail paths, exemption
correctness, the advisory JSON flag, and word-boundary false-positive
guarding.
"""

from __future__ import annotations

import json
from pathlib import Path

from apothem.conformity import reference_token_grep as rtg

_FIXTURE_DIR = Path(__file__).resolve().parent / "reference-token-grep"


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_denylist_loads_and_is_non_empty() -> None:
    tokens = rtg._load_tokens()
    assert tokens, "denylist parsed to an empty token list"
    # Comment lines and the SPDX header must be excluded.
    assert all(not t.startswith("#") for t in tokens)


def test_clean_in_scope_file_passes(tmp_path: Path) -> None:
    clean = (_FIXTURE_DIR / "pass.md").read_text(encoding="utf-8")
    _write(tmp_path / "src" / "apothem" / "rules" / "clean.md", clean)
    result = rtg.check(tmp_path)
    assert result.passed
    assert result.findings == []
    assert result.files_inspected == 1


def test_reference_token_in_scope_file_fails(tmp_path: Path) -> None:
    _write(
        tmp_path / "src" / "apothem" / "rules" / "leaky.md",
        "# Leaky\n\nThis mentions ECC in authored prose.\n",
    )
    result = rtg.check(tmp_path)
    assert not result.passed
    assert len(result.findings) >= 1
    finding = result.findings[0]
    assert finding.surface == "src/apothem/rules/leaky.md"
    assert finding.kind == "reference-token"


def test_token_only_in_exempt_location_passes(tmp_path: Path) -> None:
    # Reference tokens under exempt trees must not be flagged.
    leaky = (_FIXTURE_DIR / "fail.md").read_text(encoding="utf-8")
    _write(tmp_path / "tests" / "conformity" / "fixture.md", leaky)
    _write(tmp_path / ".plans" / "suite" / "notes.md", "ECC and affaan here.\n")
    _write(
        tmp_path / "src" / "apothem" / "schemas" / "reference-token-denylist.txt",
        "ECC\necc.tools\n",
    )
    result = rtg.check(tmp_path)
    assert result.passed
    assert result.findings == []


def test_to_json_includes_advisory_flag(tmp_path: Path) -> None:
    result = rtg.check(tmp_path)
    payload = json.loads(result.to_json())
    assert payload["advisory"] is True


def test_word_boundary_false_positive_guard(tmp_path: Path) -> None:
    # A larger word merely containing the 'ecc' substring is not flagged.
    _write(
        tmp_path / "src" / "apothem" / "rules" / "speccheck.md",
        "# Recce\n\nThe words recce, speccheck, and necessary all embed that "
        "substring inside larger words and stay clean.\n",
    )
    result = rtg.check(tmp_path)
    assert result.passed, [str(f) for f in result.findings]
