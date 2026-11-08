# SPDX-License-Identifier: MIT

"""Install, update and uninstall leave a user's files in the paths 1.5.0 swept.

Releases 1.0.1 to 1.5.0 removed each path below whole on every install and
update, whatever it held, though no release ever installed a file there
(``~/.claude/commands``, ``~/.codex/rules`` and others). Each test places a
user's file at every such path, runs the adapter's install, update and
uninstall, and checks every file is still there, byte for byte.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from apothem.harnesses._shared import install_driver
from apothem.harnesses._shared.install_driver_retention import (
    BACKUP_KEEP,
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

#: Paths in a folder Apothem owns whose name its source tree also carries:
#: uninstall removes such a name from ~/.claude/statuslines/, as it removes
#: render.py there. It is not the sweep, and install and update keep the file.
_UNINSTALL_OWNS = frozenset({Path("statuslines/__init__.py")})


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
            if action == "uninstall" and path.relative_to(root) in _UNINSTALL_OWNS:
                continue
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


@pytest.mark.parametrize("public_id", ["claude-code", "codex"])
def test_current_installs_never_back_up_a_retired_sweep_path(
    public_id: str, home: Path, backups: Path, tmp_path: Path
) -> None:
    # Otherwise RETIRED_SWEEPS would keep every set, and retention would stop.
    project = tmp_path / "project"
    project.mkdir()
    root = home / _FORMER[public_id][0].removeprefix("~/")
    _plant(root, _FORMER[public_id][1])
    # A user's own instruction file makes every pass take a backup set.
    anchor = root / ("CLAUDE.md" if public_id == "claude-code" else "AGENTS.md")
    anchor.write_text("my own instructions\n", "utf-8")
    run, _scoped = _runner(public_id, project)
    for action in ("install", "update", "update"):
        run(action)
    package = public_id.replace("-", "_")
    stamps = [p.name for p in backups.iterdir()] if backups.exists() else []
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


def test_retention_prunes_an_uninstall_set_of_the_statusline_init(
    home: Path, backups: Path
) -> None:
    # Uninstall backs up ~/.claude/statuslines/__init__.py on every run, so it
    # must not count as a swept folder, or no uninstall set would ever go.
    old = backups / "20261001T000000Z" / "claude_code" / ".claude" / "statuslines"
    old.mkdir(parents=True)
    (old / "__init__.py").write_text("", "utf-8")
    for day in range(2, 2 + BACKUP_KEEP + 1):
        newer = backups / f"202610{day:02d}T000000Z" / "claude_code" / ".claude" / "x"
        newer.mkdir(parents=True)
        (newer / "f").write_text("x", "utf-8")

    report = prune_history("claude_code")

    assert "20261001T000000Z" in report.pruned
    assert not report.retired
