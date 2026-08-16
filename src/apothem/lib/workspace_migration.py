# SPDX-License-Identifier: MIT

"""Migrate a legacy per-harness workspace into the shared ``.apothem`` layout.

Apothem once scattered its working state across a per-harness data home
(``<base>/.apothem/<harness>/{memory,contexts,learning}``) and a sibling
``<base>/.plans`` tree. The shared layout collapses both into one
``<base>/.apothem/{plans,memory,learning,contexts}`` working directory shared
across every harness.

This module migrates an existing install non-destructively:

* **Union-merge** the per-harness ``memory`` / ``contexts`` stores into the
  shared store by record id, and **concatenate-dedup** the per-harness
  ``learning`` signals. A record id present in two per-harness stores with the
  SAME body merges to one; a CONFLICT (same id, different body) is never
  silently overwritten — the incoming record is skipped and reported.
* **Move** ``<base>/.plans`` to the shared ``<base>/.apothem/plans``.
* **Back up** every source the migration consumes before touching it, so the
  pre-migration state is always recoverable.

The migration is **idempotent**: re-running it on an already-migrated tree
finds no legacy sources and reports a no-op. It never deletes operator data
without a backup, and never overwrites a conflicting record.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from apothem.lib.contexts import ContextStore
from apothem.lib.data_home import (
    _APOTHEM_SUBTREE,
    _PLANS_CHILD,
    DataHome,
    resolve_shared_data_home,
)
from apothem.lib.harness_registry import SUPPORTED_PACKAGE_KEYS
from apothem.lib.learning import LearningSignal, LearningStore
from apothem.lib.memory import MemoryStore

#: Marker file written into the backup root so a backup directory is never
#: mistaken for a live working directory.
_BACKUP_README = "MIGRATION-BACKUP.txt"


class WorkspaceMigrationError(RuntimeError):
    """Raised when the migration cannot proceed safely."""


@dataclass
class MigrationOutcome:
    """The result of one workspace migration pass.

    Attributes:
        base: The base directory the migration ran against.
        migrated: ``True`` when at least one legacy source was migrated.
        backup_root: The directory legacy sources were backed up into, or
            ``None`` when nothing was migrated (no backup created).
        memory_merged: Count of memory records merged into the shared store.
        contexts_merged: Count of context fragments merged into the shared store.
        learning_merged: Count of learning signals merged into the shared store.
        conflicts: Per-store id conflicts skipped (same id, different body).
        plans_moved: ``True`` when a legacy ``.plans`` tree was relocated.
        notes: Human-readable notes about skipped or no-op steps.
    """

    base: Path
    migrated: bool = False
    backup_root: Path | None = None
    memory_merged: int = 0
    contexts_merged: int = 0
    learning_merged: int = 0
    conflicts: list[str] = field(default_factory=list)
    plans_moved: bool = False
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable representation of the outcome."""
        return {
            "base": str(self.base),
            "migrated": self.migrated,
            "backup_root": None if self.backup_root is None else str(self.backup_root),
            "memory_merged": self.memory_merged,
            "contexts_merged": self.contexts_merged,
            "learning_merged": self.learning_merged,
            "conflicts": list(self.conflicts),
            "plans_moved": self.plans_moved,
            "notes": list(self.notes),
        }


def _legacy_home_dirs(base: Path) -> list[Path]:
    """Return the per-harness legacy data homes present under ``<base>/.apothem``.

    A legacy home is ``<base>/.apothem/<package_key>/`` for a registered
    harness, carrying at least one of the ``memory`` / ``contexts`` /
    ``learning`` child directories. The shared-layout children (``plans``,
    ``memory``, ``contexts``, ``learning`` placed DIRECTLY under ``.apothem``)
    are never harness package keys, so they are not mistaken for legacy homes.
    """
    apothem_root = base / _APOTHEM_SUBTREE
    homes: list[Path] = []
    for package_key in SUPPORTED_PACKAGE_KEYS:
        candidate = apothem_root / package_key
        if not candidate.is_dir():
            continue
        if any(
            (candidate / child).is_dir() for child in ("memory", "contexts", "learning")
        ):
            homes.append(candidate)
    return homes


def _legacy_data_home(base: Path, package_key: str) -> DataHome:
    """Resolve a legacy per-harness data home (``<base>/.apothem/<key>/``)."""
    root = base / _APOTHEM_SUBTREE / package_key
    return DataHome(
        root=root,
        plans=root / _PLANS_CHILD,
        memory=root / "memory",
        contexts=root / "contexts",
        learning=root / "learning",
    )


