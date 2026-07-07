# SPDX-License-Identifier: MIT

"""Unit tests for the plugin source-tree assembler and manifest generator."""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

from apothem.lib.plugin_tree import (
    PluginAssemblyError,
    assemble_plugin_tree,
    build_plugin_hooks_json,
    build_plugin_manifest,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SRC_ROOT = _REPO_ROOT / "src" / "apothem"
_SCHEMA_PATH = _SRC_ROOT / "schemas" / "plugin.schema.json"


def _schema() -> dict[str, object]:
    return json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))


def test_build_manifest_validates_against_schema() -> None:
    manifest = build_plugin_manifest(_SRC_ROOT)
    jsonschema.validate(instance=manifest, schema=_schema())


def test_build_manifest_name_is_apothem() -> None:
    manifest = build_plugin_manifest(_SRC_ROOT)
    assert manifest["name"] == "apothem"


def test_build_manifest_arrays_non_empty_and_sorted() -> None:
    manifest = build_plugin_manifest(_SRC_ROOT)
    for key in ("commands", "agents", "skills"):
        members = manifest[key]
        assert isinstance(members, list)
        assert members, f"{key} array must be non-empty"
        assert members == sorted(members), f"{key} array must be sorted"


def test_build_manifest_component_paths_are_plugin_root_relative() -> None:
    manifest = build_plugin_manifest(_SRC_ROOT)
    for key in ("commands", "agents", "skills"):
        members = manifest[key]
        assert isinstance(members, list)
        for path in members:
            assert isinstance(path, str)
            assert path.startswith("./"), f"{key} path {path!r} must start with ./"
    assert manifest["skills"] == ["./skills/"]


def test_build_manifest_excludes_documentation_files() -> None:
    manifest = build_plugin_manifest(_SRC_ROOT)
    for key in ("commands", "agents"):
        members = manifest[key]
        assert isinstance(members, list)
        for path in members:
            assert not path.endswith("README.md"), f"doc file leaked into {key}"
            assert not path.endswith("AGENTS.md"), f"doc file leaked into {key}"


def test_build_manifest_repo_layout_prefix() -> None:
    manifest = build_plugin_manifest(_SRC_ROOT, catalog_prefix="./src/apothem/")
    commands = manifest["commands"]
    assert isinstance(commands, list)
    assert all(path.startswith("./src/apothem/commands/") for path in commands)
    assert manifest["skills"] == ["./src/apothem/skills/"]


def test_build_manifest_addresses_default_command_dir() -> None:
    """The repo-root manifest lists ./commands/ to suppress the Claude Code
    "default commands/ folder is ignored" note (the bare ./commands/ at the
    plugin root is the Gemini / Qwen extensions' TOML command folder)."""
    manifest = build_plugin_manifest(
        _SRC_ROOT,
        catalog_prefix="./src/apothem/",
        address_default_command_dir=True,
    )
    commands = manifest["commands"]
    assert isinstance(commands, list)
    assert commands[0] == "./commands/", "default ./commands/ must be addressed first"
    assert all(path.startswith("./src/apothem/commands/") for path in commands[1:]), (
        "every other command path keeps the nested prefix"
    )


def test_build_manifest_version_override() -> None:
    manifest = build_plugin_manifest(_SRC_ROOT, version="9.8.7")
    assert manifest["version"] == "9.8.7"


def test_build_manifest_missing_catalog_dir_raises(tmp_path: Path) -> None:
    with pytest.raises(PluginAssemblyError, match="skills"):
        build_plugin_manifest(tmp_path)


def test_assemble_produces_layout_contract(tmp_path: Path) -> None:
    dest = tmp_path / "plugin_root"
    result = assemble_plugin_tree(_SRC_ROOT, dest)
    assert result == dest

    manifest_path = dest / ".claude-plugin" / "plugin.json"
    assert manifest_path.is_file()
    jsonschema.validate(
        instance=json.loads(manifest_path.read_text(encoding="utf-8")),
        schema=_schema(),
    )

    assert (dest / "lib" / "apothem" / "__init__.py").is_file()
    assert (dest / "lib" / "apothem_lib.py").is_file()
    assert (dest / "lib" / "apothem" / "_vendor").is_dir()

    for name in ("skills", "agents", "commands", "rules", "hooks"):
        assert (dest / name).is_dir(), f"catalog dir {name} missing"


def test_assemble_shim_reexports_public_api(tmp_path: Path) -> None:
    dest = tmp_path / "plugin_root"
    assemble_plugin_tree(_SRC_ROOT, dest)
    shim = (dest / "lib" / "apothem_lib.py").read_text(encoding="utf-8")
    assert "from apothem.lib import profile, propagation, reporter" in shim
    assert "from apothem import harnesses as adapters" in shim


