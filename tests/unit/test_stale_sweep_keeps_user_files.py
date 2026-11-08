# SPDX-License-Identifier: MIT

"""Install, update and uninstall leave a user's files in the paths 1.5.0 swept.

Releases 1.0.1 to 1.5.0 removed each path below whole on every install and
update, whatever it held, though no release ever installed a file there
(``~/.claude/commands``, ``~/.codex/rules`` and others). Each test places a
user's file at every such path, runs the adapter's install, update and
uninstall, and checks every file is still there, byte for byte.
"""

from __future__ import annotations

import json
import posixpath
import sys
from collections.abc import Callable
from pathlib import Path

import pytest
from click.testing import CliRunner

from apothem.cli import main
from apothem.harnesses._shared import install_driver
from apothem.harnesses._shared.install_driver_retention import (
    BACKUP_KEEP,
    RETIRED_SWEEPS,
    _holds_retired_sweep,
    prune_history,
)
from apothem.lib import install_ledger
from apothem.lib.harness_registry import get_harness_entry, load_adapter_class
from apothem.lib.install_ledger import LedgerRecord, LedgerTarget

#: The stale-sweep entries main listed before this change, by public id: the
#: install root they are relative to, and the entries.
_FORMER: dict[str, tuple[str, tuple[str, ...]]] = {
    "claude-code": (
        "~/.claude",
        (
            "src",
            "conformity",
            "schemas",
            "hooks",
            "config",
            "scripts",
            "tools",
            "lib",
            "templates",
            "docs",
            "tests",
            "packaging",
            "mcp",
            "examples",
            "assets",
            "site",
            "public",
            "commands",
            "statuslines/__init__.py",
            "rules/AGENTS.md",
            "skills/AGENTS.md",
            "agents/AGENTS.md",
            "statuslines/AGENTS.md",
            "output-styles/AGENTS.md",
        ),
    ),
    "codex": (
        "~/.codex",
        (
            "../.config/apothem/hooks",
            "../.agents/skills/AGENTS.md",
            "rules",
            "commands",
        ),
    ),
    "gemini-cli": (
        "project",
        (
            "skills/AGENTS.md",
            ".gemini/apothem/templates",
            ".gemini/apothem/hooks",
            ".gemini/apothem/rules",
        ),
    ),
    "opencode": ("~/.config/opencode", ("apothem/templates", "apothem/hooks")),
    "qwen-code": (
        "~/.qwen",
        ("skills/AGENTS.md", "apothem/templates", "apothem/hooks"),
    ),
    "hermes": (
        "~/.hermes",
        (
            "cli-config.yaml",
            "profile.yaml",
            "apothem/templates",
            "apothem/hooks",
            "apothem/skills",
            "apothem/agents",
        ),
    ),
    "open-claw": (
        "~/.openclaw",
        (
            "../.open-claw/config.yaml",
            "apothem/templates",
            "apothem/hooks",
            "apothem/skills",
            "apothem/agents",
        ),
    ),
    "antigravity": ("~/.gemini", ("antigravity",)),
    "kimi-code": (
        "project",
        (
            ".kimi-code/apothem/skills/AGENTS.md",
            ".kimi-code/apothem/templates",
            ".kimi-code/apothem/hooks",
            ".kimi-code/apothem/rules",
            ".kimi-code/apothem/skills",
            ".kimi-code/apothem/agents",
        ),
    ),
}

_FILE_SUFFIXES = (".py", ".md", ".yaml")


@pytest.fixture
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    folder = tmp_path / "home"
    folder.mkdir()
    monkeypatch.setenv("HOME", str(folder))
    monkeypatch.setenv("USERPROFILE", str(folder))
    for name in ("CODEX_HOME", "XDG_CONFIG_HOME", "OPENCODE_CONFIG_DIR"):
        monkeypatch.delenv(name, raising=False)
    return folder


