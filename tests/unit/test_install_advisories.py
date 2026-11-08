# SPDX-License-Identifier: MIT

"""Install advisories for shared roots.

Installing the owner of a shared root (Codex for ``~/.agents/skills/``) puts
Apothem content in front of every reader, so the install names the readers.
Installing a reader while the shared root already holds another adapter's
Apothem content says where that content comes from.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from click.testing import CliRunner

from apothem.cli import main
from apothem.harnesses._shared import install_driver
from apothem.lib.codex_home import codex_home
from apothem.lib.harness_materializer import APOTHEM_BLOCK_BEGIN
from apothem.lib.harness_registry import SHARED_ROOTS, get_harness_entry
from apothem.lib.install_advisories import (
    _WHITE_SPACE,
    _apothem_agent_names,
    hook_review_advisories,
    instruction_override_advisories,
    mcp_profile_advisories,
    owner_of_record,
    shared_root_advisories,
)

_AGENTS_SKILLS = next(root for root in SHARED_ROOTS if root.path == "~/.agents/skills/")


def _skill(home: Path, name: str) -> None:
    folder = home / ".agents" / "skills" / name
    folder.mkdir(parents=True)
    (folder / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: x\n---\n", encoding="utf-8"
    )


def _agent_file(folder: Path, name: str) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / name).write_text("x\n", encoding="utf-8")


def _owner_entry(advisories: list[dict[str, object]], path: str) -> dict[str, object]:
    matches = [
        a
        for a in advisories
        if a["role"] == "owner" and str(a["message"]).startswith(path)
    ]
    assert len(matches) == 1, path
    return matches[0]


def test_owner_install_names_every_reader(tmp_path: Path) -> None:
    advisories = shared_root_advisories("codex", home=tmp_path, project=None)
    entry = _owner_entry(advisories, "~/.agents/skills/")
    assert entry["outcome"] == "advisory"
    assert entry["operation"] == "shared_root"
    assert entry["harness"] == "codex"
    assert entry["path"] == str(tmp_path / ".agents" / "skills")
    message = str(entry["message"])
    for reader in _AGENTS_SKILLS.readers:
        assert get_harness_entry(reader).display_name in message, reader
    assert "Qwen Code" in message


def test_owner_note_states_the_condition_a_reader_loads_the_root_under(
    tmp_path: Path,
) -> None:
    # Open-Claw skips ~/.agents/skills when its state directory is not the default.
    advisories = shared_root_advisories("codex", home=tmp_path, project=None)
    message = str(_owner_entry(advisories, "~/.agents/skills/")["message"])
    assert "Open-Claw (only under its default state directory)" in message
    assert "Cursor," in message  # an unconditional reader carries no qualifier
    assert "Cursor (" not in message


def test_codex_agents_folder_is_shared_with_cursor(tmp_path: Path) -> None:
    advisories = shared_root_advisories("codex", home=tmp_path, project=None)
    entry = _owner_entry(advisories, "~/.codex/agents/")
    assert entry["path"] == str(tmp_path / ".codex" / "agents")
    assert entry["readers"] == ["cursor"]
    # Where Codex writes the folder is not a condition on Cursor's reading it.
    assert str(entry["message"]) == (
        "~/.codex/agents/ is shared: Cursor also loads it. Installing or "
        "uninstalling Codex changes what that tool loads."
    )


def test_claude_code_agents_folder_is_shared_with_cursor(tmp_path: Path) -> None:
    advisories = shared_root_advisories("claude-code", home=tmp_path, project=None)
    entry = _owner_entry(advisories, "~/.claude/agents/")
    assert entry["path"] == str(tmp_path / ".claude" / "agents")
    assert entry["readers"] == ["cursor"]
    assert str(entry["message"]) == (
        "~/.claude/agents/ is shared: Cursor also loads it. Installing or "
        "uninstalling Claude Code changes what that tool loads."
    )


def test_claude_code_memory_file_is_shared_with_opencode_and_windsurf(
    tmp_path: Path,
) -> None:
    # ~/.claude/CLAUDE.md has two readers; the note reads as several tools, and
    # OpenCode 1 loads the file only when it has no global AGENTS.md of its own.
    advisories = shared_root_advisories("claude-code", home=tmp_path, project=None)
    entry = _owner_entry(advisories, "~/.claude/CLAUDE.md")
    assert entry["readers"] == ["opencode", "windsurf"]
    assert str(entry["message"]) == (
        "~/.claude/CLAUDE.md is shared: OpenCode (only in OpenCode 1, when its "
        "configuration folder holds no AGENTS.md), Windsurf also load it. "
        "Installing or uninstalling Claude Code changes what those tools load."
    )


def test_owner_note_agrees_with_a_single_reader(tmp_path: Path) -> None:
    # ~/.gemini/GEMINI.md has one reader (Gemini CLI), which loads it without a
    # condition; the note reads as one tool.
    advisories = shared_root_advisories("antigravity", home=tmp_path, project=None)
    entry = _owner_entry(advisories, "~/.gemini/GEMINI.md")
    assert entry["path"] == str(tmp_path / ".gemini" / "GEMINI.md")
    assert entry["readers"] == ["gemini-cli"]
    assert str(entry["message"]) == (
        "~/.gemini/GEMINI.md is shared: Gemini CLI also loads it. "
        "Installing or uninstalling Antigravity changes what that tool loads."
    )


def test_owner_note_gives_a_single_reader_its_condition(tmp_path: Path) -> None:
    # Zed loads only the first project instruction file in its list, and four
    # files come before .github/copilot-instructions.md.
    project = tmp_path / "proj"
    project.mkdir()
    advisories = shared_root_advisories(
        "github-copilot", home=tmp_path, project=project
    )
    entry = _owner_entry(advisories, "<project>/.github/copilot-instructions.md")
    assert entry["path"] == str(project / ".github" / "copilot-instructions.md")
    assert entry["readers"] == ["zed"]
    assert str(entry["message"]) == (
        "<project>/.github/copilot-instructions.md is shared: Zed (only when the "
        "project has no .rules, .cursorrules, .windsurfrules or .clinerules) also "
        "loads it. Installing or uninstalling GitHub Copilot changes what that "
        "tool loads."
    )


def test_cursor_rules_file_is_shared_with_hermes_and_windsurf(tmp_path: Path) -> None:
    # Hermes loads the file only as its last project context fallback, so the
    # note carries that condition; Windsurf loads it unconditionally.
    project = tmp_path / "proj"
    project.mkdir()
    advisories = shared_root_advisories("cursor", home=tmp_path, project=project)
    entry = _owner_entry(advisories, "<project>/.cursor/rules/apothem-rules.mdc")
    assert entry["path"] == str(project / ".cursor" / "rules" / "apothem-rules.mdc")
    assert entry["readers"] == ["hermes", "windsurf"]
    assert str(entry["message"]) == (
        "<project>/.cursor/rules/apothem-rules.mdc is shared: Hermes (only when the "
        "project has no .hermes.md, HERMES.md, AGENTS.override.md, AGENTS.md or "
        "CLAUDE.md), Windsurf also load it. Installing or uninstalling Cursor "
        "changes what those tools load."
    )


def test_project_agents_md_note_gives_the_first_match_conditions(
    tmp_path: Path,
) -> None:
    # Claude Code, under its default setting, reads AGENTS.md only without a
    # CLAUDE.md, .claude/CLAUDE.md or CLAUDE.local.md in the project folder, the
    # working folder or above it,
    # CodeBuddy uses it only without a CODEBUDDY.md, Codex and Hermes load an
    # AGENTS.override.md beside AGENTS.md instead of it, a .hermes.md or
    # HERMES.md comes first in Hermes's order, and Zed loads only the first
    # project instruction file in its list.
    project = tmp_path / "proj"
    project.mkdir()
    advisories = shared_root_advisories("kimi-code", home=tmp_path, project=project)
    assert str(_owner_entry(advisories, "<project>/AGENTS.md")["message"]) == (
        "<project>/AGENTS.md is shared: Antigravity, Claude Code (only in "
        "v2.1.277 or later, not under the claude-md or managed-only Project "
        "instructions setting, and under the default setting only when no "
        "CLAUDE.md, .claude/CLAUDE.md or CLAUDE.local.md is in the project "
        "folder, the working folder or a folder above it, not counting "
        "~/.claude/CLAUDE.md), CodeBuddy (only "
        "when the project has no CODEBUDDY.md), Codex (only when "
        "the project has no AGENTS.override.md beside it), Cursor, GitHub Copilot, "
        "Hermes (only when the project has no .hermes.md or HERMES.md and no "
        "AGENTS.override.md beside it), Kiro, OpenCode, Windsurf, Zed (only when "
        "the project has no .rules, .cursorrules, .windsurfrules, .clinerules, "
        ".github/copilot-instructions.md or AGENT.md) also load it. Installing or "
        "uninstalling Kimi Code changes what those tools load."
    )


def test_project_gemini_md_note_gives_the_zed_condition(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    project.mkdir()
    advisories = shared_root_advisories("gemini-cli", home=tmp_path, project=project)
    assert str(_owner_entry(advisories, "<project>/GEMINI.md")["message"]) == (
        "<project>/GEMINI.md is shared: Antigravity, GitHub Copilot, Zed (only when "
        "the project has no .rules, .cursorrules, .windsurfrules, .clinerules, "
        ".github/copilot-instructions.md, AGENT.md, AGENTS.md or CLAUDE.md) also "
        "load it. Installing or uninstalling Gemini CLI changes what those tools "
        "load."
    )


def test_hermes_install_names_the_install_whose_cursor_rules_block_it_finds(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    project = tmp_path / "proj"
    rules = project / ".cursor" / "rules" / "apothem-rules.mdc"
    rules.parent.mkdir(parents=True)
    rules.write_text(
        "<!-- BEGIN APOTHEM MANAGED BLOCK -->\nx\n<!-- END APOTHEM MANAGED BLOCK -->\n",
        encoding="utf-8",
    )
    found = shared_root_advisories(
        "hermes", home=home, project=project, holders=lambda _path: ["cursor"]
    )
    assert [str(a["message"]) for a in found if a["role"] == "reader"] == [
        "Hermes (only when the project has no .hermes.md, HERMES.md, "
        "AGENTS.override.md, AGENTS.md or CLAUDE.md) also loads "
        "<project>/.cursor/rules/apothem-rules.mdc, which holds Apothem content "
        "from the Cursor install."
    ]


@pytest.mark.parametrize(
    ("base", "relative", "owner", "owner_name"),
    [
        ("<project>", ".cursor/rules/apothem-rules.mdc", "cursor", "Cursor"),
        ("~", ".claude/CLAUDE.md", "claude-code", "Claude Code"),
    ],
)
def test_windsurf_install_names_the_install_whose_rules_block_devin_loads(
    tmp_path: Path, base: str, relative: str, owner: str, owner_name: str
) -> None:
    home = tmp_path / "home"
    project = tmp_path / "proj"
    target = (project if base == "<project>" else home) / relative
    target.parent.mkdir(parents=True)
    project.mkdir(exist_ok=True)

    def reader_notes() -> list[dict[str, object]]:
        found = shared_root_advisories(
            "windsurf", home=home, project=project, holders=lambda _path: [owner]
        )
        return [a for a in found if a["role"] == "reader"]

    target.write_text("# Team rules\n", encoding="utf-8")
    assert reader_notes() == []

    target.write_text(
        "<!-- BEGIN APOTHEM MANAGED BLOCK -->\nx\n<!-- END APOTHEM MANAGED BLOCK -->\n",
        encoding="utf-8",
    )
    notes = reader_notes()
    assert len(notes) == 1
    assert notes[0]["path"] == str(target)
    assert notes[0]["owner_of_record"] == owner
    assert str(notes[0]["message"]) == (
        f"Windsurf also loads {base}/{relative}, which holds Apothem content from "
        f"the {owner_name} install."
    )


def test_reader_install_names_the_owner_when_apothem_content_is_present(
    tmp_path: Path,
) -> None:
    _skill(tmp_path, "workflow")  # an Apothem skill name
    advisories = shared_root_advisories("gemini-cli", home=tmp_path, project=None)
    reader = [a for a in advisories if a["role"] == "reader"]
    assert len(reader) == 1
    message = str(reader[0]["message"])
    assert "~/.agents/skills/" in message
    # Nothing says which install wrote the content, so the note does not guess.
    assert message.endswith("holds Apothem content from an Apothem install.")


@pytest.mark.parametrize("public_id", ["cursor", "github-copilot", "windsurf", "zed"])
def test_a_co_installer_gets_a_holder_note_whether_or_not_the_folder_has_content(
    tmp_path: Path, public_id: str
) -> None:
    # The four write the same ~/.agents/skills/ Codex does; their own install is
    # what fills it, so the note says the folder stays until the last install
    # that uses it is uninstalled, and never blames the Codex install.
    for populated in (False, True):
        if populated:
            _skill(tmp_path, "workflow")
        advisories = shared_root_advisories(public_id, home=tmp_path, project=None)
        holder = [a for a in advisories if a["role"] == "holder"]
        assert len(holder) == 1
        message = str(holder[0]["message"])
        assert message.startswith("~/.agents/skills/ is shared: ")
        assert "Codex" in message
        assert get_harness_entry(public_id).display_name not in message
        assert message.endswith(
            "It stays until the last Apothem install that uses it is uninstalled."
        )
        assert [a for a in advisories if a["role"] == "reader"] == []


def test_the_rules_and_templates_corpus_raises_no_advisory(tmp_path: Path) -> None:
    for public_id in ("codex", "cursor", "kiro"):
        advisories = shared_root_advisories(public_id, home=tmp_path, project=None)
        assert not any("apothem" in str(a["path"]) for a in advisories)


def test_qwen_code_install_names_codex_when_apothem_skills_are_present(
    tmp_path: Path,
) -> None:
    _skill(tmp_path, "workflow")
    advisories = shared_root_advisories("qwen-code", home=tmp_path, project=None)
    reader = [a for a in advisories if a["role"] == "reader"]
    assert len(reader) == 1
    assert str(reader[0]["message"]) == (
        "Qwen Code also loads ~/.agents/skills/, which holds Apothem content "
        "from an Apothem install."
    )


def test_reader_note_carries_the_condition_the_reader_loads_the_root_under(
    tmp_path: Path,
) -> None:
    _skill(tmp_path, "workflow")
    advisories = shared_root_advisories("open-claw", home=tmp_path, project=None)
    reader = [a for a in advisories if a["role"] == "reader"]
    assert len(reader) == 1
    assert str(reader[0]["message"]) == (
        "Open-Claw (only under its default state directory) also loads "
        "~/.agents/skills/, which holds Apothem content from an Apothem install."
    )


def test_opencode_reader_note_carries_its_claude_md_condition(tmp_path: Path) -> None:
    claude_md = tmp_path / ".claude" / "CLAUDE.md"
    claude_md.parent.mkdir()
    claude_md.write_text(
        "<!-- BEGIN APOTHEM MANAGED BLOCK -->\nx\n<!-- END APOTHEM MANAGED BLOCK -->\n",
        encoding="utf-8",
    )
    advisories = shared_root_advisories(
        "opencode", home=tmp_path, project=None, holders=lambda _path: ["claude-code"]
    )
    reader = [
        a for a in advisories if a["role"] == "reader" and a["path"] == str(claude_md)
    ]
    assert len(reader) == 1
    assert str(reader[0]["message"]) == (
        "OpenCode (only in OpenCode 1, when its configuration folder holds no "
        "AGENTS.md) also loads ~/.claude/CLAUDE.md, which holds Apothem content "
        "from the Claude Code install."
    )


@pytest.mark.parametrize(
    ("folder", "filename", "owner", "owner_name"),
    [
        (".claude/agents", "test-runner.md", "claude-code", "Claude Code"),
        (".codex/agents", "test-runner.toml", "codex", "Codex"),
    ],
)
def test_cursor_install_names_the_owner_of_record_when_apothem_agents_are_present(
    tmp_path: Path, folder: str, filename: str, owner: str, owner_name: str
) -> None:
    _agent_file(tmp_path / folder, filename)  # an Apothem agent name
    advisories = shared_root_advisories(
        "cursor", home=tmp_path, project=None, holders=lambda _path: [owner]
    )
    reader = [a for a in advisories if a["role"] == "reader"]
    assert len(reader) == 1
    message = str(reader[0]["message"])
    assert f"~/{folder}/" in message
    assert f"from the {owner_name} install" in message
    assert reader[0]["owner_of_record"] == owner
    assert reader[0]["holders"] == [owner]


def test_the_owner_of_record_is_the_registered_owner_while_it_holds_the_folder() -> (
    None
):
    assert owner_of_record(_AGENTS_SKILLS, ["cursor", "codex", "zed"]) == "codex"


def test_the_owner_of_record_is_the_oldest_holder_once_the_owner_is_gone() -> None:
    assert owner_of_record(_AGENTS_SKILLS, ["zed", "cursor"]) == "zed"
    assert owner_of_record(_AGENTS_SKILLS, []) is None


def test_a_reader_note_names_the_install_that_holds_the_folder_not_the_registered_owner(
    tmp_path: Path,
) -> None:
    _skill(tmp_path, "workflow")
    advisories = shared_root_advisories(
        "qwen-code", home=tmp_path, project=None, holders=lambda _path: ["cursor"]
    )
    reader = [a for a in advisories if a["role"] == "reader"]
    assert len(reader) == 1
    assert str(reader[0]["message"]) == (
        "Qwen Code also loads ~/.agents/skills/, which holds Apothem content "
        "from the Cursor install."
    )
    assert reader[0]["owner"] == "codex"
    assert reader[0]["owner_of_record"] == "cursor"


def test_holder_and_owner_notes_name_the_installs_using_the_folder(
    tmp_path: Path,
) -> None:
    def holders(_path: Path) -> list[str]:
        return ["codex", "cursor"]

    for public_id, role in (("cursor", "holder"), ("codex", "owner")):
        advisories = shared_root_advisories(
            public_id, home=tmp_path, project=None, holders=holders
        )
        note = next(
            a
            for a in advisories
            if a["role"] == role and str(a["message"]).startswith("~/.agents/skills/")
        )
        assert str(note["message"]).endswith("Installs using it now: Codex, Cursor.")
        assert note["holders"] == ["codex", "cursor"]
        assert note["owner_of_record"] == "codex"


def test_reader_install_is_silent_for_agent_files_apothem_does_not_write(
    tmp_path: Path,
) -> None:
    _agent_file(tmp_path / ".claude" / "agents", "someone-elses-agent.md")
    _agent_file(tmp_path / ".codex" / "agents", "someone-elses-agent.toml")
    advisories = shared_root_advisories("cursor", home=tmp_path, project=None)
    assert [a for a in advisories if a["role"] == "reader"] == []


def test_reader_install_is_silent_without_apothem_content(tmp_path: Path) -> None:
    _skill(tmp_path, "someone-elses-skill")
    advisories = shared_root_advisories("cursor", home=tmp_path, project=None)
    assert [a for a in advisories if a["role"] == "reader"] == []


def test_project_anchor_reader_needs_the_managed_block(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    project.mkdir()
    agents = project / "AGENTS.md"
    agents.write_text("# Team instructions\n", encoding="utf-8")

    def reader_notes() -> list[dict[str, object]]:
        found = shared_root_advisories(
            "zed", home=tmp_path, project=project, holders=lambda _path: ["kimi-code"]
        )
        return [a for a in found if a["role"] == "reader"]

    assert reader_notes() == []

    agents.write_text(
        "<!-- BEGIN APOTHEM MANAGED BLOCK -->\nx\n<!-- END APOTHEM MANAGED BLOCK -->\n",
        encoding="utf-8",
    )
    advisories = reader_notes()
    assert len(advisories) == 1
    message = str(advisories[0]["message"])
    assert "Kimi Code" in message
    # Zed loads AGENTS.md only when no earlier file in its list is there.
    assert message.startswith("Zed (only when the project has no .rules, ")


def test_project_roots_are_skipped_without_a_project(tmp_path: Path) -> None:
    advisories = shared_root_advisories("kimi-code", home=tmp_path, project=None)
    assert advisories == []


def test_unrelated_harness_gets_no_advisory(tmp_path: Path) -> None:
    _skill(tmp_path, "workflow")
    assert shared_root_advisories("glm", home=tmp_path, project=tmp_path) == []


@pytest.fixture
def cli_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setenv("APOTHEM_HOME", str(tmp_path / "apothem-home"))
    monkeypatch.setenv("CODEX_HOME", str(home / ".codex"))
    monkeypatch.setattr(install_driver, "BACKUP_ROOT", tmp_path / "backups")
    profile = tmp_path / "profile.yaml"
    profile.write_text("identity:\n  name: Test User\n", encoding="utf-8")
    return home, profile


def test_cli_codex_install_lists_the_readers(cli_env: tuple[Path, Path]) -> None:
    _home, profile = cli_env
    runner = CliRunner()
    args = ["install", "--harness", "codex", "--profile", str(profile), "--no-color"]

    plain = runner.invoke(main, args)
    assert plain.exit_code == 0, plain.output
    flat = " ".join(plain.output.split())
    assert "Note: codex - ~/.agents/skills/ is shared" in flat
    assert "Cursor" in flat

    payload = json.loads(runner.invoke(main, [*args, "--format", "json"]).output)
    shared = [w for w in payload["warnings"] if w.get("operation") == "shared_root"]
    assert {w["owner"] for w in shared} == {"codex"}
    assert len(shared) == 2  # ~/.agents/skills/ and ~/.codex/agents/
    assert {w["outcome"] for w in shared} == {"advisory"}


def test_cli_reader_installs_name_the_cursor_install_in_its_rules_file(
    cli_env: tuple[Path, Path], tmp_path: Path
) -> None:
    _home, profile = cli_env
    project = tmp_path / "project"
    project.mkdir()
    rules = project / ".cursor" / "rules" / "apothem-rules.mdc"
    runner = CliRunner()

    def shared_notes(harness: str, role: str) -> list[dict[str, object]]:
        args = ["install", "--harness", harness, "--project", str(project)]
        result = runner.invoke(
            main, [*args, "--profile", str(profile), "--no-color", "--format", "json"]
        )
        assert result.exit_code == 0, result.output
        return [
            w
            for w in json.loads(result.output)["warnings"]
            if w.get("operation") == "shared_root"
            and w.get("role") == role
            and Path(str(w["path"])) == rules
        ]

    # The Cursor install writes the rules file and names Hermes and Windsurf as
    # its readers.
    owner = shared_notes("cursor", "owner")
    assert [w["readers"] for w in owner] == [["hermes", "windsurf"]]
    # The Windsurf install then says the file holds the Cursor install's block,
    # and so does a Hermes install given the project, with its condition.
    for harness, opening in (
        ("windsurf", "Windsurf also loads "),
        (
            "hermes",
            "Hermes (only when the project has no .hermes.md, HERMES.md, "
            "AGENTS.override.md, AGENTS.md or CLAUDE.md) also loads ",
        ),
    ):
        reader = shared_notes(harness, "reader")
        assert [w["owner_of_record"] for w in reader] == ["cursor"]
        message = str(reader[0]["message"])
        assert message.startswith(opening)
        assert "from the Cursor install" in message


# --- Hook review advisories ---------------------------------------------------


def test_codebuddy_hook_registration_asks_for_a_restart_and_a_review(
    tmp_path: Path,
) -> None:
    [advisory] = hook_review_advisories("codebuddy", project=tmp_path)
    assert advisory["harness"] == "codebuddy"
    assert advisory["outcome"] == "advisory"
    assert advisory["operation"] == "hook_review"
    path = tmp_path / ".codebuddy" / "settings.local.json"
    assert advisory["path"] == str(path)
    message = " ".join(str(advisory["message"]).split())
    assert str(path) in message
    assert "restart CodeBuddy" in message
    assert "/hooks panel" in message
    assert "Git Bash" in message


def test_a_harness_with_no_review_step_gets_no_hook_advisory(tmp_path: Path) -> None:
    for harness in ("claude-code", "codex", "glm", "trae", "zed"):
        assert hook_review_advisories(harness, project=tmp_path) == []


def test_windsurf_hook_registration_names_restricted_mode_and_the_local_file(
    tmp_path: Path,
) -> None:
    review, _import = hook_review_advisories("windsurf", project=tmp_path)
    assert review["harness"] == "windsurf"
    assert review["operation"] == "hook_review"
    path = tmp_path / ".devin" / "config.local.json"
    assert review["path"] == str(path)
    message = " ".join(str(review["message"]).split())
    assert str(path) in message
    assert "Restricted Mode" in message
    assert "gitignored" in message
    # Devin excludes local config files from git itself (global-vs-local.md,
    # retrieved 2026-10-28), so the note no longer tells the operator to do it.
    assert ".git/info/exclude" in message
    assert "keep it out of version control" not in message
    assert "Windows" in message


def test_cursor_hook_registration_names_the_committed_file_hazard(
    tmp_path: Path,
) -> None:
    review, _import = hook_review_advisories("cursor", project=tmp_path)
    assert review["harness"] == "cursor"
    assert review["operation"] == "hook_review"
    path = tmp_path / ".cursor" / "hooks.json"
    assert review["path"] == str(path)
    message = " ".join(str(review["message"]).split())
    assert str(path) in message
    assert "checked into version control" in message
    assert "commit the file only if your team shares that layout" in message
    assert "your own entries and keys in it stay" in message
    assert "PowerShell" in message


def test_windsurf_names_the_switch_that_stops_the_claude_code_hooks_running_too(
    tmp_path: Path,
) -> None:
    _review, imported = hook_review_advisories("windsurf", project=tmp_path)
    assert imported["operation"] == "hook_import"
    assert imported["outcome"] == "advisory"
    message = " ".join(str(imported["message"]).split())
    assert "read_config_from.claude" in message
    assert '"claude": false' in message
    assert "~/.config/devin/config.json" in message
    assert "%APPDATA%/devin/config.json" in message
    # The vendor command and the Claude Code copy share one marker; the
    # PostToolUse counter is not de-duplicated.
    assert "the Claude Code copy of it share one marker per session" in message
    assert "whichever runs second is silent" in message
    assert "separate command" not in message
    assert "PostToolUse counter runs in both places" in message
    assert "rules, skills, commands and MCP servers" in message


def test_cursor_names_the_switch_that_stops_the_claude_code_hooks_running_too(
    tmp_path: Path,
) -> None:
    _review, imported = hook_review_advisories("cursor", project=tmp_path)
    assert imported["operation"] == "hook_import"
    message = " ".join(str(imported["message"]).split())
    assert "Include Third-Party Plugins, Skills, and Other Configs" in message
    assert "Third-Party Imports" in message
    assert "runs every matching hook from every source" in message
    assert "the Claude Code copy of it share one marker per session" in message
    assert "whichever runs second is silent" in message
    assert "separate command" not in message
    assert "PostToolUse counters" in message


def test_only_the_harnesses_that_import_claude_code_hooks_get_the_import_note(
    tmp_path: Path,
) -> None:
    for harness in ("codebuddy", "kiro", "github-copilot"):
        operations = [
            a["operation"] for a in hook_review_advisories(harness, project=tmp_path)
        ]
        assert operations == ["hook_review"], harness


def test_kiro_hook_registration_asks_for_the_workspace_trust(tmp_path: Path) -> None:
    [advisory] = hook_review_advisories("kiro", project=tmp_path)
    assert advisory["harness"] == "kiro"
    assert advisory["operation"] == "hook_review"
    path = tmp_path / ".kiro" / "hooks" / "apothem.json"
    assert advisory["path"] == str(path)
    message = " ".join(str(advisory["message"]).split())
    assert str(path) in message
    assert "Trust this workspace?" in message
    assert "kiro-cli --v3" in message
    assert "Web sessions run no hooks" in message


def test_copilot_hook_registration_names_the_committed_file_hazard(
    tmp_path: Path,
) -> None:
    [advisory] = hook_review_advisories("github-copilot", project=tmp_path)
    assert advisory["harness"] == "github-copilot"
    path = tmp_path / ".github" / "hooks" / "apothem.json"
    assert advisory["path"] == str(path)
    message = " ".join(str(advisory["message"]).split())
    assert str(path) in message
    assert "commit it only if your team shares that layout" in message
    assert "cloud agent" in message
    assert "bash command" in message


def test_a_hook_advisory_needs_a_project() -> None:
    assert hook_review_advisories("codebuddy", project=None) == []
    assert hook_review_advisories("kiro", project=None) == []
    assert hook_review_advisories("github-copilot", project=None) == []
    assert hook_review_advisories("windsurf", project=None) == []
    assert hook_review_advisories("cursor", project=None) == []


def test_cli_codebuddy_install_prints_the_hook_review_note(
    cli_env: tuple[Path, Path], tmp_path: Path
) -> None:
    _home, profile = cli_env
    project = tmp_path / "project"
    project.mkdir()
    runner = CliRunner()
    args = [
        "install",
        "--harness",
        "codebuddy",
        "--project",
        str(project),
        "--profile",
        str(profile),
        "--no-color",
    ]

    plain = runner.invoke(main, args)
    assert plain.exit_code == 0, plain.output
    flat = " ".join(plain.output.split())
    assert (
        "Note: codebuddy - Apothem registers its SessionStart and PostToolUse" in flat
    )
    assert "/hooks panel" in flat

    payload = json.loads(runner.invoke(main, [*args, "--format", "json"]).output)
    review = [w for w in payload["warnings"] if w.get("operation") == "hook_review"]
    assert len(review) == 1
    assert review[0]["harness"] == "codebuddy"
    assert review[0]["outcome"] == "advisory"

    # A dry run lists the note too, and writes nothing.
    other = tmp_path / "dry-project"
    other.mkdir()
    dry_args = [
        "install",
        "--harness",
        "codebuddy",
        "--project",
        str(other),
        "--profile",
        str(profile),
        "--no-color",
        "--dry-run",
    ]
    dry = runner.invoke(main, dry_args)
    assert dry.exit_code == 0, dry.output
    assert "/hooks panel" in " ".join(dry.output.split())
    assert not (other / ".codebuddy" / "settings.local.json").exists()


@pytest.mark.parametrize(
    ("harness", "hook_file", "switch"),
    [
        ("cursor", ".cursor/hooks.json", "Third-Party Imports"),
        ("windsurf", ".devin/config.local.json", "read_config_from.claude"),
    ],
)
def test_cli_install_prints_the_review_and_the_import_notes(
    cli_env: tuple[Path, Path],
    tmp_path: Path,
    harness: str,
    hook_file: str,
    switch: str,
) -> None:
    _home, profile = cli_env
    project = tmp_path / "project"
    project.mkdir()
    runner = CliRunner()
    args = [
        "install",
        "--harness",
        harness,
        "--project",
        str(project),
        "--profile",
        str(profile),
        "--no-color",
    ]

    plain = runner.invoke(main, args)
    assert plain.exit_code == 0, plain.output
    flat = " ".join(plain.output.split())
    assert switch in flat

    payload = json.loads(runner.invoke(main, [*args, "--format", "json"]).output)
    notes = [
        w
        for w in payload["warnings"]
        if w.get("operation") in {"hook_review", "hook_import"}
    ]
    assert [(w["harness"], w["operation"], w["outcome"]) for w in notes] == [
        (harness, "hook_review", "advisory"),
        (harness, "hook_import", "advisory"),
    ]
    assert all(Path(w["path"]) == project / hook_file for w in notes)

    # A dry run lists the notes too, and writes nothing.
    other = tmp_path / "dry-project"
    other.mkdir()
    dry_args = [
        "install",
        "--harness",
        harness,
        "--project",
        str(other),
        "--profile",
        str(profile),
        "--no-color",
        "--dry-run",
    ]
    dry = runner.invoke(main, dry_args)
    assert dry.exit_code == 0, dry.output
    assert switch in " ".join(dry.output.split())
    assert not (other / hook_file).exists()


# --- MCP profile advisories ---------------------------------------------------

_FAKE_GITHUB_TOKEN = "ghp_" + "0123456789abcdefghijABCDEFGHIJ0123"
_FAKE_API_KEY = "sk-" + "abcdefghijklmnopqrstuvwxyz012345"


def _profile(servers: dict[str, object], **extra: object) -> dict[str, object]:
    return {"identity": {"name": "Test User"}, "mcp_servers": servers, **extra}


def _fields(advisories: list[dict[str, object]], operation: str) -> list[object]:
    return [a["field"] for a in advisories if a["operation"] == operation]


def test_sse_transport_gets_a_deprecation_advisory(tmp_path: Path) -> None:
    profile = _profile(
        {"legacy": {"transport": "sse", "url": "https://mcp.example.com/sse"}}
    )
    advisories = mcp_profile_advisories(profile, tmp_path / "profile.yaml")
    assert _fields(advisories, "mcp_deprecated_transport") == [
        "mcp_servers.legacy.transport"
    ]
    entry = advisories[0]
    assert entry["outcome"] == "advisory"
    assert entry["harness"] is None
    assert "streamable-http" in str(entry["message"])


@pytest.mark.parametrize(
    ("url", "warned"),
    [
        ("http://mcp.example.com/mcp", True),
        ("http://10.0.0.5:8080/mcp", True),
        ("https://mcp.example.com/mcp", False),
        ("http://localhost:3000/mcp", False),
        ("http://127.0.0.1:3000/mcp", False),
        ("http://[::1]:3000/mcp", False),
    ],
)
def test_plain_http_to_a_remote_host_gets_an_advisory(
    tmp_path: Path, url: str, warned: bool
) -> None:
    profile = _profile({"api": {"transport": "streamable-http", "url": url}})
    advisories = mcp_profile_advisories(profile, tmp_path / "profile.yaml")
    expected = ["mcp_servers.api.url"] if warned else []
    assert _fields(advisories, "mcp_plain_http") == expected


@pytest.mark.parametrize(
    ("location", "key", "value"),
    [
        ("headers", "Authorization", f"Bearer {_FAKE_GITHUB_TOKEN}"),
        ("headers", "Authorization", "Bearer " + "a1b2c3d4e5f6g7h8i9j0k1l2m3"),
        ("env", "OPENAI_API_KEY", _FAKE_API_KEY),
        ("env", "SLACK_TOKEN", "xoxb-" + "1234567890-abcdefghij"),
        ("env", "GITHUB_TOKEN", _FAKE_GITHUB_TOKEN),
    ],
)
def test_literal_credentials_get_an_advisory_without_echoing_them(
    tmp_path: Path, location: str, key: str, value: str
) -> None:
    server: dict[str, object] = {"transport": "streamable-http"}
    server["url"] = "https://mcp.example.com/mcp"
    server[location] = {key: value}
    advisories = mcp_profile_advisories(_profile({"gh": server}), tmp_path / "p.yaml")
    assert _fields(advisories, "mcp_literal_credential") == [
        f"mcp_servers.gh.{location}.{key}"
    ]
    message = str(advisories[0]["message"])
    assert "${" in message
    assert value.split()[-1] not in json.dumps(advisories)


@pytest.mark.parametrize(
    "value",
    ["Bearer ${GITHUB_TOKEN}", "${OPENAI_API_KEY}", "Bearer short", "application/json"],
)
def test_references_and_ordinary_values_get_no_credential_advisory(
    tmp_path: Path, value: str
) -> None:
    server = {
        "transport": "streamable-http",
        "url": "https://mcp.example.com/mcp",
        "headers": {"Authorization": value},
    }
    advisories = mcp_profile_advisories(_profile({"gh": server}), tmp_path / "p.yaml")
    assert _fields(advisories, "mcp_literal_credential") == []


def test_harness_override_servers_are_checked(tmp_path: Path) -> None:
    profile = _profile(
        {},
        harnesses={
            "qwen-code": {
                "mcp_servers": {
                    "legacy": {"transport": "sse", "url": "http://mcp.example.com"}
                }
            }
        },
    )
    advisories = mcp_profile_advisories(profile, tmp_path / "profile.yaml")
    fields = [a["field"] for a in advisories]
    assert "harnesses.qwen-code.mcp_servers.legacy.transport" in fields
    assert "harnesses.qwen-code.mcp_servers.legacy.url" in fields


def test_cli_install_prints_the_mcp_advisories(cli_env: tuple[Path, Path]) -> None:
    _home, profile = cli_env
    profile.write_text(
        "identity:\n  name: Test User\n"
        "mcp_servers:\n"
        "  gh:\n"
        "    transport: sse\n"
        "    url: https://mcp.example.com/sse\n"
        "    headers:\n"
        f"      Authorization: Bearer {_FAKE_GITHUB_TOKEN}\n",
        encoding="utf-8",
    )
    result = CliRunner().invoke(
        main,
        ["install", "--harness", "qwen-code", "--profile", str(profile), "--no-color"],
    )
    assert result.exit_code == 0, result.output
    flat = " ".join(result.output.split())
    assert "mcp_servers.gh.headers.Authorization" in flat
    assert "streamable-http" in flat
    assert _FAKE_GITHUB_TOKEN not in result.output


# --- Instruction-file override advisories --------------------------------------


def _codex_override(folder: Path, text: str) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    override = folder / "AGENTS.override.md"
    override.write_text(text, encoding="utf-8")
    return override


def _override_notes(payload: dict[str, object]) -> list[dict[str, object]]:
    warnings = payload["warnings"]
    assert isinstance(warnings, list)
    return [w for w in warnings if w.get("operation") == "instruction_override"]


@pytest.fixture
def default_codex_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Return ``<home>/.codex`` with ``CODEX_HOME`` unset; *tmp_path* is home."""
    monkeypatch.delenv("CODEX_HOME", raising=False)
    return tmp_path / ".codex"


