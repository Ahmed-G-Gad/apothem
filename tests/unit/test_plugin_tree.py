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


def test_build_manifest_carries_listing_fields() -> None:
    """displayName plus the https listing links Anthropic's directory reads."""
    manifest = build_plugin_manifest(_SRC_ROOT)
    assert manifest["displayName"] == "Apothem"
    for key in ("documentationUrl", "supportUrl"):
        value = manifest[key]
        assert isinstance(value, str)
        assert value.startswith("https://"), f"{key} must be an https:// URL"


@pytest.mark.parametrize(
    "key",
    [
        "documentationUrl",
        "supportUrl",
        "privacyPolicyUrl",
        "termsOfServiceUrl",
    ],
)
def test_schema_requires_https_listing_urls(key: str) -> None:
    manifest = build_plugin_manifest(_SRC_ROOT)
    manifest[key] = "http://example.com/page"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=manifest, schema=_schema())


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
    # PreCompact and PostCompact are absent: Claude Code discards their
    # output, so the recovery context rides SessionStart(source=compact).
    assert set(events) == {"SessionStart", "PreToolUse", "PostToolUse", "Stop"}


def test_hooks_json_pretooluse_matchers() -> None:
    """PreToolUse carries the five engine matchers in stable order."""
    hooks_json = build_plugin_hooks_json("lib/apothem")
    events = hooks_json["hooks"]
    assert isinstance(events, dict)
    pretooluse = events["PreToolUse"]
    assert isinstance(pretooluse, list)
    matchers = [group["matcher"] for group in pretooluse]
    assert matchers == [
        "Write",
        "Edit",
        "NotebookEdit",
        "Bash|PowerShell",
        "AskUserQuestion",
    ]


