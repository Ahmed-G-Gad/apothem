# SPDX-License-Identifier: MIT

"""The stale sweep, its preview, backups and rollback never act through a link.

A symbolic link or a Windows junction at or below a stale path is the
operator's. Each test runs with a symbolic link (POSIX, or Windows with
symlink rights) and, on Windows, with a junction, which ``is_symlink()`` does
not see.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

import pytest

from apothem.harnesses._shared import install_driver, install_driver_pathsafety
from apothem.harnesses._shared.install_driver_backup import (
    _compensating_rollback,
    _replace_path,
)
from apothem.harnesses._shared.install_driver_pathsafety import (
    _holds_content,
    _is_link,
    _remove_tree_keeping_links,
    _stale_path_proves_install,
    _unsafe_symlink,
    _validate_target_path,
    _walk_without_links,
)
from apothem.harnesses._shared.install_driver_reversal import (
    _remove_created,
    _restore_directory,
)
from apothem.harnesses._shared.install_driver_sweep import (
    preview_stale_sweep,
    stale_needs_sweep,
    sweep_stale,
)
from apothem.harnesses._shared.install_driver_treeops import replace_tree
from apothem.harnesses._shared.install_driver_types import _result

KINDS = ["symlink", *(["junction"] if sys.platform == "win32" else [])]


def _link(kind: str, target: Path, link: Path) -> None:
    link.parent.mkdir(parents=True, exist_ok=True)
    if kind == "junction":
        import _winapi

        _winapi.CreateJunction(str(target), str(link))
        return
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError as exc:  # pragma: no cover - Windows without symlink rights
        pytest.skip(f"symlinks unavailable: {exc}")


@pytest.fixture
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(install_driver, "BACKUP_ROOT", tmp_path / "backups")
    home = tmp_path / "home"
    home.mkdir()
    return home


def _mine(home: Path) -> Path:
    mine = home / "my-rules"
    mine.mkdir(parents=True)
    (mine / "precious.md").write_text("mine\n", encoding="utf-8")
    return mine


def _warnings(results: list) -> list[str]:  # type: ignore[type-arg]
    return [r.path for r in results if r.outcome == "warning"]


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("keeps_a_file", [True, False])
def test_a_link_inside_a_stale_folder_is_kept_and_nothing_behind_it_changes(
    home: Path, kind: str, keeps_a_file: bool
) -> None:
    root = home / ".config" / "opencode"
    stale = root / "apothem" / "rules"
    stale.mkdir(parents=True)
    (stale / "old-rule.md").write_text("old\n", encoding="utf-8")
    kept = stale / "00-apothem-profile.md"
    kept.write_text("profile\n", encoding="utf-8")
    mine = _mine(home)
    link = stale / "linked"
    _link(kind, mine, link)
    preserve = frozenset({kept.resolve()}) if keeps_a_file else frozenset()

    preview = preview_stale_sweep(
        stale, preserve=preserve, protect=frozenset(), allowed_root=home, message="dry"
    )
    results = sweep_stale(["apothem/rules"], root, allowed_root=home, preserve=preserve)

    assert (mine / "precious.md").read_text(encoding="utf-8") == "mine\n"
    assert _is_link(link)
    assert not (stale / "old-rule.md").exists()
    assert kept.exists() is keeps_a_file
    assert _warnings(results) == _warnings(preview) == [str(link)]
    sweep = next(r for r in results if r.path == str(stale))
    assert sweep.outcome == "updated"
    assert not (Path(str(sweep.backup_path)) / "linked").exists()


@pytest.mark.parametrize("kind", KINDS)
def test_a_link_at_the_stale_path_is_kept_the_same_way_in_a_dry_run(
    home: Path, tmp_path: Path, kind: str
) -> None:
    root = home / ".config" / "opencode"
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "keep.md").write_text("mine\n", encoding="utf-8")
    stale = root / "apothem" / "rules"
    _link(kind, outside, stale)

    preview = preview_stale_sweep(
        stale,
        preserve=frozenset(),
        protect=frozenset(),
        allowed_root=home,
        message="dry",
    )
    results = sweep_stale(["apothem/rules"], root, allowed_root=home)

    assert [r.outcome for r in preview] == [r.outcome for r in results] == ["warning"]
    assert str(stale) in results[0].message
    assert not stale_needs_sweep(stale)
    assert (outside / "keep.md").exists()
    assert _is_link(stale)


@pytest.mark.parametrize("kind", KINDS)
def test_a_link_above_a_write_path_is_refused(home: Path, kind: str) -> None:
    real = home / "dotfiles" / "tool"
    real.mkdir(parents=True)
    _link(kind, real, home / ".tool")

    assert _unsafe_symlink(home / ".tool" / "rules" / "a.md", home) == home / ".tool"


@pytest.mark.parametrize("kind", KINDS)
def test_a_stale_link_is_not_evidence_of_an_install(home: Path, kind: str) -> None:
    elsewhere = home / "elsewhere"
    (elsewhere / ".apothem" / "support").mkdir(parents=True)
    (elsewhere / ".apothem" / "support" / "a.md").write_text("x", encoding="utf-8")
    stale = home / ".tool" / "plugins" / "apothem"
    _link(kind, elsewhere, stale)

    assert not _stale_path_proves_install(stale)


@pytest.mark.parametrize("kind", KINDS)
def test_rollback_leaves_a_link_at_the_restored_folder_in_place(
    home: Path, tmp_path: Path, kind: str
) -> None:
    # A record written before links were kept: its backup holds a copy taken
    # through the link, and the link now stands at the target.
    backup = tmp_path / "old-backup"
    backup.mkdir()
    (backup / "notes.md").write_text("copy\n", encoding="utf-8")
    elsewhere = home / "my-plugins"
    elsewhere.mkdir()
    (elsewhere / "notes.md").write_text("mine\n", encoding="utf-8")
    target = home / ".tool" / "plugins" / "apothem"
    _link(kind, elsewhere, target)

    result = _restore_directory(
        target, backup, root=home / ".tool", harness_name="t", allowed_root=home
    )

    assert result.outcome == "unchanged"
    assert "link" in result.message
    assert _is_link(target)
    assert (elsewhere / "notes.md").read_text(encoding="utf-8") == "mine\n"


@pytest.mark.parametrize("kind", KINDS)
def test_rollback_restores_a_folder_around_a_link_inside_it(
    home: Path, tmp_path: Path, kind: str
) -> None:
    backup = tmp_path / "old-backup"
    (backup / "linked").mkdir(parents=True)
    (backup / "old-rule.md").write_text("old\n", encoding="utf-8")
    (backup / "linked" / "precious.md").write_text("copy\n", encoding="utf-8")
    target = home / ".config" / "opencode" / "apothem" / "rules"
    target.mkdir(parents=True)
    mine = _mine(home)
    _link(kind, mine, target / "linked")

    result = _restore_directory(
        target, backup, root=home / ".config", harness_name="t", allowed_root=home
    )

    assert result.outcome == "updated"
    assert (target / "old-rule.md").read_text(encoding="utf-8") == "old\n"
    assert _is_link(target / "linked")
    assert (mine / "precious.md").read_text(encoding="utf-8") == "mine\n"


@pytest.mark.parametrize("kind", KINDS)
def test_the_refusal_names_the_link_and_how_to_fix_it(home: Path, kind: str) -> None:
    real = home / "dotfiles" / "tool"
    real.mkdir(parents=True)
    _link(kind, real, home / ".tool")

    result = _validate_target_path(
        home / ".tool" / "rules" / "a.md", allowed_root=home, operation="write"
    )

    assert result is not None
    assert result.outcome == "error"
    assert str(home / ".tool") in result.message
    assert "replace the link with a real folder" in result.message


@pytest.mark.parametrize("kind", KINDS)
def test_a_link_whose_folder_is_gone_is_still_refused(home: Path, kind: str) -> None:
    gone = home / "gone"
    gone.mkdir()
    _link(kind, gone, home / ".tool")
    gone.rmdir()

    assert _unsafe_symlink(home / ".tool" / "rules" / "a.md", home) == home / ".tool"


def _tree_with_a_link(home: Path, kind: str, tree: Path) -> tuple[Path, Path]:
    (tree / "sub").mkdir(parents=True)
    (tree / "sub" / "old.md").write_text("old\n", encoding="utf-8")
    mine = _mine(home)
    link = tree / "sub" / "linked"
    _link(kind, mine, link)
    return mine, link


def _untouched(mine: Path, link: Path) -> None:
    assert _is_link(link)
    assert (mine / "precious.md").read_text(encoding="utf-8") == "mine\n"


@pytest.mark.parametrize("kind", KINDS)
def test_removing_a_tree_keeps_each_link_in_it(home: Path, kind: str) -> None:
    tree = home / "tree"
    mine, link = _tree_with_a_link(home, kind, tree)

    assert _remove_tree_keeping_links(tree) == [link]

    _untouched(mine, link)
    assert not (tree / "sub" / "old.md").exists()


@pytest.mark.parametrize("kind", KINDS)
def test_replacing_a_tree_keeps_a_link_in_it(
    home: Path, tmp_path: Path, kind: str
) -> None:
    src = tmp_path / "src"
    (src / "sub" / "linked").mkdir(parents=True)
    (src / "sub" / "linked" / "new.md").write_text("new\n", encoding="utf-8")
    (src / "sub" / "new.md").write_text("new\n", encoding="utf-8")
    dst = home / "tree"
    mine, link = _tree_with_a_link(home, kind, dst)

    result = replace_tree(src, dst, None, install_root=home, allowed_root=home)  # type: ignore[arg-type]

    assert result.outcome == "updated"
    assert "did not copy over them" in result.message
    _untouched(mine, link)
    assert not (mine / "new.md").exists()
    assert (dst / "sub" / "new.md").is_file()
    assert not (dst / "sub" / "old.md").exists()


@pytest.mark.parametrize("kind", KINDS)
def test_undoing_a_failed_install_keeps_a_link_in_what_it_removes(
    home: Path, tmp_path: Path, kind: str
) -> None:
    created = home / "created"
    mine, link = _tree_with_a_link(home, kind, created)
    backup = tmp_path / "copy"
    (backup / "sub").mkdir(parents=True)
    (backup / "sub" / "before.md").write_text("before\n", encoding="utf-8")
    restored = home / "restored"
    mine_too, link_too = _tree_with_a_link(home / "b", kind, restored)

    _compensating_rollback(
        [
            _result("created", "replace_tree", created, "made"),
            _result("updated", "replace_tree", restored, "x", backup_path=backup),
        ],
        allowed_root=home,
    )

    _untouched(mine, link)
    _untouched(mine_too, link_too)
    assert (restored / "sub" / "before.md").is_file()
    assert not (restored / "sub" / "old.md").exists()


@pytest.mark.parametrize("kind", KINDS)
def test_removing_what_an_install_created_keeps_a_link_in_it(
    home: Path, kind: str
) -> None:
    created = home / ".tool" / "skills"
    mine, link = _tree_with_a_link(home, kind, created)

    result = _remove_created(
        created, root=home / ".tool", harness_name="t", allowed_root=home
    )

    assert result is not None
    assert result.outcome == "updated"
    _untouched(mine, link)


def test_a_folder_the_walk_cannot_read_is_reported(
    home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    stale = home / ".config" / "opencode" / "apothem" / "rules"
    locked = stale / "locked"
    locked.mkdir(parents=True)
    (locked / "x.md").write_text("x\n", encoding="utf-8")
    (stale / "old.md").write_text("old\n", encoding="utf-8")
    real_scandir = os.scandir

    def scandir(path: object) -> object:
        if Path(str(path)) == locked:
            raise PermissionError("denied")
        return real_scandir(path)  # type: ignore[call-overload]

    monkeypatch.setattr(install_driver_pathsafety.os, "scandir", scandir)

    assert _walk_without_links(stale).unreadable == [locked]
    preview = preview_stale_sweep(
        stale,
        preserve=frozenset(),
        protect=frozenset(),
        allowed_root=home,
        message="dry",
    )
    assert [r.path for r in _warn(preview)] == [str(locked)]
    assert "could not read" in _warn(preview)[0].message


def _warn(results: list) -> list:  # type: ignore[type-arg]
    return [r for r in results if r.outcome == "warning"]


@pytest.mark.parametrize("kind", KINDS)
def test_a_leftover_path_behind_a_link_is_kept_with_a_warning(
    home: Path, tmp_path: Path, kind: str
) -> None:
    dotfiles = tmp_path / "dotfiles"
    (dotfiles / "apothem").mkdir(parents=True)
    (dotfiles / "apothem" / "keep.md").write_text("mine\n", encoding="utf-8")
    root = home / ".tool"
    _link(kind, dotfiles, root / "plugins")

    preview = preview_stale_sweep(
        root / "plugins" / "apothem",
        preserve=frozenset(),
        protect=frozenset(),
        allowed_root=home,
        message="dry",
    )
    results = sweep_stale(["plugins/apothem"], root, allowed_root=home)

    assert [r.outcome for r in preview] == [r.outcome for r in results] == ["warning"]
    assert str(root / "plugins") in results[0].message
    assert (dotfiles / "apothem" / "keep.md").exists()


@pytest.mark.parametrize("kind", KINDS)
def test_an_uninstall_leaves_a_target_behind_a_link_with_a_warning(
    home: Path, tmp_path: Path, kind: str
) -> None:
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (elsewhere / "hook.py").write_text("mine\n", encoding="utf-8")
    hooks = home / ".tool" / ".apothem" / "support" / "hooks"
    _link(kind, elsewhere, hooks)

    removed = _replace_path(
        hooks,
        install_root=home / ".tool",
        harness_name="t",
        allowed_root=home,
        removing=True,
    )
    written = _replace_path(
        hooks / "a.py", install_root=home / ".tool", harness_name="t", allowed_root=home
    )

    assert removed is not None
    assert removed.outcome == "warning"
    assert "does not remove anything through a link" in removed.message
    assert written is not None
    assert written.outcome == "error"
    assert (elsewhere / "hook.py").exists()


@pytest.mark.parametrize("kind", KINDS)
def test_removing_an_installed_folder_keeps_a_link_in_it(home: Path, kind: str) -> None:
    skill = home / ".tool" / "skills" / "apothem-x"
    mine, link = _tree_with_a_link(home, kind, skill)

    removed = _replace_path(
        skill,
        install_root=home / ".tool",
        harness_name="t",
        allowed_root=home,
        removing=True,
    )

    assert removed is not None
    assert removed.outcome == "updated"
    assert removed.detail["kept_links"] == str(link)
    _untouched(mine, link)


@pytest.mark.parametrize("kind", KINDS)
def test_replacing_a_tree_with_an_ignore_hook_keeps_a_link(
    home: Path, tmp_path: Path, kind: str
) -> None:
    src = tmp_path / "src"
    (src / "sub").mkdir(parents=True)
    (src / "sub" / "new.md").write_text("new\n", encoding="utf-8")
    (src / "sub" / "scratch.tmp").write_text("t\n", encoding="utf-8")
    dst = home / "tree"
    mine, link = _tree_with_a_link(home, kind, dst)

    result = replace_tree(
        src, dst, shutil.ignore_patterns("*.tmp"), install_root=home, allowed_root=home
    )

    assert result.outcome == "updated"
    _untouched(mine, link)
    assert (dst / "sub" / "new.md").is_file()
    assert not (dst / "sub" / "scratch.tmp").exists()


def _deny(monkeypatch: pytest.MonkeyPatch, locked: Path) -> None:
    real_scandir = os.scandir

    def scandir(path: object) -> object:
        if Path(str(path)) == locked:
            raise PermissionError("denied")
        return real_scandir(path)  # type: ignore[call-overload]

    monkeypatch.setattr(os, "scandir", scandir)


def test_a_real_sweep_keeps_a_folder_it_cannot_read(
    home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = home / ".config" / "opencode"
    stale = root / "apothem" / "rules"
    locked = stale / "locked"
    locked.mkdir(parents=True)
    (locked / "x.md").write_text("x\n", encoding="utf-8")
    (stale / "old.md").write_text("old\n", encoding="utf-8")
    _deny(monkeypatch, locked)

    results = sweep_stale(["apothem/rules"], root, allowed_root=home)

    assert not (stale / "old.md").exists()
    assert (locked / "x.md").exists()
    assert [r.path for r in _warn(results)] == [str(locked)]
    assert results[0].outcome == "updated"


def test_a_folder_that_cannot_be_read_counts_as_content(
    home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    locked = home / "tree" / "locked"
    locked.mkdir(parents=True)
    _deny(monkeypatch, locked)

    assert _holds_content(home / "tree")


@pytest.mark.parametrize("kind", KINDS)
def test_a_file_that_cannot_be_removed_is_reported(
    home: Path, kind: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    tree = home / "tree"
    mine, link = _tree_with_a_link(home, kind, tree)
    stuck = tree / "sub" / "old.md"
    real_unlink = Path.unlink

    def unlink(self: Path, missing_ok: bool = False) -> None:
        if self == stuck:
            raise PermissionError("in use")
        real_unlink(self, missing_ok=missing_ok)

    monkeypatch.setattr(Path, "unlink", unlink)

    kept = _remove_tree_keeping_links(tree)

    assert kept == [link, stuck]
    _untouched(mine, link)


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX symlink run")
def test_the_symlink_tests_run_on_posix() -> None:
    assert KINDS == ["symlink"]
    assert os.name == "posix"
