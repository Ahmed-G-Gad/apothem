# SPDX-License-Identifier: MIT

"""Characterization coverage for plan-filename derivation.

``apothem.audit.plan_filename`` proposes the canonical ``<date>--<slug>.md``
name for a plan file. The interesting behavior is not any one of the three
functions but the precedence between them, so the ``proposed_filename`` tests
below exercise each rung of the title ladder and each date source rather than
the happy path alone.

These are characterization tests: they pin current behavior, including the
places where it is more forgiving than the signature suggests — a malformed
``created`` value is treated as absent, not as an error.
"""

from __future__ import annotations

from pathlib import Path

from apothem.audit.plan_filename import h1_of, kebab_slug, proposed_filename

# --- slug -------------------------------------------------------------------


def test_kebab_slug_lowercases_and_joins_on_hyphens() -> None:
    """Spaces and underscores collapse to single hyphens."""
    assert kebab_slug("Some  Plan_Title") == "some-plan-title"


def test_kebab_slug_drops_punctuation_and_trims_edges() -> None:
    """Non-word characters are removed, and leading/trailing hyphens go."""
    assert kebab_slug("  *Plan*: the (sequel)!  ") == "plan-the-sequel"


def test_kebab_slug_truncates_at_sixty_characters() -> None:
    """An overlong title is cut to keep filenames manageable."""
    assert len(kebab_slug("word " * 40)) <= 60


def test_kebab_slug_of_empty_text_is_empty() -> None:
    """Nothing in, nothing out — the caller decides the fallback."""
    assert kebab_slug("   ") == ""


# --- heading ----------------------------------------------------------------


def test_h1_of_reads_past_the_frontmatter() -> None:
    """The first heading is found in the body, not the frontmatter block."""
    assert h1_of("---\ntitle: T\n---\n# Real Heading\n") == "Real Heading"


def test_h1_of_returns_none_without_a_heading() -> None:
    """Body prose with no heading yields no title candidate."""
    assert h1_of("just prose\n") is None


# --- proposed filename ------------------------------------------------------


def test_proposed_filename_prefers_frontmatter_title_over_h1() -> None:
    """The declared title outranks the rendered heading.

    Frontmatter is an explicit authoring decision; the H1 is a rendering
    detail that may have drifted from it.
    """
    name = proposed_filename(
        Path("notes.md"),
        "2026-08-14T00:00:00",
        {"title": "Declared Title", "created": "2026-01-15"},
        "Rendered Heading",
    )

    assert name == "2026-01-15--declared-title.md"


def test_proposed_filename_falls_back_to_h1_then_to_the_stem() -> None:
    """With no title the heading is used; with neither, the filename stem is."""
    from_h1 = proposed_filename(
        Path("notes.md"), "2026-08-14T00:00:00", {}, "Rendered Heading"
    )
    from_stem = proposed_filename(
        Path("Some_Notes.md"), "2026-08-14T00:00:00", {}, None
    )

    assert from_h1 == "2026-08-14--rendered-heading.md"
    assert from_stem == "2026-08-14--some-notes.md"


def test_proposed_filename_uses_mtime_when_created_is_absent_or_malformed() -> None:
    """A non-ISO created value is ignored in favour of the file's mtime date."""
    name = proposed_filename(
        Path("notes.md"), "2026-08-14T00:00:00", {"created": "last Tuesday"}, "Title"
    )

    assert name.startswith("2026-08-14--")


def test_proposed_filename_truncates_a_long_created_value_to_the_date() -> None:
    """A full timestamp in `created` contributes only its date component."""
    name = proposed_filename(
        Path("notes.md"),
        "2026-08-14T00:00:00",
        {"created": "2026-01-15T09:30:00Z"},
        "Title",
    )

    assert name == "2026-01-15--title.md"
