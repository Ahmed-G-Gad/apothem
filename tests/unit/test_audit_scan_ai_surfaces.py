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

Scope. The parsing and presence-detection core: heading extraction with body
slicing, the keyword and signature matchers, and the four-branch presence
verdict. These are pure functions over strings — no filesystem, no argv.
"""

from __future__ import annotations

from apothem.audit.scan_ai_surfaces import (
    PRESENCE_ABSENT,
    PRESENCE_PRESENT,
    PRESENCE_RENAMED_PREFIX,
    CanonicalSection,
    body_signature_count,
    detect_section_presence,
    heading_text_matches,
    parse_headings,
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
