# SPDX-License-Identifier: MIT

"""Characterization coverage for the plan-frontmatter grammar.

``apothem.audit.plan_frontmatter`` answers two questions about a plan file's
opening block: what did the author declare, and where does the prose start.
Both readers were extracted from the provenance builder, where they had no
coverage of their own; these tests pin their current behavior so the grammar
can move again without silently changing meaning.
"""

from __future__ import annotations

from apothem.audit.plan_frontmatter import parse_frontmatter, strip_frontmatter


def test_parse_frontmatter_absent_block_yields_no_fields() -> None:
    """Content with no frontmatter parses to an empty mapping."""
    assert parse_frontmatter("# Heading\nbody\n") == {}


def test_parse_frontmatter_extracts_the_three_tracked_fields() -> None:
    """Only project, title, and created are lifted out of the block.

    The builder needs exactly these three to attribute and rename a file;
    other frontmatter keys are deliberately ignored rather than carried.
    """
    content = (
        "---\n"
        "project: apothem\n"
        "title: Some Plan\n"
        "created: 2026-01-15\n"
        "author: someone\n"
        "---\n"
        "body\n"
    )

    fields = parse_frontmatter(content)

    assert fields == {
        "project": "apothem",
        "title": "Some Plan",
        "created": "2026-01-15",
    }


def test_parse_frontmatter_omits_the_fields_the_block_does_not_declare() -> None:
    """A partial block yields only the keys it actually carries.

    The three fields are searched independently, so a block declaring one of
    them is not treated as malformed — the caller reads a missing key as an
    undeclared value rather than a parse failure.
    """
    assert parse_frontmatter("---\nproject: apothem\n---\nbody\n") == {
        "project": "apothem"
    }


def test_parse_frontmatter_only_matches_at_the_start_of_content() -> None:
    """A delimiter block further down the file is body text, not frontmatter."""
    assert parse_frontmatter("intro\n---\ntitle: Not Frontmatter\n---\n") == {}


def test_strip_frontmatter_removes_only_the_leading_block() -> None:
    """The body after the closing delimiter survives intact."""
    content = "---\ntitle: T\n---\n# Heading\nbody\n"

    assert strip_frontmatter(content) == "# Heading\nbody\n"


def test_strip_frontmatter_passes_content_through_when_absent() -> None:
    """Content with no frontmatter is returned unchanged."""
    assert strip_frontmatter("# Heading\n") == "# Heading\n"
