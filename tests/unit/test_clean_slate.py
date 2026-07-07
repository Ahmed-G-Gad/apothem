# SPDX-License-Identifier: MIT

"""Unit tests for the opt-in clean-slate installer routine.

Every test runs against a sandbox home directory built under ``tmp_path`` and
never touches a real home directory. The cases cover the full safety contract:
the closed removal target set, the dry-run preview, the backup-before-removal
ordering, per-target confirmation, the non-interactive override, the
unsafe-root guard, and the ``~/.config`` preservation boundary.
"""

from __future__ import annotations

import os
import stat
from datetime import datetime, timezone
from pathlib import Path

import pytest

from apothem.lib import clean_slate as _cs
from apothem.lib.clean_slate import (
    BackupError,
    CleanSlateError,
    UnsafeRootError,
    bounded_targets,
    run_clean_slate,
)


def _FIXED_CLOCK() -> datetime:
    return datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)


def _populate(home: Path) -> dict[str, Path]:
    """Create the four bounded targets plus an unrelated ~/.config sibling."""
    claude = home / ".claude"
    codex = home / ".codex"
    agents = home / ".agents"
    profile = home / ".config" / "apothem"
    other = home / ".config" / "other-app"
    for directory in (claude, codex, agents, profile, other):
        directory.mkdir(parents=True)
    (claude / "settings.json").write_text("{}", encoding="utf-8")
    (codex / "config.toml").write_text("x = 1", encoding="utf-8")
    (agents / "agent.md").write_text("# agent", encoding="utf-8")
    (profile / "profile.yaml").write_text("identity: me", encoding="utf-8")
    (other / "keep.conf").write_text("preserve me", encoding="utf-8")
    return {
        "claude": claude,
        "codex": codex,
        "agents": agents,
        "profile": profile,
        "other": other,
    }


def _backups(home: Path) -> Path:
    return home / "backups"


# --- closed target set ------------------------------------------------


def test_bounded_targets_is_the_closed_set_in_order(tmp_path: Path) -> None:
    home = tmp_path / "home"
    targets = bounded_targets(home)
    assert targets == [
        home / ".claude",
        home / ".codex",
        home / ".agents",
        home / ".config" / "apothem",
    ]


# --- dry-run preview --------------------------------------------------


def test_dry_run_previews_targets_and_removes_nothing(tmp_path: Path) -> None:
    home = tmp_path / "home"
    paths = _populate(home)
    lines: list[str] = []

    result = run_clean_slate(home, dry_run=True, echo=lines.append)

    assert result.dry_run is True
    assert result.backup_dir is None
    assert {d.path for d in result.dispositions} == {
        home / ".claude",
        home / ".codex",
        home / ".agents",
        home / ".config" / "apothem",
    }
    assert all(d.present for d in result.dispositions)
    assert not result.removed
    # Nothing on disk changed.
    for path in paths.values():
        assert path.exists()
    assert not _backups(home).exists()
    assert any("dry-run" in line.lower() for line in lines)


def test_dry_run_marks_absent_targets(tmp_path: Path) -> None:
    home = tmp_path / "home"
    (home / ".claude").mkdir(parents=True)  # only one of four present

    result = run_clean_slate(home, dry_run=True)

    by_name = {d.path.name: d.present for d in result.dispositions}
    assert by_name[".claude"] is True
    assert by_name[".codex"] is False
    assert by_name[".agents"] is False
    assert by_name["apothem"] is False


# --- backup before removal -------------------------------------------


def test_backup_precedes_removal_and_captures_each_target(tmp_path: Path) -> None:
    home = tmp_path / "home"
    _populate(home)

    result = run_clean_slate(
        home,
        assume_yes=True,
        backup_root=_backups(home),
        clock=_FIXED_CLOCK,
    )

    backup_dir = result.backup_dir
    assert backup_dir is not None
    assert backup_dir.name == "clean-slate-20260102T030405Z"
    # Every removed target's content is recoverable from the backup.
    assert (backup_dir / ".claude" / "settings.json").read_text() == "{}"
    assert (backup_dir / ".codex" / "config.toml").read_text() == "x = 1"
    assert (backup_dir / ".agents" / "agent.md").read_text() == "# agent"
    assert (
        backup_dir / ".config" / "apothem" / "profile.yaml"
    ).read_text() == "identity: me"
    # The originals are gone.
    assert not (home / ".claude").exists()
    assert not (home / ".config" / "apothem").exists()


