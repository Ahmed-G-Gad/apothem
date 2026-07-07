# SPDX-License-Identifier: MIT

"""Tests for the canonical shared-profile model and schema contract."""

from __future__ import annotations

import yaml
from jsonschema import Draft202012Validator, FormatChecker

from apothem.lib.profile import (
    MCP_REQUIRED_FIELD_BY_TRANSPORT,
    MCP_TRANSPORTS,
    SUPPORTED_HARNESS_IDS,
    EnforcementFlags,
    ProfileValidationError,
    WorkspaceConfig,
    load_profile_file,
    redact_value,
    resolve_profile_path,
    validate_profile,
)
from apothem.schemas import (
    profile_example_path,
    profile_minimal_path,
    profile_schema_path,
)


def _schema_validator() -> Draft202012Validator:
    schema = yaml.safe_load(profile_schema_path().read_text(encoding="utf-8"))
    return Draft202012Validator(schema, format_checker=FormatChecker())


def test_minimal_profile_applies_schema_aligned_defaults(tmp_path) -> None:
    profile = tmp_path / "profile.yaml"
    profile.write_text("identity:\n  name: Example User\n", encoding="utf-8")

    normalized = load_profile_file(profile).to_dict()

    assert normalized["identity"] == {
        "name": "Example User",
        "role": "senior software engineer",
    }
    assert normalized["preferences"] == {"language": "python", "style": "concise"}
    assert normalized["rules"] == []
    assert normalized["seriousness"] == "PERSONAL_USE"
    assert normalized["harnesses"] == {}
    assert normalized["exclude_harnesses"] == []


def test_enforcement_flags_default_off_on_clean_profile() -> None:
    profile = validate_profile({"identity": {"name": "Example User"}})

    assert profile.enforcement == EnforcementFlags()
    assert profile.to_dict()["enforcement"] == {
        "sprints": False,
        "agent_teams": False,
        "multitasking": False,
        "continuous_execution": False,
        "learning_loop": False,
    }


def test_enforcement_flags_opt_in_is_carried() -> None:
    profile = validate_profile(
        {
            "identity": {"name": "Example User"},
            "enforcement": {"sprints": True, "continuous_execution": True},
        }
    )

    assert profile.enforcement.sprints is True
    assert profile.enforcement.continuous_execution is True
    assert profile.enforcement.agent_teams is False
    assert profile.enforcement.multitasking is False
    assert profile.enforcement.learning_loop is False


def test_unknown_enforcement_flag_is_validation_error() -> None:
    try:
        validate_profile(
            {
                "identity": {"name": "Example User"},
                "enforcement": {"always_sprint": True},
            },
            profile_path="profile.yaml",
        )
    except ProfileValidationError as exc:
        diagnostic = exc.diagnostic.to_dict()
    else:
        raise AssertionError("unknown enforcement flag should fail validation")

    assert diagnostic["code"] == "profile.unknown_field"
    assert diagnostic["field"] == "enforcement"
    assert "always_sprint" in diagnostic["reason"]


def test_per_harness_enforcement_override_deep_merges() -> None:
    profile = validate_profile(
        {
            "identity": {"name": "Example User"},
            "enforcement": {"sprints": True},
            "harnesses": {"cursor": {"enforcement": {"agent_teams": True}}},
        }
    )

    cursor = profile.for_harness("cursor")

    assert cursor["enforcement"]["sprints"] is True
    assert cursor["enforcement"]["agent_teams"] is True


def test_normalization_is_deterministic() -> None:
    source = {
        "identity": {"name": " Example User ", "role": " Engineer\r\nLead "},
        "preferences": {"language": "Python", "style": "balanced"},
        "rules": ["first\r\nrule", "second rule"],
        "seriousness": "SHARED",
        "harnesses": {
            "cursor": {"preferences": {"style": "verbose"}},
            "claude-code": {"seriousness": "PUBLIC_LAUNCH"},
        },
        "exclude_harnesses": ["cursor", "antigravity"],
    }

    first = validate_profile(source).to_dict()
    second = validate_profile(source).to_dict()

    assert first == second
    assert first["identity"]["role"] == "Engineer\nLead"
    assert first["preferences"]["language"] == "python"
    assert first["exclude_harnesses"] == ["antigravity", "cursor"]


