# SPDX-License-Identifier: MIT

"""Cohort-packaging contract tests.

Validate that the plugin and cohort schemas are well-formed JSON Schemas, that
the minimal cohort-manifest instance validates against its schema, and that
every member named in the ``core`` cohort corresponds to a real artifact under
``src/apothem/``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft202012Validator, validate

_SCHEMAS_DIR = Path(__file__).resolve().parents[2] / "src" / "apothem" / "schemas"
_APOTHEM_ROOT = _SCHEMAS_DIR.parent
_PLUGIN_SCHEMA = _SCHEMAS_DIR / "plugin.schema.json"
_COHORT_SCHEMA = _SCHEMAS_DIR / "cohort.schema.json"
_COHORT_MANIFEST = _SCHEMAS_DIR / "cohort-manifest.yaml"


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("schema_path", [_PLUGIN_SCHEMA, _COHORT_SCHEMA])
def test_schema_is_valid_json_schema(schema_path: Path) -> None:
    """Each schema parses as JSON and passes Draft 2020-12 meta-validation."""
    schema = _load_json(schema_path)
    Draft202012Validator.check_schema(schema)


def test_cohort_manifest_validates() -> None:
    """The minimal cohort-manifest instance validates against cohort.schema.json."""
    schema = _load_json(_COHORT_SCHEMA)
    instance = _load_yaml(_COHORT_MANIFEST)
    validate(instance=instance, schema=schema)


def _member_exists(item_type: str, name: str) -> bool:
    """Return whether a cohort member resolves to a real artifact on disk."""
    if item_type == "skills":
        return (_APOTHEM_ROOT / "skills" / name / "SKILL.md").is_file()
    if item_type == "agents":
        return (_APOTHEM_ROOT / "agents" / f"{name}.md").is_file()
    if item_type == "commands":
        return (_APOTHEM_ROOT / "commands" / f"{name}.md").is_file()
    if item_type == "rules":
        return (_APOTHEM_ROOT / "rules" / f"{name}.md").is_file()
    if item_type == "hooks":
        # A hooks member is either an executable hook script or an advisory
        # message context delivered through the dispatcher.
        return (_APOTHEM_ROOT / "hooks" / f"{name}.py").is_file() or (
            _APOTHEM_ROOT / "hooks" / "messages" / f"{name}.md"
        ).is_file()
    raise AssertionError(f"unknown catalog item type: {item_type}")


_COHORT_IDS = ["core", "developer", "security", "research", "ai-engineering", "full"]


@pytest.mark.parametrize("cohort_id", _COHORT_IDS)
def test_cohort_members_are_real(cohort_id: str) -> None:
    """Every member of every cohort corresponds to a real artifact path."""
    instance = _load_yaml(_COHORT_MANIFEST)
    cohort = next(c for c in instance["cohorts"] if c["id"] == cohort_id)

    phantom: list[str] = []
    for item_type, names in cohort["members"].items():
        for name in names:
            if not _member_exists(item_type, name):
                phantom.append(f"{item_type}/{name}")

    assert not phantom, f"phantom cohort members (no artifact on disk): {phantom}"


def test_full_cohort_is_union_of_other_five() -> None:
    """`full` declares exactly the per-type union of the five named cohorts."""
    instance = _load_yaml(_COHORT_MANIFEST)
    by_id = {c["id"]: c["members"] for c in instance["cohorts"]}
    full = by_id.pop("full")

    for item_type in ("skills", "agents", "commands", "rules", "hooks"):
        union: set[str] = set()
        for members in by_id.values():
            union.update(members.get(item_type, []))
        declared = set(full.get(item_type, []))
        assert declared == union, (
            f"{item_type}: full declares {sorted(declared)} but the union of "
            f"the five named cohorts is {sorted(union)}"
        )
