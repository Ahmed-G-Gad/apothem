# SPDX-License-Identifier: MIT

"""Rollback must restore only the record's own backups, not a sibling pass's.

Regression guard for the ``restore_backup`` ``only_refs`` scoping. The backup
timestamp slug is second-granular, so two install passes in the same second
share a ``BACKUP_ROOT/<timestamp>/<harness>/`` set. The prior rollback restored
the *whole* set by timestamp+harness, so rolling back one pass clobbered the
files a sibling pass had backed up under the shared slug. ``_rollback_impl`` now
passes the record's recorded ``backup_ref`` set as ``only_refs`` so the restore
is scoped to exactly that record. ``only_refs=None`` preserves the legacy
whole-set contract for any other caller.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from apothem.harnesses._shared import install_driver

_STAMP = "20240101T000000Z"


def _shared_backup_set(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Build a shared-slug backup set with one file per (simulated) pass."""
    backup_root = tmp_path / "backups"
    monkeypatch.setattr(install_driver, "BACKUP_ROOT", backup_root)
    harness = tmp_path / "home" / "harness"
    harness.mkdir(parents=True)
    bset = backup_root / _STAMP / "codex" / "harness"
    bset.mkdir(parents=True)
    # Record A backed up a.md; a sibling pass (record B) backed up b.md under the
    # same second-granular slug.
    (bset / "a.md").write_text("A-original\n", encoding="utf-8")
    (bset / "b.md").write_text("B-original\n", encoding="utf-8")
    (harness / "a.md").write_text("A-installed\n", encoding="utf-8")
    (harness / "b.md").write_text("B-installed\n", encoding="utf-8")
    return harness


def test_only_refs_restores_record_and_spares_sibling(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    harness = _shared_backup_set(tmp_path, monkeypatch)
    only = frozenset(
        {
            str(
                (
                    install_driver.BACKUP_ROOT / _STAMP / "codex" / "harness" / "a.md"
                ).resolve()
            )
        }
    )
    install_driver.restore_backup("codex", _STAMP, harness_root=harness, only_refs=only)
    assert (harness / "a.md").read_text(encoding="utf-8") == "A-original\n"
    # The sibling pass's file must NOT be clobbered.
    assert (harness / "b.md").read_text(encoding="utf-8") == "B-installed\n"


def test_no_only_refs_restores_whole_set(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    harness = _shared_backup_set(tmp_path, monkeypatch)
    install_driver.restore_backup("codex", _STAMP, harness_root=harness)
    assert (harness / "a.md").read_text(encoding="utf-8") == "A-original\n"
    assert (harness / "b.md").read_text(encoding="utf-8") == "B-original\n"
