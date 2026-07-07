# SPDX-License-Identifier: MIT

"""Integration test for agnostic memory portability between two harnesses.

Covers Phase 00I task 6: exporting one harness's memory and importing it into
a second harness yields a byte-equivalent record set, with no harness-specific
field required for the round-trip.
"""

from __future__ import annotations

from pathlib import Path

from apothem.lib.data_home import resolve_shared_data_home
from apothem.lib.memory import MemoryRecord, MemoryStore


def _records() -> list[MemoryRecord]:
    """Build a small spread of valid, agnostic memory records."""
    return [
        MemoryRecord(
            id="conv-kebab-case",
            title="files use kebab-case",
            body="Files and folders use kebab-case naming.",
            kind="convention",
            created="2026-06-09T00:00:00Z",
            tags=("naming",),
        ),
        MemoryRecord(
            id="fact-py-floor",
            title="Python 3.10 floor",
            body="The project targets Python 3.10 and newer.",
            kind="fact",
            created="2026-06-09T00:01:00Z",
        ),
        MemoryRecord(
            id="insight-canonical-serialization",
            title="canonical serialization enables byte-equivalence",
            body="Sorting records by id makes the store byte-stable.",
            kind="insight",
            created="2026-06-09T00:02:00Z",
            confidence=0.9,
        ),
    ]


def test_memory_round_trips_between_two_harnesses(tmp_path: Path) -> None:
    # Arrange: populate harness A's memory under its own data home.
    store_a = MemoryStore(resolve_shared_data_home(base=tmp_path / "a").ensure())
    for record in _records():
        store_a.add(record)

    # Act: export A's memory and import it into harness B's distinct data home.
    store_b = MemoryStore(resolve_shared_data_home(base=tmp_path / "b").ensure())
    store_b.import_bytes(store_a.export_bytes())

    # Assert: byte-equivalent stores and an identical record-id set; the same
    # bytes serve both harnesses, so no harness-specific field was required.
    assert store_b.export_bytes() == store_a.export_bytes()
    assert {r.id for r in store_b.records()} == {r.id for r in store_a.records()}
    assert store_b.count() == len(_records())


def test_round_trip_carries_no_harness_specific_field(tmp_path: Path) -> None:
    # Arrange + Act: round-trip the records through export/import.
    store_a = MemoryStore(resolve_shared_data_home(base=tmp_path / "a").ensure())
    for record in _records():
        store_a.add(record)
    exported = store_a.export_bytes()
    store_b = MemoryStore(resolve_shared_data_home(base=tmp_path / "b").ensure())
    store_b.import_bytes(exported)

    # Assert: neither harness identifier appears anywhere in the serialized
    # bytes — the store is agnostic and portable by construction.
    text = exported.decode("utf-8").lower()
    assert "harness-a" not in text
    assert "harness-b" not in text
    assert "harness" not in text
