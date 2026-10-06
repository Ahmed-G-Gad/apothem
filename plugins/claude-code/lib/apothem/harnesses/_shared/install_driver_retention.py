# SPDX-License-Identifier: MIT

"""Retention: bound the install ledger and the backup sets it references.

Every install, uninstall and rollback appends a ledger record and may write a
timestamped backup set under ``BACKUP_ROOT/<timestamp>/<harness>/``. After each
of them :func:`apply_retention` keeps the newest :data:`BACKUP_KEEP`; ``apothem
backups prune`` runs the same pass on demand through :func:`prune_history`,
with its own bound and an optional dry run.
"""

from __future__ import annotations

import contextlib
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from apothem.harnesses._shared import install_driver
from apothem.lib import install_ledger
from apothem.lib.install_ledger import LedgerRecord

from .install_driver_types import _handle_rm_error

#: How many install records per install root, and backup sets per harness,
#: retention keeps. Older ones are deleted after each install, uninstall and
#: rollback; anything a kept record still references is never deleted.
BACKUP_KEEP: Final[int] = 10


@dataclass(frozen=True)
class RetentionReport:
    """What one retention pass over a harness kept, removed, and protected.

    Backup sets are named by their ``BACKUP_ROOT/<timestamp>/`` directory.
    *pruned* lists the sets the pass removed (for a dry run, the sets a real
    pass would remove); *protected* the sets beyond the newest *keep* that
    stay because a ledger record still references them; *failed* the
    pruned sets that could not be fully removed.
    """

    harness: str
    keep: int
    dry_run: bool
    kept: tuple[str, ...]
    pruned: tuple[str, ...]
    protected: tuple[str, ...]
    failed: tuple[str, ...]
    records_before: int
    records_after: int

    @property
    def records_dropped(self) -> int:
        """How many ledger records the pass dropped (or would drop)."""
        return self.records_before - self.records_after


def list_backup_timestamps(harness_name: str | None = None) -> list[str]:
    """Return available backup timestamps under the Apothem backup root.

    Each timestamp is a ``~/.apothem/backups/<timestamp>/`` directory created
    before a mutating install pass. When *harness_name* is given, only
    timestamps carrying a backup set for that harness are returned. Results are
    sorted oldest-to-newest (the timestamp slug sorts lexically by time).
    """
    if not install_driver.BACKUP_ROOT.is_dir():
        return []
    stamps: list[str] = []
    for ts_dir in sorted(install_driver.BACKUP_ROOT.iterdir()):
        if not ts_dir.is_dir():
            continue
        if harness_name is None or (ts_dir / harness_name).is_dir():
            stamps.append(ts_dir.name)
    return stamps


def _referenced_timestamps(records: list[LedgerRecord]) -> set[str]:
    """Return the backup-set timestamps the *records* still reference."""
    backup_root = install_driver.BACKUP_ROOT.resolve()
    stamps: set[str] = set()
    for record in records:
        for target in record.targets:
            if not target.backup_ref:
                continue
            try:
                relative = Path(target.backup_ref).resolve().relative_to(backup_root)
            except ValueError:
                continue
            if relative.parts:
                stamps.add(relative.parts[0])
    return stamps


def _latest_installs(records: list[LedgerRecord]) -> list[LedgerRecord]:
    """Return the newest ``install`` record of each install root in *records*.

    These are the records ``apothem rollback`` reverses by default.
    """
    latest: dict[str, LedgerRecord] = {}
    for record in records:
        if record.kind == "install":
            latest[record.root] = record
    return list(latest.values())


def prune_history(
    harness_name: str, *, keep: int = BACKUP_KEEP, dry_run: bool = False
) -> RetentionReport:
    """Bound *harness_name*'s ledger and backup sets to the newest *keep*.

    Compacts the ledger (see :func:`install_ledger.compact_records`), then
    removes the harness's backup sets under ``BACKUP_ROOT/<timestamp>/`` beyond
    the newest *keep*. A set is never removed while a kept ledger record, or
    the latest install record of any install root, references it, so every
    kept install, and the latest one in particular, can still be rolled back.
    A timestamp directory left empty is removed too. With *dry_run* nothing
    is changed and the report says what a real pass would do.

    Raises:
        install_ledger.LedgerError: When the ledger is corrupted; nothing is
            changed.
        OSError: When the backup root cannot be listed.
    """
    before = install_ledger.read_records(harness_name)
    kept_records = install_ledger.compact_records(
        harness_name, keep_installs=keep, dry_run=dry_run
    )
    referenced = _referenced_timestamps(kept_records) | _referenced_timestamps(
        _latest_installs(before)
    )
    stamps = list_backup_timestamps(harness_name)
    older = stamps[: max(0, len(stamps) - keep)]
    pruned = tuple(stamp for stamp in older if stamp not in referenced)
    failed: list[str] = []
    if not dry_run:
        for stamp in pruned:
            stamp_dir = install_driver.BACKUP_ROOT / stamp
            shutil.rmtree(stamp_dir / harness_name, onerror=_handle_rm_error)
            if (stamp_dir / harness_name).exists():
                failed.append(stamp)
            with contextlib.suppress(OSError):
                stamp_dir.rmdir()
    return RetentionReport(
        harness=harness_name,
        keep=keep,
        dry_run=dry_run,
        kept=tuple(stamp for stamp in stamps if stamp not in pruned),
        pruned=pruned,
        protected=tuple(stamp for stamp in older if stamp in referenced),
        failed=tuple(failed),
        records_before=len(before),
        records_after=len(kept_records),
    )


def apply_retention(harness_name: str, *, keep: int = BACKUP_KEEP) -> None:
    """Bound *harness_name*'s ledger and backup sets to the newest *keep*.

    The automatic pass after every install, uninstall and rollback: it runs
    :func:`prune_history` and is best-effort, so a retention failure never
    fails the install, uninstall or rollback that triggered it.
    """
    with contextlib.suppress(OSError, install_ledger.LedgerError):
        prune_history(harness_name, keep=keep)
