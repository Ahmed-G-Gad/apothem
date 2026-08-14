# SPDX-License-Identifier: MIT

"""Characterization coverage for the AI-surface coherence scanner.

``apothem.audit.scan_ai_surfaces`` checks that the repository's three
AI-instruction surfaces — ``AGENTS.md``, ``CLAUDE.md``, and
``.github/copilot-instructions.md`` — still carry the same shared claims. It
ships as a standalone entry point (``python -m apothem.audit.scan_ai_surfaces``)
with no importers, and it therefore had **no test coverage at all**: the suite
passed without executing one line of it.

These tests are characterization tests, not specification tests. They pin the
scanner's *current* behavior so the module can be refactored against a real
green-before / green-after baseline. Where current behavior is surprising, the
test says so in its docstring rather than quietly asserting the surprise as
intent.

Scope. Three layers. The parsing and presence-detection core (pure functions
over strings), the per-surface scan (the one layer that touches the
filesystem, exercised against ``tmp_path``), and the pairwise coherence
heuristic that compares two scanned surfaces.
"""

from __future__ import annotations

from pathlib import Path

from apothem.audit.scan_ai_surfaces import (
    COHERENCE_COHERENT,
    COHERENCE_CONTRADICTS,
    COHERENCE_NOT_APPLICABLE,
    COHERENCE_PARTIAL,
    PRESENCE_ABSENT,
    PRESENCE_PRESENT,
    PRESENCE_RENAMED_PREFIX,
    SURFACE_ABSENT,
    SURFACE_PARTIAL,
    SURFACE_PRESENT,
    CanonicalSection,
    SurfaceDescriptor,
    SurfaceScan,
    body_signature_count,
    build_coherence_map,
    coherence_verdict_for,
    detect_section_presence,
    heading_text_matches,
    parse_headings,
    scan_surface,
    section_present_in_scan,
    shared_claim_overlap,
)


def _section(
    *,
    keywords: tuple[str, ...] = ("Plans Discipline",),
    signatures: tuple[str, ...] = ("MUST",),
) -> CanonicalSection:
    """Build a section descriptor with only the fields detection reads.

    Post-conditions: ``slug`` / ``display`` / ``is_shared`` carry filler
    values — the presence heuristic never consults them, so pinning them
    would over-constrain the test.
    """
    return CanonicalSection(
        slug="sample",
        display="Sample",
        heading_keywords=keywords,
        body_signatures=signatures,
        is_shared=True,
    )


# --- parse_headings ---------------------------------------------------------


def test_parse_headings_empty_content_yields_nothing() -> None:
    """Content with no headings parses to an empty block list."""
    assert parse_headings("just prose\nand more prose\n") == []


def test_parse_headings_captures_level_and_text() -> None:
    """The `#` depth becomes the level and the trailing text is stripped."""
    blocks = parse_headings("### Plans Discipline   \nbody\n")

    assert len(blocks) == 1
    assert blocks[0].level == 3
    assert blocks[0].text == "Plans Discipline"


def test_parse_headings_body_runs_to_the_next_heading() -> None:
    """A body ends at the next heading of any depth, not just a sibling.

    The slice is flat: a deeper subheading terminates its parent's body,
    so a parent's body carries only the prose directly beneath it.
    """
    blocks = parse_headings("# One\nalpha\n## Two\nbeta\n# Three\ngamma\n")

    assert [block.text for block in blocks] == ["One", "Two", "Three"]
    assert blocks[0].body == "alpha"
    assert blocks[1].body == "beta"


def test_parse_headings_last_body_runs_to_end_of_document() -> None:
    """The final heading's body extends to the last line."""
    blocks = parse_headings("# Only\nalpha\nbeta\n")

    assert blocks[-1].body == "alpha\nbeta"


def test_parse_headings_line_numbers_are_one_based() -> None:
    """``line_start`` is the heading's own 1-based line number."""
    blocks = parse_headings("intro\n# Heading\nbody\n")

    assert blocks[0].line_start == 2