def test_backup_failure_aborts_before_any_removal(tmp_path: Path) -> None:
    home = tmp_path / "home"
    paths = _populate(home)
    # A *file* where the backup root directory is expected makes the backup
    # directory creation fail, which must abort the run before any removal.
    bad_backup_root = home / "backups-is-a-file"
    bad_backup_root.write_text("not a directory", encoding="utf-8")

    with pytest.raises(BackupError):
        run_clean_slate(
            home,
            assume_yes=True,
            backup_root=bad_backup_root,
            clock=_FIXED_CLOCK,
        )

    # Backup-before-removal ordering: every target survives the aborted run.
    for path in paths.values():
        assert path.exists()


# --- per-target confirmation -----------------------------------------


def test_per_target_confirmation_skips_only_declined_targets(tmp_path: Path) -> None:
    home = tmp_path / "home"
    _populate(home)

    # Decline only ~/.codex; every other target is confirmed.
    result = run_clean_slate(
        home,
        confirm=lambda target: target.name != ".codex",
        backup_root=_backups(home),
        clock=_FIXED_CLOCK,
    )

    removed_names = {p.name for p in result.removed}
    assert removed_names == {".claude", ".agents", "apothem"}
    assert (home / ".codex").exists()  # declined → preserved
    assert not (home / ".claude").exists()
    codex_disposition = next(d for d in result.dispositions if d.path.name == ".codex")
    assert codex_disposition.present is True
    assert codex_disposition.removed is False
    assert codex_disposition.skipped_reason == "declined"


def test_assume_yes_bypasses_confirmation(tmp_path: Path) -> None:
    home = tmp_path / "home"
    _populate(home)

    def _explode(_target: Path) -> bool:  # must never be called under --yes
        raise AssertionError("confirmation prompt invoked despite assume_yes")

    result = run_clean_slate(
        home,
        assume_yes=True,
        confirm=_explode,
        backup_root=_backups(home),
        clock=_FIXED_CLOCK,
    )

    assert len(result.removed) == 4


# --- non-interactive override ----------------------------------------


def test_non_interactive_without_yes_refuses(tmp_path: Path) -> None:
    home = tmp_path / "home"
    paths = _populate(home)

    with pytest.raises(CleanSlateError):
        run_clean_slate(home, interactive=False, assume_yes=False)

    # Refusal leaves every target intact.
    for path in paths.values():
        assert path.exists()


def test_non_interactive_with_yes_proceeds(tmp_path: Path) -> None:
    home = tmp_path / "home"
    _populate(home)

    result = run_clean_slate(
        home,
        interactive=False,
        assume_yes=True,
        backup_root=_backups(home),
        clock=_FIXED_CLOCK,
    )

    assert len(result.removed) == 4


# --- unsafe-root guard -----------------------------------------------


def test_guard_refuses_empty_home() -> None:
    with pytest.raises(UnsafeRootError):
        run_clean_slate(Path(), assume_yes=True)


def test_guard_refuses_filesystem_root_as_home() -> None:
    with pytest.raises(UnsafeRootError):
        run_clean_slate(Path(Path.cwd().anchor), assume_yes=True)