def _timestamp_slug() -> str:
    """Return a filesystem-safe UTC timestamp slug for the backup directory."""
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def detect_legacy_layout(base: Path) -> bool:
    """Return ``True`` when *base* carries a legacy layout needing migration.

    A legacy layout is present when either a per-harness data home exists under
    ``<base>/.apothem/<harness>/`` OR a legacy ``<base>/.plans`` tree exists.
    """
    if _legacy_home_dirs(base):
        return True
    return (base / ".plans").is_dir()


def _merge_memory(legacy: MemoryStore, shared: MemoryStore) -> tuple[int, list[str]]:
    """Union *legacy* records into *shared* by id; return (merged, conflicts)."""
    merged = 0
    conflicts: list[str] = []
    existing = {record.id: record for record in shared.records()}
    for record in legacy.records():
        prior = existing.get(record.id)
        if prior is None:
            shared.add(record)
            existing[record.id] = record
            merged += 1
        elif prior.to_dict() != record.to_dict():
            conflicts.append(f"memory:{record.id}")
    return merged, conflicts


def _merge_contexts(
    legacy: ContextStore, shared: ContextStore
) -> tuple[int, list[str]]:
    """Union *legacy* fragments into *shared* by id; return (merged, conflicts)."""
    merged = 0
    conflicts: list[str] = []
    existing = {fragment.id: fragment for fragment in shared.fragments()}
    for fragment in legacy.fragments():
        prior = existing.get(fragment.id)
        if prior is None:
            shared.add(fragment)
            existing[fragment.id] = fragment
            merged += 1
        elif prior.to_dict() != fragment.to_dict():
            conflicts.append(f"contexts:{fragment.id}")
    return merged, conflicts


def _signal_identity(signal: LearningSignal) -> str:
    """Return a stable identity for a learning signal for dedup purposes.

    The learning store is an append-only JSON Lines log, so the migration
    deduplicates on the signal's full canonical serialization rather than its id
    alone — two byte-identical signals captured under different harnesses are the
    same observation and collapse to one, while two signals sharing an id but
    differing in any field are both preserved.
    """
    return json.dumps(signal.to_dict(), sort_keys=True, ensure_ascii=False)


def _merge_learning(legacy: LearningStore, shared: LearningStore) -> int:
    """Concatenate-dedup *legacy* signals into *shared*; return merged count."""
    seen = {_signal_identity(signal) for signal in shared.signals()}
    merged = 0
    for signal in legacy.signals():
        identity = _signal_identity(signal)
        if identity in seen:
            continue
        # Append ungated rather than through capture(): the opt-in gate governs
        # NEW signals, not the migration of already-captured ones, so a
        # flag-off operator does not lose previously-captured data.
        shared.append_signal(signal)
        seen.add(identity)
        merged += 1
    return merged


def _backup_tree(source: Path, backup_root: Path, label: str) -> None:
    """Copy *source* into ``<backup_root>/<label>`` before it is consumed."""
    if not source.exists():
        return
    destination = backup_root / label
    destination.parent.mkdir(parents=True, exist_ok=True)
    # symlinks=True preserves links (including dangling ones) as links
    # instead of failing on their targets; a backup failure aborts BEFORE
    # any merge consumes the source, so the legacy homes stay intact.
    try:
        shutil.copytree(source, destination, dirs_exist_ok=True, symlinks=True)
    except (shutil.Error, OSError) as exc:
        raise WorkspaceMigrationError(
            f"pre-migration backup of {source} failed: {exc}"
        ) from exc


def _ensure_backup_root(base: Path) -> Path:
    """Create and return a fresh timestamped backup root under ``<base>/.apothem``."""
    backup_root = base / _APOTHEM_SUBTREE / "backups" / f"migrate-{_timestamp_slug()}"
    backup_root.mkdir(parents=True, exist_ok=True)
    (backup_root / _BACKUP_README).write_text(
        "Pre-migration backup of the legacy per-harness data homes and .plans "
        "tree. Safe to delete once the shared .apothem layout is verified.\n",
        encoding="utf-8",
    )
    return backup_root