# --- heading_text_matches ---------------------------------------------------


def test_heading_text_matches_is_case_insensitive_substring() -> None:
    """A keyword matches as a substring regardless of case."""
    assert heading_text_matches("The PLANS discipline", ("plans",))


def test_heading_text_matches_requires_only_one_keyword() -> None:
    """Any single keyword hit is enough; the others need not match."""
    assert heading_text_matches("Release Facade", ("absent", "facade"))


def test_heading_text_matches_empty_keywords_never_matches() -> None:
    """With no keywords there is nothing to match, so the answer is False."""
    assert not heading_text_matches("Anything", ())


# --- body_signature_count ---------------------------------------------------


def test_body_signature_count_is_case_sensitive() -> None:
    """Signatures are case-sensitive — modal verbs carry meaning in case.

    ``MUST`` is a directive per the RFC 2119 hierarchy; ``must`` is prose.
    """
    assert body_signature_count("this MUST hold", ("MUST",)) == 1
    assert body_signature_count("this must hold", ("MUST",)) == 0


def test_body_signature_count_counts_distinct_signatures_not_occurrences() -> None:
    """Each signature contributes at most one, however often it appears."""
    assert body_signature_count("MUST MUST MUST", ("MUST",)) == 1
    assert body_signature_count("MUST and SHOULD", ("MUST", "SHOULD")) == 2


# --- detect_section_presence ------------------------------------------------


def test_detect_presence_heading_keyword_wins() -> None:
    """A heading-text match reports present, whatever the body holds."""
    headings = parse_headings("# Plans Discipline\nno signature here\n")

    verdict = detect_section_presence(_section(), headings, "irrelevant")

    assert verdict == PRESENCE_PRESENT


def test_detect_presence_heading_match_outranks_signature_elsewhere() -> None:
    """The keyword heading wins even when another heading carries the body signature.

    The heading is the canonical claim; a signature under a different
    heading does not demote it to renamed.
    """
    headings = parse_headings("# Other\nMUST appear\n# Plans Discipline\nprose\n")

    verdict = detect_section_presence(_section(), headings, "MUST appear")

    assert verdict == PRESENCE_PRESENT


def test_detect_presence_signature_without_keyword_reads_as_renamed() -> None:
    """No keyword hit but a body signature means the section was renamed."""
    headings = parse_headings("# Some Other Title\nthis MUST hold\n")

    verdict = detect_section_presence(_section(), headings, "this MUST hold")

    assert verdict == f"{PRESENCE_RENAMED_PREFIX}Some Other Title"


def test_detect_presence_renamed_reports_the_first_signature_heading() -> None:
    """When several headings carry a signature, document order decides."""
    headings = parse_headings("# First\nMUST here\n# Second\nMUST too\n")

    verdict = detect_section_presence(_section(), headings, "MUST here MUST too")

    assert verdict == f"{PRESENCE_RENAMED_PREFIX}First"


def test_detect_presence_signature_outside_any_heading_reports_placeholder() -> None:
    """A signature in the preamble yields the no-heading-found placeholder.

    Content above the first heading belongs to no block, so the scanner
    falls back to scanning the whole document and reports that it could
    not attribute the signature to a heading.
    """
    content = "this MUST hold before any heading\n# Unrelated\nprose\n"

    verdict = detect_section_presence(_section(), parse_headings(content), content)

    assert verdict == f"{PRESENCE_RENAMED_PREFIX}<no-heading-found>"


def test_detect_presence_no_keyword_and_no_signature_is_absent() -> None:
    """Neither signal anywhere means the section is genuinely absent."""
    content = "# Unrelated\nplain prose\n"

    verdict = detect_section_presence(_section(), parse_headings(content), content)

    assert verdict == PRESENCE_ABSENT


def test_detect_presence_on_empty_document_is_absent() -> None:
    """An empty surface has no headings and no signatures."""
    assert detect_section_presence(_section(), [], "") == PRESENCE_ABSENT


# --- scan_surface -----------------------------------------------------------


