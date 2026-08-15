# SPDX-License-Identifier: MIT

"""Unit tests for the legacy-to-shared workspace migration."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from apothem.lib.contexts import ContextFragment, ContextStore
from apothem.lib.data_home import DataHome, resolve_shared_data_home
from apothem.lib.learning import LearningSignal, LearningStore
from apothem.lib.memory import MemoryRecord, MemoryStore
from apothem.lib.workspace_migration import (
    WorkspaceMigrationError,
    detect_legacy_layout,
    migrate_workspace,
)


def _legacy_home(base: Path, package_key: str) -> DataHome:
    """Build a legacy per-harness data home under <base>/.apothem/<key>/."""
    root = base / ".apothem" / package_key
    return DataHome(
        root=root,
        plans=root / "plans",
        memory=root / "memory",
        contexts=root / "contexts",
        learning=root / "learning",
    ).ensure()


def _memory_record(record_id: str, body: str = "A durable fact.") -> MemoryRecord:
    return MemoryRecord(
        id=record_id,
        title="a fact",
        body=body,
        kind="fact",
        created="2026-06-24T00:00:00Z",
    )


def _fragment(fragment_id: str) -> ContextFragment:
    return ContextFragment(
        id=fragment_id,
        name="a fragment",
        body="An injectable context fragment.",
        enabled=True,
    )


def _signal(signal_id: str) -> LearningSignal:
    return LearningSignal(
        id=signal_id,
        kind="observation",
        summary="something observed",
        captured="2026-06-24T00:00:00Z",
    )


def test_detect_legacy_layout_finds_per_harness_home(tmp_path: Path) -> None:
    # Arrange: a per-harness data home exists.
    home = _legacy_home(tmp_path, "claude_code")
    MemoryStore(home).add(_memory_record("rec-1"))

    # Act / Assert.
    assert detect_legacy_layout(tmp_path) is True


def test_detect_legacy_layout_finds_legacy_plans(tmp_path: Path) -> None:
    # Arrange: only a legacy .plans tree exists.
    (tmp_path / ".plans" / "suite").mkdir(parents=True)

    # Act / Assert.
    assert detect_legacy_layout(tmp_path) is True


def test_detect_returns_false_for_shared_layout(tmp_path: Path) -> None:
    # Arrange: a clean shared layout — no per-harness home, no .plans.
    resolve_shared_data_home(base=tmp_path).ensure()

    # Act / Assert.
    assert detect_legacy_layout(tmp_path) is False


def test_migrate_unions_two_harness_stores(tmp_path: Path) -> None:
    # Arrange: two per-harness homes, each with distinct + one shared-id record.
    home_a = _legacy_home(tmp_path, "claude_code")
    home_b = _legacy_home(tmp_path, "zed")
    MemoryStore(home_a).add(_memory_record("rec-a"))
    MemoryStore(home_a).add(_memory_record("rec-shared"))
    MemoryStore(home_b).add(_memory_record("rec-b"))
    MemoryStore(home_b).add(_memory_record("rec-shared"))  # identical body
    ContextStore(home_a).add(_fragment("frag-a"))
    ContextStore(home_b).add(_fragment("frag-b"))
    LearningStore(home_a)._append(_signal("sig-a"))
    LearningStore(home_b)._append(_signal("sig-a"))  # duplicate, deduped

    # Act.
    outcome = migrate_workspace(tmp_path)

    # Assert: the shared store carries the UNION; the identical shared record is
    # not double-counted; the learning duplicate is deduped.
    shared = resolve_shared_data_home(base=tmp_path)
    ids = {record.id for record in MemoryStore(shared).records()}
    assert ids == {"rec-a", "rec-b", "rec-shared"}
    frag_ids = {fragment.id for fragment in ContextStore(shared).fragments()}
    assert frag_ids == {"frag-a", "frag-b"}
    assert LearningStore(shared).count() == 1
    assert outcome.migrated is True
    assert outcome.conflicts == []
    # The legacy per-harness homes are consumed, leaving the shared layout.
    assert not (tmp_path / ".apothem" / "claude_code").exists()
    assert not (tmp_path / ".apothem" / "zed").exists()
    # A backup of the consumed sources exists.
    assert outcome.backup_root is not None
    assert outcome.backup_root.is_dir()


def test_conflicting_record_is_skipped_not_overwritten(tmp_path: Path) -> None:
    # Arrange: two homes carry the SAME id with DIFFERENT bodies.
    home_a = _legacy_home(tmp_path, "claude_code")
    home_b = _legacy_home(tmp_path, "zed")
    MemoryStore(home_a).add(_memory_record("rec-x", body="body from A"))
    MemoryStore(home_b).add(_memory_record("rec-x", body="body from B"))

    # Act.
    outcome = migrate_workspace(tmp_path)

    # Assert: the conflict is recorded; the first-merged body wins, the second
    # is never silently overwritten.
    shared = resolve_shared_data_home(base=tmp_path)
    records = {r.id: r.body for r in MemoryStore(shared).records()}
    assert records["rec-x"] in {"body from A", "body from B"}
    assert any("rec-x" in conflict for conflict in outcome.conflicts)


def test_plans_tree_is_relocated(tmp_path: Path) -> None:
    # Arrange: a legacy .plans suite with a file.
    suite = tmp_path / ".plans" / "my-suite"
    suite.mkdir(parents=True)
    (suite / "PROGRESS.md").write_text("state\n", encoding="utf-8")

    # Act.
    outcome = migrate_workspace(tmp_path)

    # Assert: .plans moved under .apothem/plans; the legacy tree is gone.
    shared = resolve_shared_data_home(base=tmp_path)
    assert outcome.plans_moved is True
    assert (shared.plans / "my-suite" / "PROGRESS.md").read_text(
        encoding="utf-8"
    ) == "state\n"
    assert not (tmp_path / ".plans").exists()


def test_plans_not_clobbered_when_shared_plans_populated(tmp_path: Path) -> None:
    # Arrange: BOTH a legacy .plans and a populated shared plans/ exist.
    (tmp_path / ".plans" / "legacy-suite").mkdir(parents=True)
    shared = resolve_shared_data_home(base=tmp_path).ensure()
    (shared.plans / "existing-suite").mkdir(parents=True)

    # Act.
    outcome = migrate_workspace(tmp_path)

    # Assert: the legacy .plans is left in place (no clobber); a note records it.
    assert outcome.plans_moved is False
    assert (tmp_path / ".plans" / "legacy-suite").is_dir()
    assert any("already populated" in note for note in outcome.notes)


def test_migration_is_idempotent(tmp_path: Path) -> None:
    # Arrange: migrate once.
    home = _legacy_home(tmp_path, "claude_code")
    MemoryStore(home).add(_memory_record("rec-1"))
    (tmp_path / ".plans" / "suite").mkdir(parents=True)
    first = migrate_workspace(tmp_path)
    assert first.migrated is True

    # Act: migrate again on the already-migrated tree.
    second = migrate_workspace(tmp_path)

    # Assert: the second pass is a no-op — no legacy sources remain.
    assert second.migrated is False
    assert MemoryStore(resolve_shared_data_home(base=tmp_path)).count() == 1


def test_no_op_when_no_legacy_layout(tmp_path: Path) -> None:
    # Act: nothing to migrate.
    outcome = migrate_workspace(tmp_path)

    # Assert: clean no-op, no backup created.
    assert outcome.migrated is False
    assert outcome.backup_root is None


def test_raises_on_missing_base(tmp_path: Path) -> None:
    # Act / Assert.
    with pytest.raises(WorkspaceMigrationError):
        migrate_workspace(tmp_path / "does-not-exist")


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="symlink creation needs privileges on Windows",
)
def test_backup_tree_preserves_broken_symlink(tmp_path: Path) -> None:
    """A dangling symlink in a legacy home is backed up as a link, not an error."""
    from apothem.lib.workspace_migration import _backup_tree

    source = tmp_path / "legacy"
    source.mkdir()
    (source / "dangling").symlink_to(tmp_path / "no-such-target")
    backup_root = tmp_path / "backup"
    backup_root.mkdir()

    _backup_tree(source, backup_root, "legacy")

    assert (backup_root / "legacy" / "dangling").is_symlink()


def test_migrate_reports_a_legacy_home_it_could_not_remove(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A swallowed rmtree failure is surfaced, not reported as a clean move.

    ``shutil.rmtree`` runs with ``ignore_errors=True`` so a locked or
    permission-denied tree cannot abort a migration whose records are already
    merged and backed up. Windows hits that case routinely. Without a note the
    operator is told the migration succeeded while the legacy home is still on
    disk, and the next run rediscovers it.
    """
    home = _legacy_home(tmp_path, "claude_code")
    MemoryStore(home).add(_memory_record("rec-a"))
    # Simulate the swallowed failure: removal is attempted and silently does
    # nothing, exactly as ignore_errors leaves it on a locked tree.
    monkeypatch.setattr(
        "apothem.lib.workspace_migration.shutil.rmtree",
        lambda *args, **kwargs: None,
    )

    outcome = migrate_workspace(tmp_path)

    # The records still migrated -- the merge happened before the removal.
    shared = resolve_shared_data_home(base=tmp_path)
    assert {record.id for record in MemoryStore(shared).records()} == {"rec-a"}
    assert outcome.migrated is True
    # ...and the leftover is named, with its path, rather than passing silently.
    leftover = tmp_path / ".apothem" / "claude_code"
    assert leftover.exists()
    assert any(str(leftover) in note for note in outcome.notes)


def test_migrate_refuses_a_custom_working_directory_name(tmp_path: Path) -> None:
    """A non-default directory_name is refused, not silently mishandled.

    Only the migration target honours the name; discovery resolves the legacy
    tree from the module constant. Accepting a custom name would read the
    legacy homes from `.apothem/` and merge them into the named tree -- the
    wrong source, in code that moves and deletes a user's records. Nothing
    passes a non-default today; this pins the refusal so wiring the profile's
    workspace.directory_name through cannot quietly open that gap.
    """
    _legacy_home(tmp_path, "claude_code")

    with pytest.raises(WorkspaceMigrationError) as excinfo:
        migrate_workspace(tmp_path, directory_name=".custom")

    # The message names both the unsupported value and the reason.
    assert ".custom" in str(excinfo.value)
    assert "wrong tree" in str(excinfo.value)
