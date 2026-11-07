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
import sys
from pathlib import Path
from typing import Any

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
from apothem.lib import install_ledger
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


def _read(target: Path) -> dict[str, Any]:
    loaded = json.loads(target.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


def _installed(adapter: OpenCodeAdapter, operator: dict[str, object]) -> Path:
    """Write the operator's config, install over it, and return its path."""
    target = adapter.output_path
    target.parent.mkdir(parents=True)
    target.write_text(json.dumps(operator), encoding="utf-8")
    adapter.install(_MCP_PROFILE)
    return target


def test_relocated_entries_take_only_a_moved_server_matching_whole() -> None:
    owned = (
        OwnedEntry(("mcp",), "container"),
        OwnedEntry(("mcp", "fs"), "container"),
        OwnedEntry(("mcp", "fs", "type"), "key", "local"),
        OwnedEntry(("mcp", "fs", "command"), "container"),
        OwnedEntry(("mcp", "fs", "command"), "item", "npx"),
        OwnedEntry(("mcp", "fs", "enabled"), "key", True),
        OwnedEntry(("instructions",), "item", "x"),
    )
    owned_server = {"type": "local", "command": ["npx"]}
    converted = {**owned_server, "disabled": False}

    def relocate(mcp: dict[str, object]) -> list[tuple[object, ...]]:
        current = json.dumps({"mcp": mcp})
        moved = opencode_materializer.relocated_entries(owned, current)
        return [(entry.path, entry.kind, entry.value) for entry in moved]

    assert relocate({"servers": {"fs": converted}}) == [
        (("mcp", "servers", "fs"), "key", converted),
        (("mcp", "servers"), "container", None),
    ]
    # The other two shapes a conversion may take: as written, and with enabled dropped.
    as_moved = [
        (("mcp", "servers", "fs"), "key", None),
        (("mcp", "servers"), "container", None),
    ]
    for shape in (
        {"type": "local", "command": ["npx"]},
        {**owned_server, "enabled": True},
    ):
        moved = relocate({"servers": {"fs": shape}})
        assert [(path, kind) for path, kind, _ in moved] == [
            (path, kind) for path, kind, _ in as_moved
        ]
        assert moved[0][2] == shape
    # Still in place, so a same-name server under servers is not a conversion.
    assert relocate({"fs": {"type": "local"}, "servers": {"fs": converted}}) == []
    # Changed after the conversion: left as it is.
    assert relocate({"servers": {"fs": {**converted, "timeout": 30}}}) == []
    assert relocate({"servers": {"fs": {**converted, "disabled": True}}}) == []
    assert opencode_materializer.relocated_entries(owned, None) == ()


def test_a_converted_server_is_written_back_once_and_uninstalled(
    adapter: OpenCodeAdapter, isolated_home: Path
) -> None:
    target = _installed(adapter, {"theme": "dark"})
    _move_server_to_servers(target, "fs")

    adapter.update(_MCP_PROFILE)

    config = _read(target)
    assert "servers" not in config["mcp"]
    assert config["mcp"]["fs"] == {
        "type": "local",
        "command": ["npx", "srv"],
        "enabled": True,
        "environment": {"TOKEN": "{env:FS_TOKEN}"},
    }

    _move_server_to_servers(target, "fs")
    adapter.uninstall()

    assert _read(target) == {"theme": "dark"}


@pytest.mark.parametrize(
    "change",
    [
        pytest.param({"timeout": 30}, id="edited"),
        pytest.param({"disabled": True}, id="disabled"),
    ],
)
def test_a_converted_server_the_operator_changed_is_left_alone(
    adapter: OpenCodeAdapter, isolated_home: Path, change: dict[str, object]
) -> None:
    target = _installed(adapter, {"theme": "dark"})
    _move_server_to_servers(target, "fs")
    config = _read(target)
    config["mcp"]["servers"]["fs"].update(change)
    changed = config["mcp"]["servers"]["fs"]
    target.write_text(json.dumps(config, indent=2), encoding="utf-8")

    adapter.update(_MCP_PROFILE)
    assert _read(target)["mcp"]["servers"]["fs"] == changed

    adapter.uninstall()
    assert _read(target) == {"theme": "dark", "mcp": {"servers": {"fs": changed}}}


@pytest.mark.parametrize(
    "own",
    [
        pytest.param(
            {
                "type": "local",
                "command": ["npx", "srv"],
                "environment": {"TOKEN": "{env:FS_TOKEN}"},
                "disabled": False,
            },
            id="identical",
        ),
        pytest.param(
            {
                "type": "local",
                "command": ["npx", "other-server"],
                "disabled": False,
            },
            id="different",
        ),
    ],
)
@pytest.mark.parametrize("keep_installed", [True, False], ids=["beside", "alone"])
def test_an_operator_server_of_the_same_name_is_left_alone(
    adapter: OpenCodeAdapter,
    isolated_home: Path,
    own: dict[str, object],
    keep_installed: bool,
) -> None:
    # The different server shares type, a command item and disabled with the
    # install's, so stripping it key by key would leave a broken stub.
    target = _installed(adapter, {"theme": "dark"})
    config = _read(target)
    config["mcp"]["servers"] = {"fs": own}
    if not keep_installed:
        del config["mcp"]["fs"]
    target.write_text(json.dumps(config, indent=2), encoding="utf-8")

    if own.get("environment") and not keep_installed:
        # The documented limit: with the install's mcp.fs gone, an identical
        # server cannot be told from a converted copy, so it goes with it.
        adapter.uninstall()
        assert _read(target) == {"theme": "dark"}
        return

    adapter.update(_MCP_PROFILE)
    assert _read(target)["mcp"]["servers"] == {"fs": own}

    adapter.uninstall()
    assert _read(target) == {"theme": "dark", "mcp": {"servers": {"fs": own}}}


def test_adjust_prior_leaves_a_record_without_ownership_alone() -> None:
    owned = (OwnedEntry(("mcp", "fs"), "container"),)
    current = json.dumps({"mcp": {"servers": {"fs": {}}}})
    relocate = opencode_materializer.relocated_entries

    legacy = adjust_prior(LEGACY_OWNERSHIP, relocated=relocate, current=current)
    assert legacy is LEGACY_OWNERSHIP
    assert adjust_prior(owned) is owned
    assert adjust_prior(owned, relocated=relocate, current=current) == (
        *owned,
        *relocate(owned, current),
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
    assert "earlier Apothem install is still in" in notes[0]
    assert (tmp_path / "xdg" / "opencode" / "opencode.json").is_file()


def test_install_notes_nothing_when_the_earlier_files_are_gone(
    adapter: OpenCodeAdapter,
    isolated_home: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The operator moved the folder away: the record stays, the files do not,
    # and an uninstall there would find nothing to remove.
    adapter.install({})
    default = isolated_home / ".config" / "opencode"
    default.rename(tmp_path / "moved")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))

    assert _notes(adapter.install({})) == []
    assert install_ledger.active_install_records("opencode", root=default)


def test_install_notes_mcp_references_opencode_does_not_expand(
    adapter: OpenCodeAdapter, isolated_home: Path
) -> None:
    profile = {
        "mcp_servers": {
            "fs": {
                "transport": "stdio",
                "command": "sh",
                "args": ["-c", "srv --root ${ROOT}"],
                "env": {
                    "A": "${TOKEN:-x}",
                    "B": "${PLAIN}",
                    "C": "$HOME",
                    "D": "$${KEEP}",
                },
            },
            "api": {"transport": "http", "url": "https://api.example/v1?$filter=x"},
        }
    }

    notes = _notes(adapter.install(profile))

    assert notes == [
        "MCP server fs: OpenCode does not expand the $ reference in command, "
        "environment.A, environment.C, so the server receives that text as "
        "written. In an environment, header or URL value, a plain ${NAME} is "
        "written as {env:NAME}, which OpenCode substitutes.",
        "MCP server fs: the $${...} in environment.D is copied unchanged.",
    ]


def test_install_notes_never_print_a_value(
    adapter: OpenCodeAdapter, isolated_home: Path
) -> None:
    profile = {
        "mcp_servers": {
            "api": {
                "transport": "http",
                "url": "https://api.example/v1",
                "headers": {"Authorization": "Bearer abc$Xyz1example"},
            },
            "fs": {
                "transport": "stdio",
                "command": "npx",
                "env": {"TOKEN": "pa$$word-example"},
            },
        }
    }

    notes = _notes(adapter.install(profile))

    assert len(notes) == 2
    assert "headers.Authorization" in notes[0]
    assert "environment.TOKEN" in notes[1]
    for fragment in ("abc", "Xyz1", "example", "word"):
        assert not any(fragment in note for note in notes), fragment


def test_install_notes_an_env_value_opencode_1_cannot_insert(
    adapter: OpenCodeAdapter, isolated_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # OpenCode inserts an {env:NAME} value into the config text unescaped.
    monkeypatch.setenv("FS_TOKEN", "C:\\keys\\token")
    notes = _notes(adapter.install(_MCP_PROFILE))
    assert len(notes) == 1
    assert notes[0].startswith("MCP server fs: FS_TOKEN holds a backslash")

    assert (
        "Restate that server under harnesses.opencode.mcp_servers.fs (an "
        "override replaces the whole server) with the value as {file:path}"
    ) in notes[0]

    # U+007F is legal in a JSON string, so it draws no note.
    for value in ("plain-value", "del\x7fvalue"):
        monkeypatch.setenv("FS_TOKEN", value)
        assert _notes(adapter.update(_MCP_PROFILE)) == []


@pytest.mark.skipif(sys.platform != "win32", reason="needs case-insensitive paths")
def test_a_change_of_case_in_xdg_config_home_names_the_same_install(
    adapter: OpenCodeAdapter, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    folder = tmp_path / "Config"
    folder.mkdir()
    monkeypatch.setenv("XDG_CONFIG_HOME", str(folder))
    adapter.install({})
    monkeypatch.setenv("XDG_CONFIG_HOME", str(folder).lower())

    adapter.update({})

    entries = _read(adapter.output_path)["instructions"]
    assert len(entries) == len(set(entries)) == len(instruction_entries())


def _link_folder(link: Path, target: Path) -> None:
    """Make *link* a symbolic link, or on Windows a junction, to *target*."""
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError:
        if sys.platform != "win32":
            raise
        import _winapi

        _winapi.CreateJunction(str(target), str(link))


def test_xdg_config_home_naming_the_linked_default_keeps_the_install(
    adapter: OpenCodeAdapter, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # An install made with XDG unset under a home folder reached through a link
    # (a symlink, or a junction on Windows), as when the home folder lives on a
    # linked volume, then an update with XDG_CONFIG_HOME naming the same
    # ~/.config. A link at ~/.config itself is covered in
    # test_linked_config_folder.py.
    real_home = tmp_path / "real-home"
    real_home.mkdir()
    home = tmp_path / "home-link"
    _link_folder(home, real_home)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    adapter.install({})
    root = home / ".config" / "opencode"
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / ".config"))

    adapter.update({})

    assert adapter.output_path == root / "opencode.json"
    entries = _read(root / "opencode.json")["instructions"]
    assert len(entries) == len(set(entries)) == len(instruction_entries())
    assert install_ledger.active_install_records("opencode", root=root)
    resolved = install_driver._normalized(root)
    if str(resolved) != str(root):
        assert not install_ledger.active_install_records("opencode", root=resolved)


def test_the_example_config_is_what_the_install_writes() -> None:
    # examples/harnesses/opencode/native-install/opencode.json shows a render
    # of two servers; it must stay what the materializer writes for them.
    example_path = (
        Path(__file__).resolve().parents[2]
        / "examples/harnesses/opencode/native-install/opencode.json"
    )
    example = json.loads(example_path.read_text(encoding="utf-8"))
    profile = {
        "mcp_servers": {
            "filesystem": {
                "transport": "stdio",
                "command": "npx",
                "args": [
                    "-y",
                    "@modelcontextprotocol/server-filesystem",
                    "/path/to/workspace",
                ],
            },
            "github": {
                "transport": "streamable-http",
                "url": "https://api.githubcopilot.com/mcp/",
                "headers": {"Authorization": "Bearer ${GITHUB_MCP_TOKEN}"},
            },
        }
    }

    rendered = json.loads(opencode_materializer.materialize_native_config(profile))

    assert example == rendered
