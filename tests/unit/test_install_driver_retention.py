# SPDX-License-Identifier: MIT

"""Retention never removes the backup set of a root's latest install record.

``prune_history`` (the pass behind ``apothem backups prune`` and the automatic
retention after every install) keeps the newest N backup sets per harness and
drops the ledger records retention no longer needs. Compaction alone keeps the
latest install record of a root that still has an active install, so its
backup set stays referenced. These tests pin the guarantee directly, including
the case compaction does not cover: a root whose latest install was later
uninstalled.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from apothem.harnesses._shared import install_driver
from apothem.lib import install_ledger
from apothem.lib.install_ledger import LedgerRecord, LedgerTarget

_HARNESS = "cursor"


def _backup_set(stamp: str) -> Path:
    path = install_driver.BACKUP_ROOT / stamp / _HARNESS / "rules.mdc"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(stamp, encoding="utf-8")
    return path


def _install(root: Path, backup: Path | None) -> LedgerRecord:
    target = LedgerTarget(
        path=str(root / "rules.mdc"),
        mode="write_text",
        ownership_class="operator-owned",
        backup_ref=str(backup) if backup is not None else None,
        outcome="updated",
    )
    return LedgerRecord.create(
        harness=_HARNESS, root=root, kind="install", targets=(target,)
    )


@pytest.fixture
def uninstalled_root(tmp_path: Path) -> Path:
    """Two installs at one root, then an uninstall that backed up the file.

    Sets, oldest first: S1 (first install), S2 (second install, the latest
    install record's set), S3 (the uninstall's own backup).
    """
    root = tmp_path / "project"
    s1 = _backup_set("20260101T000001Z")
    s2 = _backup_set("20260101T000002Z")
    _backup_set("20260101T000003Z")
    install_ledger.append_record(_install(root, s1))
    install_ledger.append_record(_install(root, s2))
    install_ledger.append_record(
        LedgerRecord.create(harness=_HARNESS, root=root, kind="uninstall")
    )
    return root


def _sets() -> list[str]:
    return install_driver.list_backup_timestamps(_HARNESS)


def test_latest_install_set_survives_when_compaction_drops_the_record(
    uninstalled_root: Path,
) -> None:
    report = install_driver.prune_history(_HARNESS, keep=1)

    assert _sets() == ["20260101T000002Z", "20260101T000003Z"]
    assert report.pruned == ("20260101T000001Z",)
    assert report.protected == ("20260101T000002Z",)
    assert report.records_before == 3
    assert report.records_after == 1


def test_dry_run_reports_the_same_plan_and_changes_nothing(
    uninstalled_root: Path,
) -> None:
    ledger = install_ledger.ledger_path(_HARNESS)
    ledger_before = ledger.read_bytes()

    report = install_driver.prune_history(_HARNESS, keep=1, dry_run=True)

    assert report.dry_run
    assert report.pruned == ("20260101T000001Z",)
    assert report.records_dropped == 2
    assert _sets() == ["20260101T000001Z", "20260101T000002Z", "20260101T000003Z"]
    assert ledger.read_bytes() == ledger_before


def test_apply_retention_tolerates_a_corrupted_ledger(tmp_path: Path) -> None:
    _backup_set("20260101T000001Z")
    ledger = install_ledger.ledger_path(_HARNESS)
    ledger.parent.mkdir(parents=True)
    ledger.write_text("not json\n{}\n", encoding="utf-8")

    with pytest.raises(install_ledger.LedgerError):
        install_driver.prune_history(_HARNESS, keep=1)
    install_driver.apply_retention(_HARNESS, keep=1)

    assert _sets() == ["20260101T000001Z"]


def _advancing_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make every backup-clock read land in a new second, like a slow disk."""
    from datetime import datetime, timedelta, tzinfo

    from apothem.harnesses._shared import install_driver_types

    start = datetime(2026, 1, 1, tzinfo=install_driver_types.timezone.utc)
    seconds = iter(range(1_000_000))

    class _Clock(datetime):
        @classmethod
        def now(cls, tz: tzinfo | None = None) -> datetime:
            return start + timedelta(seconds=next(seconds))

    monkeypatch.setattr(install_driver_types, "datetime", _Clock)


def test_backup_session_pins_one_slug_and_nested_sessions_share_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from apothem.harnesses._shared.install_driver_types import backup_session

    _advancing_clock(monkeypatch)
    with backup_session() as outer:
        assert install_driver._timestamp_slug() == outer
        with backup_session() as inner:
            assert inner == outer
        assert install_driver._timestamp_slug() == outer
    assert install_driver._timestamp_slug() != outer


def test_slow_uninstall_keeps_its_own_backup_of_the_settings_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An uninstall slower than retention's set count keeps its first backup.

    Uninstall backs up every file it changes. With one timestamp per backup,
    an uninstall spanning more than ``BACKUP_KEEP`` seconds wrote more sets
    than retention keeps, and the retention pass at its end deleted the
    operation's earliest backups, the pre-uninstall settings file among them.
    """
    import json

    from apothem.harnesses.claude_code import ClaudeCodeAdapter

    _advancing_clock(monkeypatch)
    target = tmp_path / "settings.json"
    adapter = ClaudeCodeAdapter()
    monkeypatch.setattr(type(adapter), "output_path", property(lambda self: target))
    adapter.install({})
    settings = json.loads(target.read_text(encoding="utf-8"))
    settings["operatorCustom"] = {"keep": True}
    target.write_text(json.dumps(settings, indent=2), encoding="utf-8")
    before = set(install_driver.list_backup_timestamps("claude_code"))

    adapter.uninstall()

    assert list(install_driver.BACKUP_ROOT.rglob("settings.json"))
    written = set(install_driver.list_backup_timestamps("claude_code")) - before
    assert len(written) == 1
