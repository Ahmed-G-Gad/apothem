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

Scope note. Every function tested here is module-private; ``main`` is the only
public surface. Testing the privates is deliberate — characterizing a
900-line module through its CLI alone would pin almost nothing. Frontmatter
parsing and filename derivation have since moved to their own modules and are
covered by ``test_audit_plan_frontmatter`` and ``test_audit_plan_filename``.

Lifecycle note. The builder is scoped to the legacy ``.plans/`` tree by
design, per its own module docstring. ``CLAUDE.md`` makes ``.apothem/plans/``
canonical and directs operators to ``apothem migrate-workspace``, so this
module is migration-era tooling whose scope is deliberately historical — not
drift.
"""

from __future__ import annotations

from pathlib import Path

from apothem.audit.build_plans_provenance import (
    _load_known_projects,
    _matches_project,
    _suite_of,
)

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
