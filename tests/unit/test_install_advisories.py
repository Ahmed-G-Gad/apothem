# SPDX-License-Identifier: MIT

"""Install advisories for shared roots.

Installing the owner of a shared root (Codex for ``~/.agents/skills/``) puts
Apothem content in front of every reader, so the install names the readers.
Installing a reader while the shared root already holds another adapter's
Apothem content says where that content comes from.
"""

from __future__ import annotations

import errno
import json
import os
import stat
import sys
from pathlib import Path

import pytest
from click.testing import CliRunner

from apothem.cli import main
from apothem.harnesses._shared import install_driver
from apothem.lib import install_advisories
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
    real_stat = Path.stat

    def is_file(self: Path, *args: object, **kwargs: object) -> bool:
        if self.name == "AGENTS.md":
            raise PermissionError(13, "Permission denied", str(self))
        return real_is_file(self, *args, **kwargs)  # type: ignore[arg-type]

    def path_stat(self: Path, **kwargs: bool) -> os.stat_result:
        if self.name == "AGENTS.md":
            raise PermissionError(13, "Permission denied", str(self))
        return real_stat(self, **kwargs)

    monkeypatch.setattr(Path, "is_file", is_file)
    monkeypatch.setattr(Path, "stat", path_stat)


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


# --- OpenCode: a same-folder opencode.jsonc replaces the instructions list ------


def _opencode_folder() -> Path:
    """Return the folder the OpenCode install writes to with XDG unset."""
    return Path.home() / ".config" / "opencode"


def _opencode_jsonc(folder: Path, text: str | bytes) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "opencode.jsonc"
    path.write_bytes(text if isinstance(text, bytes) else text.encode("utf-8"))
    return path


@pytest.mark.parametrize(
    "text",
    [
        '{"instructions": ["~/notes/rules.md"]}',
        '{"instructions": []}',
        # OpenCode parses JSONC: comments and trailing commas are allowed.
        '// mine\n{\n  /* own list */\n  "instructions": ["a.md",],\n}\n',
        # OpenCode decodes the file with TextDecoder, which drops a byte order
        # mark. chr() keeps the invisible code point out of this source.
        chr(0xFEFF)
        + '{"$schema": "https://opencode.ai/config.json", "instructions": []}',
        # Comment markers and commas inside a string are text.
        '{"instructions": ["https://x.test/*.md", "a//b,]"]}',
        # JavaScript reads every number as a float, a long one too.
        '{"n": ' + "1" * 5000 + ', "instructions": []}',
        # TextDecoder replaces bytes that are not UTF-8 instead of failing.
        b'{"instructions": ["\xff.md"]}',
    ],
)
def test_an_opencode_jsonc_instructions_list_replaces_the_written_list(
    tmp_path: Path, text: str | bytes
) -> None:
    # OpenCode 1 loads opencode.json, then opencode.jsonc, from one folder and
    # lets the later list replace the earlier one, an empty list too.
    folder = _opencode_folder()
    path = _opencode_jsonc(folder, text)
    [note] = instruction_override_advisories("opencode", home=tmp_path)
    assert note["harness"] == "opencode"
    assert note["outcome"] == "advisory"
    assert note["operation"] == "instruction_override"
    assert note["path"] == str(path)
    assert note["target"] == str(folder / "opencode.json")
    message = " ".join(str(note["message"]).split())
    assert f"OpenCode 1 reads the instructions list in {path}" in message
    assert "OpenCode 2 reads both lists" in message
    assert "therefore do not reach OpenCode 1" in message
    assert "Remove the instructions key from opencode.jsonc" in message


@pytest.mark.parametrize(
    "text",
    [
        None,
        "",
        '{"$schema": "https://opencode.ai/config.json"}',
        '{"nested": {"instructions": []}}',
        # OpenCode 1 reads empty text as {}, and TextDecoder drops a lone byte
        # order mark first, so neither file stops it.
        chr(0xFEFF),
    ],
)
def test_opencode_gives_no_note_without_a_top_level_instructions_list(
    tmp_path: Path, text: str | None
) -> None:
    folder = _opencode_folder()
    if text is not None:
        _opencode_jsonc(folder, text)
    assert instruction_override_advisories("opencode", home=tmp_path) == []


@pytest.mark.parametrize(
    "text",
    [
        # JSON5 syntax: OpenCode 1 parses JSONC only.
        "{instructions: []}",
        "{'instructions': ['a.md']}",
        '{"x": NaN, "instructions": []}',
        "not a config file",
        '{"instructions": []} /* not closed',
        '{"instructions": [',
        '{"instructions": [,]}',
        '{} {"instructions": []}',
        # Whitespace or comments alone are no value, which jsonc-parser
        # refuses; a byte order mark ahead of whitespace is dropped first.
        "  \n",
        "// nothing else\n",
        chr(0xFEFF) + " ",
    ],
)
def test_an_opencode_jsonc_opencode_1_cannot_parse_gets_a_note(
    tmp_path: Path, text: str
) -> None:
    # OpenCode 1 then loads no configuration at all; OpenCode 2 skips the file.
    folder = _opencode_folder()
    path = _opencode_jsonc(folder, text)
    [note] = instruction_override_advisories("opencode", home=tmp_path)
    assert note["harness"] == "opencode"
    assert note["outcome"] == "advisory"
    assert note["operation"] == "instruction_override"
    assert note["path"] == str(path)
    assert note["target"] == str(folder / "opencode.json")
    message = " ".join(str(note["message"]).split())
    assert f"OpenCode 1 cannot parse {path} as JSONC" in message
    assert "stops with an error saying the file is not valid JSON(C)" in message
    assert "loads none of its configuration" in message
    assert "the Apothem profile document and rules included" in message
    assert "until the file is fixed or removed" in message
    assert (
        "OpenCode 2 skips that file, which does not keep it from loading opencode.json"
        in message
    )
    assert path.read_bytes() == text.encode("utf-8")
    assert not (folder / "opencode.json").exists()


@pytest.mark.parametrize("variable", ["OPENCODE_CONFIG_DIR", "OPENCODE_CONFIG"])
def test_an_opencode_jsonc_opencode_1_cannot_parse_keeps_its_note_when_joined(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, variable: str
) -> None:
    # OpenCode 1 still reads the file with the other global files first, so a
    # later join of the lists does not save the configuration.
    folder = _opencode_folder()
    path = _opencode_jsonc(folder, "{instructions: []}")
    named = folder if variable == "OPENCODE_CONFIG_DIR" else folder / "opencode.json"
    monkeypatch.setenv(variable, str(named))
    notes = instruction_override_advisories("opencode", home=tmp_path)
    assert [note["path"] for note in notes] == [str(path)]


def test_a_folder_named_opencode_jsonc_gets_a_note(tmp_path: Path) -> None:
    # Reading a folder fails with an error OpenCode 1 does not skip.
    path = _opencode_folder() / "opencode.jsonc"
    path.mkdir(parents=True)
    [note] = instruction_override_advisories("opencode", home=tmp_path)
    assert note["path"] == str(path)
    message = " ".join(str(note["message"]).split())
    assert f"{path} is a folder" in message
    assert "so it stops with an error and loads none of its configuration" in message
    assert "until the folder is moved or renamed" in message
    assert "OpenCode 2" not in message
    assert path.is_dir()


def _refuse_read(monkeypatch: pytest.MonkeyPatch, path: Path, error: OSError) -> None:
    """Make every read of *path* raise *error*."""
    real_read_bytes = Path.read_bytes
    real_open = Path.open

    def read_bytes(self: Path) -> bytes:
        if self == path:
            raise error
        return real_read_bytes(self)

    def path_open(self: Path, *args: object, **kwargs: object) -> object:
        if self == path:
            raise error
        return real_open(self, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(Path, "read_bytes", read_bytes)
    monkeypatch.setattr(Path, "open", path_open)


@pytest.mark.parametrize("text", ['{"instructions": []}', "{instructions: []}"])
def test_an_opencode_jsonc_it_may_not_read_gets_a_note_on_windows_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, text: str
) -> None:
    # Current OpenCode 1 releases skip a file they may not read (EACCES), as if
    # missing. Windows reports such a file as EPERM, which they do not skip.
    path = _opencode_jsonc(_opencode_folder(), text)
    denied = PermissionError(errno.EACCES, "Permission denied", str(path))
    _refuse_read(monkeypatch, path, denied)
    monkeypatch.setattr(install_advisories, "_WINDOWS", False)
    assert instruction_override_advisories("opencode", home=tmp_path) == []

    monkeypatch.setattr(install_advisories, "_WINDOWS", True)
    [note] = instruction_override_advisories("opencode", home=tmp_path)
    assert note["path"] == str(path)
    message = " ".join(str(note["message"]).split())
    assert f"OpenCode 1 cannot read {path} (Permission denied)" in message
    assert "so it stops with an error and loads none of its configuration" in message
    assert "until the file can be read or is removed" in message
    assert "OpenCode 2" not in message


