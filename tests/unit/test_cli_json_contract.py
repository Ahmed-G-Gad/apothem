# SPDX-License-Identifier: MIT

"""Every ``--json`` document carries a top-level ``schema_version``.

Scripts and agents that parse CLI output need one field that says which
schema the document follows. The value is ``1`` for every command today; the
field is additive (no existing key changes). For ``profile show`` the
document *is* a profile, so its ``schema_version`` is the profile schema
version, which is also ``1``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from apothem.cli import main
from apothem.harnesses._shared import install_driver

_PROFILE = (
    "identity:\n  name: Ada Lovelace\n  email: ada@analytical.engine\n"
    "  github: adalovelace\nseriousness: PERSONAL_USE\n"
)


@pytest.fixture
def world(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
    """Isolated HOME with a personalized default profile and an empty project."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.delenv("CODEX_HOME", raising=False)
    monkeypatch.setenv("APOTHEM_HOME", str(tmp_path / "apothem-home"))
    monkeypatch.setattr(install_driver, "BACKUP_ROOT", tmp_path / "backups")
    profile = home / ".config" / "apothem" / "profile.yaml"
    profile.parent.mkdir(parents=True)
    profile.write_text(_PROFILE, encoding="utf-8")
    project = tmp_path / "proj"
    project.mkdir()
    return {"home": home, "project": project, "tmp": tmp_path}


def _argvs(world: dict[str, Path]) -> list[list[str]]:
    project = str(world["project"])
    return [
        ["harnesses", "show", "claude-code", "--json"],
        ["doctor", "--json"],
        ["status", "--json"],
        ["verify", "--harness", "claude-code", "--json"],
        ["migrate-workspace", "--project", project, "--dry-run", "--json"],
        ["profile", "show", "--json"],
        ["profile", "set", "preferences.style", "concise", "--json"],
        ["profile", "init", "--profile", str(world["tmp"] / "p2.yaml"), "--json"],
        ["install", "--harness", "claude-code", "--dry-run", "--json"],
        ["install", "--harness", "claude-code", "--json"],
        ["update", "--harness", "claude-code", "--dry-run", "--json"],
        ["diff", "--harness", "claude-code", "--json"],
        ["quickstart", "--harness", "claude-code", "--yes", "--json"],
        ["uninstall", "--harness", "claude-code", "--yes", "--json"],
        ["rollback", "--harness", "claude-code", "--last", "--yes", "--json"],
        ["backups", "prune", "--harness", "claude-code", "--dry-run", "--json"],
        ["backups", "prune", "--harness", "claude-code", "--json"],
        # Expected-error envelopes carry the field too.
        ["install", "--harness", "no-such-harness", "--json"],
        ["profile", "show", "--profile", str(world["tmp"] / "absent.yaml"), "--json"],
    ]


def test_every_json_document_carries_schema_version(
    runner: CliRunner, world: dict[str, Path]
) -> None:
    for argv in _argvs(world):
        result = runner.invoke(main, argv)
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError as exc:  # pragma: no cover - diagnostic
            raise AssertionError(f"{argv}: stdout is not one JSON document") from exc
        assert isinstance(payload, dict), argv
        assert payload.get("schema_version") == 1, (argv, payload)
        assert next(iter(payload)) == "schema_version", argv


def test_entry_point_envelope_uses_the_same_contract_version() -> None:
    """The stdlib-only prerequisite envelope in ``__main__`` stays in step."""
    from apothem import __main__ as entry
    from apothem.cli._json_formatter import JSON_SCHEMA_VERSION

    assert entry.JSON_SCHEMA_VERSION == JSON_SCHEMA_VERSION


def test_harnesses_list_keeps_its_documented_array_shape(
    runner: CliRunner, world: dict[str, Path]
) -> None:
    """The one documented exception: a bare array, unchanged for compatibility."""
    payload = json.loads(runner.invoke(main, ["harnesses", "list", "--json"]).stdout)
    assert isinstance(payload, list)
    assert all("name" in row for row in payload)
