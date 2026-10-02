# SPDX-License-Identifier: MIT

"""Agent frontmatter uses documented fields with documented values.

Claude Code documents ``memory`` as a persistent-memory scope taking ``user``,
``project`` or ``local`` (https://code.claude.com/docs/en/sub-agents, supported
frontmatter fields, retrieved 2026-10-02); ``false`` is not a value it defines.
Apothem's own metadata keys stay limited to the extensions agent.schema.json
admits.
"""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest
import yaml

_PKG = Path(__file__).resolve().parents[2] / "src" / "apothem"
_SCHEMA = json.loads((_PKG / "schemas" / "agent.schema.json").read_text("utf-8"))
_AGENTS = sorted(p for p in (_PKG / "agents").glob("*.md") if p.name != "README.md")

#: Claude Code's supported subagent frontmatter fields (sub-agents docs).
_DOCUMENTED = frozenset(
    {
        "name",
        "description",
        "tools",
        "disallowedTools",
        "model",
        "permissionMode",
        "maxTurns",
        "skills",
        "mcpServers",
        "hooks",
        "memory",
        "background",
        "omitClaudeMd",
        "effort",
        "isolation",
        "color",
        "initialPrompt",
        "experimental",
    }
)
#: Apothem metadata the schema admits as documented extensions.
_APOTHEM_EXTENSIONS = frozenset({"version", "updated", "portability"})


def _fm(path: Path) -> dict[str, object]:
    text = path.read_text(encoding="utf-8")
    loaded = yaml.safe_load(text[4 : text.index("\n---\n", 4)])
    assert isinstance(loaded, dict)
    return loaded


@pytest.mark.parametrize("agent", _AGENTS, ids=lambda p: p.stem)
def test_agent_keys_are_documented_or_admitted(agent: Path) -> None:
    keys = set(_fm(agent))
    assert keys <= _DOCUMENTED | _APOTHEM_EXTENSIONS, sorted(keys)
    assert set(_SCHEMA["properties"]) >= _APOTHEM_EXTENSIONS


@pytest.mark.parametrize("agent", _AGENTS, ids=lambda p: p.stem)
def test_agent_memory_is_absent_or_a_documented_scope(agent: Path) -> None:
    fields = _fm(agent)
    assert fields.get("memory", "user") in {"user", "project", "local"}
    jsonschema.validate(fields, _SCHEMA)


def test_schema_rejects_boolean_memory() -> None:
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate({"name": "a", "description": "b", "memory": False}, _SCHEMA)
