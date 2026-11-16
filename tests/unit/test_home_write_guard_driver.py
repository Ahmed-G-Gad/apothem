# SPDX-License-Identifier: MIT

"""The install driver and the stores stop at the real-home guard, not after it.

Each test builds what it needs in a folder under ``tmp_path`` first and only
then protects that folder as an account home with ``also_protect_home``, so the
guard sees a fake real home that already holds files. A mutation into it must
raise :class:`~apothem.lib.home_write_guard.RealHomeWriteError` (not turn into
an error or warning row) and change nothing, while a dry run, a preview and a
read-style check must still work and write nothing.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from apothem.cli import _helpers
from apothem.harnesses._shared import (
    install_driver,
    install_driver_backup,
    install_driver_lifecycle,
    install_driver_materialize,
    install_driver_retention,
    install_driver_sweep,
)
from apothem.harnesses._shared.install_driver_types import MaterializationResult
from apothem.lib import clean_slate, home_write_guard, install_ledger
from apothem.lib.data_home import resolve_shared_data_home
from apothem.lib.install_ledger import LedgerRecord

Refused = home_write_guard.RealHomeWriteError


@pytest.fixture(autouse=True)
def _forget_fake_homes() -> Iterator[None]:
    """Drop the added homes and the refusals each test logged."""
    yield
    home_write_guard.clear_extra_homes()
    home_write_guard.drain_refusals()


def _snapshot(folder: Path) -> dict[str, bytes | None]:
    """Map every path under *folder* to its bytes (``None`` for a folder)."""
    return {
        str(path): (path.read_bytes() if path.is_file() else None)
        for path in sorted(folder.rglob("*"))
    }


@pytest.fixture
def home(tmp_path: Path) -> Path:
    """Return an empty folder that a test protects once it has filled it."""
    folder = tmp_path / "account-home"
    folder.mkdir()
    return folder


def test_a_write_into_a_protected_root_raises_instead_of_an_error_row(
    home: Path,
) -> None:
    root = home / ".claude"
    root.mkdir()
    home_write_guard.also_protect_home(home)
    with pytest.raises(Refused):
        install_driver.write_bytes_safely(
            root / "CLAUDE.md", b"x", install_root=root, harness_name="claude_code"
        )
    assert _snapshot(home) == {str(root): None}


def test_an_overwrite_whose_backup_lands_in_the_home_raises_and_keeps_the_target(
    home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    install_root = tmp_path / "install-root"
    target = install_root / "file.md"
    target.parent.mkdir()
    target.write_bytes(b"before")
    monkeypatch.setattr(install_driver, "BACKUP_ROOT", home / ".apothem" / "backups")
    home_write_guard.also_protect_home(home)
    with pytest.raises(Refused):
        install_driver.write_bytes_safely(
            target, b"after", install_root=install_root, harness_name="claude_code"
        )
    assert target.read_bytes() == b"before"
    assert _snapshot(home) == {}


def _backup_sets(backups: Path, harness: str, count: int) -> None:
    for index in range(count):
        (backups / f"20260101T00000{index}Z" / harness).mkdir(parents=True)


def test_pruning_backup_sets_in_the_home_raises_and_removes_nothing(
    home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    backups = home / ".apothem" / "backups"
    _backup_sets(backups, "claude_code", 3)
    monkeypatch.setattr(install_driver, "BACKUP_ROOT", backups)
    before = _snapshot(home)
    home_write_guard.also_protect_home(home)
    report = install_driver_retention.prune_history("claude_code", keep=1, dry_run=True)
    assert len(report.pruned) == 2
    with pytest.raises(Refused):
        install_driver_retention.prune_history("claude_code", keep=1)
    assert _snapshot(home) == before


def test_a_dry_run_install_into_the_home_writes_nothing_and_a_real_one_raises() -> None:
    # The per-test home of tests/conftest.py stands in for the real one here.
    home_write_guard.also_protect_home(Path.home())
    harness_root = Path.home() / ".claude"
    before = _snapshot(Path.home())
    run = install_driver.run_install(
        "claude_code", harness_root=harness_root, dry_run=True
    )
    assert run.dry_run
    assert _snapshot(Path.home()) == before
    with pytest.raises(Refused):
        install_driver.run_install("claude_code", harness_root=harness_root)
    assert _snapshot(Path.home()) == before
    assert not install_ledger.ledger_path("claude_code").exists()


def test_the_stale_sweep_preview_works_and_the_sweep_raises(home: Path) -> None:
    stale = home / ".claude" / "old-layout"
    (stale / "rules").mkdir(parents=True)
    (stale / "rules" / "a.md").write_bytes(b"old")
    before = _snapshot(home)
    home_write_guard.also_protect_home(home)
    preview = install_driver_sweep.preview_stale_sweep(
        stale,
        preserve=frozenset(),
        protect=frozenset(),
        allowed_root=home,
        message="preview",
    )
    assert [result.outcome for result in preview] == ["skipped"]
    with pytest.raises(Refused):
        install_driver_sweep.sweep_stale(
            ["old-layout"], home / ".claude", harness_name="claude_code"
        )
    assert _snapshot(home) == before


def test_the_compensating_rollback_skips_a_refused_target(home: Path) -> None:
    written = home / ".claude" / "CLAUDE.md"
    written.parent.mkdir()
    written.write_bytes(b"written")
    home_write_guard.also_protect_home(home)
    install_driver_backup._compensating_rollback(
        [
            MaterializationResult(
                outcome="created", operation="write", path=str(written), message=""
            )
        ],
        allowed_root=home,
    )
    assert written.read_bytes() == b"written"
    assert home_write_guard.refusals() == ()


def test_creating_the_data_home_in_the_home_raises(home: Path) -> None:
    home_write_guard.also_protect_home(home)
    with pytest.raises(Refused):
        resolve_shared_data_home(base=home).ensure()
    assert _snapshot(home) == {}


def test_the_data_surfaces_raise_instead_of_a_warning_row(home: Path) -> None:
    root = home / ".claude"
    root.mkdir()
    home_write_guard.also_protect_home(home)
    with pytest.raises(Refused):
        install_driver_materialize._materialize_data_surfaces("claude_code", root)
    assert _snapshot(home) == {str(root): None}


def test_a_clean_slate_removal_in_the_home_raises(home: Path) -> None:
    target = home / ".claude"
    (target / "agents").mkdir(parents=True)
    before = _snapshot(home)
    home_write_guard.also_protect_home(home)
    with pytest.raises(Refused):
        clean_slate._remove_path(target)
    with pytest.raises(Refused):
        clean_slate._remove_path(home)
    assert _snapshot(home) == before


def test_a_profile_write_in_the_home_raises(home: Path) -> None:
    home_write_guard.also_protect_home(home)
    profile = home / ".config" / "apothem" / "profile.yaml"
    with pytest.raises(Refused):
        _helpers._write_profile_text_safely(
            profile, "schema_version: 1\n", operation="profile_write"
        )
    assert _snapshot(home) == {}


def test_a_status_check_that_would_close_an_uninstall_is_refused_quietly(
    home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(install_ledger, "STATE_ROOT", home / ".apothem" / "state")
    root = tmp_path / "claude-root"
    root.mkdir()
    install = LedgerRecord.create(harness="claude_code", root=root, kind="install")
    install_ledger.append_record(install)
    install_ledger.append_record(
        LedgerRecord.create(
            harness="claude_code",
            root=root,
            kind="uninstall-incomplete",
            install_id=install.install_id,
        )
    )
    before = _snapshot(home)
    home_write_guard.also_protect_home(home)
    assert not install_driver_lifecycle.detect_install("claude_code", harness_root=root)
    assert _snapshot(home) == before
    assert len(home_write_guard.refusals()) == 1
