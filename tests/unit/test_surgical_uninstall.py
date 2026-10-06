# SPDX-License-Identifier: MIT

"""Regression tests for surgical, operator-safe uninstall.

The uninstall path used to rename an operator-owned target to a timestamped
``.bak`` sibling, destroying the operator's prose and keys. The surgical path
replaces that with a scoped removal: only Apothem's contribution is stripped
(the sentinel-delimited managed block for Markdown anchors, Apothem's keys and
hook handlers for JSON / YAML configs), operator content survives, an
Apothem-only file is deleted, and no whole-file ``.bak`` sibling is ever left
beside the operator's file. The suite-wide autouse fixtures redirect the backup
root and the install ledger under the test's temp tree, so no real HOME state is
touched.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from apothem.harnesses._shared import install_driver
from apothem.harnesses.claude_code import ClaudeCodeAdapter
from apothem.harnesses.codex import CodexAdapter
from apothem.harnesses.hermes import HermesAdapter
from apothem.harnesses.open_claw import OpenClawAdapter


def _no_sibling_bak(directory: Path) -> bool:
    """Return True when *directory* carries no ``*.bak`` sibling backup."""
    return not list(directory.rglob("*.bak"))


# --- sentinel anchor: codex AGENTS.md --------------------------------------


def test_codex_anchor_keeps_operator_prose_and_removes_block(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    codex_root = tmp_path / ".codex"
    codex_root.mkdir()
    agents = codex_root / "AGENTS.md"
    operator_prose = "# Operator notes\n\nKeep my own instructions.\n"
    agents.write_text(operator_prose, encoding="utf-8")
    monkeypatch.setattr(
        type(CodexAdapter()), "output_path", property(lambda self: agents)
    )
    adapter = CodexAdapter()

    adapter.install({})
    installed = agents.read_text(encoding="utf-8")
    assert "BEGIN APOTHEM MANAGED BLOCK" in installed
    assert "Keep my own instructions." in installed

    adapter.uninstall()

    remainder = agents.read_text(encoding="utf-8")
    # Operator prose survives byte-for-byte; the managed block is gone.
    assert remainder == operator_prose
    assert "APOTHEM MANAGED BLOCK" not in remainder
    # No whole-file .bak sibling in the operator directory.
    assert _no_sibling_bak(codex_root)


def test_codex_apothem_only_anchor_is_deleted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    codex_root = tmp_path / ".codex"
    codex_root.mkdir()
    agents = codex_root / "AGENTS.md"  # no pre-existing operator prose
    monkeypatch.setattr(
        type(CodexAdapter()), "output_path", property(lambda self: agents)
    )
    adapter = CodexAdapter()

    adapter.install({})
    assert agents.is_file()

    adapter.uninstall()

    # An Apothem-only anchor collapses to empty and is deleted, not stubbed.
    assert not agents.exists()
    assert _no_sibling_bak(codex_root)


# --- operator-owned JSON: claude_code settings.json ------------------------


def test_claude_settings_keeps_operator_key_and_permission(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    claude_root = tmp_path / ".claude"
    claude_root.mkdir()
    settings = claude_root / "settings.json"
    monkeypatch.setattr(
        type(ClaudeCodeAdapter()), "output_path", property(lambda self: settings)
    )
    adapter = ClaudeCodeAdapter()

    adapter.install({})
    installed = json.loads(settings.read_text(encoding="utf-8"))
    assert "hooks" in installed
    assert "Bash(sudo:*)" in installed["permissions"]["deny"]

    # Operator adds a custom top-level key and an operator-authored deny entry.
    installed["operatorCustom"] = {"mySetting": True}
    installed["permissions"]["deny"].append("Read(operator-secret/**)")
    settings.write_text(json.dumps(installed, indent=2), encoding="utf-8")

    adapter.uninstall()

    assert settings.is_file()
    remaining = json.loads(settings.read_text(encoding="utf-8"))
    # Operator key and operator-added permission survive.
    assert remaining["operatorCustom"] == {"mySetting": True}
    assert remaining["permissions"]["deny"] == ["Read(operator-secret/**)"]
    # Apothem's keys and hook handlers are gone.
    assert "hooks" not in remaining
    assert "allow" not in remaining.get("permissions", {})
    assert "Bash(sudo:*)" not in remaining["permissions"].get("deny", [])
    # No whole-file .bak sibling in the operator directory.
    assert _no_sibling_bak(claude_root)


def test_claude_settings_apothem_only_is_deleted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    claude_root = tmp_path / ".claude"
    claude_root.mkdir()
    settings = claude_root / "settings.json"
    monkeypatch.setattr(
        type(ClaudeCodeAdapter()), "output_path", property(lambda self: settings)
    )
    adapter = ClaudeCodeAdapter()

    adapter.install({})  # Apothem-only settings.json
    assert settings.is_file()

    adapter.uninstall()

    # Nothing operator-authored remains, so the file is deleted.
    assert not settings.exists()
    assert _no_sibling_bak(claude_root)


def test_claude_settings_operator_added_list_item_survives(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    claude_root = tmp_path / ".claude"
    claude_root.mkdir()
    settings = claude_root / "settings.json"
    monkeypatch.setattr(
        type(ClaudeCodeAdapter()), "output_path", property(lambda self: settings)
    )
    adapter = ClaudeCodeAdapter()

    adapter.install({})
    installed = json.loads(settings.read_text(encoding="utf-8"))
    # The operator appends their own entry to an Apothem-managed allow list.
    installed["permissions"]["allow"].append("OperatorOnly")
    settings.write_text(json.dumps(installed, indent=2), encoding="utf-8")

    adapter.uninstall()

    remaining = json.loads(settings.read_text(encoding="utf-8"))
    # The Apothem-contributed list items are dropped; the operator-added item
    # survives (documented list-merge inverse: keep operator-added entries).
    assert remaining["permissions"]["allow"] == ["OperatorOnly"]
    assert "hooks" not in remaining
    assert _no_sibling_bak(claude_root)


def test_claude_settings_operator_scalar_override_is_kept(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    claude_root = tmp_path / ".claude"
    claude_root.mkdir()
    settings = claude_root / "settings.json"
    monkeypatch.setattr(
        type(ClaudeCodeAdapter()), "output_path", property(lambda self: settings)
    )
    adapter = ClaudeCodeAdapter()

    adapter.install({})
    installed = json.loads(settings.read_text(encoding="utf-8"))
    # Operator adds a scalar key alongside Apothem's permissions/hooks.
    installed["model"] = "operator-choice"
    settings.write_text(json.dumps(installed, indent=2), encoding="utf-8")

    adapter.uninstall()

    remaining = json.loads(settings.read_text(encoding="utf-8"))
    # The operator's scalar key is preserved; Apothem's keys are gone.
    assert remaining["model"] == "operator-choice"
    assert "hooks" not in remaining
    assert "permissions" not in remaining
    assert _no_sibling_bak(claude_root)


# --- operator-owned YAML: hermes config.yaml -------------------------------


def test_hermes_config_keeps_operator_keys_and_removes_apothem(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    hermes_root = tmp_path / ".hermes"
    hermes_root.mkdir()
    config = hermes_root / "config.yaml"
    monkeypatch.setattr(
        type(HermesAdapter()), "output_path", property(lambda self: config)
    )
    adapter = HermesAdapter()

    # Install with an MCP server so Apothem writes the mcp_servers block.
    adapter.install({"mcp_servers": {"demo": {"command": "demo-bin"}}})
    doc = yaml.safe_load(config.read_text(encoding="utf-8")) or {}
    assert "demo" in doc["mcp_servers"]

    # Operator adds channels/auth keys outside Apothem's namespace.
    doc["channels"] = {"slack": "xoxb-token"}
    doc["auth"] = {"token": "operator-secret"}
    config.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")

    adapter.uninstall()

    assert config.is_file()
    remaining = yaml.safe_load(config.read_text(encoding="utf-8"))
    # Operator channels/auth survive; Apothem's MCP server entry is gone.
    assert remaining["channels"] == {"slack": "xoxb-token"}
    assert remaining["auth"] == {"token": "operator-secret"}
    assert "mcp_servers" not in remaining
    # No whole-file .bak sibling in the operator directory.
    assert _no_sibling_bak(hermes_root)


def test_hermes_apothem_only_config_is_deleted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    hermes_root = tmp_path / ".hermes"
    hermes_root.mkdir()
    config = hermes_root / "config.yaml"
    monkeypatch.setattr(
        type(HermesAdapter()), "output_path", property(lambda self: config)
    )
    adapter = HermesAdapter()

    adapter.install({"mcp_servers": {"demo": {"command": "demo-bin"}}})
    assert config.is_file()

    adapter.uninstall()

    # An Apothem-only config (no operator keys) is deleted.
    assert not config.exists()
    assert _no_sibling_bak(hermes_root)


# --- backup-before-mutation is preserved under the Apothem backup root ------


def test_surgical_uninstall_backs_target_up_under_backup_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    claude_root = tmp_path / ".claude"
    claude_root.mkdir()
    settings = claude_root / "settings.json"
    monkeypatch.setattr(
        type(ClaudeCodeAdapter()), "output_path", property(lambda self: settings)
    )
    adapter = ClaudeCodeAdapter()
    adapter.install({})
    pre_uninstall = settings.read_text(encoding="utf-8")

    adapter.uninstall()

    # The pre-mutation file is recoverable from the Apothem backup root, not a
    # sibling rename next to the operator's file.
    backups = list(install_driver.BACKUP_ROOT.rglob("settings.json"))
    assert backups, "expected a backup under the Apothem backup root"
    assert backups[0].read_text(encoding="utf-8") == pre_uninstall
    assert _no_sibling_bak(claude_root)


# --- open_claw materializer config round-trip ------------------------------


def test_open_claw_keeps_operator_keys(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    openclaw_root = tmp_path / ".openclaw"
    openclaw_root.mkdir()
    config = openclaw_root / "openclaw.json"
    monkeypatch.setattr(
        type(OpenClawAdapter()), "output_path", property(lambda self: config)
    )
    adapter = OpenClawAdapter()
    adapter.install({})  # open_claw renders an empty {} config
    # Operator authors their own keys into the config file.
    config.write_text(json.dumps({"operatorKey": "value"}, indent=2), encoding="utf-8")

    adapter.uninstall()

    assert config.is_file()
    remaining = json.loads(config.read_text(encoding="utf-8"))
    assert remaining == {"operatorKey": "value"}
    assert _no_sibling_bak(openclaw_root)