def test_an_opencode_jsonc_read_refused_with_eperm_gets_a_note_everywhere(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # OpenCode 1 skips only EACCES. Python raises PermissionError for EPERM
    # too, which OpenCode 1 does not skip on any system.
    path = _opencode_jsonc(_opencode_folder(), '{"instructions": []}')
    denied = PermissionError(errno.EPERM, "Operation not permitted", str(path))
    _refuse_read(monkeypatch, path, denied)
    monkeypatch.setattr(install_advisories, "_WINDOWS", False)
    [note] = instruction_override_advisories("opencode", home=tmp_path)
    message = " ".join(str(note["message"]).split())
    assert f"OpenCode 1 cannot read {path} (Operation not permitted)" in message


@pytest.mark.parametrize("code", [errno.ELOOP, errno.EBUSY, errno.EIO])
@pytest.mark.parametrize("windows", [True, False])
def test_an_opencode_jsonc_read_error_opencode_1_does_not_skip_gets_a_note(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, code: int, windows: bool
) -> None:
    # OpenCode 1 skips only a missing file and one it may not read; a link loop
    # or a file another program holds stops its config like a parse error.
    path = _opencode_jsonc(_opencode_folder(), '{"instructions": []}')
    _refuse_read(monkeypatch, path, OSError(code, os.strerror(code), str(path)))
    monkeypatch.setattr(install_advisories, "_WINDOWS", windows)
    [note] = instruction_override_advisories("opencode", home=tmp_path)
    message = " ".join(str(note["message"]).split())
    assert f"OpenCode 1 cannot read {path} ({os.strerror(code)})" in message


def test_a_symbolic_link_loop_at_opencode_jsonc_gets_a_note(tmp_path: Path) -> None:
    folder = _opencode_folder()
    folder.mkdir(parents=True)
    path = folder / "opencode.jsonc"
    try:
        path.symlink_to(folder / "loop")
        (folder / "loop").symlink_to(path)
    except OSError:
        pytest.skip("symbolic links are not available here")
    notes = instruction_override_advisories("opencode", home=tmp_path)
    assert [note["path"] for note in notes] == [str(path)]
    assert "OpenCode 1 cannot read" in str(notes[0]["message"])


@pytest.mark.parametrize(
    ("text", "value", "parses"),
    [
        # An unquoted token parses once OpenCode 1 puts the value in.
        ('{"port": {env:APOTHEM_TEST_PORT}}', "4000", True),
        ('{"port": {env:APOTHEM_TEST_PORT}}', None, False),
        ('{"port": {env:APOTHEM_TEST_PORT}}', "", False),
        # OpenCode 1 does not escape the value, so a double quote breaks it.
        ('{"name": "{env:APOTHEM_TEST_PORT}"}', "plain", True),
        ('{"name": "{env:APOTHEM_TEST_PORT}"}', 'a"b', False),
    ],
)
def test_an_opencode_jsonc_is_parsed_after_its_env_tokens_are_replaced(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    text: str,
    value: str | None,
    parses: bool,
) -> None:
    if value is None:
        monkeypatch.delenv("APOTHEM_TEST_PORT", raising=False)
    else:
        monkeypatch.setenv("APOTHEM_TEST_PORT", value)
    path = _opencode_jsonc(_opencode_folder(), text)
    notes = instruction_override_advisories("opencode", home=tmp_path)
    assert [note["path"] for note in notes] == ([] if parses else [str(path)])
    assert path.read_text(encoding="utf-8") == text


def test_an_env_token_can_hold_the_instructions_list_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The raw text is not JSONC, but OpenCode 1 parses it once the value is in,
    # and then reads its list in place of the written one.
    monkeypatch.setenv("APOTHEM_TEST_PORT", "4000")
    text = '{"port": {env:APOTHEM_TEST_PORT}, "instructions": []}'
    path = _opencode_jsonc(_opencode_folder(), text)
    [note] = instruction_override_advisories("opencode", home=tmp_path)
    message = " ".join(str(note["message"]).split())
    assert f"OpenCode 1 reads the instructions list in {path}" in message


_BOM = chr(0xFEFF)
_LF = chr(10)
_CRLF = chr(13) + chr(10)


@pytest.mark.parametrize(
    ("text", "files", "expected"),
    [
        # OpenCode 1 puts the trimmed text in, escaped as a JSON string's inside.
        ('{"port": {file:port.txt}}', {"port.txt": "4000" + _LF}, None),
        ('{"port": {file:word.txt}}', {"word.txt": "abc"}, "parse"),
        ('{"name": "{file:note.txt}"}', {"note.txt": 'a "b"' + _LF + "c"}, None),
        ('{"name": "{file:~/home-note.txt}"}', {"~/home-note.txt": "x"}, None),
        # A token on a line that starts with // stays as it is, in a comment.
        ("// {file:missing.txt}" + _LF + "{}", {}, None),
        ("// {file:missing.txt}" + _LF + "{x}", {}, "parse"),
        # JavaScript's trim() removes a byte order mark, so the number parses.
        ('{"port": {file:n.txt}}', {"n.txt": _BOM + "5" + _CRLF}, None),
        # It keeps U+0085 and U+001C, which jsonc-parser refuses outside a
        # string; Python's strip() would remove both.
        ('{"port": {file:n.txt}}', {"n.txt": chr(0x85) + "5"}, "parse"),
        ('{"port": {file:n.txt}}', {"n.txt": chr(0x1C) + "5"}, "parse"),
        # trimStart() removes a byte order mark ahead of //, so the token stays
        # in the comment, and the stray mark then fails the parse.
        ("{}" + _LF + _BOM + "// {file:missing.txt}", {}, "parse"),
        # A file that is only a token that puts in nothing is parsed as empty
        # text, which fails, while an empty file reads as {}.
        ("{file:empty.txt}", {"empty.txt": ""}, "parse"),
        ("{file:empty.txt}", {"empty.txt": "{}"}, None),
    ],
)
def test_an_opencode_jsonc_is_parsed_after_its_file_tokens_are_replaced(
    tmp_path: Path, text: str, files: dict[str, str], expected: str | None
) -> None:
    folder = _opencode_folder()
    for name, content in files.items():
        where = Path.home() / name[2:] if name.startswith("~/") else folder / name
        where.parent.mkdir(parents=True, exist_ok=True)
        where.write_bytes(content.encode("utf-8"))
    path = _opencode_jsonc(folder, text)
    notes = instruction_override_advisories("opencode", home=tmp_path)
    assert [note["path"] for note in notes] == ([] if expected is None else [str(path)])
    if expected == "parse":
        assert "cannot parse" in str(notes[0]["message"])


@pytest.mark.parametrize(
    "text",
    [
        '{"apiKey": "{file:missing.txt}"}',
        '{"port": {file:missing.txt}}',
        # OpenCode 1 leaves a token only on a line that starts with //; one in
        # a block comment is read too.
        "/* {file:missing.txt} */ {}",
        '{"key": "{file:~/no-such-folder/key.txt}"}',
        # A folder cannot be read as a file either.
        '{"key": "{file:a-folder}"}',
        # Nor can a path with a NUL in it.
        '{"key": "{file:a' + chr(0) + 'b}"}',
    ],
)
def test_an_opencode_jsonc_file_token_it_cannot_read_gets_a_note(
    tmp_path: Path, text: str
) -> None:
    # OpenCode 1 stops with a "bad file reference" error and loads none of its
    # configuration.
    folder = _opencode_folder()
    (folder / "a-folder").mkdir(parents=True)
    path = _opencode_jsonc(folder, text)
    [note] = instruction_override_advisories("opencode", home=tmp_path)
    assert note["path"] == str(path)
    message = " ".join(str(note["message"]).split())
    start = text.index("{file:")
    # A control character, such as the NUL, is shown as an escape.
    token = text[start : text.index("}", start) + 1].replace(chr(0), "\\u0000")
    assert f"OpenCode 1 cannot read the file that {token} in {path} names" in message
    assert 'stops with a "bad file reference" error' in message
    assert "loads none of its configuration" in message
    assert "until that file can be read or the reference is removed" in message
    # OpenCode 2 puts in empty text for a file it cannot read.
    assert message.endswith("OpenCode 2 puts in empty text for that reference instead.")
    assert path.read_bytes() == text.encode("utf-8")


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        # OpenCode 1 checks for an empty file before it puts the values in, so
        # a file that is one token holding nothing is parsed as empty text.
        (None, "parse"),
        ("", "parse"),
        ('{"theme": "dark"}', None),
        ('{"instructions": []}', "replaces"),
    ],
)
def test_an_opencode_jsonc_of_one_env_token_is_checked_after_the_empty_check(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    value: str | None,
    expected: str | None,
) -> None:
    if value is None:
        monkeypatch.delenv("APOTHEM_TEST_WHOLE", raising=False)
    else:
        monkeypatch.setenv("APOTHEM_TEST_WHOLE", value)
    path = _opencode_jsonc(_opencode_folder(), "{env:APOTHEM_TEST_WHOLE}")
    notes = instruction_override_advisories("opencode", home=tmp_path)
    assert [note["path"] for note in notes] == ([] if expected is None else [str(path)])
    if expected == "parse":
        assert "cannot parse" in str(notes[0]["message"])
    if expected == "replaces":
        assert "reads the instructions list in" in str(notes[0]["message"])


def test_a_raw_line_break_in_a_string_is_not_hidden_by_a_block_comment(
    tmp_path: Path,
) -> None:
    # jsonc-parser refuses the raw line break; removing the "comment" must not
    # take it out of the string.
    path = _opencode_jsonc(_opencode_folder(), '{"a": "x /*' + _LF + '*/ y"}')
    notes = instruction_override_advisories("opencode", home=tmp_path)
    assert [note["path"] for note in notes] == [str(path)]
    # A real block comment over several lines still parses.
    _opencode_jsonc(_opencode_folder(), "/* a" + _LF + "b */ {}")
    assert instruction_override_advisories("opencode", home=tmp_path) == []


# --- OpenCode: config.json, opencode.json or opencode.jsonc OpenCode 1 refuses --

_FOLDED = ["config.json", "opencode.json", "opencode.jsonc"]


def _opencode_file(name: str, text: str) -> Path:
    """Write *text* to the global OpenCode file *name* and return its path."""
    folder = _opencode_folder()
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    path.write_bytes(text.encode("utf-8"))
    return path


@pytest.mark.parametrize("name", _FOLDED)
@pytest.mark.parametrize(
    ("text", "kind"),
    [
        # jsonc-parser refuses these: JsonError.
        ("{x: 1}", "parse"),
        ('{"instructions": [}', "parse"),
        # The schema wants an object at the top level: InvalidError.
        ("[]", "top-level"),
        ('["a.md"]', "top-level"),
        ("null", "top-level"),
        ('"text"', "top-level"),
        ("1", "top-level"),
        # And a list of strings for instructions: InvalidError.
        ('{"instructions": "a.md"}', "instructions"),
        ('{"instructions": null}', "instructions"),
        ('{"instructions": {"a": "b.md"}}', "instructions"),
        ('{"instructions": [1]}', "instructions"),
        ('{"instructions": ["a.md", null]}', "instructions"),
    ],
)
def test_each_global_opencode_file_opencode_1_refuses_gets_a_note(
    tmp_path: Path, name: str, text: str, kind: str
) -> None:
    # Each of the three files OpenCode 1 folds stops it, before it loads any
    # of its configuration, when it refuses that file.
    path = _opencode_file(name, text)
    [note] = instruction_override_advisories("opencode", home=tmp_path)
    assert note["harness"] == "opencode"
    assert note["outcome"] == "advisory"
    assert note["operation"] == "instruction_override"
    assert note["path"] == str(path)
    assert note["target"] == str(path.parent / "opencode.json")
    message = " ".join(str(note["message"]).split())
    expected = {
        "parse": f"OpenCode 1 cannot parse {path} as JSONC",
        "top-level": f"OpenCode 1 needs an object at the top level of {path}",
        "instructions": (
            f"OpenCode 1 needs the instructions value in {path} to be a list of text"
        ),
    }[kind]
    assert expected in message
    if kind != "parse":
        assert "stops with an error saying the configuration is invalid" in message
    effect = "loads none of its configuration, the Apothem profile document and rules"
    assert effect in message
    # What it says of OpenCode 2 depends on the file: OpenCode 2 reads no
    # config.json, skips a file it cannot parse or whose top level is not an
    # object, ignores an instructions value that is not a list, a string
    # included, and drops the items of a list that are not text.
    if name == "config.json":
        assert message.endswith("OpenCode 2 does not read config.json.")
    elif kind == "instructions" and text.startswith('{"instructions": ['):
        assert message.endswith(
            "OpenCode 2 instead drops what in that list is not text."
        )
    elif kind == "instructions":
        assert message.endswith(
            "OpenCode 2 instead ignores that value, which is not a list."
        )
    elif name == "opencode.json":
        assert message.endswith(
            "OpenCode 2 skips that file too, so the entries Apothem lists there "
            "do not reach it either."
        )
    else:
        assert message.endswith(
            "OpenCode 2 skips that file, which does not keep it from loading opencode.json."
        )
    assert path.read_bytes() == text.encode("utf-8")


@pytest.mark.parametrize("name", _FOLDED)
@pytest.mark.parametrize(
    "text",
    [
        None,
        # OpenCode 1 reads an empty file, or a lone byte order mark, as {}.
        "",
        _BOM,
        '{"theme": "dark"}',
        "// mine" + _LF + '{"theme": "dark",}',
        '{"$schema": "https://opencode.ai/config.json"}',
    ],
)
def test_a_global_opencode_file_opencode_1_loads_gets_no_note(
    tmp_path: Path, name: str, text: str | None
) -> None:
    if text is not None:
        _opencode_file(name, text)
    assert instruction_override_advisories("opencode", home=tmp_path) == []


@pytest.mark.parametrize("name", ["config.json", "opencode.json"])
def test_an_instructions_list_ahead_of_opencode_jsonc_gets_no_note(
    tmp_path: Path, name: str
) -> None:
    # A later file replaces config.json's list, and opencode.json's is the
    # written list itself.
    _opencode_file(name, '{"instructions": ["a.md"], "theme": "dark"}')
    assert instruction_override_advisories("opencode", home=tmp_path) == []


def test_every_global_opencode_file_opencode_1_refuses_gets_its_own_note(
    tmp_path: Path,
) -> None:
    paths = [_opencode_file(name, "[]") for name in _FOLDED]
    notes = instruction_override_advisories("opencode", home=tmp_path)
    assert [note["path"] for note in notes] == [str(path) for path in paths]


def test_an_opencode_jsonc_link_to_a_refused_opencode_json_adds_no_note(
    tmp_path: Path,
) -> None:
    # OpenCode 1 reads the same text twice; the note for opencode.json covers it.
    target = _opencode_file("opencode.json", "{x: 1}")
    try:
        (target.parent / "opencode.jsonc").symlink_to(target)
    except OSError:
        pytest.skip("symbolic links are not available here")
    notes = instruction_override_advisories("opencode", home=tmp_path)
    assert [note["path"] for note in notes] == [str(target)]


def _fake_links(monkeypatch: pytest.MonkeyPatch, links: dict[Path, Path]) -> None:
    """Make each key of *links* look like a symbolic link to its value.

    The test files are copies, so the check reads the same text through each
    name; this stands in for links where the host may not create them.
    """
    real_is_symlink = Path.is_symlink
    real_resolve = Path.resolve

    def is_symlink(self: Path) -> bool:
        return self in links or real_is_symlink(self)

    def resolve(self: Path, strict: bool = False) -> Path:
        return real_resolve(links.get(self, self), strict)

    monkeypatch.setattr(Path, "is_symlink", is_symlink)
    monkeypatch.setattr(Path, "resolve", resolve)


