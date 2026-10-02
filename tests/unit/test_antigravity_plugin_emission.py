# SPDX-License-Identifier: MIT

"""The Antigravity plugin emits rules and a manifest Antigravity accepts.

Per https://antigravity.google/docs/rules (retrieved 2026-10-02), every ``.md``
file inside a ``rules/`` directory must start with YAML frontmatter declaring a
valid ``trigger`` (``always_on``, ``model_decision``, ``glob`` or ``manual``);
a rule without one is silently discarded. ``model_decision`` needs a
``description`` and ``glob`` needs ``globs``. The Antigravity CLI activates the
rules packaged in an installed plugin's ``rules/`` directory.

Per https://antigravity.google/docs/plugins (same date), ``plugin.json`` admits
only ``name`` and ``description`` (``additionalProperties: false``).
"""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest
import yaml

from apothem.harnesses._shared import install_driver

_PKG = Path(__file__).resolve().parents[2] / "src" / "apothem"
_RULES_SRC = _PKG / "rules"
_TRIGGERS = {"always_on", "model_decision", "glob", "manual"}
_RULE_KEYS = {"trigger", "description", "globs"}

#: The "Full JSON schema" published on https://antigravity.google/docs/plugins
#: (retrieved 2026-10-02).
_PLUGIN_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string", "pattern": "^[a-zA-Z0-9-_]+$"},
        "description": {"type": "string"},
    },
    "required": ["name"],
    "additionalProperties": False,
}


def _frontmatter(text: str) -> dict[str, object]:
    assert text.startswith("---\n"), text[:80]
    loaded = yaml.safe_load(text[4 : text.index("\n---\n", 4)])
    assert isinstance(loaded, dict)
    return loaded


def _source_fields(name: str) -> dict[str, object]:
    return _frontmatter((_RULES_SRC / name).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def plugin_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("gemini-home")
    install_driver.run_install("antigravity", harness_root=root)
    return root / "antigravity-cli" / "plugins" / "apothem"


def test_every_plugin_rule_declares_a_valid_trigger(plugin_root: Path) -> None:
    rules = sorted((plugin_root / "rules").glob("*.md"))
    sources = sorted(
        p.name for p in _RULES_SRC.glob("*.md") if p.name not in {"README.md"}
    )
    assert [p.name for p in rules] == sources
    for rule in rules:
        fields = _frontmatter(rule.read_text(encoding="utf-8"))
        assert set(fields) <= _RULE_KEYS, (rule.name, sorted(fields))
        assert fields["trigger"] in _TRIGGERS, rule.name
        if fields["trigger"] == "model_decision":
            assert fields.get("description"), rule.name
        if fields["trigger"] == "glob":
            assert fields.get("globs"), rule.name


def test_trigger_follows_the_source_activation(plugin_root: Path) -> None:
    for rule in sorted((plugin_root / "rules").glob("*.md")):
        source = _source_fields(rule.name)
        fields = _frontmatter(rule.read_text(encoding="utf-8"))
        assert fields["description"] == source["description"]
        if source["alwaysApply"] is True:
            assert fields["trigger"] == "always_on", rule.name
        elif source["pathFilter"]:
            assert fields["trigger"] == "glob", rule.name
            assert fields["globs"] == source["pathFilter"]
        else:
            assert fields["trigger"] == "model_decision", rule.name


def test_rule_body_is_carried_without_source_frontmatter(plugin_root: Path) -> None:
    rule = plugin_root / "rules" / "agent-capability-discipline.md"
    text = rule.read_text(encoding="utf-8")
    assert "pathFilter" not in text.split("\n---\n", 1)[0]
    assert "<!-- SPDX-License-Identifier: MIT -->" in text
    assert text.count("\n---\n") >= 1


def test_plugin_manifest_validates_against_vendor_schema(plugin_root: Path) -> None:
    manifest = json.loads((plugin_root / "plugin.json").read_text(encoding="utf-8"))
    jsonschema.validate(manifest, _PLUGIN_SCHEMA)
    assert manifest["name"] == "apothem"


def test_reinstall_is_unchanged(tmp_path: Path) -> None:
    install_driver.run_install("antigravity", harness_root=tmp_path)
    run = install_driver.run_install("antigravity", harness_root=tmp_path)
    rules_results = [r for r in run.results if r.operation == "antigravity_rules"]
    assert rules_results
    assert {r.outcome for r in rules_results} == {"unchanged"}