def test_harness_override_deep_merges_over_shared_profile() -> None:
    profile = validate_profile(
        {
            "identity": {"name": "Example User"},
            "preferences": {"language": "python", "style": "concise"},
            "harnesses": {
                "cursor": {"preferences": {"style": "verbose"}},
            },
        }
    )

    cursor = profile.for_harness("cursor")

    assert cursor["identity"]["name"] == "Example User"
    assert cursor["preferences"] == {"language": "python", "style": "verbose"}


def test_unknown_harness_override_is_validation_error() -> None:
    try:
        validate_profile(
            {
                "identity": {"name": "Example User"},
                "harnesses": {"claude_code": {"seriousness": "SHARED"}},
            },
            profile_path="profile.yaml",
        )
    except ProfileValidationError as exc:
        diagnostic = exc.diagnostic.to_dict()
    else:
        raise AssertionError("unknown harness id should fail validation")

    assert diagnostic["code"] == "profile.unknown_field"
    assert diagnostic["field"] == "harnesses"
    assert "claude_code" in diagnostic["reason"]
    assert diagnostic["files_written"] == []


def test_invalid_excluded_harness_name_is_validation_error() -> None:
    try:
        validate_profile(
            {
                "identity": {"name": "Example User"},
                "exclude_harnesses": ["claude_code"],
            },
            profile_path="profile.yaml",
        )
    except ProfileValidationError as exc:
        diagnostic = exc.diagnostic.to_dict()
    else:
        raise AssertionError("invalid excluded harness id should fail validation")

    assert diagnostic["code"] == "profile.invalid_choice"
    assert diagnostic["field"] == "exclude_harnesses.0"
    assert "claude_code" in diagnostic["reason"]
    assert diagnostic["files_written"] == []


def test_wrong_profile_field_type_is_validation_error() -> None:
    try:
        validate_profile(
            {"identity": []},
            profile_path="profile.yaml",
        )
    except ProfileValidationError as exc:
        diagnostic = exc.diagnostic.to_dict()
    else:
        raise AssertionError("wrong identity type should fail validation")

    assert diagnostic["code"] == "profile.invalid_type"
    assert diagnostic["field"] == "identity"
    assert diagnostic["safe_value"] == []
    assert diagnostic["files_written"] == []


def test_missing_profile_file_fails_without_creating_path(tmp_path) -> None:
    profile = tmp_path / "missing.yaml"

    try:
        load_profile_file(profile)
    except ProfileValidationError as exc:
        diagnostic = exc.diagnostic.to_dict()
    else:
        raise AssertionError("missing profile path should fail validation")

    assert diagnostic["code"] == "profile.not_found"
    assert diagnostic["field"] == "profile"
    assert diagnostic["files_written"] == []
    assert not profile.exists()


def test_for_harness_rejects_unsupported_reference() -> None:
    profile = validate_profile({"identity": {"name": "Example User"}})

    try:
        profile.for_harness("not-a-harness")
    except ValueError as exc:
        message = str(exc)
    else:
        raise AssertionError("unsupported harness lookup should fail")

    assert "Unsupported harness id" in message


def test_secret_like_values_are_redacted_in_diagnostics() -> None:
    try:
        validate_profile(
            {
                "identity": {"name": "Example User"},
                "api_token": "sk-example0123456789abcdef",
            },
            profile_path="profile.yaml",
        )
    except ProfileValidationError as exc:
        diagnostic = exc.diagnostic.to_dict()
        plain = exc.diagnostic.format_plain()
    else:
        raise AssertionError("unknown secret-like field should fail validation")

    sensitive_key = "api_" + "token"
    assert diagnostic["safe_value"][sensitive_key] == redact_value(
        "sk-example0123456789abcdef"
    )
    assert "sk-example" not in plain


def test_redacts_token_shaped_string_values() -> None:
    assert redact_value("ghp_abcdefghijklmnopqrstuvwxyz123456") == "<redacted>"


