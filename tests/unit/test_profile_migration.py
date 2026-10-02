# SPDX-License-Identifier: MIT

"""Tests for the additive profile-schema versioning and migration shim."""

from __future__ import annotations

import pytest

from apothem.lib.profile import (
    _CURRENT_SCHEMA_VERSION,
    ProfileValidationError,
    load_profile_file,
    migrate_profile,
    validate_profile,
)


def test_current_schema_version_is_one() -> None:
    assert _CURRENT_SCHEMA_VERSION == 1


def test_version_less_profile_migrates_to_identical_mapping() -> None:
    source = {"identity": {"name": "Example User"}}

    migrated = migrate_profile(source)

    assert migrated == source


def test_version_less_profile_round_trips_unchanged_canonical(tmp_path) -> None:
    versioned = tmp_path / "versioned.yaml"
    versioned.write_text(
        "schema_version: 1\nidentity:\n  name: Example User\n", encoding="utf-8"
    )
    version_less = tmp_path / "version_less.yaml"
    version_less.write_text("identity:\n  name: Example User\n", encoding="utf-8")

    assert load_profile_file(versioned).to_dict() == (
        load_profile_file(version_less).to_dict()
    )
    # schema_version never leaks into the canonical model.
    assert "schema_version" not in load_profile_file(versioned).to_dict()


def test_current_version_profile_round_trips_identically() -> None:
    source = {"schema_version": 1, "identity": {"name": "Example User"}}

    first = validate_profile(source).to_dict()
    second = validate_profile(source).to_dict()

    assert first == second
    assert "schema_version" not in first


def test_newer_than_supported_version_raises_upgrade_diagnostic() -> None:
    try:
        validate_profile(
            {"schema_version": 2, "identity": {"name": "Example User"}},
            profile_path="profile.yaml",
        )
    except ProfileValidationError as exc:
        diagnostic = exc.diagnostic.to_dict()
        plain = exc.diagnostic.format_plain()
    else:
        raise AssertionError("newer schema_version should fail validation")

    assert diagnostic["code"] == "profile.version_unsupported"
    assert diagnostic["field"] == "schema_version"
    # The message conveys "written by a newer apothem; upgrade the engine".
    combined = plain.lower()
    assert "newer" in combined
    assert "upgrade" in combined
    # NOT an opaque additionalProperties / unknown-field error.
    assert diagnostic["code"] != "profile.unknown_field"


def test_migrate_profile_rejects_newer_version_directly() -> None:
    try:
        migrate_profile({"schema_version": 99, "identity": {"name": "X"}})
    except ProfileValidationError as exc:
        diagnostic = exc.diagnostic.to_dict()
    else:
        raise AssertionError("newer schema_version should raise from migrate_profile")

    assert diagnostic["code"] == "profile.version_unsupported"


def test_non_integer_version_is_left_for_schema_validator() -> None:
    try:
        validate_profile(
            {"schema_version": "1", "identity": {"name": "Example User"}},
            profile_path="profile.yaml",
        )
    except ProfileValidationError as exc:
        diagnostic = exc.diagnostic.to_dict()
    else:
        raise AssertionError("string schema_version should fail schema validation")

    # The jsonschema validator owns the type rejection, not migrate_profile.
    assert diagnostic["code"] == "profile.invalid_type"
    assert diagnostic["field"] == "schema_version"


@pytest.mark.parametrize("declared", [0, -1])
def test_below_minimum_version_is_left_for_schema_validator(declared: int) -> None:
    """schema_version < 1 has no migration entry point.

    It must fall through to the schema's minimum-1 constraint and produce
    the standard diagnostic — never a raw KeyError from the migration map.
    """
    try:
        validate_profile(
            {"schema_version": declared, "identity": {"name": "Example User"}},
            profile_path="profile.yaml",
        )
    except ProfileValidationError as exc:
        diagnostic = exc.diagnostic.to_dict()
    else:
        raise AssertionError("sub-1 schema_version should fail schema validation")

    assert diagnostic["field"] == "schema_version"


def test_validate_profile_accepts_version_less_and_current() -> None:
    version_less = validate_profile({"identity": {"name": "Example User"}})
    current = validate_profile(
        {"schema_version": 1, "identity": {"name": "Example User"}}
    )

    assert version_less.identity.name == "Example User"
    assert current.identity.name == "Example User"
    assert version_less.to_dict() == current.to_dict()


def test_validate_profile_rejects_unknown_top_level_key() -> None:
    try:
        validate_profile(
            {"identity": {"name": "Example User"}, "bogus": 1},
            profile_path="profile.yaml",
        )
    except ProfileValidationError as exc:
        diagnostic = exc.diagnostic.to_dict()
    else:
        raise AssertionError("unknown top-level key should fail validation")

    assert diagnostic["code"] == "profile.unknown_field"


def test_mixed_type_error_paths_raise_profile_error_not_type_error() -> None:
    """Violations whose paths diverge int-vs-str at the same depth must sort.

    A YAML mapping can carry an int key next to str keys; when both entries
    fail validation, the diagnostic sort must stay type-stable and surface a
    ProfileValidationError rather than crashing with TypeError.
    """
    profile = {
        "identity": {"name": "Example User"},
        "mcp_servers": {
            1: {"transport": "bogus"},
            "good": {"transport": "bogus"},
        },
    }
    with pytest.raises(ProfileValidationError):
        validate_profile(profile)


def test_version_less_profile_is_read_as_v1_once_v2_exists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A version-less profile is version 1, not "whatever is current".

    With the engine at v2 and a registered v1->v2 migration, a profile that
    carries no schema_version must go through that migration.
    """
    from apothem.lib import profile as profile_mod

    def _v1_to_v2(source: dict) -> dict:
        return {**source, "schema_version": 2, "migrated_from_v1": True}

    monkeypatch.setattr(profile_mod, "_CURRENT_SCHEMA_VERSION", 2)
    monkeypatch.setattr(profile_mod, "_MIGRATIONS", {1: _v1_to_v2})

    migrated = profile_mod.migrate_profile({"identity": {"name": "Example User"}})

    assert migrated["migrated_from_v1"] is True
    assert migrated["schema_version"] == 2


def test_profile_init_stamps_the_schema_version(tmp_path) -> None:
    """``profile init`` writes ``schema_version: 1`` into the scaffold."""
    import yaml
    from click.testing import CliRunner

    from apothem.cli import main

    target = tmp_path / "profile.yaml"
    result = CliRunner().invoke(main, ["profile", "init", "--profile", str(target)])

    assert result.exit_code == 0, result.output
    assert yaml.safe_load(target.read_text(encoding="utf-8"))["schema_version"] == 1


def test_profile_init_points_editors_at_the_published_schema(tmp_path) -> None:
    """The scaffold's first line is a YAML language-server modeline."""
    import json

    from click.testing import CliRunner

    from apothem.cli import main
    from apothem.schemas import profile_schema_path

    schema_id = json.loads(profile_schema_path().read_text(encoding="utf-8"))["$id"]
    target = tmp_path / "profile.yaml"
    result = CliRunner().invoke(main, ["profile", "init", "--profile", str(target)])

    assert result.exit_code == 0, result.output
    first_line = target.read_text(encoding="utf-8").splitlines()[0]
    assert first_line == f"# yaml-language-server: $schema={schema_id}"
    load_profile_file(target)  # the modeline is a comment; the file still loads
