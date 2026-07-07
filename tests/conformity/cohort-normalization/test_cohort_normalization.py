# SPDX-License-Identifier: MIT

"""Cohort-artifact normalization across the bundled configuration tree.

The apothem source tree carries five artifact cohorts that ship to
harnesses: commands, agents, skills, rules, and output-styles. Each
cohort has a stable normalization contract verified here against the
real tree:

* Version-field asymmetry — commands, agents, and skills carry a
  ``version:`` frontmatter field (they are versioned, invocable
  artifacts); rules and output-styles do NOT (they are behavioral
  prose governed by the always-on / path-filtered model, not SemVer).
* Required frontmatter — every cohort file declares ``name:`` and
  ``description:``; rules additionally declare ``pathFilter:`` and
  ``alwaysApply:``.
* Naming — cohort file stems and skill directory names are kebab-case.

Assertions encode only what is verifiably true of the current tree.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT: Path = Path(__file__).resolve().parents[3]
COHORTS_ROOT: Path = REPO_ROOT / "src" / "apothem"

KEBAB_CASE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


def _frontmatter(path: Path) -> str | None:
    """Return the YAML frontmatter block (without delimiters), or None."""
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    if end == -1:
        return None
    return text[3:end]


def _has_key(block: str, key: str) -> bool:
    return re.search(rf"(?m)^\s*{re.escape(key)}\s*:", block) is not None


def _flat_cohort_files(cohort: str) -> list[Path]:
    """Top-level ``*.md`` files of a flat cohort, excluding folder companions.

    ``README.md`` (human-facing) and ``AGENTS.md`` (agent-facing) are folder
    companion docs, not cohort artifacts — neither is a rule / agent /
    output-style / statusline definition the cohort ships.
    """
    directory = COHORTS_ROOT / cohort
    return sorted(
        p for p in directory.glob("*.md") if p.name not in {"README.md", "AGENTS.md"}
    )


def _skill_entrypoints() -> list[Path]:
    return sorted((COHORTS_ROOT / "skills").glob("*/SKILL.md"))


# Cohorts whose files carry a `version:` field, with their flat-file accessor.
VERSIONED_FLAT_COHORTS = ("commands", "agents")
# Cohorts whose files do NOT carry a `version:` field.
UNVERSIONED_FLAT_COHORTS = ("rules", "output-styles")


def test_cohort_directories_exist_and_are_populated() -> None:
    for cohort in (*VERSIONED_FLAT_COHORTS, *UNVERSIONED_FLAT_COHORTS):
        files = _flat_cohort_files(cohort)
        assert files, f"cohort {cohort} has no .md artifacts"
    assert _skill_entrypoints(), "skills cohort has no SKILL.md entrypoints"


@pytest.mark.parametrize("cohort", VERSIONED_FLAT_COHORTS)
def test_versioned_flat_cohorts_carry_version_field(cohort: str) -> None:
    for path in _flat_cohort_files(cohort):
        block = _frontmatter(path)
        assert block is not None, f"{path} has no YAML frontmatter"
        assert _has_key(block, "version"), f"{path} ({cohort}) is missing version:"


def test_skills_carry_version_field() -> None:
    for path in _skill_entrypoints():
        block = _frontmatter(path)
        assert block is not None, f"{path} has no YAML frontmatter"
        assert _has_key(block, "version"), f"{path} is missing version:"


@pytest.mark.parametrize("cohort", UNVERSIONED_FLAT_COHORTS)
def test_unversioned_flat_cohorts_omit_version_field(cohort: str) -> None:
    for path in _flat_cohort_files(cohort):
        block = _frontmatter(path)
        assert block is not None, f"{path} has no YAML frontmatter"
        assert not _has_key(block, "version"), (
            f"{path} ({cohort}) carries version: but this cohort is unversioned"
        )


@pytest.mark.parametrize("cohort", [*VERSIONED_FLAT_COHORTS, *UNVERSIONED_FLAT_COHORTS])
def test_flat_cohorts_carry_name_and_description(cohort: str) -> None:
    for path in _flat_cohort_files(cohort):
        block = _frontmatter(path)
        assert block is not None, f"{path} has no YAML frontmatter"
        assert _has_key(block, "name"), f"{path} ({cohort}) is missing name:"
        assert _has_key(block, "description"), (
            f"{path} ({cohort}) is missing description:"
        )


def test_skills_carry_name_and_description() -> None:
    for path in _skill_entrypoints():
        block = _frontmatter(path)
        assert block is not None, f"{path} has no YAML frontmatter"
        assert _has_key(block, "name"), f"{path} is missing name:"
        assert _has_key(block, "description"), f"{path} is missing description:"


def test_rules_carry_pathfilter_and_alwaysapply() -> None:
    """Rules declare the always-on / path-filtered control keys."""
    for path in _flat_cohort_files("rules"):
        block = _frontmatter(path)
        assert block is not None, f"{path} has no YAML frontmatter"
        assert _has_key(block, "pathFilter"), f"{path} is missing pathFilter:"
        assert _has_key(block, "alwaysApply"), f"{path} is missing alwaysApply:"


@pytest.mark.parametrize("cohort", [*VERSIONED_FLAT_COHORTS, *UNVERSIONED_FLAT_COHORTS])
def test_flat_cohort_filenames_are_kebab_case(cohort: str) -> None:
    for path in _flat_cohort_files(cohort):
        assert KEBAB_CASE.fullmatch(path.stem), f"{path} stem is not kebab-case"


def test_skill_directory_names_are_kebab_case() -> None:
    for entrypoint in _skill_entrypoints():
        directory = entrypoint.parent.name
        assert KEBAB_CASE.fullmatch(directory), f"{directory} is not kebab-case"
