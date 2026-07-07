# SPDX-License-Identifier: MIT

"""Validate shipped example cohort frontmatter against the canonical schemas.

``test_examples_validity.py`` checks that each example cohort file
(sample-agent.md / sample-command.md / SKILL.md) carries the load-bearing
``name`` + ``description`` keys. This module strengthens that guard to FULL
schema validation: each example's frontmatter is validated against its canonical
``*.schema.json`` so a future edit that introduces an invalid field value or
type — not merely a missing required key — is caught. The examples are
copy-ready demonstrations a newbie clones, so schema drift in them is a real
user-facing defect.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Final

import pytest
import yaml
from jsonschema import Draft202012Validator

REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[2]
EXAMPLES_ROOT: Final[Path] = REPO_ROOT / "examples"
SCHEMA_DIR: Final[Path] = REPO_ROOT / "src" / "apothem" / "schemas"

# Each example cohort filename mapped to its canonical schema stem.
_COHORT_SCHEMA: Final[dict[str, str]] = {
    "sample-agent.md": "agent",
    "sample-command.md": "command",
    "SKILL.md": "skill",
}


def _cohort_examples() -> list[Path]:
    return sorted(p for p in EXAMPLES_ROOT.rglob("*.md") if p.name in _COHORT_SCHEMA)


def _frontmatter(path: Path) -> dict[str, object]:
    parts = path.read_text(encoding="utf-8").split("---", 2)
    assert len(parts) >= 3, f"{path} has no frontmatter block"
    front = yaml.safe_load(parts[1])
    assert isinstance(front, dict), f"{path} frontmatter is not a mapping"
    return front


def test_cohort_examples_all_discovered() -> None:
    found = {p.name for p in _cohort_examples()}
    assert found == set(_COHORT_SCHEMA), (
        f"expected cohort examples {sorted(_COHORT_SCHEMA)}, found {sorted(found)}"
    )


@pytest.mark.parametrize(
    "example",
    _cohort_examples(),
    ids=lambda p: p.relative_to(REPO_ROOT).as_posix(),
)
def test_example_validates_against_schema(example: Path) -> None:
    schema_stem = _COHORT_SCHEMA[example.name]
    schema = json.loads(
        (SCHEMA_DIR / f"{schema_stem}.schema.json").read_text(encoding="utf-8")
    )
    front = _frontmatter(example)
    errors = sorted(
        Draft202012Validator(schema).iter_errors(front),
        key=lambda error: list(error.path),
    )
    assert not errors, (
        f"{example.relative_to(REPO_ROOT).as_posix()} violates "
        f"{schema_stem}.schema.json: " + "; ".join(e.message for e in errors[:3])
    )
