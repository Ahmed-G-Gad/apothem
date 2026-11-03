# SPDX-License-Identifier: MIT

"""The OpenCode install under both release lines, OpenCode 1 and OpenCode 2.

OpenCode 1 (v1.19.5) and OpenCode 2 (v2.2.5) read the same configuration
folder. These tests pin what the install writes so that both lines load it as
intended: helper permissions, the configuration folder, MCP servers an
operator converts to OpenCode 2's shape, and the install-time notes.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
import yaml

import apothem.harnesses.opencode.materializer as opencode_materializer
from apothem.harnesses._shared import install_driver
from apothem.harnesses._shared.install_driver_ownership import (
    LEGACY_OWNERSHIP,
    adjust_prior,
)
from apothem.harnesses.opencode import OpenCodeAdapter
from apothem.harnesses.opencode.materializer import (
    instruction_entries,
    profile_document_instruction,
)
from apothem.lib.install_ledger import OwnedEntry

_MCP_PROFILE: dict[str, object] = {
    "mcp_servers": {
        "fs": {
            "transport": "stdio",
            "command": "npx",
            "args": ["srv"],
            "env": {"TOKEN": "${FS_TOKEN}"},
        }
    }
}


@pytest.fixture
def adapter() -> OpenCodeAdapter:
    return OpenCodeAdapter()


@pytest.fixture
def isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    return home


def _frontmatter(text: str) -> dict[str, object]:
    loaded = yaml.safe_load(text.split("\n---\n", 1)[0].removeprefix("---\n"))
    assert isinstance(loaded, dict)
    return loaded


def _notes(run: install_driver.MaterializationRun) -> list[str]:
    return [
        result.message
        for result in run.results
        if result.outcome == "warning" and result.operation == "opencode_config"
    ]


def _move_server_to_servers(target: Path, name: str) -> None:
    """Convert ``mcp.<name>`` to OpenCode 2's ``mcp.servers.<name>`` shape.

    The fields are the ones OpenCode 2 converts the entry to in memory:
    ``disabled`` for ``enabled``, the other keys kept (v2.2.5
    packages/core/src/v1/config/migrate.ts:81-108). OpenCode 2 never rewrites
    the file; an operator converts it, by hand or by asking OpenCode to.
    """
    config = json.loads(target.read_text(encoding="utf-8"))
    entry = config["mcp"].pop(name)
    entry["disabled"] = not entry.pop("enabled")
    config["mcp"].setdefault("servers", {})[name] = entry
    target.write_text(json.dumps(config, indent=2), encoding="utf-8")


def test_helpers_carry_only_deny_rules() -> None:
    # Pinned to OpenCode 1.19.5 and 2.2.5; re-check when either changes its
    # permission defaults. Both allow every tool by default and ask before
    # reading .env and .env.* files, a helper's rules follow the defaults and
    # the operator's own config, and the last matching rule wins (v1
    # packages/opencode/src/agent/agent.ts:119-135,293 and
    # packages/opencode/src/permission/index.ts:28-32; v2
    # packages/schema/src/agent.ts:46-51,
    # packages/core/src/config/plugin/agent.ts:121 and
    # packages/core/src/permission.ts:86-90). An allow rule could only switch
    # the .env question off or override a stricter operator rule.
    sources = sorted(
        path
        for path in install_driver.resolve_source("agents/").glob("*.md")
        if path.name != "README.md"
    )
    rendered = {
        path.stem: _frontmatter(install_driver._opencode_agent_text(path))
        for path in sources
    }
    assert len(rendered) == 14
    for name, frontmatter in rendered.items():
        rules = frontmatter.get("permission", {})
        assert isinstance(rules, dict)
        assert set(rules.values()) <= {"deny"}, name
    assert rendered["codebase-explorer"]["permission"] == {
        "edit": "deny",
        "todowrite": "deny",
    }
    assert "permission" not in rendered["mcp-builder"]


def test_relocated_entries_follow_the_mcp_servers_path() -> None:
    owned = (
        OwnedEntry(("mcp",), "container"),
        OwnedEntry(("mcp", "fs"), "container"),
        OwnedEntry(("mcp", "fs", "enabled"), "key", True),
        OwnedEntry(("mcp", "timeout"), "key", 5),
        OwnedEntry(("instructions",), "item", "x"),
    )

    moved = opencode_materializer.relocated_entries(owned)

    assert [(entry.path, entry.kind, entry.value) for entry in moved] == [
        (("mcp", "servers", "fs"), "container", None),
        (("mcp", "servers", "fs", "enabled"), "key", True),
        (("mcp", "servers", "fs", "disabled"), "key", False),
        (("mcp", "servers"), "container", None),
    ]
    assert opencode_materializer.relocated_entries(owned[4:]) == ()


def test_a_server_opencode_2_moved_is_rewritten_once_and_uninstalled(
    adapter: OpenCodeAdapter, isolated_home: Path
) -> None:
    target = adapter.output_path
    target.parent.mkdir(parents=True)
    target.write_text(json.dumps({"theme": "dark"}), encoding="utf-8")
    adapter.install(_MCP_PROFILE)
    _move_server_to_servers(target, "fs")

    adapter.update(_MCP_PROFILE)

    config = json.loads(target.read_text(encoding="utf-8"))
    assert "servers" not in config["mcp"]
    assert config["mcp"]["fs"] == {
        "type": "local",
        "command": ["npx", "srv"],
        "enabled": True,
        "environment": {"TOKEN": "{env:FS_TOKEN}"},
    }

    _move_server_to_servers(target, "fs")
    adapter.uninstall()

    assert json.loads(target.read_text(encoding="utf-8")) == {"theme": "dark"}


def test_an_edited_moved_server_keeps_the_operator_values(
    adapter: OpenCodeAdapter, isolated_home: Path
) -> None:
    target = adapter.output_path
    target.parent.mkdir(parents=True)
    target.write_text(json.dumps({"theme": "dark"}), encoding="utf-8")
    adapter.install(_MCP_PROFILE)
    _move_server_to_servers(target, "fs")
    config = json.loads(target.read_text(encoding="utf-8"))
    config["mcp"]["servers"]["fs"]["timeout"] = 30
    target.write_text(json.dumps(config, indent=2), encoding="utf-8")

    adapter.uninstall()

    remaining = json.loads(target.read_text(encoding="utf-8"))
    assert remaining["mcp"]["servers"]["fs"] == {"timeout": 30}


def test_an_identical_operator_server_under_servers_is_taken_for_apothems(
    adapter: OpenCodeAdapter, isolated_home: Path
) -> None:
    # Documented limit: a server of the operator's own under mcp.servers with
    # the name and values of one the install wrote cannot be told apart from
    # a converted copy, so uninstall removes it with the original. The
    # operator's file is backed up first.
    target = adapter.output_path
    target.parent.mkdir(parents=True)
    target.write_text(json.dumps({"theme": "dark"}), encoding="utf-8")
    adapter.install(_MCP_PROFILE)
    config = json.loads(target.read_text(encoding="utf-8"))
    copy = {**config["mcp"]["fs"], "disabled": False}
    del copy["enabled"]
    config["mcp"]["servers"] = {"fs": copy}
    target.write_text(json.dumps(config, indent=2), encoding="utf-8")

    adapter.uninstall()

    assert json.loads(target.read_text(encoding="utf-8")) == {"theme": "dark"}


def test_adjust_prior_leaves_a_record_without_ownership_alone() -> None:
    owned = (OwnedEntry(("mcp", "fs"), "container"),)

    def relocate(entries: tuple[OwnedEntry, ...]) -> tuple[OwnedEntry, ...]:
        return opencode_materializer.relocated_entries(entries)

    assert adjust_prior(LEGACY_OWNERSHIP, relocated=relocate) is LEGACY_OWNERSHIP
    assert adjust_prior(owned) is owned
    assert adjust_prior(owned, relocated=relocate) == (
        *owned,
        *opencode_materializer.relocated_entries(owned),
    )


def test_config_root_follows_an_absolute_xdg_config_home(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))

    assert opencode_materializer.config_root() == tmp_path / "xdg" / "opencode"
    assert OpenCodeAdapter().output_path == (
        tmp_path / "xdg" / "opencode" / "opencode.json"
    )


@pytest.mark.parametrize("value", ["relative/config", "anchor"])
def test_config_root_ignores_an_unusable_xdg_config_home(
    value: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    configured = str(Path(Path.home().anchor)) if value == "anchor" else value
    monkeypatch.setenv("XDG_CONFIG_HOME", configured)

    assert opencode_materializer.config_root() == Path.home() / ".config" / "opencode"


def test_instructions_follow_the_config_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    document = install_driver.PROFILE_DOCUMENT_RELATIVE
    monkeypatch.setenv("XDG_CONFIG_HOME", str(Path.home() / "cfg"))
    assert profile_document_instruction() == f"~/cfg/opencode/{document}"

    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    outside = Path(os.path.normpath(tmp_path / "xdg" / "opencode")).as_posix()
    assert profile_document_instruction() == f"{outside}/{document}"
    assert all(entry.startswith(outside) for entry in instruction_entries())


def test_install_notes_an_opencode_config_dir_elsewhere(
    adapter: OpenCodeAdapter,
    isolated_home: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENCODE_CONFIG_DIR", str(tmp_path / "elsewhere"))
    notes = _notes(adapter.install({}))
    assert len(notes) == 1
    assert "OpenCode 2 does not load this install" in notes[0]

    monkeypatch.setenv("OPENCODE_CONFIG_DIR", str(adapter.output_path.parent))
    assert _notes(adapter.update({})) == []

    # OpenCode does not expand "~", so this names a folder it reads elsewhere.
    monkeypatch.setenv("OPENCODE_CONFIG_DIR", "~/.config/opencode")
    assert len(_notes(adapter.update({}))) == 1


def test_install_notes_an_unusable_xdg_config_home(
    adapter: OpenCodeAdapter, isolated_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", "relative/config")

    notes = _notes(adapter.install({}))

    assert len(notes) == 1
    assert notes[0].startswith("XDG_CONFIG_HOME is set to relative/config")
    expected = isolated_home / ".config" / "opencode" / "opencode.json"
    assert adapter.output_path == expected


def test_install_notes_an_earlier_install_in_the_default_folder(
    adapter: OpenCodeAdapter,
    isolated_home: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter.install({})
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))

    notes = _notes(adapter.install({}))

    assert len(notes) == 1
    assert "earlier Apothem install is still recorded" in notes[0]
    assert (tmp_path / "xdg" / "opencode" / "opencode.json").is_file()


def test_install_notes_mcp_references_opencode_does_not_expand(
    adapter: OpenCodeAdapter, isolated_home: Path
) -> None:
    profile = {
        "mcp_servers": {
            "fs": {
                "transport": "stdio",
                "command": "npx",
                "env": {"A": "${TOKEN:-x}", "B": "${PLAIN}"},
            }
        }
    }

    notes = _notes(adapter.install(profile))

    assert len(notes) == 1
    assert "does not expand ${TOKEN:-x}, so" in notes[0]
    assert "${PLAIN}," not in notes[0]
