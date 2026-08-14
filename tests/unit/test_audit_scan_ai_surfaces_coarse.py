# SPDX-License-Identifier: MIT

"""Characterization coverage for the coarse AI-surface scanner.

``apothem.audit.scan_ai_surfaces_coarse`` is the cheap first pass over the
repository's AI-instruction surfaces: it asks only whether each mandatory
block is *mentioned* anywhere in a surface, leaving structural verification to
the deeper ``scan_ai_surfaces`` pass. It was the last audit module with zero
test coverage — the suite passed without executing one line of it.

These are characterization tests, pinning current behavior so the module can
be changed against a real baseline.

Detection-strategy note worth understanding before reading the assertions: a
block counts as present when **any one** of its signal strings appears
**anywhere** in the file, with no regard to headings, ordering, or position.
That is deliberate for a coarse pass — it is tuned to avoid false alarms, and
it accepts false negatives (a block mentioned in passing reads as present) as
the cost. The deeper scan is what catches those.
"""

from __future__ import annotations

from pathlib import Path

from apothem.audit.scan_ai_surfaces_coarse import (
    _MANDATORY_BLOCKS,
    _OPTIONAL_SURFACES,
    SEVERITY_HIGH,
    SEVERITY_LOW,
    _scan_instruction_surface,
    _scan_optional_surfaces,
)

# --- _scan_instruction_surface ----------------------------------------------


def test_empty_surface_reports_every_mandatory_block_missing() -> None:
    """A blank surface is missing all four mandatory blocks."""
    hits = _scan_instruction_surface("AGENTS.md", "")

    assert len(hits) == len(_MANDATORY_BLOCKS)
    assert {hit.severity for hit in hits} == {SEVERITY_HIGH}


def test_missing_block_hits_name_the_block_and_the_file() -> None:
    """Each hit identifies which block is missing from which surface.

    The signal carries the block name so a reader can act without opening
    the remediation prose.
    """
    hits = _scan_instruction_surface("CLAUDE.md", "")

    assert all(hit.file == "CLAUDE.md" for hit in hits)
    signals = {hit.signal for hit in hits}
    assert "instruction-surface-missing-block: plans-discipline" in signals


def test_any_single_signal_satisfies_a_block() -> None:
    """One matching signal string is enough; the block needs no other evidence.

    This is the coarse pass's central tradeoff — cheap and false-alarm
    resistant, at the cost of accepting a passing mention as presence.
    """
    content = "\n".join(next(iter(_MANDATORY_BLOCKS.values()))[:1])

    hits = _scan_instruction_surface("AGENTS.md", content)

    assert len(hits) == len(_MANDATORY_BLOCKS) - 1


def test_a_surface_carrying_every_block_reports_nothing() -> None:
    """With one signal per block present, the surface is clean."""
    content = "\n".join(signals[0] for signals in _MANDATORY_BLOCKS.values())

    assert _scan_instruction_surface("AGENTS.md", content) == []


def test_block_signals_are_case_sensitive_substrings() -> None:
    """Signal matching is literal — case and spelling must match exactly.

    ``plans-discipline`` is a slug the surfaces are expected to carry
    verbatim, so lowering the bar to case-insensitive would let a prose
    mention of "Plans discipline" satisfy a structural requirement.
    """
    hits = _scan_instruction_surface("AGENTS.md", "PLANS-DISCIPLINE")
    signals = {hit.signal for hit in hits}

    assert "instruction-surface-missing-block: plans-discipline" in signals


def test_signal_matches_anywhere_including_mid_word() -> None:
    """Matching is a bare substring test, with no token boundary.

    Pinned deliberately: a signal embedded inside a longer word still
    counts. The coarse pass accepts this to stay cheap; the deeper
    section-presence scan is what distinguishes a heading from a mention.
    """
    hits = _scan_instruction_surface("AGENTS.md", "xxplans-disciplineyy")
    signals = {hit.signal for hit in hits}

    assert "instruction-surface-missing-block: plans-discipline" not in signals


# --- _scan_optional_surfaces ------------------------------------------------


def test_no_optional_surfaces_on_disk_yields_no_hits(tmp_path: Path) -> None:
    """Absent opt-in surfaces are informational-only, so silence is correct."""
    assert _scan_optional_surfaces(tmp_path) == []


def test_present_optional_surface_is_reported_at_low_severity(tmp_path: Path) -> None:
    """An opt-in surface that exists is surfaced, but never as a problem.

    Presence is a fact the operator ratifies (keep / refit / remove), not a
    finding — hence LOW rather than a warning severity.
    """
    (tmp_path / ".cursorrules").write_text("rules\n", encoding="utf-8")

    hits = _scan_optional_surfaces(tmp_path)

    assert len(hits) == 1
    assert hits[0].severity == SEVERITY_LOW
    assert hits[0].signal == "optional-surface-present: .cursorrules"


def test_optional_surface_hits_use_line_zero(tmp_path: Path) -> None:
    """A whole-file observation carries line 0, not line 1.

    Line 1 would imply the finding sits at a location in the file; line 0
    marks it as a statement about the file's existence.
    """
    (tmp_path / ".windsurfrules").write_text("rules\n", encoding="utf-8")

    assert _scan_optional_surfaces(tmp_path)[0].line == 0


def test_every_optional_surface_is_probed(tmp_path: Path) -> None:
    """All declared opt-in paths are checked, including nested ones."""
    for relative in _OPTIONAL_SURFACES:
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("content\n", encoding="utf-8")

    hits = _scan_optional_surfaces(tmp_path)

    assert len(hits) == len(_OPTIONAL_SURFACES)
    assert {hit.file for hit in hits} == set(_OPTIONAL_SURFACES)


def test_a_directory_at_an_optional_path_counts_as_present(tmp_path: Path) -> None:
    """The probe is an existence test, so a directory satisfies it.

    Pinned as current behavior, not endorsed: ``.exists()`` does not
    discriminate file from directory, so a stray directory named
    ``.cursorrules`` would read as an authored surface.
    """
    (tmp_path / ".cursorrules").mkdir()

    assert len(_scan_optional_surfaces(tmp_path)) == 1
