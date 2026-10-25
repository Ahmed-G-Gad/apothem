# SPDX-License-Identifier: MIT

"""The one emission every writer of the shared skill folders uses.

``~/.agents/skills/`` is a single copy read by many tools, written by every
install that names it. Each writer must produce the same bytes, or installs
would rewrite each other's folders; the emission is therefore independent of
the harness doing the writing (``SHARED_EMISSION``).
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest
import yaml

from apothem.harnesses._shared import install_driver
from apothem.harnesses._shared.install_driver_converters import _native_skill_emission
from apothem.harnesses._shared.install_driver_layout import (
    ANNOUNCEMENT_HEADING,
    REFERENCE_NOTE_HEADING,
    shared_corpus_layout,
    shared_reference_note,
)
from apothem.harnesses._shared.install_driver_shared import (
    SHARED_EMISSION,
    SHARED_TOPLEVEL_KEYS,
)
from apothem.lib import propagation
from apothem.lib.frontmatter import field_value, split_frontmatter
from apothem.lib.propagation import HarnessRules, load_manifest

_PKG = Path(__file__).resolve().parents[2] / "src" / "apothem"
_FORBIDDEN = {"userInvocable", "version", "updated", "archetype", "portability"}


def _sources() -> dict[str, Path]:
    """Map each installed skill name to its source; a skill wins over a command."""
    sources = {
        command.stem: command
        for command in (_PKG / "commands").glob("*.md")
        if command.name not in {"README.md", "AGENTS.md"}
    }
    sources.update({p.parent.name: p for p in (_PKG / "skills").glob("*/SKILL.md")})
    return sources


def _frontmatter(path: Path) -> dict[str, object]:
    parts = split_frontmatter(path.read_text(encoding="utf-8"))
    assert parts is not None, path
    block = "\n".join(parts[0].strip().split("\n")[1:-1])
    loaded = yaml.safe_load(block)
    assert isinstance(loaded, dict), path
    return loaded


def _digests(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


@dataclass(frozen=True)
class _Installed:
    codex: Path
    cursor: Path


@pytest.fixture(scope="module")
def installed(tmp_path_factory: pytest.TempPathFactory) -> Iterator[_Installed]:
    """Install the real corpus twice, as Codex and as a project-scope adapter."""
    codex_home = tmp_path_factory.mktemp("codex-home")
    cursor_home = tmp_path_factory.mktemp("cursor-home")
    project = tmp_path_factory.mktemp("project")
    real_load_rules = install_driver.load_rules
    codex_rules = real_load_rules("codex")
    user_entries = [entry for entry in codex_rules.install if entry.user_level]
    cursor_rules = real_load_rules("cursor")
    combined = HarnessRules(
        install=[*user_entries, *cursor_rules.install],
        exclude=cursor_rules.exclude,
        stale_sweep=[],
    )
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(
            install_driver,
            "load_rules",
            lambda name: combined if name == "cursor" else real_load_rules(name),
        )
        patch.setattr(propagation, "USER_HOME", codex_home)
        install_driver.run_install("codex", harness_root=codex_home / ".codex")
        patch.setattr(propagation, "USER_HOME", cursor_home)
        install_driver.run_install("cursor", project_root=project)
    return _Installed(codex_home, cursor_home)


def test_every_writer_emits_the_same_bytes(installed: _Installed) -> None:
    codex = _digests(installed.codex / ".agents")
    cursor = _digests(installed.cursor / ".agents")
    assert codex == cursor
    assert _digests(installed.codex / ".config") == _digests(
        installed.cursor / ".config"
    )
    assert any(name.endswith("SKILL.md") for name in codex)


def test_every_source_skill_is_a_folder(installed: _Installed) -> None:
    folders = {p.name for p in (installed.codex / ".agents" / "skills").iterdir()}
    assert folders == set(_sources())


def test_the_top_level_keys_stay_in_the_shared_set(installed: _Installed) -> None:
    for name in _sources():
        keys = set(
            _frontmatter(installed.codex / ".agents" / "skills" / name / "SKILL.md")
        )
        assert keys <= SHARED_TOPLEVEL_KEYS, (name, keys - SHARED_TOPLEVEL_KEYS)
        assert not keys & _FORBIDDEN, name
        assert "allowedTools" not in keys, name


def test_the_name_is_the_folder_and_the_description_fits(installed: _Installed) -> None:
    for name in _sources():
        front = _frontmatter(installed.codex / ".agents" / "skills" / name / "SKILL.md")
        assert front["name"] == name
        assert 0 < len(str(front["description"])) <= 1024, name


def test_the_apothem_keys_move_under_metadata(installed: _Installed) -> None:
    front = _frontmatter(
        installed.codex / ".agents" / "skills" / "plan-suite" / "SKILL.md"
    )
    metadata = front["metadata"]
    assert isinstance(metadata, dict)
    assert set(metadata) <= {"version", "updated", "archetype", "portability"}
    assert all(isinstance(value, str) for value in metadata.values())
    assert "user-invocable" in front or "userInvocable" not in front


def test_the_sidecar_exists_exactly_for_skills_that_disable_model_invocation(
    installed: _Installed,
) -> None:
    skills = installed.codex / ".agents" / "skills"
    for name, source in _sources().items():
        sidecar = skills / name / "agents" / "openai.yaml"
        assert sidecar.is_file() == (
            field_value(source, "disable-model-invocation") == "true"
        )
    sidecar_text = (skills / "plan-suite" / "agents" / "openai.yaml").read_text("utf-8")
    assert yaml.safe_load(sidecar_text) == {
        "policy": {"allow_implicit_invocation": False}
    }


def test_a_command_skill_carries_one_note_with_no_absolute_path(
    installed: _Installed,
) -> None:
    commands = {
        c.stem
        for c in (_PKG / "commands").glob("*.md")
        if c.name not in {"README.md", "AGENTS.md"}
    } - {p.parent.name for p in (_PKG / "skills").glob("*/SKILL.md")}
    assert commands
    for name in commands:
        text = (installed.codex / ".agents" / "skills" / name / "SKILL.md").read_text(
            "utf-8"
        )
        assert text.count(REFERENCE_NOTE_HEADING) == 1, name
        assert str(installed.codex) not in text
        assert str(installed.cursor) not in text
        assert "`rules/<path>` is `~/.config/apothem/rules/<path>`" in text
        assert "`templates/<path>` is `~/.config/apothem/templates/<path>`" in text
        assert "hooks/" not in text.split(REFERENCE_NOTE_HEADING)[1]


def test_the_note_text_does_not_depend_on_the_writer(installed: _Installed) -> None:
    layout = shared_corpus_layout()
    assert [(name, path.as_posix()) for name, path in layout.dirs] == [
        ("rules", "~/.config/apothem/rules"),
        ("templates", "~/.config/apothem/templates"),
    ]


def test_every_user_level_corpus_entry_matches_the_note() -> None:
    # The fixed note names these folders, so every writer must install them there.
    expected = {
        "rules": "${USER_HOME}/.config/apothem/rules/",
        "templates": "${USER_HOME}/.config/apothem/templates/",
    }
    for name, rules in load_manifest().items():
        for entry in rules.install:
            if entry.user_level and entry.mode == "merge_tree_entries":
                assert entry.target == expected[entry.source.rstrip("/")], name


def test_the_emission_does_not_depend_on_the_calling_harness() -> None:
    source = (_PKG / "skills" / "plan-suite" / "SKILL.md").read_text("utf-8")
    assert _native_skill_emission(SHARED_EMISSION, source) == _native_skill_emission(
        SHARED_EMISSION, source
    )
    assert _native_skill_emission("codex", source) != _native_skill_emission(
        SHARED_EMISSION, source
    )


def test_the_shared_key_set_is_the_documented_one() -> None:
    assert {
        "name",
        "description",
        "user-invocable",
        "disable-model-invocation",
        "allowed-tools",
        "argument-hint",
        "metadata",
    } == SHARED_TOPLEVEL_KEYS


def test_the_shared_note_defers_other_folders_to_the_instruction_file(
    installed: _Installed,
) -> None:
    # The note lists only the corpus folders every writer installs. A skill that
    # cites `hooks/...` in a Codex install resolves it through the support-files
    # section of Codex's AGENTS.md, which the note points at.
    note = shared_reference_note()
    assert note.count(REFERENCE_NOTE_HEADING) == 1
    assert note.endswith("when that section lists one.\n")
    assert ANNOUNCEMENT_HEADING.lstrip("# ") in note
    assert "hooks/" not in note
    agents = (installed.codex / ".codex" / "AGENTS.md").read_text(encoding="utf-8")
    section = agents.split(ANNOUNCEMENT_HEADING)[1]
    assert "`hooks/<path>`" in section
