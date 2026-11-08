# SPDX-License-Identifier: MIT

"""The stale sweep, its preview, backups and rollback never act through a link.

A symbolic link or a Windows junction at or below a stale path is the
operator's. Each test runs with a symbolic link (POSIX, or Windows with
symlink rights) and, on Windows, with a junction, which ``is_symlink()`` does
not see.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from apothem.harnesses._shared import install_driver
from apothem.harnesses._shared.install_driver_pathsafety import (
    _is_link,
    _stale_path_proves_install,
    _unsafe_symlink,
)
from apothem.harnesses._shared.install_driver_reversal import _restore_directory
from apothem.harnesses._shared.install_driver_sweep import (
    preview_stale_sweep,
    stale_needs_sweep,
    sweep_stale,
)

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
    mine.mkdir()
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


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX symlink run")
def test_the_symlink_tests_run_on_posix() -> None:
    assert KINDS == ["symlink"]
    assert os.name == "posix"
