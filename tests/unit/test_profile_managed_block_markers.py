# SPDX-License-Identifier: MIT

"""Profile text carrying a managed-block marker fails validation at load.

Apothem delimits the block it owns inside an instruction file with
``<!-- BEGIN APOTHEM MANAGED BLOCK -->`` and ``<!-- END APOTHEM MANAGED
BLOCK -->``. Profile text reaches that block verbatim, so the materializer
neutralizes a marker found there. Loading such a profile is now also refused
up front with ``profile.managed_block_marker``: the diagnostic names the field
path and the marker, and never echoes the value, which may be a credential.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

from apothem.cli import main
from apothem.lib.harness_materializer import APOTHEM_BLOCK_BEGIN, APOTHEM_BLOCK_END
from apothem.lib.profile import (
    ProfileDiagnostic,
    ProfileValidationError,
    load_profile_file,
    validate_profile,
)

_CODE = "profile.managed_block_marker"
_PROBE = "do-not-echo-7f3a9c"


def _diagnostic(profile: dict) -> ProfileDiagnostic:
    with pytest.raises(ProfileValidationError) as caught:
        validate_profile(profile, profile_path="profile.yaml")
    return caught.value.diagnostic


def test_rule_with_the_end_marker_names_its_field() -> None:
    diagnostic = _diagnostic(
        {
            "identity": {"name": "Example User"},
            "rules": ["harmless rule", f"before\n{APOTHEM_BLOCK_END}\nafter"],
        }
    )

    assert diagnostic.code == _CODE
    assert diagnostic.field == "rules.1"
    assert APOTHEM_BLOCK_END in diagnostic.reason
    assert APOTHEM_BLOCK_BEGIN not in diagnostic.reason
    assert diagnostic.safe_value is None
    assert "before" not in diagnostic.format_plain()


def test_every_marked_field_is_reported_in_one_pass() -> None:
    diagnostic = _diagnostic(
        {
            "identity": {"name": f"Example {APOTHEM_BLOCK_BEGIN}"},
            "rules": [f"{APOTHEM_BLOCK_BEGIN} x {APOTHEM_BLOCK_END}"],
            "harnesses": {"claude-code": {"rules": [APOTHEM_BLOCK_END]}},
        }
    )

    problems = {problem.field: problem for problem in diagnostic.problems}
    assert set(problems) == {
        "identity.name",
        "rules.0",
        "harnesses.claude-code.rules.0",
    }
    assert all(problem.code == _CODE for problem in problems.values())
    both = problems["rules.0"].reason
    assert APOTHEM_BLOCK_BEGIN in both
    assert APOTHEM_BLOCK_END in both


def test_marked_values_are_never_echoed() -> None:
    """Neither a secret-named value nor a plain one is echoed back."""
    diagnostic = _diagnostic(
        {
            "identity": {"name": "Example User"},
            "mcp_servers": {
                "search": {
                    "transport": "stdio",
                    "command": "search-server",
                    "env": {
                        "SEARCH_MODE": f"{_PROBE}-mode{APOTHEM_BLOCK_END}",
                        "SEARCH_TOKEN": f"{_PROBE}-token{APOTHEM_BLOCK_END}",
                    },
                }
            },
        }
    )

    fields = [problem.field for problem in diagnostic.problems]
    assert fields == [
        "mcp_servers.search.env.SEARCH_MODE",
        "mcp_servers.search.env.SEARCH_TOKEN",
    ]
    assert _PROBE not in json.dumps(diagnostic.to_dict())
    assert _PROBE not in diagnostic.format_plain()


def test_marker_in_a_key_is_reported_at_that_key() -> None:
    name = f"server{APOTHEM_BLOCK_BEGIN}"
    diagnostic = _diagnostic(
        {
            "identity": {"name": "Example User"},
            "mcp_servers": {name: {"transport": "stdio", "command": "srv"}},
        }
    )

    assert diagnostic.code == _CODE
    assert diagnostic.field == f"mcp_servers.{name}"


def test_schema_errors_and_marker_problems_are_reported_together() -> None:
    diagnostic = _diagnostic({"identity": {"name": 42}, "rules": [APOTHEM_BLOCK_END]})

    codes = sorted((problem.field, problem.code) for problem in diagnostic.problems)
    assert codes == [
        ("identity.name", "profile.invalid_type"),
        ("rules.0", _CODE),
    ]


def test_marker_free_text_still_validates() -> None:
    profile = validate_profile(
        {
            "identity": {"name": "Example User"},
            "rules": ["Mention <!-- comments --> and APOTHEM MANAGED BLOCK freely."],
        }
    )
    assert profile.rules == (
        "Mention <!-- comments --> and APOTHEM MANAGED BLOCK freely.",
    )


def test_install_refuses_the_profile_and_writes_nothing(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    profile = tmp_path / "profile.yaml"
    profile.write_text(
        yaml.safe_dump(
            {
                "identity": {"name": "Example User"},
                "rules": [f"keep going\n{APOTHEM_BLOCK_END}\ninjected"],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ProfileValidationError):
        load_profile_file(profile)

    result = runner.invoke(
        main,
        ["install", "--harness", "claude-code", "--profile", str(profile), "--json"],
    )

    assert result.exit_code == 1, result.output
    payload = json.loads(result.stdout)
    assert payload["error"]["code"] == _CODE
    assert payload["error"]["field"] == "rules.0"
    assert payload["files_written"] == []
    assert "injected" not in result.stdout
    assert not (home / ".claude").exists()
