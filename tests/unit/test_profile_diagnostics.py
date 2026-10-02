# SPDX-License-Identifier: MIT

"""Profile validation reports every error, and labels the echoed value plainly.

``validate_profile`` collected every schema error but raised on the
first, so operators fixed one field per run. The plain ``Safe value:`` label
read like a suggested replacement although it echoes the (redacted) bad input,
and an unknown top-level key echoed the whole profile.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from apothem.cli import main
from apothem.lib.profile import ProfileValidationError, validate_profile

_TWO_TYPE_ERRORS = {"identity": {"name": 42, "email": ["not", "a", "string"]}}
_TWO_TYPE_ERRORS_YAML = "identity:\n  name: 42\n  email: [not, a, string]\n"


def _diagnostic(profile: dict) -> ProfileValidationError:
    with pytest.raises(ProfileValidationError) as caught:
        validate_profile(profile, profile_path="profile.yaml")
    return caught.value


def test_every_schema_error_is_reported() -> None:
    payload = _diagnostic(_TWO_TYPE_ERRORS).diagnostic.to_dict()
    fields = sorted(item["field"] for item in payload["errors"])
    assert fields == ["identity.email", "identity.name"]
    assert all(item["code"] == "profile.invalid_type" for item in payload["errors"])
    # The first error still fills the top-level fields (compatible shape).
    assert payload["field"] == payload["errors"][0]["field"]


def test_plain_diagnostic_lists_every_error_with_a_clear_label() -> None:
    plain = _diagnostic(_TWO_TYPE_ERRORS).diagnostic.format_plain()
    assert "Safe value:" not in plain
    assert "Offending value (redacted):" in plain
    assert "identity.name" in plain
    assert "identity.email" in plain


def test_unknown_top_level_key_echoes_only_that_key() -> None:
    payload = _diagnostic(
        {"identity": {"name": "Example User"}, "bogus": 1}
    ).diagnostic.to_dict()
    assert payload["code"] == "profile.unknown_field"
    assert payload["safe_value"] == {"bogus": 1}


def test_cli_reports_both_errors(runner: CliRunner, tmp_path: Path) -> None:
    profile = tmp_path / "wrongtype.yaml"
    profile.write_text(_TWO_TYPE_ERRORS_YAML, encoding="utf-8")

    as_json = runner.invoke(
        main,
        ["install", "--harness", "claude-code", "--profile", str(profile), "--json"],
    )
    assert as_json.exit_code == 1, as_json.output
    assert len(json.loads(as_json.stdout)["error"]["errors"]) == 2

    plain = runner.invoke(
        main, ["install", "--harness", "claude-code", "--profile", str(profile)]
    )
    assert plain.exit_code == 1, plain.output
    assert "Safe value:" not in plain.output
    assert "identity.name" in plain.output
    assert "identity.email" in plain.output
