# SPDX-License-Identifier: MIT

"""Claude Code receives the skill user-invocability key it reads.

Claude Code reads ``user-invocable`` (``false`` hides a skill from the ``/``
menu; default ``true``) and silently ignores unknown keys such as the source
corpus's camelCase ``userInvocable``, per https://code.claude.com/docs/en/skills
(retrieved 2026-10-02). The claude_code install and the plugin assembler
translate the key name; the source corpus keeps ``userInvocable``.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import jsonschema
import pytest
import yaml

from apothem.harnesses._shared import install_driver
from apothem.lib.plugin_tree import assemble_plugin_tree

_PKG = Path(__file__).resolve().parents[2] / "src" / "apothem"
_SCHEMA = json.loads((_PKG / "schemas" / "skill.schema.json").read_text("utf-8"))
_NOT_USER_INVOCABLE = {"plan-suite", "research-suite"}
_CAMEL = re.compile(r"^userInvocable:", re.MULTILINE)


def _fm(path: Path) -> dict[str, object]:
    text = path.read_text(encoding="utf-8")
    loaded = yaml.safe_load(text[4 : text.index("\n---\n", 4)])
    assert isinstance(loaded, dict)
    return loaded


def _assert_translated(skills_dir: Path) -> None:
    skill_files = sorted(skills_dir.glob("*/SKILL.md"))
    assert skill_files
    for skill in skill_files:
        text = skill.read_text(encoding="utf-8")
        assert not _CAMEL.search(text), skill
        fields = _fm(skill)
        if skill.parent.name in _NOT_USER_INVOCABLE:
            assert fields["user-invocable"] is False, skill
        source = _PKG / "skills" / skill.parent.name / "SKILL.md"
        from_command = (_PKG / "commands" / f"{skill.parent.name}.md").is_file()
        if source.is_file() and not from_command:
            assert fields["user-invocable"] is _fm(source)["userInvocable"], skill


def test_claude_code_install_translates_user_invocable(tmp_path: Path) -> None:
    install_driver.run_install("claude_code", harness_root=tmp_path)
    _assert_translated(tmp_path / "skills")
    for name in _NOT_USER_INVOCABLE:
        text = (tmp_path / "skills" / name / "SKILL.md").read_text("utf-8")
        assert re.search(r"^user-invocable: false$", text, re.MULTILINE)


def test_claude_code_reinstall_is_unchanged(tmp_path: Path) -> None:
    install_driver.run_install("claude_code", harness_root=tmp_path)
    run = install_driver.run_install("claude_code", harness_root=tmp_path)
    skill_results = [r for r in run.results if r.operation == "native_skills"]
    assert skill_results
    assert {r.outcome for r in skill_results} == {"unchanged"}


def test_plugin_tree_translates_user_invocable(tmp_path: Path) -> None:
    plugin = assemble_plugin_tree(_PKG, tmp_path / "plugin")
    _assert_translated(plugin / "skills")
    # The verbatim engine copy keeps the source spelling.
    engine_copy = plugin / "lib" / "apothem" / "skills" / "plan-suite" / "SKILL.md"
    assert _CAMEL.search(engine_copy.read_text(encoding="utf-8"))


def test_other_harnesses_keep_the_source_spelling(tmp_path: Path) -> None:
    install_driver.run_install("opencode", harness_root=tmp_path)
    text = (tmp_path / "skills" / "plan-suite" / "SKILL.md").read_text("utf-8")
    assert _CAMEL.search(text)


@pytest.mark.parametrize("key", ["userInvocable", "user-invocable"])
def test_schema_accepts_either_spelling(key: str) -> None:
    fields = _fm(_PKG / "skills" / "plan-suite" / "SKILL.md")
    value = fields.pop("userInvocable")
    fields[key] = value
    jsonschema.validate(fields, _SCHEMA)


def test_schema_requires_exactly_one_spelling() -> None:
    fields = _fm(_PKG / "skills" / "plan-suite" / "SKILL.md")
    both = {**fields, "user-invocable": False}
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(both, _SCHEMA)
    neither = {k: v for k, v in fields.items() if k != "userInvocable"}
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(neither, _SCHEMA)