def _plant(root: Path, entries: tuple[str, ...]) -> dict[Path, bytes]:
    """Put a user's file at or inside each former entry; return what was written."""
    planted: dict[Path, bytes] = {}
    for entry in entries:
        target = root / entry
        if not target.name.endswith(_FILE_SUFFIXES):
            target = target / "mine.txt"
        target.parent.mkdir(parents=True, exist_ok=True)
        body = f"a user's own file at {entry}\n".encode()
        target.write_bytes(body)
        planted[target] = body
    return planted


def _runner(public_id: str, project: Path) -> tuple[Callable[[str], object], bool]:
    adapter = load_adapter_class(get_harness_entry(public_id))()
    scoped = _FORMER[public_id][0] == "project"

    def run(action: str) -> object:
        method = getattr(adapter, action)
        if action == "uninstall":
            return method(project=project) if scoped else method()
        return method({}, project=project) if scoped else method({})

    return run, scoped


@pytest.mark.parametrize("public_id", sorted(_FORMER))
def test_a_users_files_in_formerly_swept_paths_survive(
    public_id: str, home: Path, tmp_path: Path
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    base, entries = _FORMER[public_id]
    root = project if base == "project" else home / base.removeprefix("~/")
    planted = _plant(root, entries)
    run, _scoped = _runner(public_id, project)

    for action in ("install", "update", "uninstall"):
        run(action)
        for path, body in planted.items():
            assert path.read_bytes() == body, f"{action} changed {path}"


def test_no_stale_sweep_entry_names_a_folder_a_user_or_tool_writes() -> None:
    # The sweep removes a listed path whole, so only Apothem's own namespace may
    # be listed: a path inside an apothem folder, or Kimi Code's .apothem tree.
    for name in (
        "claude_code",
        "codex",
        "gemini_cli",
        "opencode",
        "qwen_code",
        "hermes",
        "open_claw",
        "kimi_code",
    ):
        for entry in install_driver.load_rules(name).stale_sweep:
            parts = Path(entry).parts
            assert "apothem" in parts or ".apothem" in parts, (name, entry)


def _old_sweep_record(home: Path, backups: Path, stamp: str) -> LedgerRecord:
    """Record a 1.5.0-style install that swept ~/.claude/commands whole."""
    copy = backups / stamp / "claude_code" / ".claude" / "commands"
    copy.mkdir(parents=True)
    (copy / "deploy.md").write_text("my deploy command\n", "utf-8")
    (copy / "review.md").write_text("my review command\n", "utf-8")
    record = LedgerRecord.create(
        harness="claude_code",
        root=home / ".claude",
        kind="install",
        targets=(
            LedgerTarget(
                str(home / ".claude" / "commands"),
                "sweep_stale",
                "operator-owned",
                backup_ref=str(copy),
                outcome="updated",
            ),
        ),
    )
    install_ledger.append_record(record)
    return record


@pytest.fixture
def backups(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    folder = tmp_path / "backups"
    monkeypatch.setattr(install_driver, "BACKUP_ROOT", folder)
    return folder


def test_rollback_restores_a_swept_folder_that_is_gone(
    home: Path, backups: Path
) -> None:
    record = _old_sweep_record(home, backups, "20261001T000000Z")

    results = install_driver.rollback_install(
        record, harness_name="claude_code", harness_root=home / ".claude"
    )

    commands = home / ".claude" / "commands"
    assert (commands / "deploy.md").read_text("utf-8") == "my deploy command\n"
    assert (commands / "review.md").read_text("utf-8") == "my review command\n"
    restore = [r for r in results if r.operation == "restore_backup"]
    assert restore[0].backup_path is not None


def test_rollback_never_overwrites_what_is_there_now(home: Path, backups: Path) -> None:
    record = _old_sweep_record(home, backups, "20261001T000000Z")
    commands = home / ".claude" / "commands"
    commands.mkdir(parents=True)
    (commands / "deploy.md").write_text("my newer deploy command\n", "utf-8")
    (commands / "added-later.md").write_text("added later\n", "utf-8")

    install_driver.rollback_install(
        record, harness_name="claude_code", harness_root=home / ".claude"
    )

    assert (commands / "deploy.md").read_text("utf-8") == "my newer deploy command\n"
    assert (commands / "added-later.md").read_text("utf-8") == "added later\n"
    assert (commands / "review.md").read_text("utf-8") == "my review command\n"


def test_retention_keeps_a_backup_set_holding_a_swept_folder(
    home: Path, backups: Path
) -> None:
    _old_sweep_record(home, backups, "20261001T000000Z")
    for day in range(2, 2 + BACKUP_KEEP + 3):
        newer = backups / f"202610{day:02d}T000000Z" / "claude_code" / ".claude" / "x"
        newer.mkdir(parents=True)
        (newer / "f").write_text("x", "utf-8")
        install_ledger.append_record(
            LedgerRecord.create(
                harness="claude_code", root=home / ".claude", kind="install"
            )
        )

    report = prune_history("claude_code")

    assert (
        backups / "20261001T000000Z" / "claude_code" / ".claude" / "commands"
    ).is_dir()
    assert "20261001T000000Z" not in report.pruned
    assert "20261001T000000Z" in report.retired
    assert report.pruned  # other old sets still go


#: Where a harness's backup set keys a path under its install root: relative
#: to the write boundary, the root's parent (the project for project scope).
_BACKUP_PREFIX = {
    "claude-code": ".claude",
    "codex": ".codex",
    "gemini-cli": "",
    "opencode": "opencode",
    "qwen-code": ".qwen",
    "hermes": ".hermes",
    "open-claw": ".openclaw",
    "kimi-code": "",
    "antigravity": ".gemini",
}


@pytest.mark.parametrize("public_id", sorted(_FORMER))
def test_every_formerly_swept_path_keeps_its_backup(public_id: str) -> None:
    # A backup set that holds one of these may be the user's only copy.
    package = public_id.replace("-", "_")
    still_swept = set(install_driver.load_rules(package).stale_sweep)
    retired = RETIRED_SWEEPS[package]
    for entry in _FORMER[public_id][1]:
        if entry in still_swept:
            continue
        key = posixpath.normpath(posixpath.join(_BACKUP_PREFIX[public_id], entry))
        assert any(key == r or key.startswith(f"{r}/") for r in retired), key


@pytest.mark.parametrize("public_id", sorted(_FORMER))
def test_current_installs_never_back_up_a_retired_sweep_path(
    public_id: str, home: Path, backups: Path, tmp_path: Path
) -> None:
    # Otherwise RETIRED_SWEEPS would keep every set, and retention would stop.
    project = tmp_path / "project"
    project.mkdir()
    base = _FORMER[public_id][0]
    root = project if base == "project" else home / base.removeprefix("~/")
    _plant(root, _FORMER[public_id][1])
    if public_id in ("claude-code", "codex"):
        # A user's own instruction file makes every pass take a backup set.
        anchor = root / ("CLAUDE.md" if public_id == "claude-code" else "AGENTS.md")
        anchor.write_text("my own instructions\n", "utf-8")
    run, _scoped = _runner(public_id, project)
    for action in ("install", "update", "update", "uninstall"):
        run(action)
    package = public_id.replace("-", "_")
    stamps = [p.name for p in backups.iterdir()] if backups.exists() else []
    if public_id in ("claude-code", "codex"):
        assert stamps
    assert not [s for s in stamps if _holds_retired_sweep(s, package)]


def test_rollback_leaves_a_swept_folder_that_is_now_a_file(
    home: Path, backups: Path
) -> None:
    record = _old_sweep_record(home, backups, "20261001T000000Z")
    commands = home / ".claude" / "commands"
    commands.parent.mkdir(parents=True, exist_ok=True)
    commands.write_text("now a file\n", "utf-8")

    results = install_driver.rollback_install(
        record, harness_name="claude_code", harness_root=home / ".claude"
    )

    assert commands.read_text("utf-8") == "now a file\n"
    [row] = [r for r in results if r.operation == "restore_backup"]
    assert row.outcome == "skipped"
    assert row.backup_path is not None
    assert "is now a file" in row.message


@pytest.mark.parametrize(
    "kind", ["symlink", *(["junction"] if sys.platform == "win32" else [])]
)
def test_rollback_leaves_a_swept_folder_that_is_now_a_link(
    kind: str, home: Path, backups: Path
) -> None:
    # A junction is not is_symlink(), but it is a link all the same.
    record = _old_sweep_record(home, backups, "20261001T000000Z")
    elsewhere = home / "my-commands"
    elsewhere.mkdir()
    commands = home / ".claude" / "commands"
    commands.parent.mkdir(parents=True, exist_ok=True)
    if kind == "junction":
        import _winapi

        _winapi.CreateJunction(str(elsewhere), str(commands))
    else:
        try:
            commands.symlink_to(elsewhere, target_is_directory=True)
        except OSError as exc:  # pragma: no cover - Windows without symlink rights
            pytest.skip(f"symlinks unavailable: {exc}")

    results = install_driver.rollback_install(
        record, harness_name="claude_code", harness_root=home / ".claude"
    )

    assert not list(elsewhere.iterdir())
    [row] = [r for r in results if r.operation == "restore_backup"]
    assert row.outcome == "skipped"
    assert row.backup_path is not None
    assert "is now a link" in row.message


def test_rollback_fails_and_lists_a_file_it_cannot_write(
    home: Path, backups: Path
) -> None:
    # A file stands where the backup has a folder: that file cannot be written,
    # the rest is still restored, and the rollback reports a failure.
    record = _old_sweep_record(home, backups, "20261001T000000Z")
    nested = Path(str(record.targets[0].backup_ref)) / "sub" / "deep.md"
    nested.parent.mkdir()
    nested.write_text("nested\n", "utf-8")
    commands = home / ".claude" / "commands"
    commands.mkdir(parents=True)
    (commands / "sub").write_text("a file now\n", "utf-8")

    results = install_driver.rollback_install(
        record, harness_name="claude_code", harness_root=home / ".claude"
    )

    rows = [r for r in results if r.operation == "restore_backup"]
    [row] = [r for r in rows if r.outcome == "error"]
    assert str(commands / "sub" / "deep.md") in row.message
    assert row.backup_path is not None
    assert {Path(r.path).name for r in rows if r.outcome == "created"} == {
        "deploy.md",
        "review.md",
    }
    assert (commands / "deploy.md").read_text("utf-8") == "my deploy command\n"
    assert (commands / "sub").read_text("utf-8") == "a file now\n"


def test_a_partly_failed_restore_is_a_partial_rollback(
    home: Path, backups: Path
) -> None:
    # Exit 2 (partial), not 1 ("nothing was rolled back"), naming what it wrote.
    record = _old_sweep_record(home, backups, "20261001T000000Z")
    nested = Path(str(record.targets[0].backup_ref)) / "sub" / "deep.md"
    nested.parent.mkdir()
    nested.write_text("nested\n", "utf-8")
    commands = home / ".claude" / "commands"
    commands.mkdir(parents=True)
    (commands / "sub").write_text("a file now\n", "utf-8")

    outcome = CliRunner().invoke(
        main, ["rollback", "--harness", "claude-code", "--yes", "--json"]
    )

    assert outcome.exit_code == 2, outcome.output
    payload = json.loads(outcome.output)
    written = {Path(path).name for path in payload["files_written"]}
    assert {"deploy.md", "review.md"} <= written
    assert "deep.md" not in written


def test_a_file_that_cannot_be_read_is_listed(
    home: Path, backups: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    record = _old_sweep_record(home, backups, "20261001T000000Z")
    unreadable = Path(str(record.targets[0].backup_ref)) / "review.md"
    real_read = Path.read_bytes

    def read_bytes(self: Path) -> bytes:
        if self == unreadable:
            raise PermissionError(13, "denied", str(self))
        return real_read(self)

    monkeypatch.setattr(Path, "read_bytes", read_bytes)

    results = install_driver.rollback_install(
        record, harness_name="claude_code", harness_root=home / ".claude"
    )

    commands = home / ".claude" / "commands"
    [row] = [r for r in results if r.outcome == "error"]
    assert str(commands / "review.md") in row.message
    assert (commands / "deploy.md").read_text("utf-8") == "my deploy command\n"
    assert not (commands / "review.md").exists()


def test_a_file_backup_never_lands_on_a_folder(home: Path, backups: Path) -> None:
    copy = backups / "20261001T000000Z" / "hermes" / ".hermes" / "profile.yaml"
    copy.parent.mkdir(parents=True)
    copy.write_text("my profile\n", "utf-8")
    target = home / ".hermes" / "profile.yaml"
    target.mkdir(parents=True)
    record = LedgerRecord.create(
        harness="hermes",
        root=home / ".hermes",
        kind="install",
        targets=(
            LedgerTarget(
                str(target),
                "sweep_stale",
                "operator-owned",
                backup_ref=str(copy),
                outcome="updated",
            ),
        ),
    )
    install_ledger.append_record(record)

    results = install_driver.rollback_install(
        record, harness_name="hermes", harness_root=home / ".hermes"
    )

    [row] = [r for r in results if r.operation == "restore_backup"]
    assert row.outcome == "skipped"
    assert "is now a folder" in row.message
    assert target.is_dir()


@pytest.mark.parametrize("folder", ["rules", "commands"])
def test_retention_keeps_a_custom_codex_home_set(
    home: Path, backups: Path, folder: str
) -> None:
    # Releases 1.0.1 to 1.5.0 keyed Codex backups relative to CODEX_HOME's
    # parent, so CODEX_HOME=~/work/codex-home put them under codex-home/.
    kept = backups / "20261001T000000Z" / "codex" / "codex-home" / folder
    kept.mkdir(parents=True)
    (kept / "mine.rules").write_text("mine\n", "utf-8")
    # Codex's own ~/.config/apothem/<folder>, three folders deep, is no match.
    other = backups / "20261002T000000Z" / "codex" / ".config" / "apothem" / folder
    other.mkdir(parents=True)
    (other / "f").write_text("x", "utf-8")

    assert _holds_retired_sweep("20261001T000000Z", "codex")
    assert not _holds_retired_sweep("20261002T000000Z", "codex")


def test_a_custom_codex_home_install_never_backs_up_a_retired_path(
    home: Path, backups: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    codex_home = home / "work" / "codex-home"
    codex_home.mkdir(parents=True)
    monkeypatch.setenv("CODEX_HOME", str(codex_home))
    _plant(codex_home, _FORMER["codex"][1])
    (codex_home / "AGENTS.md").write_text("my own instructions\n", "utf-8")
    run, _scoped = _runner("codex", tmp_path)
    for action in ("install", "update", "update", "uninstall"):
        run(action)
    stamps = [p.name for p in backups.iterdir()] if backups.exists() else []
    assert stamps
    assert not [s for s in stamps if _holds_retired_sweep(s, "codex")]


def _retired_and_newer(home: Path, backups: Path) -> None:
    _old_sweep_record(home, backups, "20261001T000000Z")
    for day in range(2, 2 + BACKUP_KEEP + 1):
        newer = backups / f"202610{day:02d}T000000Z" / "claude_code" / ".claude" / "x"
        newer.mkdir(parents=True)
        (newer / "f").write_text("x", "utf-8")


def test_prune_names_why_it_keeps_a_set_holding_a_swept_path(
    home: Path, backups: Path
) -> None:
    _retired_and_newer(home, backups)
    runner = CliRunner()

    payload = json.loads(
        runner.invoke(
            main, ["backups", "prune", "--harness", "claude-code", "--json"]
        ).output
    )
    verbose = runner.invoke(
        main, ["backups", "prune", "--harness", "claude-code", "--verbose"]
    ).output

    [kept] = [r for r in payload["results"] if "20261001T000000Z" in r["path"]]
    assert kept["outcome"] == "skipped"
    assert kept["message"].endswith(
        "it holds a path an earlier release removed, which may be your only copy"
    )
    assert "kept (holds a path an earlier release removed) 20261001T000000Z" in verbose
