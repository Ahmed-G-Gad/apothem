# SPDX-License-Identifier: MIT

"""Characterization coverage for the plan-suite provenance builder.

``apothem.audit.build_plans_provenance`` attributes every file in a legacy
plan-suite tree to the project it belongs to, so a migration can route each
one to its rightful home. Like its sibling scanners it ships as a standalone
entry point with no importers, and it therefore had **no test coverage at
all** — the suite passed without executing one line of it.

These are characterization tests. They pin current behavior so the module can
be refactored against a real green-before / green-after baseline, and they say
so in the docstring wherever the behavior is more surprising than the function
name suggests.

Scope note. Every function in the module is module-private; ``main`` is the
only public surface. Testing the privates is deliberate — characterizing a
1,005-line module through its CLI alone would pin almost nothing.

Lifecycle note. The builder is scoped to the legacy ``.plans/`` tree by
design, per its own module docstring. ``CLAUDE.md`` makes ``.apothem/plans/``
canonical and directs operators to ``apothem migrate-workspace``, so this
module is migration-era tooling whose scope is deliberately historical — not
drift.
"""

from __future__ import annotations

from pathlib import Path

from apothem.audit.build_plans_provenance import (
    _h1_of,
    _kebab_slug,
    _load_known_projects,
    _matches_project,
    _parse_frontmatter,
    _proposed_filename,
    _strip_frontmatter,
    _suite_of,
)

# --- frontmatter ------------------------------------------------------------


def test_parse_frontmatter_absent_block_yields_no_fields() -> None:
    """Content with no frontmatter parses to an empty mapping."""
    assert _parse_frontmatter("# Heading\nbody\n") == {}


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

    fields = _parse_frontmatter(content)

    assert fields == {
        "project": "apothem",
        "title": "Some Plan",
        "created": "2026-01-15",
    }


def test_parse_frontmatter_only_matches_at_the_start_of_content() -> None:
    """A delimiter block further down the file is body text, not frontmatter."""
    assert _parse_frontmatter("intro\n---\ntitle: Not Frontmatter\n---\n") == {}


def test_strip_frontmatter_removes_only_the_leading_block() -> None:
    """The body after the closing delimiter survives intact."""
    content = "---\ntitle: T\n---\n# Heading\nbody\n"

    assert _strip_frontmatter(content) == "# Heading\nbody\n"


def test_strip_frontmatter_passes_content_through_when_absent() -> None:
    """Content with no frontmatter is returned unchanged."""
    assert _strip_frontmatter("# Heading\n") == "# Heading\n"


# --- slug and heading -------------------------------------------------------


def test_kebab_slug_lowercases_and_joins_on_hyphens() -> None:
    """Spaces and underscores collapse to single hyphens."""
    assert _kebab_slug("Some  Plan_Title") == "some-plan-title"


def test_kebab_slug_drops_punctuation_and_trims_edges() -> None:
    """Non-word characters are removed, and leading/trailing hyphens go."""
    assert _kebab_slug("  *Plan*: the (sequel)!  ") == "plan-the-sequel"


def test_kebab_slug_truncates_at_sixty_characters() -> None:
    """An overlong title is cut to keep filenames manageable."""
    assert len(_kebab_slug("word " * 40)) <= 60


def test_kebab_slug_of_empty_text_is_empty() -> None:
    """Nothing in, nothing out — the caller decides the fallback."""
    assert _kebab_slug("   ") == ""


def test_h1_of_reads_past_the_frontmatter() -> None:
    """The first heading is found in the body, not the frontmatter block."""
    assert _h1_of("---\ntitle: T\n---\n# Real Heading\n") == "Real Heading"


def test_h1_of_returns_none_without_a_heading() -> None:
    """Body prose with no heading yields no title candidate."""
    assert _h1_of("just prose\n") is None


# --- proposed filename ------------------------------------------------------


def test_proposed_filename_prefers_frontmatter_title_over_h1() -> None:
    """The declared title outranks the rendered heading.

    Frontmatter is an explicit authoring decision; the H1 is a rendering
    detail that may have drifted from it.
    """
    name = _proposed_filename(
        Path("notes.md"),
        "2026-08-14T00:00:00",
        {"title": "Declared Title", "created": "2026-01-15"},
        "Rendered Heading",
    )

    assert name == "2026-01-15--declared-title.md"