@pytest.mark.parametrize(
    ("links", "holder"),
    [
        # A link to a file read earlier, and to one read later: the note goes
        # to opencode.json, the file Apothem writes, when it is one of them.
        ({"opencode.jsonc": "opencode.json"}, "opencode.json"),
        ({"config.json": "opencode.json"}, "opencode.json"),
        ({"opencode.json": "config.json"}, "opencode.json"),
        # Else to the name that is not a link.
        ({"config.json": "opencode.jsonc"}, "opencode.jsonc"),
        ({"opencode.jsonc": "config.json"}, "config.json"),
        # Else, when every name is a link to a file elsewhere, to the first
        # name OpenCode 1 reads.
        (
            {"config.json": "elsewhere.json", "opencode.jsonc": "elsewhere.json"},
            "config.json",
        ),
    ],
)
def test_names_that_lead_to_one_refused_file_share_one_note(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    links: dict[str, str],
    holder: str,
) -> None:
    folder = _opencode_folder()
    for name in {*links, *links.values()}:
        _opencode_file(name, "{x: 1}")
    _fake_links(monkeypatch, {folder / a: folder / b for a, b in links.items()})
    notes = instruction_override_advisories("opencode", home=tmp_path)
    assert [note["path"] for note in notes] == [str(folder / holder)]


@pytest.mark.parametrize(
    ("text", "tail"),
    [
        (
            "{x: 1}",
            "OpenCode 2 skips that file, which does not keep it from loading opencode.json.",
        ),
        (
            '{"instructions": "a.md"}',
            "OpenCode 2 instead ignores that value, which is not a list.",
        ),
    ],
)
def test_a_config_json_note_says_what_opencode_2_does_with_its_jsonc_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, text: str, tail: str
) -> None:
    # config.json carries the note for an opencode.jsonc that links to it, and
    # OpenCode 2, which reads no config.json, reads that file as opencode.jsonc.
    folder = _opencode_folder()
    for name in ("config.json", "opencode.jsonc"):
        _opencode_file(name, text)
    _fake_links(monkeypatch, {folder / "opencode.jsonc": folder / "config.json"})
    [note] = instruction_override_advisories("opencode", home=tmp_path)
    assert note["path"] == str(folder / "config.json")
    message = " ".join(str(note["message"]).split())
    assert message.endswith(
        f"OpenCode 2 reads that file as opencode.jsonc, not as config.json. {tail}"
    )


