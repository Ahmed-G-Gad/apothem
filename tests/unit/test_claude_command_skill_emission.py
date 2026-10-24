# SPDX-License-Identifier: MIT

"""The Claude Code install emits commands as split skills; others are untouched."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from apothem.harnesses._shared import install_driver
from apothem.harnesses._shared import install_driver_converters as conv
from apothem.lib import claude_skill_split as split_mod
from apothem.lib.claude_skill_split import (
    NATIVE_SKILL_CEILINGS,
    SKILL_MD_CAP_BYTES,
    SplitSkill,
)
from apothem.lib.frontmatter import split_frontmatter

_PKG = Path(__file__).resolve().parents[2] / "src" / "apothem"
_COMMANDS = sorted(p for p in (_PKG / "commands").glob("*.md") if p.name != "README.md")
_NATIVE = {p.parent.name for p in (_PKG / "skills").glob("*/SKILL.md")}
_SHADOWED = {"projectify", "workflow"}
_EMITTED = [p for p in _COMMANDS if p.stem not in _NATIVE]
_LONG_ROOT_LIMIT = 140
_SKILL_OPERATIONS = {"command_skills", "native_skills"}


def _old_command_skill_files(
    source_path: Path, *, harness_name: str, install_root: Path
) -> dict[str, bytes]:
    """A local copy of ``_command_skill_files`` as it was before the split."""
    text, sidecars = conv._native_skill_emission(
        harness_name,
        conv._generated_skill_text(
            source_path, harness_name=harness_name, install_root=install_root
        ),
    )
    files = {name: body.encode("utf-8") for name, body in sidecars.items()}
    files["SKILL.md"] = text.encode("utf-8")
    return files


def _note(root: Path) -> str:
    return conv._installed_reference_note("claude_code", root)


@pytest.fixture(scope="module")
def claude_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("home") / ".claude"
    install_driver.run_install("claude_code", harness_root=root)
    return root


def test_the_corpus_has_43_emitted_command_skills() -> None:
    assert len(_COMMANDS) == 45
    assert {p.stem for p in _COMMANDS} & _NATIVE == _SHADOWED
    assert len(_EMITTED) == 43


# --------------------------------------------------------------------------
# The pure emission
# --------------------------------------------------------------------------


@pytest.mark.parametrize("path", _EMITTED[::6], ids=lambda p: p.stem)
def test_engine_variant_is_the_plugin_variant_plus_the_note(path: Path) -> None:
    source = path.read_text(encoding="utf-8")
    note = _note(Path("/home/user/.claude"))
    plugin = conv.claude_code_command_skill_files(source)
    engine = conv.claude_code_command_skill_files(source, note=note)
    assert engine.pop("SKILL.md") == plugin["SKILL.md"] + note
    assert engine == {k: v for k, v in plugin.items() if k != "SKILL.md"}
    assert plugin["SKILL.md"].endswith("\n")
    assert "Installed Reference Paths" not in plugin["SKILL.md"]


def test_the_skill_dir_variable_survives_emission() -> None:
    source = (_PKG / "commands" / "plan-execute.md").read_text(encoding="utf-8")
    skill = conv.claude_code_command_skill_files(source)["SKILL.md"]
    assert "`${CLAUDE_SKILL_DIR}/references/`" in skill


def test_a_minimal_command_is_byte_identical_to_the_old_emission(
    tmp_path: Path,
) -> None:
    source = tmp_path / "sample.md"
    source.write_text(
        '---\nname: "sample"\nversion: "1"\ndescription: "d"\n---\n\nBody.',
        encoding="utf-8",
    )
    root = Path("/home/user/.claude")
    new = conv._command_skill_files(
        source, harness_name="claude_code", install_root=root
    )
    old = _old_command_skill_files(
        source, harness_name="claude_code", install_root=root
    )
    assert new == old
    assert set(new) == {"SKILL.md"}
    assert b"metadata:\n  version" in new["SKILL.md"]


@pytest.mark.parametrize(
    "harness", ["codex", "hermes", "kimi_code", "open_claw", "antigravity"]
)
@pytest.mark.parametrize("name", ["plan-execute", "a11y-audit", "elevate"])
def test_other_harnesses_emit_what_they_always_did(harness: str, name: str) -> None:
    path = _PKG / "commands" / f"{name}.md"
    root = Path("/home/user/.config")
    new = conv._command_skill_files(path, harness_name=harness, install_root=root)
    old = _old_command_skill_files(path, harness_name=harness, install_root=root)
    assert new == old
    assert "SKILL.md" in new
    assert b"## Bindings" in new["SKILL.md"]
    assert not any(name.startswith("references/") for name in new)
    if harness == "codex" and name == "a11y-audit":
        assert "agents/openai.yaml" in new


def test_the_cap_holds_for_every_command_with_a_120_character_note() -> None:
    root = Path("/" + "r" * 119)
    note = _note(root)
    assert len(str(root)) == 120
    for path in _EMITTED:
        skill = conv.claude_code_command_skill_files(
            path.read_text(encoding="utf-8"), note=note
        )["SKILL.md"]
        assert len(skill.encode("utf-8")) <= SKILL_MD_CAP_BYTES, path.stem


def test_the_note_reserve_covers_a_140_character_root() -> None:
    note = _note(Path("/" + "r" * 139))
    assert len(note.encode("utf-8")) <= split_mod.NOTE_RESERVE_BYTES


# --------------------------------------------------------------------------
# A real install
# --------------------------------------------------------------------------


def test_plan_execute_is_a_slim_skill_with_step_files(claude_root: Path) -> None:
    skill_dir = claude_root / "skills" / "plan-execute"
    assert (skill_dir / "references" / "step-01-load-context.md").is_file()
    assert (skill_dir / "references" / "foundational-stanzas.md").is_file()
    skill = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
    assert "## Bindings" not in skill
    assert skill.endswith(_note(claude_root))
    for reference in (skill_dir / "references").iterdir():
        assert reference.read_text(encoding="utf-8").startswith(
            split_mod.REFERENCE_HEADER
        )


def test_every_installed_skill_md_is_at_or_under_the_cap(claude_root: Path) -> None:
    if len(str(claude_root)) > _LONG_ROOT_LIMIT:
        pytest.skip("temp root is longer than the note reserve assumes")
    for path in _EMITTED:
        skill = claude_root / "skills" / path.stem / "SKILL.md"
        assert skill.stat().st_size <= SKILL_MD_CAP_BYTES, path.stem
    for name in sorted(_NATIVE):
        size = (claude_root / "skills" / name / "SKILL.md").stat().st_size
        ceiling = NATIVE_SKILL_CEILINGS.get(name)
        if ceiling is None:
            assert size <= SKILL_MD_CAP_BYTES, name
        else:
            assert SKILL_MD_CAP_BYTES < size <= ceiling, name


def test_shadowed_commands_keep_their_native_skill(claude_root: Path) -> None:
    for name in sorted(_SHADOWED):
        installed = (claude_root / "skills" / name / "SKILL.md").read_text("utf-8")
        source = (_PKG / "skills" / name / "SKILL.md").read_text(encoding="utf-8")
        assert installed == conv.claude_code_skill_text(source)
        assert not (claude_root / "skills" / name / "references").exists()


def test_native_skills_carry_their_keys_under_metadata(claude_root: Path) -> None:
    text = (claude_root / "skills" / "plan-suite" / "SKILL.md").read_text("utf-8")
    parts = split_frontmatter(text)
    assert parts is not None
    fields = yaml.safe_load(parts[0][4 : parts[0].rindex("---")])
    assert fields["metadata"]["archetype"] == "workflow-template"
    assert "archetype" not in fields


def test_reinstall_is_unchanged(tmp_path: Path) -> None:
    root = tmp_path / ".claude"
    install_driver.run_install("claude_code", harness_root=root)
    run = install_driver.run_install("claude_code", harness_root=root)
    outcomes = {
        r.operation: set() for r in run.results if r.operation in _SKILL_OPERATIONS
    }
    for result in run.results:
        if result.operation in _SKILL_OPERATIONS:
            outcomes[result.operation].add(result.outcome)
    assert outcomes == {"command_skills": {"unchanged"}, "native_skills": {"unchanged"}}
    preview = install_driver.run_install("claude_code", harness_root=root, dry_run=True)
    assert {r.outcome for r in preview.results if r.operation in _SKILL_OPERATIONS} == {
        "unchanged"
    }


def test_a_smaller_budget_adds_references_and_reinstall_removes_them(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / ".claude"
    references = root / "skills" / "plan-execute" / "references"
    install_driver.run_install("claude_code", harness_root=root)
    default_files = {p.name for p in references.iterdir()}

    original = conv.split_command_skill

    def tight(text: str) -> SplitSkill:
        return original(text, budget=0)

    monkeypatch.setattr(conv, "split_command_skill", tight)
    install_driver.run_install("claude_code", harness_root=root)
    tight_files = {p.name for p in references.iterdir()}
    assert default_files < tight_files

    monkeypatch.setattr(conv, "split_command_skill", original)
    run = install_driver.run_install("claude_code", harness_root=root)
    assert {p.name for p in references.iterdir()} == default_files
    assert any(
        r.operation == "command_skills" and r.outcome == "updated" for r in run.results
    )


def test_uninstall_removes_the_skill_directories(tmp_path: Path) -> None:
    root = tmp_path / ".claude"
    install_driver.run_install("claude_code", harness_root=root)
    assert (root / "skills" / "plan-execute" / "references").is_dir()
    install_driver.run_uninstall("claude_code", harness_root=root)
    for name in ("plan-execute", "elevate", "plan-suite"):
        assert not (root / "skills" / name).exists(), name


def test_other_harness_installs_write_no_references(tmp_path: Path) -> None:
    root = tmp_path / ".codex"
    install_driver.run_install("codex", harness_root=root)
    skills = tmp_path / ".agents" / "skills"
    assert (skills / "plan-execute" / "SKILL.md").is_file()
    assert not list(skills.glob("*/references/step-*.md"))
