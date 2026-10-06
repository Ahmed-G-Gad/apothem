# SPDX-License-Identifier: MIT

"""Skill and command descriptions fit the Agent Skills limit.

The Agent Skills specification caps ``description`` at 1024 characters
(https://agentskills.io/specification, retrieved 2026-10-03), and strict
consumers reject or truncate a longer one. Commands count too: several
harnesses install every command as a skill whose description is the
command's own.
"""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest
import yaml

from apothem.harnesses._shared import install_driver

_PKG = Path(__file__).resolve().parents[2] / "src" / "apothem"
_LIMIT = 1024
_SOURCES = sorted(_PKG.glob("skills/*/SKILL.md")) + sorted(
    p for p in _PKG.glob("commands/*.md") if p.name not in {"README.md", "AGENTS.md"}
)


def _description(text: str) -> str:
    fields = yaml.safe_load(text[4 : text.index("\n---\n", 4)])
    assert isinstance(fields, dict)
    return str(fields["description"])


@pytest.mark.parametrize(
    "source", _SOURCES, ids=lambda p: p.relative_to(_PKG).as_posix()
)
def test_source_description_fits(source: Path) -> None:
    assert len(_description(source.read_text(encoding="utf-8"))) <= _LIMIT


def test_emitted_skill_descriptions_fit(tmp_path: Path) -> None:
    # The codex install is the widest skill emission: every skill plus every
    # command, under the home's .agents/skills/.
    install_driver.run_install("codex", harness_root=tmp_path / ".codex")
    skills = sorted((tmp_path / ".agents" / "skills").glob("*/SKILL.md"))
    assert len(skills) >= 60
    over = {
        p.parent.name: n
        for p in skills
        if (n := len(_description(p.read_text(encoding="utf-8")))) > _LIMIT
    }
    assert not over


@pytest.mark.parametrize("schema_name", ["skill", "command"])
def test_schema_caps_description(schema_name: str) -> None:
    schema = json.loads(
        (_PKG / "schemas" / f"{schema_name}.schema.json").read_text("utf-8")
    )
    assert schema["properties"]["description"]["maxLength"] == _LIMIT
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate("x" * (_LIMIT + 1), schema["properties"]["description"])
