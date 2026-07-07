# SPDX-License-Identifier: MIT

"""Tests for the advisory-mode auditor findings schema contract."""

from __future__ import annotations

import json

from jsonschema import Draft202012Validator

from apothem.schemas import advisory_finding_schema_path


def _schema() -> dict:
    return json.loads(advisory_finding_schema_path().read_text(encoding="utf-8"))


def _validator() -> Draft202012Validator:
    schema = _schema()
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def _example_findings() -> dict:
    return {
        "strict": False,
        "findings": [
            {
                "id": "secret-leak-grep",
                "category": "secret",
                "severity": "HIGH",
                "location": {"path": "src/app/config.py", "line": 12},
                "message": "A token-shaped literal is committed to source.",
                "next_step": "Move the value to an environment variable and rotate the token.",
            }
        ],
        "summary": {"total": 1, "high": 1, "medium": 0, "low": 0},
    }


def test_schema_is_valid_draft_2020_12() -> None:
    _validator()


def test_well_formed_findings_document_validates() -> None:
    validator = _validator()
    assert list(validator.iter_errors(_example_findings())) == []


def test_empty_advisory_run_validates() -> None:
    validator = _validator()
    empty = {
        "strict": False,
        "findings": [],
        "summary": {"total": 0, "high": 0, "medium": 0, "low": 0},
    }
    assert list(validator.iter_errors(empty)) == []


def test_finding_without_next_step_is_rejected() -> None:
    validator = _validator()
    doc = _example_findings()
    del doc["findings"][0]["next_step"]
    errors = list(validator.iter_errors(doc))
    assert errors, "every finding must carry a definitive next_step"


def test_error_category_is_admitted() -> None:
    validator = _validator()
    doc = _example_findings()
    doc["findings"][0]["category"] = "error"
    doc["findings"][0]["message"] = "The auditor failed to parse a config file."
    doc["findings"][0]["next_step"] = "Inspect the malformed file and re-run the audit."
    assert list(validator.iter_errors(doc)) == []


def test_unknown_finding_field_is_rejected() -> None:
    validator = _validator()
    doc = _example_findings()
    doc["findings"][0]["blocking"] = True
    errors = list(validator.iter_errors(doc))
    assert errors, "advisory findings carry no blocking field; the run is advisory"
