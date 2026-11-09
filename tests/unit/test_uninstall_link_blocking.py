# SPDX-License-Identifier: MIT

"""An uninstall never removes the operator's files, and never hides what it left.

Two cases from the Claude Code adapter:

* A hand-cleaned install whose remaining folders hold the operator's own files
  reads as not installed, so an uninstall removes nothing.
* An installed folder replaced by a link (``~/.claude/rules`` moved to a
  dotfiles folder and linked back) is left in place. Claude Code still loads
  it, so the uninstall is partial: exit 2, the record kept, and a second run
  after the link is replaced finishes the job.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pytest
from click.testing import CliRunner

from apothem import cli
from apothem.harnesses._shared import install_driver
from apothem.harnesses.claude_code import ClaudeCodeAdapter


@pytest.fixture
def claude(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the user home and the backup root into *tmp_path*; return ``~/.claude``."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setattr(install_driver, "BACKUP_ROOT", tmp_path / "apothem-backups")
    return home / ".claude"


def _link_folder(link: Path, target: Path) -> None:
    if sys.platform == "win32":
        import _winapi

        _winapi.CreateJunction(str(target), str(link))
    else:
        link.symlink_to(target, target_is_directory=True)


def _uninstall() -> tuple[int, dict]:  # type: ignore[type-arg]
    result = CliRunner().invoke(
        cli.main, ["uninstall", "--harness", "claude-code", "--yes", "--format", "json"]
    )
    return result.exit_code, json.loads(result.output)


def test_a_hand_cleaned_install_with_the_users_files_is_left_alone(
    claude: Path,
) -> None:
    adapter = ClaudeCodeAdapter()
    adapter.install({})
    skills = claude / "skills"
    keep = sorted(p for p in skills.iterdir() if p.is_dir())[0]
    for path in (
        claude / "CLAUDE.md",
        claude / ".apothem",
        claude / "rules",
        claude / "agents",
    ):
        if path.is_dir():
            shutil.rmtree(path)
        elif path.exists():
            path.unlink()
    for skill in skills.iterdir():
        if skill != keep:
            shutil.rmtree(skill)
    mine = keep / "my-notes.md"
    mine.write_text("mine\n", encoding="utf-8")
    (claude / "agents").mkdir()
    agent = claude / "agents" / "citation-auditor.md"
    agent.write_text("mine\n", encoding="utf-8")

    installed = adapter.is_installed()
    code, envelope = _uninstall()

    assert installed is False
    assert code == 0
    assert [r["outcome"] for r in envelope["results"]] == ["skipped"]
    assert mine.read_text(encoding="utf-8") == "mine\n"
    assert agent.read_text(encoding="utf-8") == "mine\n"


def test_a_linked_installed_folder_makes_the_uninstall_partial(
    claude: Path, tmp_path: Path
) -> None:
    ClaudeCodeAdapter().install({})
    rules = claude / "rules"
    dotfiles = tmp_path / "dotfiles" / "rules"
    dotfiles.parent.mkdir(parents=True)
    shutil.move(str(rules), str(dotfiles))
    _link_folder(rules, dotfiles)
    kept = sorted(dotfiles.iterdir())

    first_code, first = _uninstall()
    left = [path.exists() for path in kept]
    still_installed = ClaudeCodeAdapter().is_installed()
    rules.rmdir() if sys.platform == "win32" else rules.unlink()
    shutil.move(str(dotfiles), str(rules))
    second_code, second = _uninstall()

    assert first_code == cli._EXIT_PARTIAL
    assert first["status"] == "partial"
    summary = first["results"][0]
    assert summary["operation"] == "uninstall"
    assert summary["outcome"] == "error"
    assert str(rules) in summary["message"]
    assert "still loads them" in summary["message"]
    assert kept
    assert all(left)
    assert still_installed is True
    assert second_code == 0, second
    assert [r["outcome"] for r in second["results"]] == ["updated"]
    assert not any((rules / path.name).exists() for path in kept)