def migrate_workspace(
    base: Path, *, directory_name: str = ".apothem"
) -> MigrationOutcome:
    """Migrate the legacy layout under *base* to the shared ``.apothem`` layout.

    The migration is non-destructive and idempotent:

    * Per-harness data homes (``<base>/.apothem/<harness>/``) union-merge into
      the shared store. A conflicting record (same id, different body) is
      skipped and recorded, never overwritten.
    * A legacy ``<base>/.plans`` tree moves to ``<base>/.apothem/plans``. When
      the shared ``plans`` already exists, the move is skipped and recorded
      (no clobber).
    * Every consumed source is backed up first.

    Args:
        base: The base directory the working directory sits beneath.
        directory_name: The shared working-directory name. Only the default
            ``.apothem`` is supported; see Raises.

    Returns:
        A :class:`MigrationOutcome` describing what was migrated.

    Raises:
        WorkspaceMigrationError: When *base* is not an existing directory, or
            when *directory_name* is not the default. Only the migration
            TARGET honours the name — discovery (``_legacy_data_home``,
            ``detect_legacy_layout``) resolves the legacy tree from the module
            constant instead. Accepting a custom name would therefore read the
            legacy homes from ``.apothem/`` while merging them into the named
            tree: the wrong source, in code that moves and deletes a user's
            records. Refusing is the honest behaviour until discovery is
            threaded through too. Nothing passes a non-default today, so this
            raise is unreachable from the shipped CLI; it exists to stop the
            trap closing when the profile's ``workspace.directory_name`` is
            eventually wired to this call.
    """
    if not base.is_dir():
        raise WorkspaceMigrationError(f"base directory does not exist: {base}")
    if directory_name != _APOTHEM_SUBTREE:
        raise WorkspaceMigrationError(
            f"migrate_workspace supports only the default working directory "
            f"{_APOTHEM_SUBTREE!r}; got {directory_name!r}. Legacy-layout "
            f"discovery is not yet parameterized, so a custom name would "
            f"migrate from the wrong tree."
        )

    outcome = MigrationOutcome(base=base)
    legacy_homes = _legacy_home_dirs(base)
    legacy_plans = base / ".plans"
    has_legacy_plans = legacy_plans.is_dir()

    if not legacy_homes and not has_legacy_plans:
        outcome.notes.append("no legacy layout detected — nothing to migrate")
        return outcome

    shared = resolve_shared_data_home(base=base, directory_name=directory_name).ensure()
    backup_root = _ensure_backup_root(base)
    outcome.backup_root = backup_root

    shared_memory = MemoryStore(shared)
    shared_contexts = ContextStore(shared)
    shared_learning = LearningStore(shared)
    shared_memory.ensure_initialized()
    shared_contexts.ensure_initialized()
    shared_learning.ensure_initialized()

    for home_dir in legacy_homes:
        package_key = home_dir.name
        _backup_tree(home_dir, backup_root, f"data-home/{package_key}")
        legacy = _legacy_data_home(base, package_key)
        mem_merged, mem_conflicts = _merge_memory(MemoryStore(legacy), shared_memory)
        ctx_merged, ctx_conflicts = _merge_contexts(
            ContextStore(legacy), shared_contexts
        )
        lrn_merged = _merge_learning(LearningStore(legacy), shared_learning)
        outcome.memory_merged += mem_merged
        outcome.contexts_merged += ctx_merged
        outcome.learning_merged += lrn_merged
        outcome.conflicts.extend(
            f"{package_key}:{conflict}" for conflict in (*mem_conflicts, *ctx_conflicts)
        )
        # The merged legacy home is removed only after a successful backup +
        # union merge, so its records are preserved both in the shared store and
        # in the backup.
        shutil.rmtree(home_dir, ignore_errors=True)
        # `ignore_errors` keeps a locked or permission-denied tree from aborting
        # a migration whose records are already safe, but it also hides the
        # leftover. Report it: silence would leave the operator believing the
        # legacy home is gone while the next run rediscovers it.
        if home_dir.exists():
            outcome.notes.append(
                f"legacy data home {home_dir} could not be removed — its records "
                "are merged into the shared store and preserved in the backup; "
                "delete the directory manually"
            )
        outcome.migrated = True

    if has_legacy_plans:
        if shared.plans.exists() and any(shared.plans.iterdir()):
            outcome.notes.append(
                "shared plans/ already populated — legacy .plans left in place; "
                f"merge manually from {legacy_plans}"
            )
        else:
            _backup_tree(legacy_plans, backup_root, "plans")
            # Remove the empty placeholder so the rename lands cleanly.
            if shared.plans.exists():
                shared.plans.rmdir()
            shutil.move(str(legacy_plans), str(shared.plans))
            outcome.plans_moved = True
            outcome.migrated = True

    return outcome


__all__ = [
    "MigrationOutcome",
    "WorkspaceMigrationError",
    "detect_legacy_layout",
    "migrate_workspace",
]
