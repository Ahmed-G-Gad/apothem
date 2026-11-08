# SPDX-License-Identifier: MIT

"""An uninstall removes only what the install record shows Apothem wrote.

Each install record carries the SHA-256 of every file the install wrote. An
uninstall removes a file only while it still has that content, so the
operator's own files survive whatever happened in between: a partial uninstall,
a folder cleaned by hand, a rollback, a link to a dotfiles folder. An uninstall
that does not finish appends an ``uninstall-incomplete`` record, which a second
run, an install, an update or a rollback supersedes.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pytest
from click.testing import CliRunner

from apothem import cli
from apothem.harnesses._shared import install_driver, install_driver_lifecycle
from apothem.harnesses._shared import install_driver_written as written
from apothem.harnesses.claude_code import ClaudeCodeAdapter
from apothem.lib import install_ledger
from apothem.lib.install_ledger import LedgerRecord, LedgerTarget


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


def _unlink_folder(link: Path) -> None:
    link.rmdir() if sys.platform == "win32" else link.unlink()


def _run(*args: str) -> tuple[int, dict]:  # type: ignore[type-arg]
    result = CliRunner().invoke(cli.main, [*args, "--format", "json"])
    return result.exit_code, json.loads(result.output)


def _uninstall() -> tuple[int, dict]:  # type: ignore[type-arg]
    return _run("uninstall", "--harness", "claude-code", "--yes")


def _root(claude: Path) -> str:
    return str(claude)


def _unfinished(claude: Path) -> LedgerRecord | None:
    return install_ledger.unfinished_uninstall("claude_code", root=_root(claude))


def _partial_uninstall(claude: Path, tmp_path: Path) -> tuple[Path, Path]:
    """Install, link ``~/.claude/rules`` to a dotfiles folder, uninstall (partial)."""
    ClaudeCodeAdapter().install({})
    rules = claude / "rules"
    dotfiles = tmp_path / "dotfiles" / "rules"
    dotfiles.parent.mkdir(parents=True)
    shutil.move(str(rules), str(dotfiles))
    _link_folder(rules, dotfiles)
    code, _ = _uninstall()
    assert code == cli._EXIT_PARTIAL
    return rules, dotfiles


def _restore_link(rules: Path, dotfiles: Path) -> None:
    _unlink_folder(rules)
    shutil.move(str(dotfiles), str(rules))


def _skill_name() -> str:
    return sorted(
        path.name
        for path in Path("src/apothem/skills").iterdir()
        if path.is_dir() and not path.name.startswith("_")
    )[0]


def _add_users_files(claude: Path, rule_name: str) -> list[Path]:
    """Write the operator's own files where Apothem's used to be."""
    skill = claude / "skills" / _skill_name()
    skill.mkdir(parents=True, exist_ok=True)
    agents = claude / "agents"
    agents.mkdir(parents=True, exist_ok=True)
    rules = claude / "rules"
    rules.mkdir(parents=True, exist_ok=True)
    mine = [
        skill / "my-notes.md",
        agents / "citation-auditor.md",
        rules / rule_name,
    ]
    for path in mine:
        path.write_text("mine\n", encoding="utf-8")
    return mine


def test_a_target_records_digests_and_older_records_still_load() -> None:
    target = LedgerTarget(
        path="/x/skills/a",
        mode="merge_tree_entries",
        ownership_class="apothem-owned",
        files={"SKILL.md": "ab", "ref/b.md": "cd"},
    )
    older = {"path": "/x/a.md", "mode": "write_text", "ownership_class": "generated"}

    again = LedgerTarget.from_dict(json.loads(json.dumps(target.to_dict())))
    loaded = LedgerTarget.from_dict(older)

    assert again == target
    assert again.files == {"SKILL.md": "ab", "ref/b.md": "cd"}
    assert loaded.digest is None
    assert loaded.files is None


def test_an_install_records_what_it_wrote(claude: Path) -> None:
    ClaudeCodeAdapter().install({})

    record = install_ledger.current_install_record("claude_code", root=_root(claude))

    assert record is not None
    skill = next(t for t in record.targets if t.path.endswith(_skill_name()))
    assert skill.files
    assert all(len(digest) == 64 for digest in skill.files.values())
    agent = next(t for t in record.targets if t.path.endswith("citation-auditor.md"))
    assert agent.digest is not None


def test_a_hand_cleaned_partial_uninstall_keeps_the_users_files(
    claude: Path, tmp_path: Path
) -> None:
    rules, dotfiles = _partial_uninstall(claude, tmp_path)
    rule_name = sorted(path.name for path in dotfiles.iterdir())[0]
    _unlink_folder(rules)
    shutil.rmtree(claude)
    mine = _add_users_files(claude, rule_name)
    (claude / "CLAUDE.md").write_text("my own CLAUDE.md\n", encoding="utf-8")

    code, envelope = _uninstall()

    assert code == 0, envelope
    assert all(path.read_text(encoding="utf-8") == "mine\n" for path in mine)
    assert (claude / "CLAUDE.md").read_text(encoding="utf-8") == "my own CLAUDE.md\n"
    assert _unfinished(claude) is None


def test_the_users_files_survive_an_uninstall_after_a_rollback(
    claude: Path, tmp_path: Path
) -> None:
    rules, dotfiles = _partial_uninstall(claude, tmp_path)
    _restore_link(rules, dotfiles)

    rolled = CliRunner().invoke(
        cli.main, ["rollback", "--harness", "claude-code", "--yes"]
    )
    cleared = _unfinished(claude)
    mine = _add_users_files(claude, "my-rule.md")
    code, envelope = _uninstall()

    assert rolled.exit_code == 0, rolled.output
    assert cleared is None
    assert code in (0, cli._EXIT_PARTIAL), envelope
    assert all(path.read_text(encoding="utf-8") == "mine\n" for path in mine)


@pytest.mark.parametrize("command", ["install", "update"])
def test_an_install_or_update_clears_the_unfinished_uninstall(
    claude: Path, tmp_path: Path, command: str
) -> None:
    rules, dotfiles = _partial_uninstall(claude, tmp_path)
    before = _unfinished(claude)
    _restore_link(rules, dotfiles)

    adapter = ClaudeCodeAdapter()
    run = adapter.install({}) if command == "install" else adapter.update({})

    assert before is not None
    assert not run.errors, run.errors
    assert _unfinished(claude) is None
    code, envelope = _uninstall()
    assert code == 0, envelope
    assert ClaudeCodeAdapter().is_installed() is False


def test_a_finished_retry_clears_the_unfinished_uninstall(
    claude: Path, tmp_path: Path
) -> None:
    rules, dotfiles = _partial_uninstall(claude, tmp_path)
    _restore_link(rules, dotfiles)

    code, envelope = _uninstall()

    assert code == 0, envelope
    assert _unfinished(claude) is None
    assert ClaudeCodeAdapter().is_installed() is False
    assert not rules.exists() or not any(rules.iterdir())


def test_a_link_holding_only_the_users_files_lets_the_uninstall_finish(
    claude: Path, tmp_path: Path
) -> None:
    rules, dotfiles = _partial_uninstall(claude, tmp_path)
    edited, *others = sorted(dotfiles.iterdir())
    for path in others:
        shutil.rmtree(path) if path.is_dir() else path.unlink()
    edited.write_text("my edits\n", encoding="utf-8")
    mine = dotfiles / "my-own-rule.md"
    mine.write_text("mine\n", encoding="utf-8")

    installed = ClaudeCodeAdapter().is_installed()
    code, envelope = _uninstall()
    again, _ = _uninstall()

    assert installed is True
    assert code == 0, envelope
    assert envelope["status"] == "success"
    messages = [str(w["message"]) for w in envelope["warnings"]]
    assert any(str(rules) in message for message in messages), messages
    assert again == 0
    assert mine.read_text(encoding="utf-8") == "mine\n"
    assert edited.read_text(encoding="utf-8") == "my edits\n"
    assert ClaudeCodeAdapter().is_installed() is False


def test_a_cleared_link_reads_as_not_installed(claude: Path, tmp_path: Path) -> None:
    _, dotfiles = _partial_uninstall(claude, tmp_path)
    for path in list(dotfiles.iterdir()):
        shutil.rmtree(path) if path.is_dir() else path.unlink()
    mine = dotfiles / "my-own-rule.md"
    mine.write_text("mine\n", encoding="utf-8")

    code, envelope = _uninstall()

    assert code == 0, envelope
    assert [r["outcome"] for r in envelope["results"]] == ["skipped"]
    assert mine.read_text(encoding="utf-8") == "mine\n"


def test_a_linked_whole_home_folder_is_left_as_it_is(
    claude: Path, tmp_path: Path
) -> None:
    ClaudeCodeAdapter().install({})
    dotfiles = tmp_path / "dotfiles" / ".claude"
    dotfiles.parent.mkdir(parents=True)
    shutil.move(str(claude), str(dotfiles))
    _link_folder(claude, dotfiles)
    before = sorted(str(path) for path in dotfiles.rglob("*"))

    code, envelope = _uninstall()

    assert code in (cli._EXIT_PARTIAL, cli._EXIT_EXPECTED), envelope
    assert sorted(str(path) for path in dotfiles.rglob("*")) == before


def test_an_exception_mid_uninstall_keeps_the_install_for_a_retry(
    claude: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ClaudeCodeAdapter().install({})
    real = written.backup_existing
    calls = {"n": 0}

    def fails_third(*args: object, **kwargs: object) -> object:
        calls["n"] += 1
        if calls["n"] == 3:
            raise OSError("backup disk full")
        return real(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(written, "backup_existing", fails_third)
    code, envelope = _uninstall()
    monkeypatch.setattr(written, "backup_existing", real)
    unfinished = _unfinished(claude)
    installed = ClaudeCodeAdapter().is_installed()
    retry_code, retry = _uninstall()

    assert code == cli._EXIT_EXPECTED, envelope
    assert envelope["results"][0]["outcome"] == "error"
    assert unfinished is not None
    assert unfinished.targets
    assert installed is True
    assert retry_code == 0, retry
    assert ClaudeCodeAdapter().is_installed() is False
    assert not (claude / "agents" / "citation-auditor.md").exists()


def test_a_failed_step_with_the_rest_removed_is_partial(
    claude: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ClaudeCodeAdapter().install({})
    real = install_driver_lifecycle.remove_written
    calls = {"n": 0}

    def fails_third(target: Path, **kwargs: object) -> object:
        calls["n"] += 1
        if calls["n"] == 3:
            return install_driver._result(
                "error", "remove", target, "simulated failure"
            )
        return real(target, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(install_driver_lifecycle, "remove_written", fails_third)
    code, envelope = _uninstall()
    monkeypatch.setattr(install_driver_lifecycle, "remove_written", real)
    retry_code, retry = _uninstall()

    assert code == cli._EXIT_PARTIAL, envelope
    assert envelope["status"] == "partial"
    assert envelope["results"][0]["outcome"] == "error"
    assert retry_code == 0, retry


def test_a_changed_apothem_file_is_kept_and_named(claude: Path) -> None:
    ClaudeCodeAdapter().install({})
    agent = claude / "agents" / "citation-auditor.md"
    agent.write_text("my edits\n", encoding="utf-8")
    skill = claude / "skills" / _skill_name()
    notes = skill / "my-notes.md"
    notes.write_text("mine\n", encoding="utf-8")

    code, envelope = _uninstall()

    assert code == 0, envelope
    assert agent.read_text(encoding="utf-8") == "my edits\n"
    assert notes.read_text(encoding="utf-8") == "mine\n"
    assert sorted(path.name for path in skill.iterdir()) == ["my-notes.md"]
    named = [str(path) for w in envelope["warnings"] for path in w["paths"]]
    assert str(agent) in named
    assert str(skill) in named


def test_json_warnings_are_grouped_like_the_plain_output(
    claude: Path, tmp_path: Path
) -> None:
    ClaudeCodeAdapter().install({})
    agents = sorted((claude / "agents").iterdir())[:3]
    for agent in agents:
        agent.write_text("my edits\n", encoding="utf-8")

    code, envelope = _uninstall()
    plain = CliRunner().invoke(
        cli.main, ["uninstall", "--harness", "claude-code", "--yes", "--no-color"]
    )

    assert code == 0, envelope
    changed = [w for w in envelope["warnings"] if w.get("count") == 3]
    assert len(changed) == 1
    assert sorted(changed[0]["paths"]) == sorted(str(a) for a in agents)
    assert plain.exit_code == 0