def test_verify_keeps_the_note_opencode_json_shares_with_a_link(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from apothem.harnesses._shared.install_driver_merge import (
        PROFILE_DOCUMENT_RELATIVE,
    )

    folder = _opencode_folder()
    target = _opencode_file("opencode.json", "[]")
    _opencode_file("config.json", "[]")
    document = folder / PROFILE_DOCUMENT_RELATIVE
    document.parent.mkdir(parents=True)
    document.write_text(APOTHEM_BLOCK_BEGIN + _LF, encoding="utf-8")
    _fake_links(monkeypatch, {target: folder / "config.json"})
    verify = {"home": tmp_path, "require_block": True}
    notes = instruction_override_advisories("opencode", **verify)
    assert [note["path"] for note in notes] == [str(target)]


_BACKSLASH = chr(92)


@pytest.mark.parametrize("name", _FOLDED)
@pytest.mark.parametrize(
    ("text", "value"),
    [
        # A Windows path holds backslashes, which OpenCode 1 puts in as they
        # are; OpenCode 2 escapes them once the text fails to parse.
        (
            '{"instructions": ["{env:APOTHEM_TEST_DIR}/rules.md"]}',
            "C:" + _BACKSLASH + "Users" + _BACKSLASH + "me",
        ),
        ('{"theme": "{env:APOTHEM_TEST_DIR}"}', 'a"b'),
        ('{"theme": "{env:APOTHEM_TEST_DIR}"}', "a" + _LF + "b"),
    ],
)
def test_an_env_value_that_breaks_only_opencode_1_gets_its_own_note(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    name: str,
    text: str,
    value: str,
) -> None:
    monkeypatch.setenv("APOTHEM_TEST_DIR", value)
    path = _opencode_file(name, text)
    [note] = instruction_override_advisories("opencode", home=tmp_path)
    assert note["path"] == str(path)
    message = " ".join(str(note["message"]).split())
    assert f"OpenCode 1 cannot parse {path} as JSONC once it puts in its" in message
    assert "because it does not escape a backslash, a double quote" in message
    assert "until those values change or their references are removed" in message
    if name == "config.json":
        assert message.endswith("OpenCode 2 does not read config.json.")
    else:
        assert message.endswith(
            "OpenCode 2 escapes those values when the file would not parse "
            "otherwise, so it parses that file."
        )
    assert path.read_bytes() == text.encode("utf-8")


@pytest.mark.parametrize(
    "text",
    [
        # Escaping does not make an unquoted value parse, so OpenCode 2 skips
        # the file too.
        '{"theme": {env:APOTHEM_TEST_DIR}}',
        # Nor does it fix an error the value has no part in.
        '{"theme": "{env:APOTHEM_TEST_DIR}", x: 1}',
    ],
)
def test_an_env_value_escaping_does_not_save_gets_the_parse_note(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, text: str
) -> None:
    monkeypatch.setenv("APOTHEM_TEST_DIR", "a" + _BACKSLASH + "b")
    path = _opencode_jsonc(_opencode_folder(), text)
    [note] = instruction_override_advisories("opencode", home=tmp_path)
    message = " ".join(str(note["message"]).split())
    assert f"OpenCode 1 cannot parse {path} as JSONC (JSON with comments" in message
    assert message.endswith(
        "OpenCode 2 skips that file, which does not keep it from loading opencode.json."
    )


@pytest.mark.parametrize("name", _FOLDED)
def test_an_env_note_says_a_top_level_that_is_not_an_object_needs_a_fix_too(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    # Once the value parses, OpenCode 1 still refuses the list at the top
    # level, and OpenCode 2, which escapes the value, then skips the file.
    monkeypatch.setenv("APOTHEM_TEST_DIR", "C:" + _BACKSLASH + "x")
    path = _opencode_file(name, '["{env:APOTHEM_TEST_DIR}"]')
    [note] = instruction_override_advisories("opencode", home=tmp_path)
    message = " ".join(str(note["message"]).split())
    assert f"OpenCode 1 cannot parse {path} as JSONC once it puts in its" in message
    assert "rules included, until the file is fixed or removed." in message
    assert (
        "Changing those values is not enough: the top level of that file is not "
        "an object either, which OpenCode 1 also refuses."
    ) in message
    assert "references are removed" not in message
    assert "so it parses that file" not in message
    tail = {
        "config.json": "OpenCode 2 does not read config.json.",
        "opencode.json": (
            "OpenCode 2 escapes those values when the file would not parse "
            "otherwise, but then skips that file because its top level is not "
            "an object, so the entries Apothem lists there do not reach it either."
        ),
        "opencode.jsonc": (
            "OpenCode 2 escapes those values when the file would not parse "
            "otherwise, but then skips that file because its top level is not "
            "an object; skipping it does not keep OpenCode 2 from loading "
            "opencode.json."
        ),
    }[name]
    assert message.endswith(tail)


@pytest.mark.parametrize(
    ("value", "dropped"),
    [
        ("5", "ignores that value, which is not a list"),
        ('"AGENTS.md"', "ignores that value, which is not a list"),
        ('["a.md", 1]', "drops what in that list is not text"),
    ],
)
def test_an_env_note_says_an_instructions_value_needs_a_fix_too(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, value: str, dropped: str
) -> None:
    monkeypatch.setenv("APOTHEM_TEST_DIR", 'say "hi"')
    text = '{"a": "{env:APOTHEM_TEST_DIR}", "instructions": ' + value + "}"
    path = _opencode_jsonc(_opencode_folder(), text)
    [note] = instruction_override_advisories("opencode", home=tmp_path)
    message = " ".join(str(note["message"]).split())
    assert f"OpenCode 1 cannot parse {path} as JSONC once it puts in its" in message
    assert (
        "until those values change or their references are removed and its "
        "instructions value is a list of text or is removed."
    ) in message
    assert message.endswith(
        "OpenCode 2 escapes those values when the file would not parse "
        f"otherwise, so it loads that file, but {dropped}."
    )


@pytest.mark.parametrize("windows", [True, False])
@pytest.mark.parametrize(
    ("token", "where"),
    [
        # Node's path.resolve and path.join drop ".." from the text, so a
        # missing folder before it does not matter.
        ("{file:missing/../port.txt}", "port.txt"),
        ("{file:./a/./../port.txt}", "port.txt"),
        ("{file:~/missing/../home-port.txt}", "~/home-port.txt"),
    ],
)
def test_a_file_token_path_is_normalized_as_opencode_1_does(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    token: str,
    where: str,
    windows: bool,
) -> None:
    if windows and sys.platform != "win32":
        # The Windows branch leaves ".." to the system, and only Windows
        # reads it by the text; a POSIX kernel looks up the missing folder.
        pytest.skip("only Windows folds '..' in a path by its text")
    monkeypatch.setattr(install_advisories, "_WINDOWS", windows)
    folder = _opencode_folder()
    file = Path.home() / where[2:] if where.startswith("~/") else folder / where
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text("4000", encoding="utf-8")
    _opencode_jsonc(folder, '{"port": ' + token + "}")
    assert instruction_override_advisories("opencode", home=tmp_path) == []


def _fake_pipe(monkeypatch: pytest.MonkeyPatch, path: Path) -> None:
    """Make *path* look like a named pipe that must never be read.

    The check reads a global file through ``Path`` and a ``{file:path}`` file
    through ``os.stat`` and ``open`` with the path as OpenCode 1 spells it, so
    both are faked; neither fake calls anything that stats a path itself.
    """
    real_stat = Path.stat
    real_read_bytes = Path.read_bytes
    real_path_open = Path.open
    real_os_stat = os.stat
    pipe = os.stat_result((stat.S_IFIFO | 0o644, 0, 0, 1, 0, 0, 0, 0, 0, 0))

    def fake_stat(self: Path, **kwargs: bool) -> os.stat_result:
        if self == path:
            return pipe
        return real_stat(self, **kwargs)

    def read_bytes(self: Path) -> bytes:
        assert self != path, "a named pipe was read"
        return real_read_bytes(self)

    def path_open(self: Path, *args: object, **kwargs: object) -> object:
        assert self != path, "a named pipe was opened"
        return real_path_open(self, *args, **kwargs)  # type: ignore[arg-type]

    def fake_os_stat(name: object, *args: object, **kwargs: object) -> os.stat_result:
        if isinstance(name, str) and name == str(path):
            return pipe
        return real_os_stat(name, *args, **kwargs)  # type: ignore[arg-type]

    def fake_open(name: object, *args: object, **kwargs: object) -> object:
        assert not (isinstance(name, str) and name == str(path)), "a pipe was read"
        return open(name, *args, **kwargs)  # type: ignore[call-overload]  # noqa: PTH123

    monkeypatch.setattr(Path, "stat", fake_stat)
    monkeypatch.setattr(Path, "read_bytes", read_bytes)
    monkeypatch.setattr(Path, "open", path_open)
    monkeypatch.setattr(os, "stat", fake_os_stat)
    monkeypatch.setattr(install_advisories, "open", fake_open, raising=False)


@pytest.mark.parametrize("name", _FOLDED)
def test_a_global_file_that_is_not_a_regular_file_is_not_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    # A named pipe or a device could block the read; the check skips it.
    path = _opencode_file(name, "{x: 1}")
    _fake_pipe(monkeypatch, path)
    assert instruction_override_advisories("opencode", home=tmp_path) == []


def test_a_file_token_naming_a_pipe_is_not_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Outside a string the pipe's text decides whether the file parses, so the
    # file is not checked.
    folder = _opencode_folder()
    _opencode_jsonc(folder, '{"port": {file:pipe}}')
    pipe = folder / "pipe"
    pipe.write_text("x", encoding="utf-8")
    _fake_pipe(monkeypatch, pipe)
    assert instruction_override_advisories("opencode", home=tmp_path) == []


@pytest.mark.parametrize(
    "text",
    [
        '{"key": "{file:pipe}", "instructions": "AGENTS.md"}',
        '{"key": "{file:pipe}", x: 1}',
        '["{file:pipe}"]',
        # OpenCode 1 reads the references in order and may wait on the pipe
        # forever, so a later one it cannot read does not count either.
        '{"key": "{file:pipe}", "z": "{file:missing.txt}"}',
    ],
)
def test_a_file_token_naming_a_pipe_leaves_the_file_unchecked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, text: str
) -> None:
    # OpenCode 1 may wait on a pipe forever, which no note describes. On
    # Windows a reference to anything but a file or a folder is checked as
    # empty text inside a string (see
    # test_a_windows_device_name_inside_a_string_is_checked_as_empty_text).
    folder = _opencode_folder()
    path = _opencode_jsonc(folder, text)
    pipe = folder / "pipe"
    pipe.write_text("x", encoding="utf-8")
    _fake_pipe(monkeypatch, pipe)
    notes = instruction_override_advisories("opencode", home=tmp_path)
    if sys.platform == "win32":
        # A Windows device blocks nothing, so the rest of the file counts.
        [note] = notes
        assert note["path"] == str(path)
        if "missing" in text:
            assert f"{{file:missing.txt}} in {path}" in str(note["message"])
        return
    assert notes == []


def _advisories_within(home: Path, fifo: Path) -> list[dict[str, object]]:
    """Return the OpenCode notes, failing instead of hanging on *fifo*.

    The check runs in a thread. Should it open the pipe, which blocks while
    no writer has it open, a writer opened and closed here lets it return.
    """
    import threading

    found: list[list[dict[str, object]]] = []
    worker = threading.Thread(
        target=lambda: found.append(
            instruction_override_advisories("opencode", home=home)
        ),
        daemon=True,
    )
    worker.start()
    worker.join(10)
    if worker.is_alive():
        os.close(os.open(fifo, os.O_WRONLY | os.O_NONBLOCK))
        worker.join(10)
        pytest.fail("the check opened the named pipe")
    return found[0]


@pytest.mark.skipif(sys.platform == "win32", reason="named pipes are POSIX here")
def test_a_file_token_naming_a_real_pipe_is_not_opened(tmp_path: Path) -> None:
    # Opening a named pipe with no writer would block; the check never opens it.
    folder = _opencode_folder()
    folder.mkdir(parents=True)
    fifo = folder / "pipe"
    os.mkfifo(fifo)
    _opencode_jsonc(folder, '{"key": "{file:pipe}", "instructions": 1}')
    assert _advisories_within(tmp_path, fifo) == []
    _opencode_jsonc(folder, '{"key": {file:pipe}, "instructions": 1}')
    assert _advisories_within(tmp_path, fifo) == []
    # A reference before the pipe that OpenCode 1 cannot read stops it first.
    text = '{"z": "{file:missing.txt}", "key": "{file:pipe}"}'
    path = _opencode_jsonc(folder, text)
    [note] = _advisories_within(tmp_path, fifo)
    assert f"cannot read the file that {{file:missing.txt}} in {path}" in str(
        note["message"]
    )


@pytest.mark.skipif(sys.platform == "win32", reason="sockets are POSIX here")
def test_a_file_token_naming_a_socket_gets_the_reference_note(tmp_path: Path) -> None:
    # The system refuses to open a socket (ENXIO on Linux), for OpenCode 1's
    # readFile too, so it stops with "bad file reference". A short folder keeps the socket path within its limit.
    import shutil
    import socket
    import tempfile

    short = Path(tempfile.mkdtemp(prefix="ap-", dir="/tmp"))
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        server.bind(str(short / "s"))
        token = "{file:" + str(short / "s") + "}"
        path = _opencode_jsonc(_opencode_folder(), '{"x": "' + token + '"}')
        [note] = instruction_override_advisories("opencode", home=tmp_path)
        assert note["path"] == str(path)
        assert f"cannot read the file that {token} in {path}" in str(note["message"])
    finally:
        server.close()
        shutil.rmtree(short, ignore_errors=True)


@pytest.mark.skipif(sys.platform == "win32", reason="/dev/null is a POSIX device")
def test_the_null_device_reads_as_empty_text(tmp_path: Path) -> None:
    # OpenCode 1 reads the null device as empty text and goes on, so the error
    # elsewhere in the file still stops it, and outside a string the empty
    # text it puts in is known too.
    device = "/dev/null"
    text = '{"x": "{file:' + device + '}", "instructions": "AGENTS.md"}'
    path = _opencode_jsonc(_opencode_folder(), text)
    [note] = instruction_override_advisories("opencode", home=tmp_path)
    assert note["path"] == str(path)
    message = " ".join(str(note["message"]).split())
    assert f"OpenCode 1 needs the instructions value in {path}" in message
    assert message.endswith(
        "OpenCode 2 instead ignores that value, which is not a list."
    )
    _opencode_jsonc(_opencode_folder(), '{"x": "{file:' + device + '}"}')
    assert instruction_override_advisories("opencode", home=tmp_path) == []
    _opencode_jsonc(_opencode_folder(), '{"x": {file:' + device + "}}")
    [note] = instruction_override_advisories("opencode", home=tmp_path)
    assert f"OpenCode 1 cannot parse {path} as JSONC" in str(note["message"])


# What a note adds for a {file:path} whose file the check cannot tell
# OpenCode 1 reads.
_UNKNOWN = (
    "Apothem cannot tell whether OpenCode 1 can read the file that {reference} "
    'names; if it cannot, OpenCode 1 stops at that reference first, with a "bad '
    'file reference" error.'
)


@pytest.mark.skipif(sys.platform != "win32", reason="NUL is a Windows device name")
def test_a_windows_device_name_inside_a_string_is_checked_as_empty_text(
    tmp_path: Path,
) -> None:
    # Python reads NUL in any folder as the device; Node opens it as a file
    # name there, so whether OpenCode 1 reads it is not known. Inside a string
    # the rest of the file decides: OpenCode 1 refuses this one either way.
    text = '{"x": "{file:NUL}", "instructions": "AGENTS.md"}'
    path = _opencode_jsonc(_opencode_folder(), text)
    [note] = instruction_override_advisories("opencode", home=tmp_path)
    message = " ".join(str(note["message"]).split())
    assert f"OpenCode 1 needs the instructions value in {path}" in message
    assert _UNKNOWN.format(reference="{file:NUL}") in message
    # A file that is otherwise fine gets no note, and nor does one where the
    # text decides, outside a string.
    _opencode_jsonc(_opencode_folder(), '{"x": "{file:NUL}"}')
    assert instruction_override_advisories("opencode", home=tmp_path) == []
    _opencode_jsonc(_opencode_folder(), '{"x": {file:NUL}, "instructions": 1}')
    assert instruction_override_advisories("opencode", home=tmp_path) == []
    # A later reference OpenCode 1 cannot read still stops it, unless the
    # earlier one does first, which the note says too.
    text = '{"x": "{file:NUL}", "z": "{file:missing.txt}"}'
    path = _opencode_jsonc(_opencode_folder(), text)
    [note] = instruction_override_advisories("opencode", home=tmp_path)
    message = " ".join(str(note["message"]).split())
    assert f"cannot read the file that {{file:missing.txt}} in {path}" in message
    assert _UNKNOWN.format(reference="{file:NUL}") in message


@pytest.mark.skipif(sys.platform != "win32", reason="a drive is a Windows path part")
@pytest.mark.parametrize("root", ["/", chr(92)])
def test_a_windows_file_token_rooted_without_a_drive_is_not_read(
    tmp_path: Path, root: str
) -> None:
    # OpenCode 1 reads such a path on the drive of its working directory, which
    # the check cannot know, so it neither reads it nor notes it, and checks
    # the rest of the file while the token is inside a string.
    token = "{file:" + root + "no-such-folder" + root + "key.txt}"
    _opencode_jsonc(_opencode_folder(), '{"key": "' + token + '"}')
    assert instruction_override_advisories("opencode", home=tmp_path) == []
    _opencode_jsonc(_opencode_folder(), '{"key": "' + token + '", "instructions": 1}')
    [note] = instruction_override_advisories("opencode", home=tmp_path)
    assert "needs the instructions value" in str(note["message"])
    _opencode_jsonc(_opencode_folder(), '{"port": ' + token + "}")
    assert instruction_override_advisories("opencode", home=tmp_path) == []


@pytest.mark.parametrize(
    "name", ["key.txt.", "key.txt ", "key.txt...", "sub./key.txt", "sub /key.txt"]
)
def test_a_windows_file_token_with_a_part_ending_in_a_dot_is_checked_in_a_string(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    # Python drops a trailing dot or space from each part and reads key.txt,
    # but Node opens the path as written, where key.txt. is another, missing
    # file, so whether OpenCode 1 can read it is not known. The rule reads
    # only the text, so it is checked wherever the tests run.
    monkeypatch.setattr(install_advisories, "_WINDOWS", True)
    folder = _opencode_folder()
    folder.mkdir(parents=True)
    (folder / "key.txt").write_text("secret", encoding="utf-8")
    (folder / "sub").mkdir()
    (folder / "sub" / "key.txt").write_text("secret", encoding="utf-8")
    token = "{file:" + name + "}"
    # Inside a string OpenCode 1 refuses this file whichever way the read goes.
    path = _opencode_jsonc(folder, '{"key": "' + token + '", "instructions": 1}')
    [note] = instruction_override_advisories("opencode", home=tmp_path)
    message = " ".join(str(note["message"]).split())
    assert f"OpenCode 1 needs the instructions value in {path}" in message
    assert _UNKNOWN.format(reference=token) in message
    # A parse error carries the sentence too.
    path = _opencode_jsonc(folder, '{"key": "' + token + '", y: 1}')
    [note] = instruction_override_advisories("opencode", home=tmp_path)
    message = " ".join(str(note["message"]).split())
    assert f"OpenCode 1 cannot parse {path} as JSONC" in message
    assert _UNKNOWN.format(reference=token) in message
    # Outside a string the file's text decides, so the file is not checked.
    _opencode_jsonc(folder, '{"key": ' + token + ', "instructions": 1}')
    assert instruction_override_advisories("opencode", home=tmp_path) == []
    # A path without such a part is read and checked, with no such sentence.
    if sys.platform == "win32":
        _opencode_jsonc(folder, '{"key": "{file:sub/key.txt}", "instructions": 1}')
        [note] = instruction_override_advisories("opencode", home=tmp_path)
        assert "needs the instructions value" in str(note["message"])
        assert "cannot tell" not in str(note["message"])


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX path semantics")
@pytest.mark.parametrize(
    ("token", "readable"),
    [
        # OpenCode 1 uses an absolute path as written, and the system refuses
        # a regular file followed by "/" or "/." (ENOTDIR).
        ("{file:ABS/key.txt/}", False),
        ("{file:ABS/key.txt/.}", False),
        ("{file:ABS/key.txt}", True),
        # path.join keeps a trailing "/" and folds a trailing "/.".
        ("{file:~/key.txt/}", False),
        ("{file:~/key.txt/.}", True),
        # path.resolve drops a trailing "/".
        ("{file:key.txt/}", True),
    ],
)
def test_a_file_token_with_a_trailing_slash_is_read_as_opencode_1_spells_it(
    tmp_path: Path, token: str, readable: bool
) -> None:
    folder = _opencode_folder()
    folder.mkdir(parents=True)
    for where in (folder / "key.txt", Path.home() / "key.txt"):
        where.write_text("secret", encoding="utf-8")
    token = token.replace("ABS", str(folder))
    path = _opencode_jsonc(folder, '{"key": "' + token + '"}')
    notes = instruction_override_advisories("opencode", home=tmp_path)
    assert [note["path"] for note in notes] == ([] if readable else [str(path)])
    if not readable:
        assert f"cannot read the file that {token} in {path}" in str(
            notes[0]["message"]
        )


@pytest.mark.parametrize("name", _FOLDED)
def test_a_file_over_the_read_limit_is_not_checked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    monkeypatch.setattr(install_advisories, "_READ_LIMIT", 8)
    path = _opencode_file(name, "{x: 1, y: 2}")
    assert instruction_override_advisories("opencode", home=tmp_path) == []
    # A file at the limit is checked: this one puts in a number, which is
    # not an object. A {file:path} file over the limit is not read.
    path.write_bytes(b"{file:n}")
    _opencode_file("n", "12345678")
    assert len(instruction_override_advisories("opencode", home=tmp_path)) == 1
    _opencode_file("n", "123456789")
    assert instruction_override_advisories("opencode", home=tmp_path) == []


def test_a_file_token_over_the_read_limit_in_a_string_leaves_the_other_checks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The file over the limit is not read, but inside a string its text cannot
    # change the outcome, so the instructions value still gets its note.
    monkeypatch.setattr(install_advisories, "_READ_LIMIT", 64)
    _opencode_file("big", "1" * 65)
    path = _opencode_file("opencode.jsonc", '{"k": "{file:big}", "instructions": 1}')
    [note] = instruction_override_advisories("opencode", home=tmp_path)
    assert note["path"] == str(path)
    assert "needs the instructions value" in str(note["message"])
    _opencode_file("opencode.jsonc", '{"k": "{file:big}"}')
    assert instruction_override_advisories("opencode", home=tmp_path) == []


@pytest.mark.parametrize(
    "text",
    [
        # In a key the text decides which key it is: "instructions" here.
        '{"in{file:big}structions": "AGENTS.md"}',
        '{"in{file:big}structions" /* c */ : "AGENTS.md"}',
        # After an odd backslash the text's first character ends the escape.
        '{"x": "a' + chr(92) + '{file:big}", "y": "b"}',
        # Within a \u escape the text supplies its last digits.
        '{"x": "' + chr(92) + 'u00{file:big}41", "instructions": 1}',
        # Right after a closing quote or right before an opening one.
        '{"k": "a"{file:big}, "instructions": 1}',
        '{"k": {file:big}"a", "instructions": 1}',
    ],
)
def test_a_file_token_over_the_read_limit_where_its_text_decides_is_not_checked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, text: str
) -> None:
    monkeypatch.setattr(install_advisories, "_READ_LIMIT", 64)
    _opencode_file("big", "n" * 65)
    _opencode_file("opencode.jsonc", text)
    assert instruction_override_advisories("opencode", home=tmp_path) == []


@pytest.mark.parametrize(
    ("text", "noted"),
    [
        # Two backslashes are one escape, so the token starts a new character.
        ('{"x": "a' + chr(92) * 2 + '{file:big}", "instructions": 1}', True),
        # A string value followed by a comment is still a value.
        ('{"x": "{file:big}" /* : */, "instructions": 1}', True),
        # The readable reference before the unread one moves where it sits.
        ('{"a": "{file:small}", "k": "{file:big}", "instructions": 1}', True),
        ('{"a": "{file:small}", "k": {file:big}, "instructions": 1}', False),
        # So does a token left as it is on a line that starts with "//".
        (
            '{"a": 1,' + _LF + "// {file:big}" + _LF + '"k": "{file:big}",'
            ' "instructions": 1}',
            True,
        ),
        (
            '{"a": 1,' + _LF + "// {file:big}" + _LF + '"k": {file:big},'
            ' "instructions": 1}',
            False,
        ),
    ],
)
def test_the_check_finds_where_an_unread_file_token_sits(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, text: str, noted: bool
) -> None:
    monkeypatch.setattr(install_advisories, "_READ_LIMIT", 64)
    _opencode_file("big", "n" * 65)
    _opencode_file("small", "a much longer text than the token it replaces")
    path = _opencode_file("opencode.jsonc", text)
    notes = instruction_override_advisories("opencode", home=tmp_path)
    if not noted:
        assert notes == []
        return
    [note] = notes
    assert f"needs the instructions value in {path}" in str(note["message"])


def test_an_env_parse_note_says_nothing_of_opencode_2_when_an_unread_file_decides(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The raw value's quote puts the token in a string, where its text cannot
    # save the parse; the escaped value leaves it in a comment, where its text
    # decides whether OpenCode 2 parses the file.
    monkeypatch.setattr(install_advisories, "_READ_LIMIT", 64)
    monkeypatch.setenv("APOTHEM_TEST_DIR", 'a"')
    _opencode_file("big", "n" * 65)
    text = '{"k": "{env:APOTHEM_TEST_DIR}", /* {file:big} */ "c": 1}'
    path = _opencode_file("opencode.jsonc", text)
    [note] = instruction_override_advisories("opencode", home=tmp_path)
    message = " ".join(str(note["message"]).split())
    assert f"OpenCode 1 cannot parse {path} as JSONC (JSON with comments" in message
    assert message.endswith("rules included, until the file is fixed or removed.")
    assert "OpenCode 2" not in message


@pytest.mark.parametrize("text", ["{x: 1}", "[]", '{"instructions": 1}'])
def test_the_verify_note_for_opencode_json_needs_the_profile_document(
    tmp_path: Path, text: str
) -> None:
    from apothem.harnesses._shared.install_driver_merge import (
        PROFILE_DOCUMENT_RELATIVE,
    )

    # opencode.json may list nothing readable, so verify looks for the profile
    # document the install writes instead.
    target = _opencode_file("opencode.json", text)
    verify = {"home": tmp_path, "require_block": True}
    assert instruction_override_advisories("opencode", **verify) == []
    document = target.parent / PROFILE_DOCUMENT_RELATIVE
    document.parent.mkdir(parents=True)
    document.write_text(APOTHEM_BLOCK_BEGIN + _LF, encoding="utf-8")
    [note] = instruction_override_advisories("opencode", **verify)
    assert note["path"] == str(target)
    # A note for another file still needs opencode.json to list an entry.
    _opencode_file("opencode.jsonc", "[]")
    notes = instruction_override_advisories("opencode", **verify)
    assert [note["path"] for note in notes] == [str(target)]


def test_the_verify_notes_count_entries_beside_an_item_that_is_not_text(
    tmp_path: Path,
) -> None:
    from apothem.harnesses.opencode.materializer import instruction_entries

    listed = json.dumps({"instructions": [1, *instruction_entries()]})
    target = _opencode_file("opencode.json", listed)
    jsonc = _opencode_file("opencode.jsonc", "{x: 1}")
    verify = {"home": tmp_path, "require_block": True}
    notes = instruction_override_advisories("opencode", **verify)
    assert [note["path"] for note in notes] == [str(target), str(jsonc)]


def test_the_opencode_check_follows_xdg_config_home(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    xdg = tmp_path / "xdg"
    monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg))
    _opencode_jsonc(_opencode_folder(), '{"instructions": []}')
    path = _opencode_jsonc(xdg / "opencode", '{"instructions": []}')
    [note] = instruction_override_advisories("opencode", home=tmp_path)
    assert note["path"] == str(path)
    assert note["target"] == str(xdg / "opencode" / "opencode.json")


def test_an_opencode_config_dir_list_joins_and_gets_no_note(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # OpenCode 1 merges the OPENCODE_CONFIG_DIR folder by joining the lists,
    # and the install does not write there.
    other = tmp_path / "other"
    _opencode_jsonc(other, '{"instructions": []}')
    monkeypatch.setenv("OPENCODE_CONFIG_DIR", str(other))
    assert instruction_override_advisories("opencode", home=tmp_path) == []

    # The global folder is still folded first, so a list there still hides
    # the written one.
    path = _opencode_jsonc(_opencode_folder(), '{"instructions": []}')
    notes = instruction_override_advisories("opencode", home=tmp_path)
    assert [note["path"] for note in notes] == [str(path)]


def test_opencode_config_dir_naming_the_folder_drops_the_note(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # OpenCode 1 then reads opencode.json and opencode.jsonc there a second
    # time, joining the lists, which brings the written list back.
    folder = _opencode_folder()
    _opencode_jsonc(folder, '{"instructions": []}')
    assert len(instruction_override_advisories("opencode", home=tmp_path)) == 1
    monkeypatch.setenv("OPENCODE_CONFIG_DIR", str(folder))
    assert instruction_override_advisories("opencode", home=tmp_path) == []


@pytest.mark.parametrize("names_written", [True, False])
def test_opencode_config_naming_opencode_json_drops_the_note(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, names_written: bool
) -> None:
    # OpenCode 1 reads the OPENCODE_CONFIG file after the fold and joins its
    # list, which brings the written list back; another file does not.
    folder = _opencode_folder()
    path = _opencode_jsonc(folder, '{"instructions": []}')
    named = folder / "opencode.json" if names_written else tmp_path / "mine.json"
    monkeypatch.setenv("OPENCODE_CONFIG", str(named))
    notes = instruction_override_advisories("opencode", home=tmp_path)
    assert [note["path"] for note in notes] == ([] if names_written else [str(path)])


def test_a_relative_opencode_config_keeps_the_note(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # OpenCode reads a relative path from its own working folder.
    _opencode_jsonc(_opencode_folder(), '{"instructions": []}')
    monkeypatch.setenv("OPENCODE_CONFIG", "opencode.json")
    assert len(instruction_override_advisories("opencode", home=tmp_path)) == 1


def test_an_opencode_jsonc_copy_of_the_written_list_says_it_is_not_refreshed(
    tmp_path: Path,
) -> None:
    from apothem.harnesses.opencode.materializer import instruction_entries

    listed = json.dumps({"instructions": [*instruction_entries(), "mine.md"]})
    path = _opencode_jsonc(_opencode_folder(), listed)
    [note] = instruction_override_advisories("opencode", home=tmp_path)
    assert note["path"] == str(path)
    message = " ".join(str(note["message"]).split())
    assert "holds its own copy of every entry Apothem writes" in message
    assert "installs and updates do not refresh" in message
    assert "do not reach OpenCode 1" not in message


def test_a_symbolic_link_to_opencode_json_hides_nothing(tmp_path: Path) -> None:
    folder = _opencode_folder()
    folder.mkdir(parents=True)
    target = folder / "opencode.json"
    target.write_text('{"instructions": ["a.md"]}', encoding="utf-8")
    try:
        (folder / "opencode.jsonc").symlink_to(target)
    except OSError:
        pytest.skip("symbolic links are not available here")
    assert instruction_override_advisories("opencode", home=tmp_path) == []


@pytest.mark.parametrize("text", ['{"instructions": []}', "{instructions: []}"])
def test_the_opencode_verify_note_needs_an_entry_the_install_wrote(
    tmp_path: Path, text: str
) -> None:
    from apothem.harnesses.opencode.materializer import instruction_entries

    folder = _opencode_folder()
    _opencode_jsonc(folder, text)
    target = folder / "opencode.json"
    verify = {"home": tmp_path, "require_block": True}
    assert instruction_override_advisories("opencode", **verify) == []
    target.write_text('{"instructions": ["CONTRIBUTING.md"]}', encoding="utf-8")
    assert instruction_override_advisories("opencode", **verify) == []
    listed = json.dumps({"instructions": ["CONTRIBUTING.md", *instruction_entries()]})
    target.write_text(listed, encoding="utf-8")
    [note] = instruction_override_advisories("opencode", **verify)
    assert note["target"] == str(target)


def test_cli_opencode_install_update_and_verify_name_a_replacing_jsonc(
    cli_env: tuple[Path, Path],
) -> None:
    home, profile = cli_env
    folder = home / ".config" / "opencode"
    path = _opencode_jsonc(folder, '// mine\n{"instructions": [],}\n')
    expected = [(str(path), str(folder / "opencode.json"))]
    runner = CliRunner()
    for args in (
        ["install", "--harness", "opencode", "--profile", str(profile)],
        ["update", "--harness", "opencode", "--profile", str(profile)],
        ["verify", "--harness", "opencode"],
    ):
        result = runner.invoke(main, [*args, "--no-color", "--format", "json"])
        assert result.exit_code == 0, result.output
        notes = _override_notes(json.loads(result.output))
        assert [(n["path"], n["target"]) for n in notes] == expected, args[0]
    assert (folder / "opencode.json").is_file()

    # The note does not fail verify; plain mode prints it under the row.
    plain = runner.invoke(main, ["verify", "--harness", "opencode", "--no-color"])
    assert plain.exit_code == 0, plain.output
    flat = " ".join(plain.output.split())
    assert "Note: OpenCode 1 reads the instructions list in" in flat

    args = ["install", "--harness", "opencode", "--profile", str(profile)]
    plain = runner.invoke(main, [*args, "--no-color"])
    assert plain.exit_code == 0, plain.output
    flat = " ".join(plain.output.split())
    assert "Note: opencode - OpenCode 1 reads the instructions list in" in flat


@pytest.mark.parametrize(
    "text",
    ['{"instructions": ["mine.md"]}', "{instructions: []}", '{"instructions": 1}'],
)
def test_cli_opencode_dry_runs_name_a_replacing_jsonc(
    cli_env: tuple[Path, Path], text: str
) -> None:
    home, profile = cli_env
    folder = home / ".config" / "opencode"
    path = _opencode_jsonc(folder, text)
    runner = CliRunner()
    for verb in ("install", "update"):
        args = [verb, "--harness", "opencode", "--profile", str(profile), "--dry-run"]
        result = runner.invoke(main, [*args, "--no-color", "--format", "json"])
        assert result.exit_code == 0, result.output
        notes = _override_notes(json.loads(result.output))
        assert [n["path"] for n in notes] == [str(path)], verb
    assert not (folder / "opencode.json").exists()


@pytest.mark.parametrize("text", ['{"instructions": []}', "{instructions: []}"])
def test_cli_opencode_verify_gives_no_note_without_an_install(
    cli_env: tuple[Path, Path], text: str
) -> None:
    home, profile = cli_env
    _opencode_jsonc(home / ".config" / "opencode", text)
    runner = CliRunner()
    verify = ["verify", "--harness", "opencode", "--no-color", "--format", "json"]
    before = runner.invoke(main, verify)
    assert _override_notes(json.loads(before.output)) == []

    install = ["install", "--harness", "opencode", "--profile", str(profile)]
    assert runner.invoke(main, [*install, "--no-color"]).exit_code == 0
    uninstall = ["uninstall", "--harness", "opencode", "--yes", "--no-color"]
    removed = runner.invoke(main, uninstall)
    assert removed.exit_code == 0, removed.output
    after = runner.invoke(main, verify)
    assert _override_notes(json.loads(after.output)) == []


def test_cli_opencode_install_says_nothing_without_an_instructions_list(
    cli_env: tuple[Path, Path],
) -> None:
    home, profile = cli_env
    _opencode_jsonc(home / ".config" / "opencode", '{"theme": "dark"}')
    args = ["install", "--harness", "opencode", "--profile", str(profile)]
    result = CliRunner().invoke(main, [*args, "--no-color", "--format", "json"])
    assert result.exit_code == 0, result.output
    assert _override_notes(json.loads(result.output)) == []


def test_cli_opencode_install_update_and_verify_name_an_unparsable_jsonc(
    cli_env: tuple[Path, Path],
) -> None:
    home, profile = cli_env
    folder = home / ".config" / "opencode"
    text = "{instructions: ['mine.md']}"
    path = _opencode_jsonc(folder, text)
    expected = [(str(path), str(folder / "opencode.json"))]
    runner = CliRunner()
    for args in (
        ["install", "--harness", "opencode", "--profile", str(profile)],
        ["update", "--harness", "opencode", "--profile", str(profile)],
        ["verify", "--harness", "opencode"],
    ):
        result = runner.invoke(main, [*args, "--no-color", "--format", "json"])
        assert result.exit_code == 0, result.output
        notes = _override_notes(json.loads(result.output))
        assert [(n["path"], n["target"]) for n in notes] == expected, args[0]
    # The note changes no file of the operator's.
    assert path.read_text(encoding="utf-8") == text

    # The note does not fail verify; plain mode prints it under the row.
    plain = runner.invoke(main, ["verify", "--harness", "opencode", "--no-color"])
    assert plain.exit_code == 0, plain.output
    flat = " ".join(plain.output.split())
    assert f"Note: OpenCode 1 cannot parse {path} as JSONC" in flat


def _verify_code_without_notes(
    monkeypatch: pytest.MonkeyPatch, runner: CliRunner, args: list[str]
) -> int:
    """Return verify's exit code for *args* with the override notes turned off."""
    from apothem.cli import _cmd_verify

    with monkeypatch.context() as patch:
        patch.setattr(
            _cmd_verify, "instruction_override_advisories", lambda *a, **k: []
        )
        result = runner.invoke(main, [*args, "--no-color", "--format", "json"])
    return result.exit_code


def _opencode_cli_args(profile: Path) -> list[list[str]]:
    """Return the install, update and verify arguments for OpenCode."""
    return [
        ["install", "--harness", "opencode", "--profile", str(profile)],
        ["update", "--harness", "opencode", "--profile", str(profile)],
        ["verify", "--harness", "opencode"],
    ]


@pytest.mark.parametrize(
    ("text", "start"),
    [
        # The install leaves a top level that is not an object as it is.
        ("[]", "OpenCode 1 needs an object at the top level of"),
        # It keeps an item of the operator's that is not text in the list.
        ('{"instructions": [1]}', "OpenCode 1 needs the instructions value in"),
    ],
)
def test_cli_opencode_install_names_an_opencode_json_opencode_1_refuses(
    cli_env: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
    text: str,
    start: str,
) -> None:
    # Neither file stops the install, which reports neither; the note does.
    home, profile = cli_env
    folder = home / ".config" / "opencode"
    folder.mkdir(parents=True)
    target = folder / "opencode.json"
    target.write_text(text, encoding="utf-8")
    runner = CliRunner()
    for args in _opencode_cli_args(profile):
        result = runner.invoke(main, [*args, "--no-color", "--format", "json"])
        if args[0] != "verify":
            assert result.exit_code == 0, result.output
        else:
            # The note does not change verify's exit code.
            quiet = _verify_code_without_notes(monkeypatch, runner, args)
            assert result.exit_code == quiet, result.output
        notes = _override_notes(json.loads(result.output))
        assert [n["path"] for n in notes] == [str(target)], args[0]
        assert f"{start} {target}" in " ".join(str(notes[0]["message"]).split())


def test_cli_opencode_install_names_a_config_json_opencode_1_cannot_parse(
    cli_env: tuple[Path, Path],
) -> None:
    home, profile = cli_env
    folder = home / ".config" / "opencode"
    folder.mkdir(parents=True)
    config = folder / "config.json"
    config.write_text("{theme: 'dark'}", encoding="utf-8")
    runner = CliRunner()
    for args in _opencode_cli_args(profile):
        result = runner.invoke(main, [*args, "--no-color", "--format", "json"])
        assert result.exit_code == 0, result.output
        notes = _override_notes(json.loads(result.output))
        assert [n["path"] for n in notes] == [str(config)], args[0]
    message = " ".join(str(notes[0]["message"]).split())
    assert f"OpenCode 1 cannot parse {config} as JSONC" in message
    assert message.endswith("OpenCode 2 does not read config.json.")
    assert config.read_text(encoding="utf-8") == "{theme: 'dark'}"


def test_cli_opencode_install_refusing_opencode_json_adds_no_note(
    cli_env: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    # The install and update refuse an opencode.json they cannot parse
    # (config.unparseable) and stop before any note; verify, which fails the
    # row without a reason, gives the note.
    home, profile = cli_env
    target = home / ".config" / "opencode" / "opencode.json"
    runner = CliRunner()
    install, update, verify = _opencode_cli_args(profile)
    assert runner.invoke(main, [*install, "--no-color"]).exit_code == 0
    target.write_text("not a config file", encoding="utf-8")
    for args in ([*install, "--dry-run"], install, update):
        result = runner.invoke(main, [*args, "--no-color", "--format", "json"])
        assert result.exit_code != 0, result.output
        payload = json.loads(result.output)
        assert payload["error"]["code"] == "config.unparseable"
        assert _override_notes(payload) == [], args
    result = runner.invoke(main, [*verify, "--no-color", "--format", "json"])
    notes = _override_notes(json.loads(result.output))
    assert [n["path"] for n in notes] == [str(target)]
    assert f"OpenCode 1 cannot parse {target}" in str(notes[0]["message"])
    # Verify fails the row, and the note does not change its exit code.
    assert result.exit_code != 0, result.output
    assert result.exit_code == _verify_code_without_notes(monkeypatch, runner, verify)
    assert target.read_text(encoding="utf-8") == "not a config file"


def test_cli_opencode_update_names_an_opencode_json_it_keeps_as_json5(
    cli_env: tuple[Path, Path],
) -> None:
    # An update keeps a JSON5 opencode.json that already lists every entry, and
    # reports nothing, but OpenCode 1 cannot parse it.
    home, profile = cli_env
    target = home / ".config" / "opencode" / "opencode.json"
    runner = CliRunner()
    install, update, _verify = _opencode_cli_args(profile)
    assert runner.invoke(main, [*install, "--no-color"]).exit_code == 0
    text = target.read_text(encoding="utf-8").replace("{", "{'theme': 'dark',", 1)
    target.write_text(text, encoding="utf-8")
    result = runner.invoke(main, [*update, "--no-color", "--format", "json"])
    assert result.exit_code == 0, result.output
    notes = _override_notes(json.loads(result.output))
    assert [n["path"] for n in notes] == [str(target)]
    message = " ".join(str(notes[0]["message"]).split())
    assert f"OpenCode 1 cannot parse {target} as JSONC" in message
    assert "OpenCode 2 skips that file too" in message
    assert target.read_text(encoding="utf-8") == text


# A Windows folder as a user's environment holds it: OpenCode 1 puts it in as
# it is, and "\U" and "\A" are not JSON escapes.
_WINDOWS_FOLDER = _BACKSLASH.join(["C:", "Users", "name", "AppData", "Roaming"])


def _mcp_profile(profile: Path, variable: str) -> None:
    """Give *profile* an MCP server fs whose environment uses ${variable}."""
    profile.write_text(
        "identity:\n  name: Test User\n"
        "mcp_servers:\n"
        "  fs:\n"
        "    transport: stdio\n"
        "    command: npx\n"
        "    args: [srv]\n"
        "    env:\n"
        f"      DATA: ${{{variable}}}\n",
        encoding="utf-8",
    )


def test_cli_opencode_env_note_names_the_mcp_server_apothem_writes(
    cli_env: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    # Apothem writes {env:NAME} for a ${NAME} in an MCP server's environment.
    # OpenCode 1 cannot parse opencode.json with a Windows folder in it, so the
    # note says so; removing the reference by hand is no remedy, since the next
    # update writes it back, so the note gives the profile override instead,
    # as the MCP note does.
    home, profile = cli_env
    _mcp_profile(profile, "APOTHEM_TEST_DATA")
    monkeypatch.setenv("APOTHEM_TEST_DATA", _WINDOWS_FOLDER)
    target = home / ".config" / "opencode" / "opencode.json"
    runner = CliRunner()
    for args in _opencode_cli_args(profile):
        result = runner.invoke(main, [*args, "--no-color", "--format", "json"])
        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        notes = _override_notes(payload)
        assert [n["path"] for n in notes] == [str(target)], args[0]
        message = " ".join(str(notes[0]["message"]).split())
        assert f"OpenCode 1 cannot parse {target} as JSONC once it puts in" in message
        assert "rules included, until those values change." in message
        assert "references are removed" not in message
        assert (
            "Apothem writes {env:APOTHEM_TEST_DATA} there for the MCP server fs in "
            "the profile, and an update writes back a reference removed from "
            "opencode.json: to keep the variable as it is, restate that server "
            "under harnesses.opencode.mcp_servers.fs (an override replaces the "
            "whole server) with the value saved in a file and written as a "
            "{file:path} that names it."
        ) in message
        assert message.endswith(
            "OpenCode 2 escapes those values when the file would not parse "
            "otherwise, so it parses that file."
        )
        if args[0] != "verify":
            mcp = [
                w
                for w in payload["warnings"]
                if "harnesses.opencode.mcp_servers.fs" in str(w.get("message"))
                and w.get("operation") != "instruction_override"
            ]
            assert len(mcp) == 1, args[0]
    assert "{env:APOTHEM_TEST_DATA}" in target.read_text(encoding="utf-8")
    # The claim holds: an update writes back the reference removed by hand.
    document = json.loads(target.read_text(encoding="utf-8"))
    del document["mcp"]["fs"]["environment"]["DATA"]
    target.write_text(json.dumps(document), encoding="utf-8")
    _install, update, _verify = _opencode_cli_args(profile)
    assert runner.invoke(main, [*update, "--no-color"]).exit_code == 0
    assert "{env:APOTHEM_TEST_DATA}" in target.read_text(encoding="utf-8")


def test_cli_opencode_env_note_keeps_the_removal_remedy_for_an_operator_reference(
    cli_env: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    # The operator's own {env:NAME} beside the one Apothem writes can be removed,
    # so the note keeps that remedy and names only Apothem's reference.
    home, profile = cli_env
    _mcp_profile(profile, "APOTHEM_TEST_DATA")
    monkeypatch.setenv("APOTHEM_TEST_DATA", _WINDOWS_FOLDER)
    monkeypatch.setenv("APOTHEM_TEST_MINE", _WINDOWS_FOLDER)
    target = home / ".config" / "opencode" / "opencode.json"
    runner = CliRunner()
    install, _update, verify = _opencode_cli_args(profile)
    assert runner.invoke(main, [*install, "--no-color"]).exit_code == 0
    text = target.read_text(encoding="utf-8")
    text = text.replace("{", '{"theme": "{env:APOTHEM_TEST_MINE}",', 1)
    target.write_text(text, encoding="utf-8")
    result = runner.invoke(main, [*verify, "--no-color", "--format", "json"])
    [note] = _override_notes(json.loads(result.output))
    message = " ".join(str(note["message"]).split())
    assert "until those values change or their references are removed." in message
    assert "Apothem writes {env:APOTHEM_TEST_DATA} there for the MCP server fs" in (
        message
    )
    assert "{env:APOTHEM_TEST_MINE} there" not in message


def test_cli_opencode_env_note_is_plain_for_an_env_reference_in_another_file(
    cli_env: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    # Apothem writes only opencode.json, so a note for opencode.jsonc that uses
    # the same variable keeps the plain remedy.
    home, profile = cli_env
    _mcp_profile(profile, "APOTHEM_TEST_DATA")
    monkeypatch.setenv("APOTHEM_TEST_DATA", _WINDOWS_FOLDER)
    folder = home / ".config" / "opencode"
    runner = CliRunner()
    install, _update, verify = _opencode_cli_args(profile)
    assert runner.invoke(main, [*install, "--no-color"]).exit_code == 0
    jsonc = folder / "opencode.jsonc"
    jsonc.write_text('{"theme": "{env:APOTHEM_TEST_DATA}"}', encoding="utf-8")
    result = runner.invoke(main, [*verify, "--no-color", "--format", "json"])
    notes = _override_notes(json.loads(result.output))
    assert [n["path"] for n in notes] == [str(folder / "opencode.json"), str(jsonc)]
    message = " ".join(str(notes[1]["message"]).split())
    assert "until those values change or their references are removed." in message
    assert "Apothem writes" not in message


def _owned_mcp(
    monkeypatch: pytest.MonkeyPatch, entries: list[tuple[object, ...]]
) -> None:
    """Make the install record own each ``(*path, value)`` key in opencode.json."""
    from apothem.harnesses._shared import install_driver_ownership
    from apothem.lib.install_ledger import OwnedEntry

    owned = tuple(
        OwnedEntry(tuple(str(key) for key in entry[:-1]), "key", entry[-1])
        for entry in entries
    )
    monkeypatch.setattr(
        install_driver_ownership, "prior_ownership", lambda *_args: owned
    )


@pytest.mark.parametrize(
    ("owned", "values", "named"),
    [
        # A server an operator moved to mcp.servers.<name> is still Apothem's,
        # given as one key that holds the whole server.
        (
            [("mcp", "servers", "fs", {"environment": {"DATA": "{env:APX_A}"}})],
            {"APX_A": "C:" + _BACKSLASH + "x"},
            "Apothem writes {env:APX_A} there for the MCP server fs in the profile",
        ),
        # A server named "servers" written under mcp is not that envelope.
        (
            [("mcp", "servers", "environment", "DATA", "{env:APX_A}")],
            {"APX_A": "C:" + _BACKSLASH + "x"},
            "Apothem writes {env:APX_A} there for the MCP server servers in the "
            "profile",
        ),
        # A double quote alone breaks the text too.
        (
            [("mcp", "fs", "environment", "DATA", "{env:APX_A}")],
            {"APX_A": 'say "hi"'},
            "Apothem writes {env:APX_A} there for the MCP server fs in the profile",
        ),
        (
            [
                ("mcp", "fs", "environment", "DATA", "{env:APX_A}"),
                ("mcp", "gh", "headers", "Authorization", "{env:APX_B}"),
                ("mcp", "web", "url", "https://{env:APX_C}/mcp"),
            ],
            {"APX_A": _BACKSLASH, "APX_B": '"', "APX_C": _LF},
            "Apothem writes {env:APX_A}, {env:APX_B} and {env:APX_C} there for "
            "the MCP servers fs, gh and web in the profile",
        ),
    ],
)
def test_an_env_note_names_each_mcp_server_apothem_wrote_a_reference_for(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    owned: list[tuple[object, ...]],
    values: dict[str, str],
    named: str,
) -> None:
    for name, value in values.items():
        monkeypatch.setenv(name, value)
    _owned_mcp(monkeypatch, owned)
    document: dict[str, object] = {}
    for entry in owned:
        node = document
        for key in entry[:-2]:
            node = node.setdefault(str(key), {})  # type: ignore[assignment]
        node[str(entry[-2])] = entry[-1]
    path = _opencode_file("opencode.json", json.dumps(document))
    [note] = instruction_override_advisories("opencode", home=tmp_path)
    assert note["path"] == str(path)
    message = " ".join(str(note["message"]).split())
    assert "rules included, until those values change." in message
    assert named in message
    servers = {entry[2] if isinstance(entry[-1], dict) else entry[1] for entry in owned}
    restate = (
        "each of those servers under harnesses.opencode.mcp_servers.<name>"
        if len(servers) > 1
        else f"that server under harnesses.opencode.mcp_servers.{servers.pop()}"
    )
    assert f"to keep the variable as it is, restate {restate}" in message


# A string never closed, full of escaped quotes: each quote used to start
# another scan to the end, so the time grew with the square of the length
# (about 20 s for this one, against milliseconds for one scan).
_NEVER_CLOSED = '{"a": "' + (_BACKSLASH + '"') * 20_000


def test_a_string_never_closed_is_scanned_once(tmp_path: Path) -> None:
    import time

    path = _opencode_file("opencode.jsonc", _NEVER_CLOSED)
    started = time.perf_counter()
    [note] = instruction_override_advisories("opencode", home=tmp_path)
    elapsed = time.perf_counter() - started
    assert f"OpenCode 1 cannot parse {path} as JSONC" in str(note["message"])
    assert elapsed < 10


def test_the_check_for_where_a_token_sits_scans_a_string_never_closed_once() -> None:
    import time

    started = time.perf_counter()
    inside = install_advisories._inside_strings(_NEVER_CLOSED, [len(_NEVER_CLOSED) - 1])
    elapsed = time.perf_counter() - started
    # A string never closed is no value, so text put in there is not safe.
    assert inside is False
    assert elapsed < 10


def test_verify_reads_no_opencode_json_over_the_read_limit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from apothem.harnesses.opencode.materializer import instruction_entries

    listed = json.dumps({"instructions": instruction_entries()})
    _opencode_file("opencode.json", listed)
    jsonc = _opencode_file("opencode.jsonc", '{"instructions": []}')
    verify = {"home": tmp_path, "require_block": True}
    notes = instruction_override_advisories("opencode", **verify)
    assert [note["path"] for note in notes] == [str(jsonc)]
    # The check skips an opencode.json over the limit, and verify, which
    # would read it to find the entries, does not read it either.
    monkeypatch.setattr(install_advisories, "_READ_LIMIT", len(listed) - 1)
    assert instruction_override_advisories("opencode", home=tmp_path) != []
    assert instruction_override_advisories("opencode", **verify) == []


def _count_reads(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    """Count the bytes the check reads from the files ``{file:path}`` names."""
    import builtins

    sizes: list[int] = []

    class Counted:
        def __init__(self, handle: object) -> None:
            self.handle = handle

        def __enter__(self) -> Counted:
            return self

        def __exit__(self, *_exc: object) -> None:
            self.handle.close()  # type: ignore[attr-defined]

        def read(self, *args: int) -> bytes:
            data: bytes = self.handle.read(*args)  # type: ignore[attr-defined]
            sizes.append(len(data))
            return data

    def counted_open(*args: object, **kwargs: object) -> Counted:
        handle = builtins.open(*args, **kwargs)  # type: ignore[call-overload]  # noqa: PTH123, SIM115
        return Counted(handle)

    monkeypatch.setattr(install_advisories, "open", counted_open, raising=False)
    return sizes


def test_the_files_one_config_names_are_read_up_to_a_total(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Ten references to one file each put its text in before; past the total,
    # a reference is checked as one to a file too large to read.
    monkeypatch.setattr(install_advisories, "_PUT_IN_LIMIT", 100)
    sizes = _count_reads(monkeypatch)
    _opencode_file("part", "x" * 60)
    text = '{"k": "' + "{file:part}" * 10 + '", "instructions": 1}'
    path = _opencode_file("opencode.jsonc", text)
    [note] = instruction_override_advisories("opencode", home=tmp_path)
    assert f"needs the instructions value in {path}" in str(note["message"])
    assert sum(sizes) <= 100
    put_in, _unknown = install_advisories._opencode_substitute(text, path.parent)
    assert len(put_in) <= len(text) + 100
    # Such a reference outside a string decides the outcome, so the file is
    # not checked: its text would not parse there.
    _opencode_file("opencode.jsonc", '{"k": "{file:part}", "n": {file:part}}')
    assert instruction_override_advisories("opencode", home=tmp_path) == []
    # A later reference to a file that cannot be read still gets its note.
    _opencode_file("opencode.jsonc", '{"k": "' + "{file:part}" * 3 + '{file:gone}"}')
    [note] = instruction_override_advisories("opencode", home=tmp_path)
    assert "the file that {file:gone} in" in str(note["message"])


def test_env_values_past_the_total_leave_the_file_unchecked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(install_advisories, "_PUT_IN_LIMIT", 100)
    monkeypatch.setenv("APOTHEM_TEST_DIR", "x" * 60)
    text = '{"k": "{env:APOTHEM_TEST_DIR}", "instructions": 1}'
    _opencode_file("opencode.jsonc", text)
    assert len(instruction_override_advisories("opencode", home=tmp_path)) == 1
    text = '{"k": "{env:APOTHEM_TEST_DIR}{env:APOTHEM_TEST_DIR}", "instructions": 1}'
    _opencode_file("opencode.jsonc", text)
    assert instruction_override_advisories("opencode", home=tmp_path) == []


@pytest.mark.parametrize(
    ("value", "text", "written"),
    [
        # OpenCode 1 finds {file:path} tokens once the values are in, so a
        # value can hold one; the note names the reference that held it.
        (
            "{file:dummy-secret-value}",
            '{"k": "{env:APOTHEM_TEST_SECRET}"}',
            "{env:APOTHEM_TEST_SECRET}",
        ),
        (
            "dummy-secret-value",
            '{"k": "{file:~/{env:APOTHEM_TEST_SECRET}}"}',
            "{file:~/{env:APOTHEM_TEST_SECRET}}",
        ),
    ],
)
def test_a_reference_note_never_shows_an_env_value(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    value: str,
    text: str,
    written: str,
) -> None:
    monkeypatch.setenv("APOTHEM_TEST_SECRET", value)
    path = _opencode_file("opencode.jsonc", text)
    [note] = instruction_override_advisories("opencode", home=tmp_path)
    message = str(note["message"])
    assert f"OpenCode 1 cannot read the file that {written} in {path} names" in message
    assert "dummy-secret-value" not in message


@pytest.mark.parametrize(
    "rest",
    [
        "/secrets/token.txt",
        pytest.param(
            _BACKSLASH + "secrets/token.txt",
            marks=pytest.mark.skipif(
                sys.platform != "win32", reason="a backslash separates on Windows"
            ),
        ),
    ],
)
def test_a_home_file_token_with_a_separator_after_the_tilde_reads_from_home(
    tmp_path: Path, rest: str
) -> None:
    # Node's path.join keeps the home folder for "~//secrets/token.txt" and, on
    # Windows, for a backslash after "~/"; the file there reads.
    secret = Path.home() / "secrets" / "token.txt"
    secret.parent.mkdir(parents=True)
    secret.write_bytes(b"x")
    token = "{file:~/" + rest + "}"
    # Written as it is: OpenCode 1 puts in the file's text before it parses.
    _opencode_file("opencode.jsonc", '{"k": "' + token + '"}')
    assert instruction_override_advisories("opencode", home=tmp_path) == []
    # With the file gone, the same token gets its note.
    secret.unlink()
    [note] = instruction_override_advisories("opencode", home=tmp_path)
    assert f"cannot read the file that {token} in" in str(note["message"])


@pytest.mark.parametrize(
    ("form", "flag"),
    [
        # JSON5, which the install reads too: OpenCode 1 refuses the file.
        ("{instructions: LIST}", ""),
        # An unquoted {env:NAME}, which OpenCode 1 parses once it is in.
        ('{"instructions": LIST, "autoupdate": {env:APOTHEM_TEST_FLAG}}', "true"),
    ],
)
def test_verify_finds_the_written_list_in_an_opencode_json_that_is_not_jsonc(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, form: str, flag: str
) -> None:
    from apothem.harnesses.opencode.materializer import instruction_entries

    monkeypatch.setenv("APOTHEM_TEST_FLAG", flag)
    text = form.replace("LIST", json.dumps(instruction_entries()))
    target = _opencode_file("opencode.json", text)
    jsonc = _opencode_file("opencode.jsonc", '{"instructions": []}')
    verify = {"home": tmp_path, "require_block": True}
    notes = instruction_override_advisories("opencode", **verify)
    expected = [str(jsonc)] if flag else [str(target), str(jsonc)]
    assert [note["path"] for note in notes] == expected


def test_a_note_does_not_say_opencode_2_loads_a_broken_opencode_json(
    tmp_path: Path,
) -> None:
    _opencode_file("opencode.json", "{x: 1}")
    jsonc = _opencode_file("opencode.jsonc", "{x: 1}")
    notes = instruction_override_advisories("opencode", home=tmp_path)
    [message] = [
        " ".join(str(note["message"]).split())
        for note in notes
        if note["path"] == str(jsonc)
    ]
    assert "still loads" not in message
    assert message.endswith(
        "OpenCode 2 skips that file, which does not keep it from loading opencode.json."
    )


def test_an_opencode_jsonc_with_part_of_the_written_list_says_what_is_missing(
    tmp_path: Path,
) -> None:
    from apothem.harnesses.opencode.materializer import instruction_entries

    entries = instruction_entries()
    assert len(entries) > 1
    path = _opencode_jsonc(
        _opencode_folder(), json.dumps({"instructions": entries[1:]})
    )
    [note] = instruction_override_advisories("opencode", home=tmp_path)
    assert note["path"] == str(path)
    message = " ".join(str(note["message"]).split())
    assert (
        f"holds {len(entries) - 1} of the {len(entries)} entries Apothem writes, "
        "as a copy installs and updates do not refresh, and lacks the other one, "
        "so it does not reach OpenCode 1."
    ) in message
    assert "The profile document and rules Apothem lists" not in message


@pytest.mark.parametrize(
    "text",
    [
        # Each "{env:" or "{file:" with no "}" after it used to start another
        # scan to the end, so the time grew with the square of the length.
        pytest.param('{"a": "' + "{env:" * 40_000, id="env"),
        pytest.param('{"a": "' + "{file:" * 40_000, id="file"),
        # Each token on one long line used to look back to the line's start.
        pytest.param("// " + "{file:x}" * 200_000 + chr(10) + "{x: 1}", id="line"),
    ],
)
def test_tokens_are_found_in_one_pass(tmp_path: Path, text: str) -> None:
    import time

    path = _opencode_file("opencode.jsonc", text)
    started = time.perf_counter()
    [note] = instruction_override_advisories("opencode", home=tmp_path)
    elapsed = time.perf_counter() - started
    assert f"OpenCode 1 cannot parse {path} as JSONC" in str(note["message"])
    assert elapsed < 20


def test_each_file_a_config_names_is_read_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # OpenCode 1 reads it for each token, and finds the same text each time.
    sizes = _count_reads(monkeypatch)
    _opencode_file("part", "x")
    text = '{"k": "' + "{file:part}" * 1000 + '", "instructions": 1}'
    path = _opencode_file("opencode.jsonc", text)
    [note] = instruction_override_advisories("opencode", home=tmp_path)
    assert f"needs the instructions value in {path}" in str(note["message"])
    assert len(sizes) == 1


def test_a_file_token_after_a_comment_never_closed_leaves_the_file_unchecked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The text of a file too large to read can close the comment ("*/" needs
    # no escape in a string), after which OpenCode 1 may parse the file.
    monkeypatch.setattr(install_advisories, "_PUT_IN_LIMIT", 2)
    _opencode_file("big", "*/,")
    _opencode_file("opencode.jsonc", '{"a": 1 /*"{file:big}"k": 2}')
    assert instruction_override_advisories("opencode", home=tmp_path) == []
    # Before such a comment, the token sits inside a string, as before.
    path = _opencode_file("opencode.jsonc", '{"a": "{file:big}" /* x')
    [note] = instruction_override_advisories("opencode", home=tmp_path)
    assert f"OpenCode 1 cannot parse {path} as JSONC" in str(note["message"])


@pytest.mark.parametrize(
    ("value", "note"),
    [
        # OpenCode 1 finds a {file:path} in a value once the values are in.
        (
            "{file:dummy-secret-value}",
            "OpenCode 1 cannot read the file that {env:APOTHEM_TEST_SECRET} in",
        ),
        # A backslash before the closing quote breaks the text.
        ("dummy-secret-value" + _BACKSLASH, "once it puts in its {env:NAME} values"),
    ],
)
def test_cli_opencode_notes_never_show_an_env_value(
    cli_env: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
    value: str,
    note: str,
) -> None:
    # A note names a variable, never its value, which may be a secret.
    home, profile = cli_env
    monkeypatch.setenv("APOTHEM_TEST_SECRET", value)
    folder = home / ".config" / "opencode"
    folder.mkdir(parents=True)
    jsonc = folder / "opencode.jsonc"
    jsonc.write_bytes(b'{"theme": "{env:APOTHEM_TEST_SECRET}"}')
    runner = CliRunner()
    for args in _opencode_cli_args(profile):
        for mode in (["--format", "json"], []):
            result = runner.invoke(main, [*args, "--no-color", *mode])
            # Plain output wraps lines, so the value is looked for unwrapped.
            assert "dummy-secret-value" not in "".join(result.output.split())
            assert note in " ".join(result.output.split()), (args[0], mode)


@pytest.mark.parametrize(
    ("value", "text", "reference"),
    [
        # The {file:path} comes from the value, and its file cannot be told.
        (
            "{file:dummy-secret-value.}",
            '"{env:APOTHEM_TEST_SECRET}"',
            "{env:APOTHEM_TEST_SECRET}",
        ),
        # The value is the path itself.
        (
            "dummy-secret-value.",
            '"{file:{env:APOTHEM_TEST_SECRET}}"',
            "{file:{env:APOTHEM_TEST_SECRET}}",
        ),
    ],
)
def test_cli_opencode_unknown_reference_never_shows_an_env_value(
    cli_env: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
    value: str,
    text: str,
    reference: str,
) -> None:
    # The sentence on a reference the check cannot tell OpenCode 1 reads names
    # the token as the file spells it, never the value.
    home, profile = cli_env
    monkeypatch.setattr(install_advisories, "_WINDOWS", True)
    monkeypatch.setenv("APOTHEM_TEST_SECRET", value)
    folder = home / ".config" / "opencode"
    folder.mkdir(parents=True)
    jsonc = folder / "opencode.jsonc"
    jsonc.write_bytes(('{"a": ' + text + ', "instructions": 5}').encode("utf-8"))
    runner = CliRunner()
    for args in _opencode_cli_args(profile):
        for mode in (["--format", "json"], []):
            result = runner.invoke(main, [*args, "--no-color", *mode])
            assert "dummy-secret-value" not in "".join(result.output.split())
            flat = " ".join(result.output.split())
            assert f"the file that {reference} names" in flat, (args[0], mode)


def test_distinct_files_one_config_names_are_read_up_to_a_total(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Two files that add up to more than the total: the second is not read.
    monkeypatch.setattr(install_advisories, "_PUT_IN_LIMIT", 100)
    sizes = _count_reads(monkeypatch)
    _opencode_file("first", "x" * 60)
    _opencode_file("second", "y" * 60)
    text = '{"k": "{file:first}{file:second}", "instructions": 1}'
    path = _opencode_file("opencode.jsonc", text)
    [note] = instruction_override_advisories("opencode", home=tmp_path)
    assert f"needs the instructions value in {path}" in str(note["message"])
    assert sum(sizes) <= 100


def test_a_file_counts_against_the_total_as_its_escaped_text(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Each control character is put in as a six-character escape, so 30 bytes
    # put in 180 characters, past a total of 100.
    monkeypatch.setattr(install_advisories, "_PUT_IN_LIMIT", 100)
    _opencode_file("controls", chr(1) * 30)
    text = '{"k": "{file:controls}", "instructions": 1}'
    path = _opencode_file("opencode.jsonc", text)
    put_in, _unknown = install_advisories._opencode_substitute(text, path.parent)
    assert len(put_in) <= len(text) + 100
    [note] = instruction_override_advisories("opencode", home=tmp_path)
    assert f"needs the instructions value in {path}" in str(note["message"])
    # The escaped text is not even built, so a large file of such characters
    # takes no more than its own size.
    assert install_advisories._reference("controls", path.parent, 100).piece is None
    assert install_advisories._reference("controls", path.parent, 180).piece


def test_the_escaped_length_is_what_json_puts_in() -> None:
    text = "".join(chr(code) for code in (*range(0x80), 0xE9, 0x4E2D, 0x2028))
    expected = len(json.dumps(text, ensure_ascii=False)) - 2
    assert install_advisories._escaped_length(text) == expected


@pytest.mark.parametrize(
    ("name", "text"),
    [
        # A file larger than what is left of the total.
        ("big", '{"k": "TOKENS", "instructions": 1}'),
        # The same, in a file OpenCode 2 reads a second time with its
        # {env:NAME} values escaped.
        ("big", '{"k": "{env:APOTHEM_TEST_UNSET}TOKENS", y: 1}'),
        # A path the check cannot tell OpenCode 1 reads.
        ("big.txt.", '{"k": "TOKENS", "instructions": 1}'),
    ],
)
def test_each_path_a_config_names_is_looked_up_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, name: str, text: str
) -> None:
    # OpenCode 1 reads the file for each token; the check looks it up once,
    # whatever it found, so many tokens cost no more than one.
    monkeypatch.setattr(install_advisories, "_PUT_IN_LIMIT", 2)
    if name.endswith("."):
        monkeypatch.setattr(install_advisories, "_WINDOWS", True)
    monkeypatch.delenv("APOTHEM_TEST_UNSET", raising=False)
    looked_up: list[str] = []
    real = install_advisories._referenced_text

    def counted(found: str, folder: Path, room: int) -> str | None:
        looked_up.append(found)
        return real(found, folder, room)

    monkeypatch.setattr(install_advisories, "_referenced_text", counted)
    _opencode_file("big", "x" * 8)
    tokens = ("{file:" + name + "}") * 20_000
    path = _opencode_file("opencode.jsonc", text.replace("TOKENS", tokens))
    [note] = instruction_override_advisories("opencode", home=tmp_path)
    assert str(path) in str(note["message"])
    assert looked_up == [name]


def test_a_config_naming_too_many_files_is_not_checked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(install_advisories, "_LOOKUP_LIMIT", 3)
    for name in ("p1", "p2", "p3", "p4"):
        _opencode_file(name, "x")
    _opencode_file(
        "opencode.jsonc", '{"k": "{file:p1}{file:p2}{file:p3}", "instructions": 1}'
    )
    assert len(instruction_override_advisories("opencode", home=tmp_path)) == 1
    text = '{"k": "{file:p1}{file:p2}{file:p3}{file:p4}", "instructions": 1}'
    _opencode_file("opencode.jsonc", text)
    assert instruction_override_advisories("opencode", home=tmp_path) == []


def test_a_note_shows_a_file_token_without_control_characters_and_cut_short(
    tmp_path: Path,
) -> None:
    # A token can hold characters that drive a terminal, and be very long.
    name = chr(27) + "]0;x" + chr(7) + "a" * 300
    path = _opencode_file("opencode.jsonc", '{"k": "{file:' + name + '}"}')
    [note] = instruction_override_advisories("opencode", home=tmp_path)
    message = str(note["message"])
    assert "OpenCode 1 cannot read the file that {file:\\u001b]0;x\\u0007a" in message
    assert chr(27) not in message
    assert chr(7) not in message
    assert "a" * 300 not in message
    assert "...} in" not in message
    assert f"... in {path} names" in message


def test_verify_does_not_open_an_opencode_json_that_is_not_a_regular_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from apothem.harnesses.opencode.materializer import instruction_entries

    target = _opencode_file(
        "opencode.json", json.dumps({"instructions": instruction_entries()})
    )
    _opencode_file("opencode.jsonc", '{"instructions": []}')
    verify = {"home": tmp_path, "require_block": True}
    assert len(instruction_override_advisories("opencode", **verify)) == 1
    # Seen as a named pipe, it is neither read by the check nor opened to find
    # the written list, so verify finds no list there.
    _fake_pipe(monkeypatch, target)
    assert instruction_override_advisories("opencode", **verify) == []


def test_a_global_file_is_read_no_further_than_the_read_limit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The file grew after its size was taken: what is read stops at the limit.
    path = _opencode_file("opencode.jsonc", "{x: 1}" + " " * 20)
    assert len(instruction_override_advisories("opencode", home=tmp_path)) == 1
    monkeypatch.setattr(install_advisories, "_READ_LIMIT", 10)
    real_stat = Path.stat
    small = os.stat_result((stat.S_IFREG | 0o644, 0, 0, 1, 0, 0, 5, 0, 0, 0))

    def fake_stat(self: Path, **kwargs: bool) -> os.stat_result:
        return small if self == path else real_stat(self, **kwargs)

    monkeypatch.setattr(Path, "stat", fake_stat)
    assert instruction_override_advisories("opencode", home=tmp_path) == []


@pytest.mark.parametrize(
    "text",
    [
        pytest.param('{"a": "' + "x" * 200_000 + '"}', id="string"),
        pytest.param('{"a": "' + (_BACKSLASH + '"') * 100_000 + '"}', id="escapes"),
        pytest.param('{"a": "x"' + " " * 200_000 + "}", id="gap"),
    ],
)
def test_the_jsonc_scan_keeps_no_state_per_character(text: str) -> None:
    # A regular expression such as (?:a|b)* kept about 120 bytes for each
    # character of a long string or gap, gigabytes for a large file.
    import tracemalloc

    tracemalloc.start()
    try:
        install_advisories._parse_jsonc(text)
        install_advisories._inside_strings(text, [7])
        peak = tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()
    assert peak < 4 * len(text)