def test_assemble_is_idempotent(tmp_path: Path) -> None:
    dest = tmp_path / "plugin_root"
    assemble_plugin_tree(_SRC_ROOT, dest)
    first = json.loads(
        (dest / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
    )
    # Second run must not raise and must yield a stable manifest.
    assemble_plugin_tree(_SRC_ROOT, dest)
    second = json.loads(
        (dest / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
    )
    assert first == second
    assert (dest / "lib" / "apothem" / "__init__.py").is_file()


def test_assemble_missing_source_raises(tmp_path: Path) -> None:
    with pytest.raises(PluginAssemblyError, match="source package directory"):
        assemble_plugin_tree(tmp_path / "nonexistent", tmp_path / "dest")


def test_manifest_carries_hooks_field_assembled() -> None:
    """The assembled-tree manifest points hooks at the lib/apothem engine copy."""
    manifest = build_plugin_manifest(_SRC_ROOT)
    assert manifest["hooks"] == "./lib/apothem/hooks/hooks.json"


def test_manifest_carries_hooks_field_repo_layout() -> None:
    """The repo-root manifest points hooks at the in-tree src/apothem engine."""
    manifest = build_plugin_manifest(_SRC_ROOT, catalog_prefix="./src/apothem/")
    assert manifest["hooks"] == "./src/apothem/hooks/hooks.json"


def test_manifest_hooks_field_matches_schema_pattern() -> None:
    """The hooks field validates against the schema's leading-./ pattern."""
    manifest = build_plugin_manifest(_SRC_ROOT)
    jsonschema.validate(instance=manifest, schema=_schema())
    hooks = manifest["hooks"]
    assert isinstance(hooks, str)
    assert hooks.startswith("./")


def test_hooks_json_mirrors_engine_event_set() -> None:
    """The generated hooks.json carries the dispatch-routable event set."""
    hooks_json = build_plugin_hooks_json("lib/apothem")
    events = hooks_json["hooks"]
    assert isinstance(events, dict)
    assert set(events) == {
        "SessionStart",
        "PreToolUse",
        "PostToolUse",
        "PreCompact",
        "PostCompact",
        "Stop",
    }


def test_hooks_json_pretooluse_matchers() -> None:
    """PreToolUse carries the five engine matchers in stable order."""
    hooks_json = build_plugin_hooks_json("lib/apothem")
    events = hooks_json["hooks"]
    assert isinstance(events, dict)
    pretooluse = events["PreToolUse"]
    assert isinstance(pretooluse, list)
    matchers = [group["matcher"] for group in pretooluse]
    assert matchers == ["Write", "Edit", "NotebookEdit", "Bash", "AskUserQuestion"]


def test_hooks_json_every_command_pairs_bash_and_powershell() -> None:
    """Every matcher group emits matched bash + powershell command pairs."""
    hooks_json = build_plugin_hooks_json("lib/apothem")
    events = hooks_json["hooks"]
    assert isinstance(events, dict)
    for groups in events.values():
        assert isinstance(groups, list)
        for group in groups:
            commands = group["hooks"]
            assert isinstance(commands, list)
            shells = [cmd["shell"] for cmd in commands]
            # Pairs interleave bash then powershell — equal counts of each.
            assert shells.count("bash") == shells.count("powershell")
            assert shells.count("bash") >= 1


def test_hooks_json_commands_resolve_under_plugin_root() -> None:
    """Every command references the bootstrap stub under ${CLAUDE_PLUGIN_ROOT}."""
    hooks_json = build_plugin_hooks_json("lib/apothem")
    events = hooks_json["hooks"]
    assert isinstance(events, dict)
    for groups in events.values():
        assert isinstance(groups, list)
        for group in groups:
            for cmd in group["hooks"]:
                command = cmd["command"]
                assert isinstance(command, str)
                assert "${CLAUDE_PLUGIN_ROOT}/lib/apothem/hooks/lib/bootstrap." in (
                    command
                )


def test_hooks_json_no_conformity_gate_entry() -> None:
    """The bootstrap-only hooks.json omits the gate.py --hook entries."""
    hooks_json = build_plugin_hooks_json("lib/apothem")
    serialized = json.dumps(hooks_json)
    assert "gate.py" not in serialized
    assert "conformity" not in serialized


def test_hooks_json_timeouts_mirror_engine() -> None:
    """Per-event timeouts mirror the engine settings.json block."""
    hooks_json = build_plugin_hooks_json("lib/apothem")
    events = hooks_json["hooks"]
    assert isinstance(events, dict)

    def _timeout(event: str) -> set[int]:
        groups = events[event]
        assert isinstance(groups, list)
        return {cmd["timeout"] for group in groups for cmd in group["hooks"]}

    assert _timeout("SessionStart") == {30}
    assert _timeout("PreToolUse") == {10}
    assert _timeout("PostToolUse") == {10}
    assert _timeout("PreCompact") == {30}
    assert _timeout("PostCompact") == {30}
    assert _timeout("Stop") == {60}


def test_assemble_writes_hooks_json(tmp_path: Path) -> None:
    """The assembled tree materializes hooks.json beside the engine copy."""
    dest = tmp_path / "plugin_root"
    assemble_plugin_tree(_SRC_ROOT, dest)
    hooks_json_path = dest / "lib" / "apothem" / "hooks" / "hooks.json"
    assert hooks_json_path.is_file()
    loaded = json.loads(hooks_json_path.read_text(encoding="utf-8"))
    assert loaded == build_plugin_hooks_json("lib/apothem")


def test_committed_repo_hooks_json_matches_generator() -> None:
    """The committed src/apothem/hooks/hooks.json must not drift."""
    committed_path = _SRC_ROOT / "hooks" / "hooks.json"
    assert committed_path.is_file(), "repo-root hooks.json must exist"
    committed = json.loads(committed_path.read_text(encoding="utf-8"))
    assert committed == build_plugin_hooks_json("src/apothem")


def test_committed_repo_manifest_validates() -> None:
    committed = _REPO_ROOT / ".claude-plugin" / "plugin.json"
    assert committed.is_file(), "repo-root .claude-plugin/plugin.json must exist"
    jsonschema.validate(
        instance=json.loads(committed.read_text(encoding="utf-8")),
        schema=_schema(),
    )


def test_committed_repo_manifest_matches_generator() -> None:
    """The committed manifest must never drift from the generator's output."""
    committed = json.loads(
        (_REPO_ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
    )
    generated = build_plugin_manifest(
        _SRC_ROOT,
        catalog_prefix="./src/apothem/",
        address_default_command_dir=True,
    )
    assert committed == generated
