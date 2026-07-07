# SPDX-License-Identifier: MIT

"""Per-Write matcher root-resolution against the matched hook scope.

The anchor-scoped matchers must resolve write targets against the matched hook
scope, not only against the apothem repo root (``ECOSYSTEM_ROOT``). A matcher
that resolved only against the repo root would SILENTLY pass anything outside
it — a headerless write to a hook scope (``~/.claude/rules/x.md``) would never
be checked, and the sibling matchers would return a clean synthetic pass with
no indication the check did not run. These tests pin the scope-aware
resolution so that regression cannot recur.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from apothem.conformity import (
    copilot_instructions_presence_grep as copilot,
)
from apothem.conformity import (
    file_header_grep as fh,
)
from apothem.conformity import (
    license_author_consistency_grep as lic,
)
from apothem.conformity import (
    multi_surface_coherence_grep as msc,
)


@pytest.fixture
def claude_scope(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Point the conformity scope at a tmp dir and return it (a hook scope)."""
    monkeypatch.setenv("APOTHEM_CONFORMITY_SCOPE", str(tmp_path))
    return tmp_path


# --- file_header_grep: the load-bearing SPDX case (30.1) --------------------


def test_header_absent_on_hook_scope_path_now_fails(claude_scope: Path) -> None:
    target = claude_scope / "rules" / "no-header.md"
    result = fh.check("# not a spdx header\n\nbody\n", target)
    assert result.passed is False
    assert result.findings[0].rule == fh.RULE_ABSENT


def test_exempt_path_under_scope_still_passes(claude_scope: Path) -> None:
    # `.apothem/**` is an exception glob; a scope-relative .apothem path passes.
    target = claude_scope / ".apothem" / "draft.md"
    result = fh.check("# no header here\n", target)
    assert result.passed is True


def test_path_under_no_anchor_is_pass_through() -> None:
    # No repo root and no configured scope contains this path → skip (pass).
    result = fh.check("# no header\n", Path("/nonexistent-anchor-xyz/x.md"))
    assert result.passed is True


# --- the three sibling matchers: visible skip, not silent pass (30.2) -------


def test_multi_surface_emits_visible_skip_out_of_anchor() -> None:
    result = msc.check("", Path("/nonexistent-anchor-xyz/whatever.md"))
    assert result.passed is True
    assert result.note == "check skipped (scope not resolvable)"


def test_license_author_emits_visible_skip_out_of_anchor() -> None:
    result = lic.check("", Path("/nonexistent-anchor-xyz/LICENSE"))
    assert result.passed is True
    assert result.note == "check skipped (scope not resolvable)"


def test_copilot_emits_visible_skip_out_of_anchor() -> None:
    result = copilot.check("", Path("/nonexistent-anchor-xyz/whatever.md"))
    assert result.passed is True
    assert result.note == "check skipped (scope not resolvable)"


def test_copilot_in_anchor_non_target_is_silent_pass_no_note() -> None:
    # An in-repo file that is simply not the Copilot surface is legitimately
    # not-applicable — a clean pass with no skip note (not a scope failure).
    repo_file = Path(__file__).resolve().parents[2] / "pyproject.toml"
    result = copilot.check("", repo_file)
    assert result.passed is True
    assert result.note is None


def test_skip_note_surfaces_in_json() -> None:
    result = msc.check("", Path("/nonexistent-anchor-xyz/whatever.md"))
    assert '"note": "check skipped (scope not resolvable)"' in result.to_json()
