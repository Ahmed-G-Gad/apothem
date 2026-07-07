# SPDX-License-Identifier: MIT

"""Integration tests for shared data-surface materialization + cross-harness sharing.

Memory, contexts, and learning materialize into ONE shared data home beneath the
install root (and nowhere else), and a record written under one harness is
visible to a second harness sharing the same base — the data home is shared, not
per-harness.
"""

from __future__ import annotations

from pathlib import Path

from apothem.harnesses._shared.install_driver import (
    _materialize_data_surfaces,
    run_install,
)
from apothem.lib.data_home import resolve_shared_data_home
from apothem.lib.memory import MemoryRecord, MemoryStore


def _record(record_id: str) -> MemoryRecord:
    """Build a minimal valid memory record for tests."""
    return MemoryRecord(
        id=record_id,
        title="prefers explicit configuration",
        body="The operator prefers explicit configuration over implicit defaults.",
        kind="preference",
        created="2026-06-09T00:00:00Z",
    )


def test_run_install_materializes_data_surfaces(tmp_path: Path) -> None:
    # Arrange: a clean harness root.
    harness_root = tmp_path / "home"

    # Act: run a real install into the tmp harness root.
    run = run_install("claude_code", harness_root=harness_root)

    # Assert: memory + contexts + learning artifacts exist under the single
    # shared data home, seeded as empty canonical stores.
    home = resolve_shared_data_home(base=harness_root)
    records_file = home.memory / "records.json"
    fragments_file = home.contexts / "fragments.json"
    signals_file = home.learning / "signals.jsonl"
    assert records_file.is_file()
    assert fragments_file.is_file()
    assert signals_file.is_file()
    assert records_file.read_text(encoding="utf-8") == "[]\n"
    assert fragments_file.read_text(encoding="utf-8") == "[]\n"
    # The learning store is JSON Lines: an empty store is a zero-length file
    # that the store reads back as zero captured signals.
    assert signals_file.read_text(encoding="utf-8") == ""

    # The run reports the data-surface materialization.
    data_surface_paths = {
        result.path for result in run.results if result.operation == "data_surface"
    }
    assert str(records_file) in data_surface_paths
    assert str(fragments_file) in data_surface_paths
    assert str(signals_file) in data_surface_paths


def test_data_surfaces_written_nowhere_else(tmp_path: Path) -> None:
    # Arrange / Act: install one harness into a clean root.
    harness_root = tmp_path / "home"
    run_install("claude_code", harness_root=harness_root)

    # Assert: every memory/contexts/learning store artifact lives under the
    # single shared data home — none leaked elsewhere under the harness root.
    home = resolve_shared_data_home(base=harness_root)
    records_files = list(harness_root.rglob("records.json"))
    fragments_files = list(harness_root.rglob("fragments.json"))
    signals_files = list(harness_root.rglob("signals.jsonl"))
    assert records_files == [home.memory / "records.json"]
    assert fragments_files == [home.contexts / "fragments.json"]
    assert signals_files == [home.learning / "signals.jsonl"]


def test_memory_write_is_shared_across_harnesses(tmp_path: Path) -> None:
    # Arrange: write a record under the shared data home (a single base shared
    # by every harness — there is no per-harness segment to separate them).
    base = tmp_path
    store_a = MemoryStore(resolve_shared_data_home(base=base).ensure())
    record = _record("rec-sharing")
    store_a.add(record)

    # Act: materialize a second harness under the same base.
    _materialize_data_surfaces("harness-b", base)

    # Assert: the second harness sees A's record — the home is shared. The
    # idempotent seed never clobbers the operator's accumulated record.
    store_b = MemoryStore(resolve_shared_data_home(base=base))
    assert store_b.contains(record.id)
    assert store_b.count() == 1
    assert store_a.contains(record.id)


def test_re_materialization_preserves_operator_records(tmp_path: Path) -> None:
    # Arrange: materialize the shared home, then the operator accumulates a record.
    base = tmp_path
    _materialize_data_surfaces("harness-a", base)
    store_a = MemoryStore(resolve_shared_data_home(base=base))
    record = _record("rec-survives-reinstall")
    store_a.add(record)

    # Act: re-materialize (a re-install, or a second harness sharing the base).
    results = _materialize_data_surfaces("harness-a", base)

    # Assert: the record survives; the re-seed is non-destructive + reported
    # unchanged (the data home already existed).
    assert store_a.contains(record.id)
    assert store_a.count() == 1
    assert all(result.outcome == "unchanged" for result in results)