def test_guard_refuses_home_itself_as_target(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    with pytest.raises(UnsafeRootError):
        run_clean_slate(home, targets=[home], assume_yes=True)


def test_guard_refuses_parent_directory_traversal(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    # A ".."-bearing target climbs back up to the home directory; it must be
    # refused, not resolved-and-removed (the equality checks compare the
    # unresolved path, so the traversal guard catches it first).
    with pytest.raises(UnsafeRootError):
        run_clean_slate(home, targets=[home / "x" / ".."], assume_yes=True)


def test_guard_refuses_filesystem_root_as_target(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    with pytest.raises(UnsafeRootError):
        run_clean_slate(home, targets=[Path(Path.cwd().anchor)], assume_yes=True)


# --- ~/.config preservation boundary ---------------------------------


def test_guard_refuses_entire_config_directory(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    with pytest.raises(UnsafeRootError):
        run_clean_slate(home, targets=[home / ".config"], assume_yes=True)


def test_guard_refuses_non_apothem_config_child(tmp_path: Path) -> None:
    home = tmp_path / "home"
    (home / ".config" / "other-app").mkdir(parents=True)
    with pytest.raises(UnsafeRootError):
        run_clean_slate(
            home,
            targets=[home / ".config" / "other-app"],
            assume_yes=True,
        )


def test_unrelated_config_apps_are_untouched(tmp_path: Path) -> None:
    home = tmp_path / "home"
    paths = _populate(home)

    run_clean_slate(
        home,
        assume_yes=True,
        backup_root=_backups(home),
        clock=_FIXED_CLOCK,
    )

    # Only ~/.config/apothem is removed; the sibling app is byte-for-byte intact.
    assert not paths["profile"].exists()
    assert paths["other"].exists()
    assert (paths["other"] / "keep.conf").read_text() == "preserve me"
    assert (home / ".config").exists()


# --- absent targets and symlinks ----------------------------------------------


def test_absent_targets_are_skipped_cleanly(tmp_path: Path) -> None:
    home = tmp_path / "home"
    (home / ".claude").mkdir(parents=True)  # only one present

    result = run_clean_slate(
        home,
        assume_yes=True,
        backup_root=_backups(home),
        clock=_FIXED_CLOCK,
    )

    assert {p.name for p in result.removed} == {".claude"}
    assert all(not d.removed for d in result.dispositions if not d.present)


def test_symlink_target_is_removed_without_following(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "precious.txt").write_text("do not delete", encoding="utf-8")
    link = home / ".claude"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError as exc:  # pragma: no cover - platform dependent
        pytest.skip(f"symlinks unavailable on this platform: {exc}")

    run_clean_slate(
        home,
        assume_yes=True,
        backup_root=_backups(home),
        clock=_FIXED_CLOCK,
    )

    # The symlink is gone but its target (outside the home) is untouched.
    assert not link.exists()
    assert (outside / "precious.txt").read_text() == "do not delete"


# --- private helpers + edge branches ----------------------------------


def test_utcnow_returns_aware_utc_datetime() -> None:
    now = _cs._utcnow()
    assert now.tzinfo is timezone.utc


def test_default_confirm_accepts_yes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("builtins.input", lambda _prompt: " Yes ")
    assert _cs._default_confirm(Path("x")) is True


def test_default_confirm_rejects_other(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("builtins.input", lambda _prompt: "no")
    assert _cs._default_confirm(Path("x")) is False


def test_default_confirm_treats_eof_as_no(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise_eof(_prompt: str) -> str:
        raise EOFError

    monkeypatch.setattr("builtins.input", _raise_eof)
    assert _cs._default_confirm(Path("x")) is False


def test_file_target_is_backed_up_and_removed(tmp_path: Path) -> None:
    # A non-directory target exercises the copy2 backup branch and the file
    # unlink removal branch (distinct from the directory copytree / rmtree paths).
    home = tmp_path / "home"
    home.mkdir()
    file_target = home / ".claude"  # a file sitting at a bounded-target path
    file_target.write_text("just a file", encoding="utf-8")

    result = run_clean_slate(
        home,
        assume_yes=True,
        targets=[file_target],
        backup_root=_backups(home),
        clock=_FIXED_CLOCK,
    )

    assert not file_target.exists()
    assert result.backup_dir is not None
    assert any(result.backup_dir.rglob("*"))  # the file landed in the backup


def test_target_outside_home_backs_up_under_its_basename(tmp_path: Path) -> None:
    # A present target not relative to home falls back to Path(src.name) for its
    # backup layout (the relative_to ValueError branch), then is removed.
    home = tmp_path / "home"
    home.mkdir()
    outside = tmp_path / "elsewhere" / "stray"
    outside.parent.mkdir(parents=True)
    outside.write_text("stray", encoding="utf-8")

    result = run_clean_slate(
        home,
        assume_yes=True,
        targets=[outside],
        backup_root=_backups(home),
        clock=_FIXED_CLOCK,
    )

    assert not outside.exists()
    assert result.backup_dir is not None
    assert (result.backup_dir / "stray").exists()


@pytest.mark.skipif(
    os.name != "nt", reason="the read-only-bit retry path is Windows-specific"
)
def test_remove_tree_retries_after_clearing_readonly(tmp_path: Path) -> None:
    # On Windows a read-only file blocks the first shutil.rmtree; the routine
    # clears the read-only attribute and retries.
    home = tmp_path / "home"
    target = home / ".claude"
    target.mkdir(parents=True)
    locked = target / "locked.txt"
    locked.write_text("x", encoding="utf-8")
    locked.chmod(stat.S_IREAD)

    run_clean_slate(
        home,
        assume_yes=True,
        targets=[target],
        backup_root=_backups(home),
        clock=_FIXED_CLOCK,
    )

    assert not target.exists()