def test_hooks_json_registers_each_hook_once_through_bash() -> None:
    """Each hook is one shell-form command that invokes bash by name.

    A dual bash + powershell registration ran twice wherever both shells exist
    and errored on every call wherever one is missing; executing the stub path
    directly depended on the file's executable bit. Invoking ``bash`` keeps the
    hook independent of the tracked file mode.
    """
    hooks_json = build_plugin_hooks_json("lib/apothem")
    events = hooks_json["hooks"]
    assert isinstance(events, dict)
    for groups in events.values():
        assert isinstance(groups, list)
        for group in groups:
            commands = group["hooks"]
            assert isinstance(commands, list)
            for cmd in commands:
                assert "shell" not in cmd
                assert str(cmd["command"]).startswith('bash "${CLAUDE_PLUGIN_ROOT}/')
            names = [str(cmd["command"]).split()[-1] for cmd in commands]
            assert len(names) == len(set(names)), names


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
                assert "${CLAUDE_PLUGIN_ROOT}/lib/apothem/hooks/lib/bootstrap.sh" in (
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


def test_repo_root_carries_no_plugin_manifest() -> None:
    """The repository root is not a plugin, so it ships no plugin manifest.

    The marketplace installs ``plugins/claude-code``. A second manifest at the
    root was a hand-kept duplicate that no install path read, and it failed
    ``claude plugin validate --strict`` (a root ``CLAUDE.md`` is not plugin
    context). Only ``marketplace.json`` belongs in the root ``.claude-plugin``.
    """
    root_meta = _REPO_ROOT / ".claude-plugin"
    assert not (root_meta / "plugin.json").exists(), (
        "repo-root .claude-plugin/plugin.json is vestigial; the marketplace "
        "source is plugins/claude-code"
    )
    assert sorted(p.name for p in root_meta.iterdir()) == ["marketplace.json"]


def test_every_marketplace_source_carries_a_valid_manifest() -> None:
    """Each marketplace entry resolves to a directory with a valid manifest."""
    marketplace = json.loads(
        (_REPO_ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8")
    )
    plugins = marketplace["plugins"]
    assert plugins, "the marketplace lists no plugins"
    for entry in plugins:
        source = _REPO_ROOT / entry["source"]
        assert source.resolve() != _REPO_ROOT.resolve(), (
            f"{entry['name']}: the repository root cannot be a plugin source"
        )
        manifest = source / ".claude-plugin" / "plugin.json"
        assert manifest.is_file(), f"{entry['name']}: {manifest} is missing"
        jsonschema.validate(
            instance=json.loads(manifest.read_text(encoding="utf-8")),
            schema=_schema(),
        )


# --- Committed distribution tree ------------------------------------------
#
# The repository root is not a shippable plugin package: Cowork caps a plugin
# package at 5,000 files and the repo carries ~6,150, because site/ and tests/
# are 85% of it and neither is plugin content. Plugin packages have no
# exclusion mechanism, so the distribution unit is the assembled tree committed
# at plugins/claude-code/, which the marketplace points at.

_DIST_ROOT = _REPO_ROOT / "plugins" / "claude-code"

#: Cowork's documented per-plugin-package limits.
_COWORK_MAX_FILES = 5_000
_COWORK_MAX_BYTES = 200 * 1024**2


def _tree_files(root: Path) -> set[str]:
    """Return every file under ``root`` as a POSIX path relative to it."""
    return {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()}


def test_assemble_prunes_catalog_doc_files(tmp_path: Path) -> None:
    """Catalog roots become discovery directories — no README/AGENTS may ship.

    Claude Code scans the default component folders directly, so a copied
    ``commands/README.md`` loads as a frontmatter-less command even though the
    manifest omits it.
    """
    dest = tmp_path / "plugin_root"
    assemble_plugin_tree(_SRC_ROOT, dest)
    for name in ("skills", "agents", "commands", "rules"):
        for doc in ("README.md", "AGENTS.md"):
            assert not (dest / name / doc).exists(), (
                f"{name}/{doc} leaked into the tree"
            )


def test_assemble_keeps_docs_nested_inside_skills(tmp_path: Path) -> None:
    """Pruning is catalog-root-only: a skill's own reference docs survive."""
    dest = tmp_path / "plugin_root"
    assemble_plugin_tree(_SRC_ROOT, dest)
    src_nested = {
        p.relative_to(_SRC_ROOT / "skills").as_posix()
        for p in (_SRC_ROOT / "skills").rglob("README.md")
        if p.parent != _SRC_ROOT / "skills"
    }
    dest_nested = {
        p.relative_to(dest / "skills").as_posix()
        for p in (dest / "skills").rglob("README.md")
        if p.parent != dest / "skills"
    }
    assert dest_nested == src_nested


#: The three files the assembler writes rather than copies. Copied files carry
#: their source bytes; only these pass through ``write_text``, so only these can
#: pick up the host's line-ending convention.
_GENERATED_FILES = (
    ".claude-plugin/plugin.json",
    "lib/apothem/hooks/hooks.json",
    "lib/apothem_lib.py",
)


def test_generated_files_use_lf_line_endings(tmp_path: Path) -> None:
    """Written files must be LF on every host, or the drift gate is unusable.

    ``write_text`` without ``newline=`` translates "\\n" to ``os.linesep``, so a
    Windows assembly emits CRLF. Git normalizes the committed bytes to LF, and
    the next Windows re-assembly then reports drift against a clone the author
    cannot reproduce locally. The drift test alone cannot catch this: both sides
    of its comparison are generated on the same host, so they always agree.
    """
    dest = tmp_path / "plugin_root"
    assemble_plugin_tree(_SRC_ROOT, dest)
    for rel in _GENERATED_FILES:
        raw = (dest / rel).read_bytes()
        assert b"\r\n" not in raw, f"{rel} carries CRLF; pass newline='\\n'"


def test_committed_dist_tree_generated_files_use_lf() -> None:
    """The committed copies carry LF, matching what a clone checks out."""
    for rel in _GENERATED_FILES:
        raw = (_DIST_ROOT / rel).read_bytes()
        assert b"\r\n" not in raw, f"committed {rel} carries CRLF"


def test_committed_dist_tree_exists() -> None:
    """The marketplace resolves ./plugins/claude-code from a clone."""
    assert (_DIST_ROOT / ".claude-plugin" / "plugin.json").is_file(), (
        "run: python scripts/dev/assemble_plugin_tree.py"
    )


def test_committed_dist_tree_matches_generator(tmp_path: Path) -> None:
    """The committed distribution tree must never drift from the generator."""
    reference = tmp_path / "claude-code"
    assemble_plugin_tree(_SRC_ROOT, reference)

    expected = _tree_files(reference)
    actual = _tree_files(_DIST_ROOT)
    assert expected == actual, (
        "plugins/claude-code has drifted; regenerate with "
        "python scripts/dev/assemble_plugin_tree.py"
    )
    differing = [
        rel
        for rel in sorted(expected)
        if (reference / rel).read_bytes() != (_DIST_ROOT / rel).read_bytes()
    ]
    assert not differing, f"content drift in {len(differing)} file(s): {differing[:5]}"


def test_committed_dist_tree_fits_cowork_limits() -> None:
    """The distribution tree must stay inside Cowork's per-package caps."""
    files = _tree_files(_DIST_ROOT)
    total = sum((_DIST_ROOT / rel).stat().st_size for rel in files)
    assert len(files) <= _COWORK_MAX_FILES, (
        f"{len(files)} files exceeds Cowork's {_COWORK_MAX_FILES}-file cap"
    )
    assert total <= _COWORK_MAX_BYTES, (
        f"{total} bytes exceeds Cowork's {_COWORK_MAX_BYTES}-byte cap"
    )


def test_marketplace_source_points_at_committed_dist_tree() -> None:
    """The marketplace must ship the scoped tree, never the repository root.

    ``"source": "./"`` makes the plugin package the whole repository, which
    installs in Claude Code (no file cap on a local clone) and fails in Cowork.
    """
    marketplace = json.loads(
        (_REPO_ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8")
    )
    plugins = marketplace["plugins"]
    assert isinstance(plugins, list)
    entry = next(item for item in plugins if item["name"] == "apothem")
    assert entry["source"] == "./plugins/claude-code"