def _descriptor(path: str = "AGENTS.md") -> SurfaceDescriptor:
    """Build a mandatory surface descriptor pointing at ``path``."""
    return SurfaceDescriptor(path=path, role="test surface", mandatory=True)


def test_scan_surface_missing_file_is_absent(tmp_path: Path) -> None:
    """A surface that does not exist scans as absent with no digest.

    Post-conditions: every canonical section is marked absent, so the
    downstream authoring plan sees a complete gap rather than a partial one.
    """
    scan = scan_surface(_descriptor(), tmp_path)

    assert scan.presence == SURFACE_ABSENT
    assert scan.sha256 is None
    assert scan.line_count == 0
    assert scan.headings == []
    assert set(scan.section_presence.values()) == {PRESENCE_ABSENT}


def test_scan_surface_empty_file_is_partial_not_absent(tmp_path: Path) -> None:
    """An existing but empty file is partial — the file exists, the content does not.

    This is the distinction that keeps "never authored" separate from
    "authored then emptied"; both would otherwise read as absent.
    """
    (tmp_path / "AGENTS.md").write_text("", encoding="utf-8")

    scan = scan_surface(_descriptor(), tmp_path)

    assert scan.presence == SURFACE_PARTIAL
    assert scan.sha256 is None


def test_scan_surface_directory_at_the_path_is_absent(tmp_path: Path) -> None:
    """A directory where a file is expected reads as absent, not as an error."""
    (tmp_path / "AGENTS.md").mkdir()

    assert scan_surface(_descriptor(), tmp_path).presence == SURFACE_ABSENT


def test_scan_surface_populated_file_hashes_and_parses(tmp_path: Path) -> None:
    """A present surface carries a digest, a line count, and parsed headings."""
    (tmp_path / "AGENTS.md").write_text(
        "# Plans Discipline\nthis MUST hold\n", encoding="utf-8"
    )

    scan = scan_surface(_descriptor(), tmp_path)

    assert scan.presence == SURFACE_PRESENT
    assert scan.sha256 is not None
    assert len(scan.sha256) == 64
    assert scan.line_count == 2
    assert [block.text for block in scan.headings] == ["Plans Discipline"]


def test_scan_surface_digest_is_content_addressed(tmp_path: Path) -> None:
    """Identical bytes at different paths produce the same digest."""
    (tmp_path / "AGENTS.md").write_text("# Same\nbody\n", encoding="utf-8")
    (tmp_path / "CLAUDE.md").write_text("# Same\nbody\n", encoding="utf-8")

    first = scan_surface(_descriptor("AGENTS.md"), tmp_path)
    second = scan_surface(_descriptor("CLAUDE.md"), tmp_path)

    assert first.sha256 == second.sha256


# --- coherence --------------------------------------------------------------


def _scan(content: str, path: str = "AGENTS.md") -> SurfaceScan:
    """Build a present SurfaceScan over ``content`` without touching disk."""
    section = _section()
    headings = parse_headings(content)
    return SurfaceScan(
        descriptor=_descriptor(path),
        presence=SURFACE_PRESENT,
        sha256="0" * 64,
        line_count=len(content.splitlines()),
        headings=headings,
        section_presence={
            section.slug: detect_section_presence(section, headings, content)
        },
        raw_content=content,
    )


def test_section_present_in_scan_counts_renamed_as_present() -> None:
    """A renamed section still counts as present — the claim exists, retitled."""
    scan = _scan("# Some Other Title\nthis MUST hold\n")

    assert scan.section_presence["sample"].startswith(PRESENCE_RENAMED_PREFIX)
    assert section_present_in_scan(scan, "sample")


def test_section_present_in_scan_unknown_slug_reads_absent() -> None:
    """A slug the scan never recorded defaults to absent rather than raising."""
    assert not section_present_in_scan(_scan("# Plans Discipline\nbody\n"), "unknown")