def test_proposed_filename_falls_back_to_h1_then_to_the_stem() -> None:
    """With no title the heading is used; with neither, the filename stem is."""
    from_h1 = _proposed_filename(
        Path("notes.md"), "2026-08-14T00:00:00", {}, "Rendered Heading"
    )
    from_stem = _proposed_filename(
        Path("Some_Notes.md"), "2026-08-14T00:00:00", {}, None
    )

    assert from_h1 == "2026-08-14--rendered-heading.md"
    assert from_stem == "2026-08-14--some-notes.md"


def test_proposed_filename_uses_mtime_when_created_is_absent_or_malformed() -> None:
    """A non-ISO created value is ignored in favour of the file's mtime date."""
    name = _proposed_filename(
        Path("notes.md"), "2026-08-14T00:00:00", {"created": "last Tuesday"}, "Title"
    )

    assert name.startswith("2026-08-14--")


def test_proposed_filename_truncates_a_long_created_value_to_the_date() -> None:
    """A full timestamp in `created` contributes only its date component."""
    name = _proposed_filename(
        Path("notes.md"),
        "2026-08-14T00:00:00",
        {"created": "2026-01-15T09:30:00Z"},
        "Title",
    )

    assert name == "2026-01-15--title.md"


# --- suite resolution -------------------------------------------------------


def test_suite_of_reads_the_directory_under_the_legacy_plans_root() -> None:
    """The suite is the path segment directly beneath ``.plans``."""
    assert _suite_of(".plans/my-suite/PROGRESS.md") == "my-suite"


def test_suite_of_normalises_windows_separators() -> None:
    """Backslash-separated paths resolve identically to POSIX ones."""
    assert _suite_of(r".plans\my-suite\PROGRESS.md") == "my-suite"


def test_suite_of_returns_empty_outside_the_legacy_root() -> None:
    """A path not under ``.plans`` carries no suite.

    That includes the canonical ``.apothem/plans/`` tree: this builder is
    migration-era tooling scoped to the legacy layout by design, so a
    canonical path is simply out of its scope rather than misfiled.
    """
    assert _suite_of("src/apothem/cli/install.py") == ""
    assert _suite_of(".apothem/plans/my-suite/PROGRESS.md") == ""


# --- known-projects registry ------------------------------------------------


def test_load_known_projects_absent_file_yields_no_entries(tmp_path: Path) -> None:
    """A missing registry is an empty list, not an error."""
    assert _load_known_projects(tmp_path / "absent.txt") == []


def test_load_known_projects_skips_comments_and_blank_lines(tmp_path: Path) -> None:
    """Hash comments and blanks are ignored so the file can be annotated."""
    registry = tmp_path / "projects.txt"
    registry.write_text("# a comment\n\nname = ref\n", encoding="utf-8")

    assert _load_known_projects(registry) == [{"name": "name", "ref": "ref"}]


def test_load_known_projects_derives_a_name_from_a_bare_url(tmp_path: Path) -> None:
    """A bare URL entry takes its name from the repository slug.

    The trailing ``.git`` and any trailing slash are stripped, so the same
    repository written either way resolves to one name.
    """
    registry = tmp_path / "projects.txt"
    registry.write_text("https://example.invalid/owner/apothem.git\n", encoding="utf-8")

    assert _load_known_projects(registry) == [
        {"name": "apothem", "ref": "https://example.invalid/owner/apothem.git"}
    ]


def test_matches_project_is_case_insensitive_on_name_or_ref() -> None:
    """Either the project name or its ref matching the value is enough."""
    project = {"name": "Apothem", "ref": "https://example.invalid/owner/apothem"}

    assert _matches_project("see APOTHEM docs", project)
    assert _matches_project("https://EXAMPLE.invalid/owner/apothem", project)


def test_matches_project_ignores_empty_registry_fields() -> None:
    """An entry with no name and no ref never matches, rather than matching all.

    An empty substring is contained in every string, so a naive check would
    attribute every file to a blank registry row.
    """
    assert not _matches_project("anything at all", {"name": "", "ref": ""})
