# SPDX-License-Identifier: MIT

"""Operator entries in shared settings files survive install and uninstall.

Install merges Apothem's keys into settings files the operator also edits:
Claude Code's ``settings.json`` (permission lists), Qwen Code's
``settings.json`` and OpenCode's ``opencode.json`` (MCP server maps), and the
Hermes ``config.yaml``. The merge records, in the install ledger, exactly which
keys and list items Apothem added; uninstall removes only those. So an operator
``permissions.deny`` rule, an operator MCP server, or an operator key that
happens to equal one of Apothem's own values is never dropped.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pytest
import yaml

from apothem.harnesses import HarnessAdapter
from apothem.lib.harness_registry import get_harness_entry, load_adapter_class

_MCP_PROFILE: dict[str, Any] = {
    "mcp_servers": {"fs": {"transport": "stdio", "command": "npx", "args": ["fs"]}}
}


def _adapter(
    harness_id: str, home: Path, monkeypatch: pytest.MonkeyPatch
) -> HarnessAdapter:
    monkeypatch.setenv("HOME", str(home))
    return load_adapter_class(get_harness_entry(harness_id))()


def _read_json(path: Path) -> dict[str, Any]:
    return cast("dict[str, Any]", json.loads(path.read_text(encoding="utf-8")))


def test_claude_permissions_survive_install_update_uninstall(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    settings = home / ".claude" / "settings.json"
    settings.parent.mkdir(parents=True)
    seed = {
        "model": "operator-choice",
        "permissions": {
            # "Read" is also one of Apothem's own allow entries.
            "allow": ["Bash(npm test:*)", "Read"],
            "deny": ["Bash(curl:*)", "WebFetch", "Read(./secrets/**)"],
        },
    }
    settings.write_text(json.dumps(seed, indent=2) + "\n", encoding="utf-8")
    adapter = _adapter("claude-code", home, monkeypatch)

    adapter.install({})
    installed = _read_json(settings)
    for rule in seed["permissions"]["allow"]:
        assert rule in installed["permissions"]["allow"]
    for rule in seed["permissions"]["deny"]:
        assert rule in installed["permissions"]["deny"]
    assert "Bash(sudo:*)" in installed["permissions"]["deny"]  # Apothem's floor

    adapter.update({})
    updated = _read_json(settings)
    assert updated == installed

    adapter.uninstall()
    assert _read_json(settings) == seed


def test_qwen_operator_mcp_server_survives_uninstall(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    settings = home / ".qwen" / "settings.json"
    settings.parent.mkdir(parents=True)
    seed = {"mcpServers": {"mine": {"command": "my-server", "args": ["--x"]}}}
    settings.write_text(json.dumps(seed, indent=2) + "\n", encoding="utf-8")
    adapter = _adapter("qwen-code", home, monkeypatch)

    adapter.install(_MCP_PROFILE)
    assert set(_read_json(settings)["mcpServers"]) == {"mine", "fs"}

    adapter.uninstall()
    assert _read_json(settings) == seed


def test_opencode_operator_mcp_and_schema_survive_uninstall(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    config = home / ".config" / "opencode" / "opencode.json"
    config.parent.mkdir(parents=True)
    seed = {
        # Equal to the value Apothem writes, but the operator's own.
        "$schema": "https://opencode.ai/config.json",
        "mcp": {"mine": {"type": "local", "command": ["my-server"]}},
    }
    config.write_text(json.dumps(seed, indent=2) + "\n", encoding="utf-8")
    adapter = _adapter("opencode", home, monkeypatch)

    adapter.install(_MCP_PROFILE)
    installed = _read_json(config)
    assert set(installed["mcp"]) == {"mine", "fs"}
    assert installed["instructions"]

    adapter.uninstall()
    assert _read_json(config) == seed


def test_hermes_operator_auxiliary_block_survives_uninstall(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    config = home / ".hermes" / "config.yaml"
    config.parent.mkdir(parents=True)
    seed = {"auxiliary": {"compression": {"provider": "openrouter"}}}
    config.write_text(yaml.safe_dump(seed, sort_keys=False), encoding="utf-8")
    adapter = _adapter("hermes", home, monkeypatch)

    adapter.install(_MCP_PROFILE)
    adapter.uninstall()

    assert yaml.safe_load(config.read_text(encoding="utf-8")) == seed


def test_update_drops_an_mcp_server_removed_from_the_profile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    settings = home / ".qwen" / "settings.json"
    adapter = _adapter("qwen-code", home, monkeypatch)
    two = {
        "mcp_servers": {
            "fs": {"transport": "stdio", "command": "npx"},
            "gone": {"transport": "stdio", "command": "old"},
        }
    }

    adapter.install(two)
    assert set(_read_json(settings)["mcpServers"]) == {"fs", "gone"}

    adapter.update(_MCP_PROFILE)
    assert set(_read_json(settings)["mcpServers"]) == {"fs"}
    assert _read_json(settings)["mcpServers"]["fs"]["args"] == ["fs"]
