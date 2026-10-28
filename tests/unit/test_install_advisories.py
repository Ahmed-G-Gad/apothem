# SPDX-License-Identifier: MIT

"""Install advisories for shared roots.

Installing the owner of a shared root (Codex for ``~/.agents/skills/``) puts
Apothem content in front of every reader, so the install names the readers.
Installing a reader while the shared root already holds another adapter's
Apothem content says where that content comes from.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from apothem.cli import main
from apothem.harnesses._shared import install_driver
from apothem.lib.harness_registry import SHARED_ROOTS, get_harness_entry
from apothem.lib.install_advisories import (
    hook_review_advisories,
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


def test_owner_note_agrees_with_a_single_reader(tmp_path: Path) -> None:
    # ~/.claude/CLAUDE.md has one reader (OpenCode); the note reads as one tool.
    advisories = shared_root_advisories("claude-code", home=tmp_path, project=None)
    messages = [
        str(a["message"])
        for a in advisories
        if a["role"] == "owner" and str(a["message"]).startswith("~/.claude/CLAUDE.md")
    ]
    assert messages == [
        "~/.claude/CLAUDE.md is shared: OpenCode also loads it. Installing or "
        "uninstalling Claude Code changes what that tool loads."
    ]


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
    assert "Kimi Code" in str(advisories[0]["message"])


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
    # The marker silences a repeat of this command only; nothing is de-duplicated
    # across the Claude Code copy or the PostToolUse counter.
    assert "records one marker per session" in message
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
    assert "records one marker per session" in message
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