def test_packaged_examples_validate() -> None:
    validator = _schema_validator()
    for path in (profile_minimal_path(), profile_example_path()):
        profile = yaml.safe_load(path.read_text(encoding="utf-8"))
        errors = list(validator.iter_errors(profile))
        assert errors == []
        validate_profile(profile)


def test_schema_and_runtime_share_supported_harness_ids() -> None:
    schema = yaml.safe_load(profile_schema_path().read_text(encoding="utf-8"))
    schema_ids = tuple(schema["$defs"]["harnessId"]["enum"])
    assert schema_ids == SUPPORTED_HARNESS_IDS


def test_schema_and_runtime_share_mcp_transports() -> None:
    schema = yaml.safe_load(profile_schema_path().read_text(encoding="utf-8"))
    schema_transports = tuple(
        schema["$defs"]["mcpServer"]["properties"]["transport"]["enum"]
    )
    assert schema_transports == MCP_TRANSPORTS
    # Every code-side transport has a schema if/then required-key block.
    assert set(MCP_REQUIRED_FIELD_BY_TRANSPORT) == set(MCP_TRANSPORTS)
    schema_required = {
        block["then"]["required"][0] for block in schema["$defs"]["mcpServer"]["allOf"]
    }
    assert schema_required == set(MCP_REQUIRED_FIELD_BY_TRANSPORT.values())


def test_mcp_inventory_round_trips_in_stable_order() -> None:
    profile = validate_profile(
        {
            "identity": {"name": "Example User"},
            "mcp_servers": {
                "zeta": {"transport": "stdio", "command": "z-server"},
                "alpha": {
                    "transport": "streamable-http",
                    "url": "https://mcp.example.invalid/a",
                },
            },
        }
    )

    rendered = profile.to_dict()["mcp_servers"]

    assert list(rendered) == ["alpha", "zeta"]
    assert rendered["alpha"] == {
        "transport": "streamable-http",
        "url": "https://mcp.example.invalid/a",
    }
    assert rendered["zeta"] == {"transport": "stdio", "command": "z-server"}


def test_per_harness_mcp_override_unions_by_name() -> None:
    profile = validate_profile(
        {
            "identity": {"name": "Example User"},
            "mcp_servers": {"shared": {"transport": "stdio", "command": "s"}},
            "harnesses": {
                "cursor": {
                    "mcp_servers": {
                        "extra": {
                            "transport": "http",
                            "url": "https://mcp.example.invalid/x",
                        }
                    }
                }
            },
        }
    )

    cursor = profile.for_harness("cursor")

    assert set(cursor["mcp_servers"]) == {"shared", "extra"}
    assert cursor["mcp_servers"]["shared"]["command"] == "s"
    assert cursor["mcp_servers"]["extra"]["url"] == "https://mcp.example.invalid/x"


def test_stdio_mcp_server_without_command_is_validation_error() -> None:
    try:
        validate_profile(
            {
                "identity": {"name": "Example User"},
                "mcp_servers": {"broken": {"transport": "stdio"}},
            },
            profile_path="profile.yaml",
        )
    except ProfileValidationError as exc:
        diagnostic = exc.diagnostic.to_dict()
    else:
        raise AssertionError("stdio server without command should fail validation")

    assert diagnostic["code"] == "profile.required"


def test_unknown_mcp_server_key_is_validation_error() -> None:
    try:
        validate_profile(
            {
                "identity": {"name": "Example User"},
                "mcp_servers": {
                    "broken": {"transport": "stdio", "command": "c", "bogus": 1}
                },
            },
            profile_path="profile.yaml",
        )
    except ProfileValidationError as exc:
        diagnostic = exc.diagnostic.to_dict()
    else:
        raise AssertionError("unknown mcp server key should fail validation")

    assert diagnostic["code"] == "profile.unknown_field"


def test_resolve_profile_path_expands_home() -> None:
    resolved = resolve_profile_path("~/profile.yaml")
    assert resolved.is_absolute()
    assert "~" not in str(resolved)