def test_shared_claim_overlap_partitions_signatures() -> None:
    """Signatures split into shared, only-A, and only-B buckets."""
    section = _section(signatures=("ALPHA", "BETA", "GAMMA"))
    scan_a = _scan("# Plans Discipline\nALPHA BETA\n")
    scan_b = _scan("# Plans Discipline\nALPHA GAMMA\n", path="CLAUDE.md")

    assert shared_claim_overlap(section, scan_a, scan_b) == (1, 1, 1)


def test_coherence_is_not_applicable_when_one_surface_lacks_the_section() -> None:
    """Coherence is undefined until both surfaces author the section."""
    present = _scan("# Plans Discipline\nMUST\n")
    missing = _scan("# Unrelated\nplain prose\n", path="CLAUDE.md")

    verdict = coherence_verdict_for(_section(), present, missing)

    assert verdict.verdict == COHERENCE_NOT_APPLICABLE


def test_coherence_is_coherent_when_claims_are_symmetric() -> None:
    """Shared signatures with no asymmetry read as coherent."""
    section = _section(signatures=("ALPHA",))
    scan_a = _scan("# Plans Discipline\nALPHA\n")
    scan_b = _scan("# Plans Discipline\nALPHA\n", path="CLAUDE.md")

    assert coherence_verdict_for(section, scan_a, scan_b).verdict == COHERENCE_COHERENT


def test_coherence_is_partial_when_only_one_side_claims() -> None:
    """A one-sided claim is partial — reconcilable by mirroring, not a conflict."""
    section = _section(signatures=("ALPHA", "BETA"))
    scan_a = _scan("# Plans Discipline\nALPHA BETA\n")
    scan_b = _scan("# Plans Discipline\nALPHA\n", path="CLAUDE.md")

    assert coherence_verdict_for(section, scan_a, scan_b).verdict == COHERENCE_PARTIAL


def test_coherence_is_partial_when_headings_exist_but_no_signatures() -> None:
    """Both headings present with no signatures anywhere is partial, not coherent.

    Absence of evidence on both sides is not evidence of agreement; the
    rigorous test lives in the multi-surface coherence validator.
    """
    section = _section(signatures=("ALPHA",))
    scan_a = _scan("# Plans Discipline\nprose only\n")
    scan_b = _scan("# Plans Discipline\nother prose\n", path="CLAUDE.md")

    assert coherence_verdict_for(section, scan_a, scan_b).verdict == COHERENCE_PARTIAL


def test_coherence_contradicts_when_both_sides_claim_asymmetrically() -> None:
    """Each surface carrying a claim the other lacks is a candidate contradiction."""
    section = _section(signatures=("ALPHA", "BETA"))
    scan_a = _scan("# Plans Discipline\nALPHA\n")
    scan_b = _scan("# Plans Discipline\nBETA\n", path="CLAUDE.md")

    verdict = coherence_verdict_for(section, scan_a, scan_b)

    assert verdict.verdict == COHERENCE_CONTRADICTS
    assert "only-A=1" in verdict.rationale


def test_build_coherence_map_skips_surfaces_that_are_not_present() -> None:
    """Only present surfaces enter the pairwise map."""
    present = _scan("# Plans Discipline\nMUST\n")
    absent = SurfaceScan(
        descriptor=_descriptor("CLAUDE.md"),
        presence=SURFACE_ABSENT,
        sha256=None,
        line_count=0,
        headings=[],
        section_presence={},
        raw_content="",
    )

    assert build_coherence_map([present, absent]) == {}


def test_build_coherence_map_keys_each_unordered_pair_once() -> None:
    """Three present surfaces yield three pairs, not six — order is not repeated."""
    scans = [
        _scan("# Plans Discipline\nMUST\n", path="AGENTS.md"),
        _scan("# Plans Discipline\nMUST\n", path="CLAUDE.md"),
        _scan("# Plans Discipline\nMUST\n", path=".github/copilot-instructions.md"),
    ]

    coherence = build_coherence_map(scans)

    assert len(coherence) == 3
    assert "AGENTS.md__vs__CLAUDE.md" in coherence
