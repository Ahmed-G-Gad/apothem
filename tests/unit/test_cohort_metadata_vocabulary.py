# SPDX-License-Identifier: MIT

"""Consistency tests for the canonical cohort-metadata vocabulary.

``src/apothem/schemas/cohort-metadata-vocabulary.yaml`` is the single
repo-controlled source of truth for status names, severity names, ownership
classes, frontmatter key sets, version-field rules, and output-contract field
shapes. These tests assert that every live schema and validator the registry
names under ``controlled_by`` actually agrees with the values declared there —
so drift on either surface (the registry or the live artifact) fails the gate.
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from apothem.conformity import frontmatter_grep
from apothem.harnesses._shared import install_driver
from apothem.lib import propagation

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCHEMAS = _REPO_ROOT / "src" / "apothem" / "schemas"
_VOCAB_PATH = _SCHEMAS / "cohort-metadata-vocabulary.yaml"


def _vocab() -> dict[str, object]:
    return yaml.safe_load(_VOCAB_PATH.read_text(encoding="utf-8"))


def _schema_required(name: str) -> list[str]:
    data = json.loads((_SCHEMAS / f"{name}.schema.json").read_text(encoding="utf-8"))
    return sorted(data.get("required", []))


def test_vocabulary_loads() -> None:
    vocab = _vocab()
    assert vocab["schema_version"] == 1


def test_plan_lifecycle_matches_plan_schema() -> None:
    vocab = _vocab()
    declared = sorted(vocab["status_vocabulary"]["plan_lifecycle"]["values"])
    plan = json.loads((_SCHEMAS / "plan.schema.json").read_text(encoding="utf-8"))
    actual = sorted(plan["properties"]["status"]["enum"])
    assert declared == actual


def test_review_verdict_matches_handoff_manifest() -> None:
    vocab = _vocab()
    declared = sorted(vocab["status_vocabulary"]["review_verdict"]["values"])
    hm = yaml.safe_load(
        (_SCHEMAS / "handoff-manifest.yaml").read_text(encoding="utf-8")
    )
    actual = sorted(hm["plan_review"]["properties"]["verdict"]["enum"])
    assert declared == actual


def test_plan_design_applicability_matches_handoff_manifest() -> None:
    vocab = _vocab()
    declared = sorted(vocab["status_vocabulary"]["plan_design_applicability"]["values"])
    hm = yaml.safe_load(
        (_SCHEMAS / "handoff-manifest.yaml").read_text(encoding="utf-8")
    )
    actual = sorted(hm["plan_design"]["properties"]["applicability"]["enum"])
    assert declared == actual


def test_materialization_outcome_matches_install_driver() -> None:
    vocab = _vocab()
    declared = sorted(vocab["status_vocabulary"]["materialization_outcome"]["values"])
    actual = sorted(install_driver._OUTCOMES)
    assert declared == actual


def test_ownership_classes_match_propagation() -> None:
    vocab = _vocab()
    declared = sorted(vocab["ownership_classes"]["values"])
    actual = sorted(propagation.OWNERSHIP_CLASSES)
    assert declared == actual


def test_gate_result_exit_codes_match_gate_module() -> None:
    vocab = _vocab()
    gate_result = vocab["status_vocabulary"]["gate_result"]
    assert gate_result["pass_exit_code"] == frontmatter_grep.EXIT_PASS
    assert gate_result["fail_exit_code"] == frontmatter_grep.EXIT_FAIL


def test_mechanical_floor_matches_frontmatter_grep() -> None:
    vocab = _vocab()
    declared = {
        cohort: sorted(keys)
        for cohort, keys in vocab["frontmatter"]["mechanical_floor"][
            "required_keys"
        ].items()
    }
    actual = {
        cohort: sorted(keys) for cohort, keys in frontmatter_grep.REQUIRED_KEYS.items()
    }
    assert declared == actual


def test_authoritative_contract_matches_json_schemas() -> None:
    vocab = _vocab()
    contract = vocab["frontmatter"]["authoritative_contract"]["required_keys"]
    for cohort, schema_name in (
        ("agents", "agent"),
        ("commands", "command"),
        ("skills", "skill"),
        ("output-styles", "output-style"),
    ):
        declared = sorted(contract[cohort]["keys"])
        assert declared == _schema_required(schema_name), cohort


def test_version_field_rule_matches_schemas() -> None:
    vocab = _vocab()
    rule = vocab["frontmatter"]["version_field_rule"]
    # Required cohorts: `version` is in the schema's required array.
    for cohort, schema_name in (
        ("commands", "command"),
        ("skills", "skill"),
    ):
        assert cohort in rule["required"]
        assert "version" in _schema_required(schema_name)
    # Optional cohorts: the schema carries `version` as a property but does not
    # require it. agent has always been optional; output-style joined them when
    # the schema was reconciled to the shipped styles, which carry only
    # name + description.
    for cohort, schema_name in (
        ("agents", "agent"),
        ("output-styles", "output-style"),
    ):
        schema = json.loads(
            (_SCHEMAS / f"{schema_name}.schema.json").read_text(encoding="utf-8")
        )
        assert cohort in rule["optional"]
        assert "version" in schema["properties"]
        assert "version" not in schema.get("required", [])


def test_materialization_result_fields_match_install_driver() -> None:
    vocab = _vocab()
    declared_required = set(
        vocab["output_contract_fields"]["materialization_result"]["required_keys"]
    )
    declared_optional = set(
        vocab["output_contract_fields"]["materialization_result"]["optional_keys"]
    )
    result = install_driver.MaterializationResult(
        outcome="created",
        operation="install",
        path="x",
        message="m",
    )
    payload = result.to_dict()
    # Required keys are always present; optional keys are a superset of what a
    # minimal result emits.
    assert declared_required <= set(payload)
    assert declared_required == set(payload)
    assert declared_optional == {"source", "backup_path", "detail"}
