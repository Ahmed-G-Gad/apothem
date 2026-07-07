# SPDX-License-Identifier: MIT

"""Unit tests for the agnostic memory surface."""

from __future__ import annotations

from pathlib import Path

import pytest

from apothem.lib.data_home import resolve_shared_data_home
from apothem.lib.memory import (
    MemoryRecord,
    MemoryStore,
    MemoryStoreError,
    validate_record,
)


def _fixture_record() -> MemoryRecord:
    """Build a fully-populated, schema-valid memory record."""
    return MemoryRecord(
        id="rec-0001",
        title="Plans live at the project root",
        body="Plan suites are written under <project-root>/.plans/ and gitignored.",
        kind="convention",
        created="2026-06-09T12:00:00Z",
        tags=("plans", "layout"),
        updated="2026-06-09T13:00:00Z",
        source="operator statement",
        confidence=0.95,
    )


def test_fixture_record_validates_with_zero_errors() -> None:
    # Arrange
    record = _fixture_record()

    # Act / Assert
    validate_record(record.to_dict())


def test_minimal_record_validates() -> None:
    # Arrange
    record = MemoryRecord(
        id="rec-min",
        title="A fact",
        body="The CLI entry point is apothem.",
        kind="fact",
        created="2026-06-09T12:00:00Z",
    )

    # Act / Assert
    validate_record(record.to_dict())


def test_add_and_records_round_trips(tmp_path: Path) -> None:
    # Arrange
    home = resolve_shared_data_home(base=tmp_path).ensure()
    store = MemoryStore(home)
    record = _fixture_record()

    # Act
    store.add(record)
    loaded = store.records()

    # Assert
    assert loaded == [record]
    assert store.contains("rec-0001")
    assert store.count() == 1


def test_records_empty_when_file_absent(tmp_path: Path) -> None:
    # Arrange
    home = resolve_shared_data_home(base=tmp_path).ensure()
    store = MemoryStore(home)

    # Act / Assert
    assert store.records() == []
    assert store.count() == 0
    assert not store.contains("missing")


def test_re_add_same_id_replaces(tmp_path: Path) -> None:
    # Arrange
    home = resolve_shared_data_home(base=tmp_path).ensure()
    store = MemoryStore(home)
    store.add(_fixture_record())

    # Act
    replacement = MemoryRecord(
        id="rec-0001",
        title="Updated title",
        body="Updated body.",
        kind="insight",
        created="2026-06-09T12:00:00Z",
    )
    store.add(replacement)

    # Assert
    assert store.count() == 1
    assert store.records() == [replacement]


def test_invalid_missing_required_raises(tmp_path: Path) -> None:
    # Arrange
    home = resolve_shared_data_home(base=tmp_path).ensure()
    store = MemoryStore(home)
    bad = {"id": "x", "title": "t", "body": "b", "kind": "fact"}  # no created

    # Act / Assert
    with pytest.raises(MemoryStoreError):
        validate_record(bad)
    with pytest.raises(MemoryStoreError):
        store.import_bytes(b'[{"id": "x", "title": "t", "body": "b", "kind": "fact"}]')


def test_invalid_bad_kind_raises() -> None:
    # Arrange
    bad = {
        "id": "x",
        "title": "t",
        "body": "b",
        "kind": "nonsense",
        "created": "2026-06-09T12:00:00Z",
    }

    # Act / Assert
    with pytest.raises(MemoryStoreError):
        validate_record(bad)


def test_invalid_additional_property_raises() -> None:
    # Arrange
    bad = {
        "id": "x",
        "title": "t",
        "body": "b",
        "kind": "fact",
        "created": "2026-06-09T12:00:00Z",
        "harness": "alpha",
    }

    # Act / Assert
    with pytest.raises(MemoryStoreError):
        validate_record(bad)


def test_export_import_byte_equivalent_across_homes(tmp_path: Path) -> None:
    # Arrange: two distinct bases yield two distinct shared homes, so the
    # export/import round-trip is exercised across genuinely separate stores.
    home_a = resolve_shared_data_home(base=tmp_path / "a").ensure()
    home_b = resolve_shared_data_home(base=tmp_path / "b").ensure()
    store_a = MemoryStore(home_a)
    store_b = MemoryStore(home_b)
    store_a.add(_fixture_record())
    store_a.add(
        MemoryRecord(
            id="rec-0002",
            title="Second",
            body="Another record.",
            kind="reference",
            created="2026-06-09T11:00:00Z",
        )
    )

    # Act
    store_b.import_bytes(store_a.export_bytes())

    # Assert
    assert store_b.export_bytes() == store_a.export_bytes()
    assert {r.id for r in store_b.records()} == {r.id for r in store_a.records()}


def test_export_empty_is_canonical(tmp_path: Path) -> None:
    # Arrange
    home = resolve_shared_data_home(base=tmp_path).ensure()
    store = MemoryStore(home)

    # Act / Assert
    assert store.export_bytes() == b"[]\n"


def test_serialized_record_carries_no_harness_token(tmp_path: Path) -> None:
    # Arrange
    home = resolve_shared_data_home(base=tmp_path).ensure()
    store = MemoryStore(home)
    store.add(_fixture_record())

    # Act
    serialized = store.export_bytes().decode("utf-8")

    # Assert — the agnostic guarantee: no harness identifier leaks into a record
    assert "gemini_cli" not in serialized
    assert "harness" not in serialized


def test_to_dict_omits_unset_optionals() -> None:
    # Arrange
    record = MemoryRecord(
        id="rec-min",
        title="A fact",
        body="Body.",
        kind="fact",
        created="2026-06-09T12:00:00Z",
    )

    # Act
    data = record.to_dict()

    # Assert
    assert set(data) == {"id", "title", "body", "kind", "created"}


def test_from_dict_round_trips() -> None:
    # Arrange
    record = _fixture_record()

    # Act
    rebuilt = MemoryRecord.from_dict(record.to_dict())

    # Assert
    assert rebuilt == record
