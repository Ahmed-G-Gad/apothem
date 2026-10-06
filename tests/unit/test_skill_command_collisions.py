# SPDX-License-Identifier: MIT

"""A skill and a command sharing a name resolve to the same body everywhere.

Some names ship both as a command (``commands/<name>.md``) and as a skill
(``skills/<name>/SKILL.md``). The Claude Code plugin ships both, and Claude
Code resolves a skill and a command that share a name to the skill
(https://code.claude.com/docs/en/skills.md#resolve-skills-that-share-a-name).
An engine install that converts commands into skills writes both into one
``skills/<name>/`` slot, so it must keep the skill there too. These tests fail
on any shared name whose engine-installed body differs from the body the plugin
resolves, or from the source skill.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import apothem
from apothem.harnesses._shared import install_driver
from apothem.harnesses._shared.install_driver_converters import claude_code_skill_text
from apothem.lib.plugin_tree import assemble_plugin_tree
from apothem.lib.propagation import load_manifest, resolve_target

_SRC = Path(apothem.__file__).resolve().parent

#: Names that ship both as a skill and as a command.
_SHARED_NAMES = sorted(
    {path.parent.name for path in (_SRC / "skills").glob("*/SKILL.md")}
    & {
        path.stem
        for path in (_SRC / "commands").glob("*.md")
        if path.name not in {"README.md", "AGENTS.md"}
    }
)

#: Harnesses whose command_skills entry targets the directory its skills/ tree
#: is installed into, so a shared name lands in one slot.
_FOLDING_HARNESSES = sorted(
    name
    for name, rules in load_manifest().items()
    if {
        entry.target.rstrip("/")
        for entry in rules.install
        if entry.mode == "command_skills"
    }
    & {
        entry.target.rstrip("/")
        for entry in rules.install
        if entry.source.rstrip("/") == "skills"
    }
)


def test_the_corpus_has_shared_names() -> None:
    # Guard against a vacuous pass: the corpus ships projectify and workflow
    # both ways today.
    assert {"projectify", "workflow"} <= set(_SHARED_NAMES)
    assert "claude_code" in _FOLDING_HARNESSES


@pytest.fixture(scope="module")
def plugin_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return assemble_plugin_tree(_SRC, tmp_path_factory.mktemp("plugin") / "claude-code")


@pytest.fixture(scope="module")
def claude_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("home") / ".claude"
    install_driver.run_install("claude_code", harness_root=root)
    return root


@pytest.mark.parametrize("name", _SHARED_NAMES)
def test_engine_and_plugin_resolve_the_same_body(
    name: str, plugin_root: Path, claude_root: Path
) -> None:
    # The plugin ships both members; the skill is the one Claude Code runs.
    assert (plugin_root / "commands" / f"{name}.md").is_file()
    plugin_body = (plugin_root / "skills" / name / "SKILL.md").read_text("utf-8")
    engine_body = (claude_root / "skills" / name / "SKILL.md").read_text("utf-8")
    assert engine_body == plugin_body
    source = (_SRC / "skills" / name / "SKILL.md").read_text(encoding="utf-8")
    assert engine_body == claude_code_skill_text(source)


@pytest.mark.parametrize("harness", _FOLDING_HARNESSES)
def test_every_folding_install_keeps_the_skill(harness: str, tmp_path: Path) -> None:
    rules = install_driver.load_rules(harness)
    project_scope = any("${PROJECT_ROOT}" in entry.target for entry in rules.install)
    harness_root = None if project_scope else tmp_path / "home" / f".{harness}"
    project_root = tmp_path / "project" if project_scope else None
    if project_root is not None:
        project_root.mkdir()
    install_driver.run_install(
        harness, harness_root=harness_root, project_root=project_root
    )
    skills_dir = next(
        resolve_target(
            entry.target, harness_root=harness_root, project_root=project_root
        )
        for entry in rules.install
        if entry.mode == "command_skills"
    )
    for name in _SHARED_NAMES:
        installed = (skills_dir / name / "SKILL.md").read_text(encoding="utf-8")
        source = (_SRC / "skills" / name / "SKILL.md").read_text(encoding="utf-8")
        expected = (
            claude_code_skill_text(source) if harness == "claude_code" else source
        )
        assert installed == expected, (harness, name)