def test_workspace_defaults_when_block_omitted() -> None:
    """A profile omitting ``workspace`` resolves to today's behavior exactly."""
    profile = validate_profile({"identity": {"name": "Example User"}})

    assert profile.workspace == WorkspaceConfig()
    assert profile.workspace.directory_name == ".apothem"
    assert profile.workspace.scope == "project-local"
    assert profile.to_dict()["workspace"] == {
        "directory_name": ".apothem",
        "scope": "project-local",
    }


def test_workspace_omitted_profile_matches_explicit_default_profile() -> None:
    """Omitting ``workspace`` is byte-identical to stating its defaults."""
    omitted = validate_profile({"identity": {"name": "Example User"}}).to_dict()
    explicit = validate_profile(
        {
            "identity": {"name": "Example User"},
            "workspace": {"directory_name": ".apothem", "scope": "project-local"},
        }
    ).to_dict()

    assert omitted == explicit


def test_workspace_explicit_values_are_carried() -> None:
    profile = validate_profile(
        {
            "identity": {"name": "Example User"},
            "workspace": {"directory_name": ".work", "scope": "user-home"},
        }
    )

    assert profile.workspace.directory_name == ".work"
    assert profile.workspace.scope == "user-home"
    assert profile.to_dict()["workspace"] == {
        "directory_name": ".work",
        "scope": "user-home",
    }


def test_workspace_partial_block_fills_each_missing_default() -> None:
    """A partial ``workspace`` block defaults only the absent field."""
    only_scope = validate_profile(
        {
            "identity": {"name": "Example User"},
            "workspace": {"scope": "user-home"},
        }
    )
    only_dir = validate_profile(
        {
            "identity": {"name": "Example User"},
            "workspace": {"directory_name": ".work"},
        }
    )

    assert only_scope.workspace.directory_name == ".apothem"
    assert only_scope.workspace.scope == "user-home"
    assert only_dir.workspace.directory_name == ".work"
    assert only_dir.workspace.scope == "project-local"


def test_workspace_invalid_scope_is_validation_error() -> None:
    try:
        validate_profile(
            {
                "identity": {"name": "Example User"},
                "workspace": {"scope": "global"},
            },
            profile_path="profile.yaml",
        )
    except ProfileValidationError as exc:
        diagnostic = exc.diagnostic.to_dict()
    else:
        raise AssertionError("invalid workspace scope should fail validation")

    assert diagnostic["code"] == "profile.invalid_choice"
    assert diagnostic["field"] == "workspace.scope"


def test_workspace_unknown_field_is_validation_error() -> None:
    try:
        validate_profile(
            {
                "identity": {"name": "Example User"},
                "workspace": {"directory_name": ".work", "bogus": 1},
            },
            profile_path="profile.yaml",
        )
    except ProfileValidationError as exc:
        diagnostic = exc.diagnostic.to_dict()
    else:
        raise AssertionError("unknown workspace field should fail validation")

    assert diagnostic["code"] == "profile.unknown_field"
    assert diagnostic["field"] == "workspace"


def test_workspace_directory_name_separator_is_validation_error() -> None:
    try:
        validate_profile(
            {
                "identity": {"name": "Example User"},
                "workspace": {"directory_name": "a/b"},
            },
            profile_path="profile.yaml",
        )
    except ProfileValidationError as exc:
        diagnostic = exc.diagnostic.to_dict()
    else:
        raise AssertionError("path-separator directory_name should fail validation")

    assert diagnostic["field"] == "workspace.directory_name"


def test_workspace_is_stripped_from_per_harness_projection() -> None:
    """``workspace`` is project-global; it never reaches a per-harness profile."""
    profile = validate_profile(
        {
            "identity": {"name": "Example User"},
            "workspace": {"directory_name": ".work", "scope": "user-home"},
        }
    )

    cursor = profile.for_harness("cursor")

    assert "workspace" not in cursor


def test_schema_and_runtime_share_workspace_defaults() -> None:
    schema = yaml.safe_load(profile_schema_path().read_text(encoding="utf-8"))
    workspace_def = schema["$defs"]["workspace"]["properties"]
    assert workspace_def["scope"]["enum"] == ["project-local", "user-home"]
    assert workspace_def["scope"]["default"] == WorkspaceConfig().scope
    assert workspace_def["directory_name"]["default"] == (
        WorkspaceConfig().directory_name
    )