def test_a_codex_override_with_text_hides_the_apothem_block(
    tmp_path: Path, default_codex_home: Path
) -> None:
    # Codex reads only the first non-empty of AGENTS.override.md and AGENTS.md in
    # its home folder, so an override with text hides the block in AGENTS.md.
    override = _codex_override(default_codex_home, "# Personal rules\n")
    [note] = instruction_override_advisories("codex", home=tmp_path)
    assert note["harness"] == "codex"
    assert note["outcome"] == "advisory"
    assert note["operation"] == "instruction_override"
    assert note["path"] == str(override)
    assert note["target"] == str(default_codex_home / "AGENTS.md")
    message = " ".join(str(note["message"]).split())
    assert "Codex loads AGENTS.override.md instead of AGENTS.md" in message
    assert "first of AGENTS.override.md and AGENTS.md there that has text" in message


def test_the_codex_override_check_follows_codex_home(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    folder = tmp_path / "codex-elsewhere"
    monkeypatch.setenv("CODEX_HOME", str(folder))
    _codex_override(tmp_path / ".codex", "# Not the folder Codex reads\n")
    override = _codex_override(folder, "# Personal rules\n")
    [note] = instruction_override_advisories("codex", home=tmp_path)
    assert note["path"] == str(override)
    assert note["target"] == str(folder / "AGENTS.md")


@pytest.mark.parametrize("text", ["", " \n\t\r\n", "\u00a0\u3000\u2028\u205f"])
def test_an_empty_codex_override_falls_through_without_a_note(
    tmp_path: Path, default_codex_home: Path, text: str
) -> None:
    _codex_override(default_codex_home, text)
    assert instruction_override_advisories("codex", home=tmp_path) == []


def test_no_codex_override_means_no_note(
    tmp_path: Path, default_codex_home: Path
) -> None:
    default_codex_home.mkdir()
    assert instruction_override_advisories("codex", home=tmp_path) == []


def test_a_folder_named_like_the_codex_override_is_skipped(
    tmp_path: Path, default_codex_home: Path
) -> None:
    # Codex skips a candidate that is not a file.
    (default_codex_home / "AGENTS.override.md").mkdir(parents=True)
    assert instruction_override_advisories("codex", home=tmp_path) == []


def test_a_harness_without_a_hiding_file_gets_no_override_note(
    tmp_path: Path, default_codex_home: Path
) -> None:
    _codex_override(default_codex_home, "# Personal rules\n")
    assert instruction_override_advisories("claude-code", home=tmp_path) == []


def test_cli_codex_install_update_and_verify_name_a_hiding_override(
    cli_env: tuple[Path, Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _home, profile = cli_env
    folder = tmp_path / "codex-elsewhere"
    monkeypatch.setenv("CODEX_HOME", str(folder))
    override = _codex_override(folder, "# Personal rules\n")
    expected = [(str(override), str(folder / "AGENTS.md"))]
    runner = CliRunner()
    for args in (
        ["install", "--harness", "codex", "--profile", str(profile)],
        ["update", "--harness", "codex", "--profile", str(profile)],
        ["verify", "--harness", "codex"],
    ):
        result = runner.invoke(main, [*args, "--no-color", "--format", "json"])
        assert result.exit_code == 0, result.output
        notes = _override_notes(json.loads(result.output))
        assert [(n["path"], n["target"]) for n in notes] == expected, args[0]
    assert (folder / "AGENTS.md").is_file()

    # The note does not fail verify; plain mode prints it under the row.
    plain = runner.invoke(main, ["verify", "--harness", "codex", "--no-color"])
    assert plain.exit_code == 0, plain.output
    flat = " ".join(plain.output.split())
    assert "Note: Codex loads AGENTS.override.md instead of AGENTS.md" in flat


@pytest.mark.parametrize("text", [None, "", "\n \n"])
def test_cli_codex_install_says_nothing_without_an_override_that_has_text(
    cli_env: tuple[Path, Path],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    text: str | None,
) -> None:
    _home, profile = cli_env
    folder = tmp_path / "codex-elsewhere"
    monkeypatch.setenv("CODEX_HOME", str(folder))
    if text is not None:
        _codex_override(folder, text)
    args = ["install", "--harness", "codex", "--profile", str(profile)]
    result = CliRunner().invoke(main, [*args, "--no-color", "--format", "json"])
    assert result.exit_code == 0, result.output
    assert _override_notes(json.loads(result.output)) == []
    assert (folder / "AGENTS.md").is_file()


def test_codex_counts_the_separator_controls_python_strips_as_text(
    tmp_path: Path, default_codex_home: Path
) -> None:
    # Rust's str::trim keeps U+001C to U+001F, so Codex loads such a file.
    _codex_override(default_codex_home, "\x1c\x1d\x1e\x1f")
    assert len(instruction_override_advisories("codex", home=tmp_path)) == 1


def test_a_hard_link_to_agents_md_counts_as_a_copy(
    tmp_path: Path, default_codex_home: Path
) -> None:
    # An install replaces AGENTS.md, which splits a hard link into a copy that
    # holds the old block, so the note says to remove it.
    default_codex_home.mkdir(parents=True)
    target = default_codex_home / "AGENTS.md"
    target.write_text(f"{APOTHEM_BLOCK_BEGIN}\n# Rules\n", encoding="utf-8")
    try:
        os.link(target, default_codex_home / "AGENTS.override.md")
    except OSError as exc:
        pytest.skip(f"hard links are not available here: {exc}")
    [note] = instruction_override_advisories("codex", home=tmp_path)
    assert "holds its own copy of the Apothem block" in str(note["message"])


def test_the_verify_note_needs_the_apothem_block_in_agents_md(
    tmp_path: Path, default_codex_home: Path
) -> None:
    _codex_override(default_codex_home, "# Personal rules\n")
    assert (
        instruction_override_advisories("codex", home=tmp_path, require_block=True)
        == []
    )
    (default_codex_home / "AGENTS.md").write_text(
        f"{APOTHEM_BLOCK_BEGIN}\n# Rules\n", encoding="utf-8"
    )
    notes = instruction_override_advisories("codex", home=tmp_path, require_block=True)
    assert len(notes) == 1


@pytest.mark.parametrize("configured", [False, True])
def test_the_advisory_and_the_adapter_use_the_same_codex_home(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, configured: bool
) -> None:
    from apothem.harnesses.codex import CodexAdapter

    if configured:
        monkeypatch.setenv("CODEX_HOME", str(tmp_path / "codex-elsewhere"))
    else:
        monkeypatch.delenv("CODEX_HOME", raising=False)
    _codex_override(codex_home(Path.home()), "# Personal rules\n")
    [note] = instruction_override_advisories("codex", home=Path.home())
    assert note["target"] == str(CodexAdapter().output_path)


def test_the_codex_agents_note_follows_codex_home(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Cursor reads ~/.codex/agents/, so the note names it only while the Codex
    # install writes its agents there.
    agents = str(tmp_path / ".codex" / "agents")
    skills = str(tmp_path / ".agents" / "skills")
    monkeypatch.delenv("CODEX_HOME", raising=False)
    advisories = shared_root_advisories("codex", home=tmp_path, project=None)
    assert {agents, skills} <= {a["path"] for a in advisories}
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "codex-elsewhere"))
    advisories = shared_root_advisories("codex", home=tmp_path, project=None)
    paths = {a["path"] for a in advisories}
    assert agents not in paths
    assert skills in paths


def test_cli_codex_dry_runs_and_the_plain_line_name_a_hiding_override(
    cli_env: tuple[Path, Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _home, profile = cli_env
    folder = tmp_path / "codex-elsewhere"
    monkeypatch.setenv("CODEX_HOME", str(folder))
    override = _codex_override(folder, "# Personal rules\n")
    runner = CliRunner()
    for verb in ("install", "update"):
        args = [verb, "--harness", "codex", "--profile", str(profile), "--dry-run"]
        result = runner.invoke(main, [*args, "--no-color", "--format", "json"])
        assert result.exit_code == 0, result.output
        notes = _override_notes(json.loads(result.output))
        assert [n["path"] for n in notes] == [str(override)], verb
    assert not (folder / "AGENTS.md").exists()

    args = ["install", "--harness", "codex", "--profile", str(profile), "--no-color"]
    plain = runner.invoke(main, args)
    assert plain.exit_code == 0, plain.output
    flat = " ".join(plain.output.split())
    assert "Note: codex - Codex loads AGENTS.override.md instead of AGENTS.md" in flat


def test_cli_codex_verify_gives_no_note_without_the_apothem_block(
    cli_env: tuple[Path, Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _home, profile = cli_env
    folder = tmp_path / "codex-elsewhere"
    monkeypatch.setenv("CODEX_HOME", str(folder))
    _codex_override(folder, "# Personal rules\n")
    runner = CliRunner()
    verify = ["verify", "--harness", "codex", "--no-color", "--format", "json"]
    # Before an install there is no block to hide; verify fails without a note.
    before = runner.invoke(main, verify)
    assert _override_notes(json.loads(before.output)) == []

    install = ["install", "--harness", "codex", "--profile", str(profile)]
    assert runner.invoke(main, [*install, "--no-color"]).exit_code == 0
    uninstall = ["uninstall", "--harness", "codex", "--yes", "--no-color"]
    removed = runner.invoke(main, uninstall)
    assert removed.exit_code == 0, removed.output
    after = runner.invoke(main, verify)
    assert _override_notes(json.loads(after.output)) == []


def test_a_symbolic_link_to_agents_md_hides_nothing(
    tmp_path: Path, default_codex_home: Path
) -> None:
    default_codex_home.mkdir(parents=True)
    target = default_codex_home / "AGENTS.md"
    target.write_text(f"{APOTHEM_BLOCK_BEGIN}\n# Rules\n", encoding="utf-8")
    try:
        (default_codex_home / "AGENTS.override.md").symlink_to(target)
    except OSError as exc:
        pytest.skip(f"symlinks are not available here: {exc}")
    assert instruction_override_advisories("codex", home=tmp_path) == []


def test_the_verify_note_needs_the_block_not_just_agents_md(
    tmp_path: Path, default_codex_home: Path
) -> None:
    _codex_override(default_codex_home, "# Personal rules\n")
    (default_codex_home / "AGENTS.md").write_text("# My own rules\n", encoding="utf-8")
    assert (
        instruction_override_advisories("codex", home=tmp_path, require_block=True)
        == []
    )


def test_the_white_space_set_is_unicode_white_space() -> None:
    # Python's isspace() adds U+001C to U+001F, which Rust's str::trim keeps.
    separators = {chr(code) for code in range(0x1C, 0x20)}
    spaces = {chr(code) for code in range(0x110000) if chr(code).isspace()}
    assert set(_WHITE_SPACE) == spaces - separators
    assert len(_WHITE_SPACE) == len(set(_WHITE_SPACE)) == 25


def _deny_agents_md(monkeypatch: pytest.MonkeyPatch) -> None:
    real_is_file = Path.is_file

    def is_file(self: Path, *args: object, **kwargs: object) -> bool:
        if self.name == "AGENTS.md":
            raise PermissionError(13, "Permission denied", str(self))
        return real_is_file(self, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(Path, "is_file", is_file)


def test_an_unreadable_agents_md_gives_no_note_instead_of_an_error(
    tmp_path: Path, default_codex_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _codex_override(default_codex_home, "# Personal rules\n")
    _deny_agents_md(monkeypatch)
    assert (
        instruction_override_advisories("codex", home=tmp_path, require_block=True)
        == []
    )


def test_cli_verify_finishes_when_agents_md_cannot_be_read(
    cli_env: tuple[Path, Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _home, profile = cli_env
    folder = tmp_path / "codex-elsewhere"
    monkeypatch.setenv("CODEX_HOME", str(folder))
    _codex_override(folder, "# Personal rules\n")
    runner = CliRunner()
    install = ["install", "--harness", "codex", "--profile", str(profile)]
    assert runner.invoke(main, [*install, "--no-color"]).exit_code == 0
    _deny_agents_md(monkeypatch)
    verify = ["verify", "--harness", "codex", "--no-color", "--format", "json"]
    result = runner.invoke(main, verify)
    payload = json.loads(result.output)
    assert len(payload["results"]) == 1
    assert _override_notes(payload) == []


def test_cli_verify_after_uninstall_keeps_operator_text_and_gives_no_note(
    cli_env: tuple[Path, Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _home, profile = cli_env
    folder = tmp_path / "codex-elsewhere"
    monkeypatch.setenv("CODEX_HOME", str(folder))
    _codex_override(folder, "# Personal rules\n")
    agents_md = folder / "AGENTS.md"
    agents_md.write_text("# My own rules\n", encoding="utf-8")
    runner = CliRunner()
    install = ["install", "--harness", "codex", "--profile", str(profile)]
    assert runner.invoke(main, [*install, "--no-color"]).exit_code == 0
    uninstall = ["uninstall", "--harness", "codex", "--yes", "--no-color"]
    assert runner.invoke(main, uninstall).exit_code == 0
    assert "# My own rules" in agents_md.read_text(encoding="utf-8")
    verify = ["verify", "--harness", "codex", "--no-color", "--format", "json"]
    assert _override_notes(json.loads(runner.invoke(main, verify).output)) == []


def test_agents_left_in_the_default_codex_home_get_a_note(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # CODEX_HOME moved, but an earlier install left Apothem agents where Cursor
    # reads them; this install neither updates nor removes them.
    agents = tmp_path / ".codex" / "agents"
    agents.mkdir(parents=True)
    name = sorted(_apothem_agent_names())[0]
    (agents / f"{name}.toml").write_text('name = "x"\n', encoding="utf-8")
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "codex-elsewhere"))
    advisories = shared_root_advisories("codex", home=tmp_path, project=None)
    [note] = [a for a in advisories if a["path"] == str(agents)]
    message = " ".join(str(note["message"]).split())
    assert "still holds Apothem content from an earlier Codex install" in message
    assert "neither updates nor removes" in message


def test_an_unreadable_default_agents_folder_gives_no_note_instead_of_an_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    agents = tmp_path / ".codex" / "agents"
    real_is_dir = Path.is_dir

    def is_dir(self: Path, *args: object, **kwargs: object) -> bool:
        if self == agents:
            raise PermissionError(13, "Permission denied", str(self))
        return real_is_dir(self, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "codex-elsewhere"))
    monkeypatch.setattr(Path, "is_dir", is_dir)
    advisories = shared_root_advisories("codex", home=tmp_path, project=None)
    assert str(agents) not in {a["path"] for a in advisories}
