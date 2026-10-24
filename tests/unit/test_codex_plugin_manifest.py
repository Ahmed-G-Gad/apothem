# SPDX-License-Identifier: MIT

"""The Codex plugin under ``plugins/apothem/`` matches the documented layout.

Codex documents a portable plugin as a root ``plugin.json`` manifest, a root
``skills/`` directory it discovers by convention, and optional ``mcp.json`` and
``assets/``. The manifest validates against the Agent Plugins 1.0.0 schema
(``https://agent-plugins.org/schemas/1.0.0/plugin.schema.json``), which sets
``additionalProperties: false`` and lists only ``$schema``, ``name``,
``version``, ``description``, ``author``, ``homepage``, ``repository``,
``license``, ``keywords`` and ``extensions``. A ``.codex-plugin/plugin.json``
file stays supported as a compatibility fallback: the root manifest is
canonical for identity, and the fallback only supplies OpenAI-specific settings
when the root has no ``extensions.com.openai`` object.

Codex documents no custom-agents plugin component, so neither manifest may
declare one; agents reach Codex through ``~/.codex/agents/*.toml`` via the
engine instead. The Codex adapter's convention pin records the same facts.

No offline copy of the vendor schema is committed, so this suite encodes the
schema's documented shape (property set, required keys, name pattern, author
keys) rather than fetching it.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_PLUGIN_ROOT = _REPO_ROOT / "plugins" / "apothem"
_ROOT_MANIFEST = _PLUGIN_ROOT / "plugin.json"
_LEGACY_MANIFEST = _PLUGIN_ROOT / ".codex-plugin" / "plugin.json"
_MARKETPLACE = _REPO_ROOT / ".agents" / "plugins" / "marketplace.json"

_SCHEMA_URL = "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
_SCHEMA_PROPERTIES = frozenset(
    {
        "$schema",
        "name",
        "version",
        "description",
        "author",
        "homepage",
        "repository",
        "license",
        "keywords",
        "extensions",
    }
)
_SCHEMA_REQUIRED = frozenset({"$schema", "name"})
_AUTHOR_PROPERTIES = frozenset({"name", "email", "url"})
# The schema's name pattern, written as an equivalent alternation: one
# alphanumeric, or alphanumeric ends around a run of alphanumerics, dots and
# hyphens, with no doubled hyphen or dot anywhere.
_NAME_PATTERN = re.compile(
    r"^(?!.*(?:--|\.\.))(?:[a-z0-9]|[a-z0-9][a-z0-9.-]*[a-z0-9])$"
)
# The marketplace ``policy`` block the vendor says to always include on each
# entry (openai/skills plugin-creator ``plugin-json-spec.md``, read 2026-10-24).
_INSTALLATION_VALUES = frozenset({"AVAILABLE", "INSTALLED_BY_DEFAULT", "NOT_AVAILABLE"})
_AUTHENTICATION_VALUES = frozenset({"ON_INSTALL", "ON_USE"})
# Manifest keys that would declare a custom-agents component, which Codex does
# not document for plugins (the request is tracked upstream as still open).
_UNDOCUMENTED_AGENT_KEYS = frozenset({"agents", "subagents", "customAgents"})


def _load(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict), f"{path.name} is not a JSON object"
    return data


def _keys_anywhere(node: object) -> set[str]:
    """Return every object key found at any depth under *node*."""
    found: set[str] = set()
    if isinstance(node, dict):
        for key, value in node.items():
            found.add(key)
            found |= _keys_anywhere(value)
    elif isinstance(node, list):
        for item in node:
            found |= _keys_anywhere(item)
    return found


def test_root_manifest_exists_at_the_documented_location() -> None:
    assert _ROOT_MANIFEST.is_file(), (
        "Codex's documented manifest for a new package is a root plugin.json"
    )


def test_root_manifest_declares_the_portable_schema() -> None:
    manifest = _load(_ROOT_MANIFEST)
    assert manifest.get("$schema") == _SCHEMA_URL


def test_root_manifest_stays_inside_the_portable_schema() -> None:
    manifest = _load(_ROOT_MANIFEST)
    extra = set(manifest) - _SCHEMA_PROPERTIES
    assert not extra, (
        f"plugin.json carries keys the portable schema forbids "
        f"(additionalProperties: false): {sorted(extra)}"
    )
    missing = _SCHEMA_REQUIRED - set(manifest)
    assert not missing, f"plugin.json lacks required keys: {sorted(missing)}"

    name = manifest["name"]
    assert isinstance(name, str)
    assert 1 <= len(name) <= 64
    assert _NAME_PATTERN.fullmatch(name), f"plugin name {name!r} breaks the pattern"

    author = manifest.get("author", {})
    assert isinstance(author, dict)
    assert set(author) <= _AUTHOR_PROPERTIES, "author admits name, email and url only"
    assert all(isinstance(value, str) for value in author.values())

    keywords = manifest.get("keywords", [])
    assert isinstance(keywords, list)
    assert all(isinstance(word, str) for word in keywords)


def test_root_manifest_does_not_declare_skills() -> None:
    """Portable packages find ``skills/`` by convention; ``skills`` is not a key."""
    assert "skills" not in _load(_ROOT_MANIFEST)


def test_skills_are_discoverable_by_convention() -> None:
    skills_root = _PLUGIN_ROOT / "skills"
    assert skills_root.is_dir(), "plugins/apothem/skills/ is missing"
    skill_dirs = [child for child in skills_root.iterdir() if child.is_dir()]
    assert skill_dirs, "plugins/apothem/skills/ holds no skill"
    for skill_dir in skill_dirs:
        assert (skill_dir / "SKILL.md").is_file(), (
            f"skills/{skill_dir.name}/ has no SKILL.md"
        )


@pytest.mark.parametrize(
    "path",
    [_ROOT_MANIFEST, _LEGACY_MANIFEST],
    ids=lambda path: path.relative_to(_PLUGIN_ROOT).as_posix(),
)
def test_manifest_declares_no_custom_agents_component(path: Path) -> None:
    """Codex lists no custom-agents plugin component (openai/codex #18988)."""
    present = _keys_anywhere(_load(path)) & _UNDOCUMENTED_AGENT_KEYS
    assert not present, f"{path.name} declares an undocumented agents key: {present}"


def test_fallback_does_not_contradict_the_root_manifest() -> None:
    """The root is canonical for identity; the fallback must not drift from it."""
    root = _load(_ROOT_MANIFEST)
    legacy = _load(_LEGACY_MANIFEST)
    for key in ("name", "version", "description"):
        assert legacy[key] == root[key], f"fallback {key} differs from the root"
    # A legacy reader that does not know the portable layout still needs the
    # skills path, and it must resolve to the directory the root convention uses.
    skills_path = legacy.get("skills")
    assert skills_path == "./skills/"
    assert (_PLUGIN_ROOT / skills_path).is_dir()


def test_root_manifest_leaves_the_fallback_in_force() -> None:
    """An ``extensions.com.openai`` object replaces the whole fallback overlay.

    The two are not merged, so adding that object to the root would silently
    retire ``.codex-plugin/plugin.json``. Retire it on purpose instead: remove
    the file and this test together.
    """
    extensions = _load(_ROOT_MANIFEST).get("extensions", {})
    assert "com.openai" not in extensions, (
        "root extensions.com.openai replaces the .codex-plugin overlay"
    )


def _marketplace_entries() -> list[dict[str, Any]]:
    entries = _load(_MARKETPLACE).get("plugins", [])
    assert isinstance(entries, list)
    return entries


def test_marketplace_entry_resolves_to_the_plugin_root() -> None:
    manifest_name = _load(_ROOT_MANIFEST)["name"]
    entries = [e for e in _marketplace_entries() if e.get("name") == manifest_name]
    assert len(entries) == 1, f"expected one marketplace entry for {manifest_name!r}"
    source = entries[0]["source"]
    assert source["source"] == "local"
    target = (_REPO_ROOT / source["path"]).resolve()
    assert target == _PLUGIN_ROOT.resolve()
    assert (target / "plugin.json").is_file()


def test_marketplace_entry_carries_a_policy_with_documented_values() -> None:
    """Every entry sets ``policy.installation`` and ``policy.authentication``.

    The vendor says to always include both on each plugin entry, each with a
    value from its documented set.
    """
    for entry in _marketplace_entries():
        policy = entry.get("policy")
        assert isinstance(policy, dict), f"{entry.get('name')!r} sets no policy"
        assert policy.get("installation") in _INSTALLATION_VALUES
        assert policy.get("authentication") in _AUTHENTICATION_VALUES
