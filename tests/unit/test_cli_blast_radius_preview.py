# SPDX-License-Identifier: MIT

"""The install-all blast-radius preview + confirmation gate.

``install --harness all`` fans out into mixed scopes: the ten project-scope
adapters (cursor, gemini-cli, github-copilot, windsurf, kimi-code, codebuddy,
kiro, trae, zed, glm) materialize under the supplied ``--project`` root, while
the seven user-scope adapters (antigravity, claude-code, codex, hermes,
open-claw, opencode, qwen-code) write under the operator's real home
directory — outside that root. The command discloses that partition before any write and, when home-rooted
writes are involved, guards them with an interactive confirmation. ``--yes``, a
non-interactive context, ``--dry-run``, and ``--format json`` each bypass the
prompt; dry-run and json still avoid mutation.

These tests drive the real seventeen-adapter registry through the CLI under an
isolated HOME so no real harness state is touched.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from click.testing import CliRunner

import apothem.cli as cli
from apothem.cli import main
from apothem.harnesses._shared import install_driver

PROJECT_ROOTED = frozenset(
    {
        "cursor",
        "gemini-cli",
        "github-copilot",
        "windsurf",
        "kimi-code",
        "codebuddy",
        "kiro",
        "trae",
        "zed",
        "glm",
    }
)
HOME_ROOTED = frozenset(
    {
        "antigravity",
        "claude-code",
        "codex",
        "hermes",
        "open-claw",
        "opencode",
        "qwen-code",
    }
)
_PROFILE = "identity:\n  name: Test User\nseriousness: PERSONAL_USE\n"
_TARGET_RE = re.compile(r"^\s+(?P<id>[a-z0-9-]+)\s+->")


@pytest.fixture
def install_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[Path, Path, Path]:
    """Isolate HOME so user-scope writes land under tmp. Returns (profile, project, home)."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))  # Windows HOME resolution
    monkeypatch.setenv("APOTHEM_HOME", str(tmp_path / "apothem-home"))
    monkeypatch.setattr(install_driver, "BACKUP_ROOT", tmp_path / "backups")

    profile = tmp_path / "profile.yaml"
    profile.write_text(_PROFILE, encoding="utf-8")
    project = tmp_path / "proj"
    project.mkdir()
    return profile, project, home


def _parse_preview_groups(output: str) -> tuple[set[str], set[str]]:
    """Return (project-rooted ids, home-rooted ids) parsed from the preview."""
    project_ids: set[str] = set()
    home_ids: set[str] = set()
    section: str | None = None
    for line in output.splitlines():
        if "Under the project root" in line:
            section = "project"
            continue
        if "Under your home directory" in line:
            section = "home"
            continue
        match = _TARGET_RE.match(line)
        if not match:
            continue
        if section == "project":
            project_ids.add(match["id"])
        elif section == "home":
            home_ids.add(match["id"])
    return project_ids, home_ids


def test_preview_partitions_home_and_project_targets(
    runner: CliRunner, install_env: tuple[Path, Path, Path]
) -> None:
    """The preview lists the 7 home-rooted adapters separately from project-rooted."""
    profile, project, _ = install_env
    # Non-interactive (no TTY under the runner) bypasses the prompt and proceeds.
    result = runner.invoke(
        main,
        [
            "install",
            "--harness",
            "all",
            "--profile",
            str(profile),
            "--project",
            str(project),
            "--no-color",
        ],
    )
    assert result.exit_code == 0, result.output

    project_ids, home_ids = _parse_preview_groups(result.output)
    assert home_ids == set(HOME_ROOTED)
    assert project_ids == set(PROJECT_ROOTED)
    # The two groups are disjoint and cover all seventeen adapters.
    assert project_ids & home_ids == set()
    assert len(project_ids | home_ids) == 17


def test_declined_confirmation_writes_zero_files(
    runner: CliRunner,
    install_env: tuple[Path, Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An interactive decline aborts before any write — project and home untouched."""
    profile, project, home = install_env
    monkeypatch.setattr(cli, "_stdin_is_interactive", lambda: True)

    result = runner.invoke(
        main,
        [
            "install",
            "--harness",
            "all",
            "--profile",
            str(profile),
            "--project",
            str(project),
            "--no-color",
        ],
        input="n\n",
    )

    assert result.exit_code != 0  # click.Abort -> non-zero, "Aborted!"
    assert "Proceed and write" in result.output  # the prompt was shown
    # No file written anywhere: project tree and a representative home target.
    assert [p for p in project.rglob("*") if p.is_file()] == []
    assert not (home / ".claude" / "settings.json").exists()
    assert not (home / ".codex" / "AGENTS.md").exists()


def test_yes_bypasses_prompt_and_proceeds(
    runner: CliRunner,
    install_env: tuple[Path, Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``--yes`` proceeds without prompting even with a TTY attached."""
    profile, project, _ = install_env
    monkeypatch.setattr(cli, "_stdin_is_interactive", lambda: True)

    result = runner.invoke(
        main,
        [
            "install",
            "--harness",
            "all",
            "--profile",
            str(profile),
            "--project",
            str(project),
            "--no-color",
            "--yes",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Proceed and write" not in result.output  # no prompt attempted
    assert any("Installed" in line for line in result.output.splitlines())


def test_json_mode_attempts_no_prompt_and_emits_no_preview(
    runner: CliRunner,
    install_env: tuple[Path, Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``--format json`` never prompts and keeps the machine envelope clean."""
    profile, project, _ = install_env
    monkeypatch.setattr(cli, "_stdin_is_interactive", lambda: True)

    result = runner.invoke(
        main,
        [
            "install",
            "--harness",
            "all",
            "--profile",
            str(profile),
            "--project",
            str(project),
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Proceed and write" not in result.output
    assert "will write" not in result.output  # the plain-text preview heading
    payload = json.loads(result.output)  # the envelope still parses cleanly
    assert payload["command"] == "install"


def test_dry_run_shows_preview_and_writes_nothing(
    runner: CliRunner, install_env: tuple[Path, Path, Path]
) -> None:
    """``--dry-run`` discloses the same partition without prompting or writing."""
    profile, project, home = install_env

    result = runner.invoke(
        main,
        [
            "install",
            "--harness",
            "all",
            "--profile",
            str(profile),
            "--project",
            str(project),
            "--no-color",
            "--dry-run",
        ],
    )

    assert result.exit_code == 0, result.output
    project_ids, home_ids = _parse_preview_groups(result.output)
    assert home_ids == set(HOME_ROOTED)
    assert project_ids == set(PROJECT_ROOTED)
    # Nothing mutated under either root.
    assert [p for p in project.rglob("*") if p.is_file()] == []
    assert not (home / ".claude" / "settings.json").exists()
