# SPDX-License-Identifier: MIT

"""Agnostic, operator-portable memory surface for the durable knowledge store.

The memory surface holds durable knowledge records — stable facts, ratified
conventions, operator preferences, derived insights, and external references.
Records are fully agnostic: a record carries no tool-specific or vendor-specific
identifier, so the same record round-trips between any two installation targets
without loss.

A :class:`MemoryStore` is bound to a :class:`~apothem.lib.data_home.DataHome`'s
``memory`` directory and persists every record to a single canonical
``records.json`` file. Serialization is deterministic — records are sorted by
id and emitted with sorted keys and stable indentation — so two stores holding
the same record set produce byte-identical files, which is what makes the
export/import round-trip a byte-for-byte guarantee.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final, cast

from jsonschema import Draft202012Validator

from apothem.lib.atomic_io import advisory_lock, write_bytes_atomically
from apothem.lib.data_home import DataHome
from apothem.lib.schema_errors import format_schema_errors
from apothem.schemas import memory_record_schema_path

#: The canonical filename, under a data home's ``memory`` dir, holding the
#: serialized JSON array of records.
_RECORDS_FILENAME: Final[str] = "records.json"

#: The advisory-lock filename guarding the records read-modify-write window.
_RECORDS_LOCK_FILENAME: Final[str] = ".records.lock"

#: The canonical serialization of an empty store — a JSON array with the same
#: indentation and trailing newline a populated store would carry.
_EMPTY_CANONICAL: Final[bytes] = b"[]\n"


class MemoryStoreError(ValueError):
    """Raised when a memory record fails schema validation."""


def _schema() -> dict[str, object]:
    """Load and parse the memory-record JSON schema.

    Returns:
        The parsed schema document.
    """
    raw = memory_record_schema_path().read_text(encoding="utf-8")
    return cast("dict[str, object]", json.loads(raw))


def validate_record(data: Mapping[str, object]) -> None:
    """Validate *data* against the memory-record schema.

    Args:
        data: The candidate record mapping to validate.

    Raises:
        MemoryStoreError: When *data* violates the schema. The message lists every
            validation error discovered.
    """
    validator = Draft202012Validator(_schema())
    details = format_schema_errors(validator, dict(data))
    if details:
        raise MemoryStoreError(f"invalid memory record: {details}")


@dataclass(frozen=True)
class MemoryRecord:
    """One durable, agnostic knowledge record in the memory surface.

    The record shape mirrors the memory-record schema and carries no
    harness-specific or vendor-specific field, so it is portable across any
    installation target.

    Attributes:
        id: Stable record identifier, unique within a store.
        title: One-line summary used to decide relevance during recall.
        body: The knowledge itself, stated specifically.
        kind: Record taxonomy; one of ``fact``, ``convention``, ``preference``,
            ``insight``, or ``reference``.
        created: ISO 8601 date-time the record was first written.
        tags: Discovery tags for recall filtering.
        updated: ISO 8601 date-time the record was last amended, if any.
        source: Provenance of the knowledge, if recorded.
        confidence: Optional confidence in the record's accuracy, in ``[0, 1]``.
    """

    id: str
    title: str
    body: str
    kind: str
    created: str
    tags: tuple[str, ...] = ()
    updated: str | None = None
    source: str | None = None
    confidence: float | None = None

    def to_dict(self) -> dict[str, object]:
        """Render the record as a schema-conformant mapping.

        Optional keys are omitted when unset (``None`` scalars, empty ``tags``)
        so the output validates under ``additionalProperties: false`` and
        round-trips cleanly.

        Returns:
            A JSON-serializable mapping of the record's set fields.
        """
        data: dict[str, object] = {
            "id": self.id,
            "title": self.title,
            "body": self.body,
            "kind": self.kind,
            "created": self.created,
        }
        if self.tags:
            data["tags"] = list(self.tags)
        if self.updated is not None:
            data["updated"] = self.updated
        if self.source is not None:
            data["source"] = self.source
        if self.confidence is not None:
            data["confidence"] = self.confidence
        return data

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> MemoryRecord:
        """Reconstruct a record from a schema-conformant mapping.

        Args:
            data: A mapping carrying at least the required record fields.

        Returns:
            The reconstructed :class:`MemoryRecord`.
        """
        raw_tags = data.get("tags", ())
        tags: tuple[str, ...] = ()
        if isinstance(raw_tags, Sequence) and not isinstance(raw_tags, (str, bytes)):
            tags = tuple(str(tag) for tag in raw_tags)

        updated = data.get("updated")
        source = data.get("source")
        raw_confidence = data.get("confidence")
        confidence: float | None = None
        if isinstance(raw_confidence, (int, float)) and not isinstance(
            raw_confidence, bool
        ):
            confidence = float(raw_confidence)
        return cls(
            id=str(data["id"]),
            title=str(data["title"]),
            body=str(data["body"]),
            kind=str(data["kind"]),
            created=str(data["created"]),
            tags=tags,
            updated=None if updated is None else str(updated),
            source=None if source is None else str(source),
            confidence=confidence,
        )


def _serialize(records: Sequence[MemoryRecord]) -> bytes:
    """Serialize *records* into the canonical on-disk byte form.

    Records are sorted by id and emitted with sorted keys, two-space
    indentation, and a trailing newline, so the same record set always yields
    byte-identical output.

    Args:
        records: The records to serialize.

    Returns:
        The canonical serialized bytes.
    """
    payload = [record.to_dict() for record in sorted(records, key=lambda r: r.id)]
    text = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False)
    return (text + "\n").encode("utf-8")


def _parse(data: bytes) -> list[MemoryRecord]:
    """Parse canonical bytes into records, validating each.

    Args:
        data: The serialized JSON array of records.

    Returns:
        The parsed records.

    Raises:
        MemoryStoreError: When the payload is not a JSON array or any record fails
            schema validation.
    """
    loaded = json.loads(data.decode("utf-8"))
    if not isinstance(loaded, list):
        raise MemoryStoreError("memory payload must be a JSON array of records")
    records: list[MemoryRecord] = []
    for item in loaded:
        if not isinstance(item, Mapping):
            raise MemoryStoreError("each memory record must be a JSON object")
        validate_record(item)
        records.append(MemoryRecord.from_dict(item))
    return records


class MemoryStore:
    """A canonical, deterministic on-disk store of memory records.

    The store persists to a single ``records.json`` file under a data home's
    ``memory`` directory. All mutations re-serialize the full record set
    canonically, so the file is always byte-stable for a given set of records.
    """

    def __init__(self, data_home: DataHome) -> None:
        """Bind the store to *data_home*'s memory directory.

        Args:
            data_home: The per-target data home whose ``memory`` directory
                holds this store's canonical records file.
        """
        self._memory_dir = data_home.memory
        self._records_path = data_home.memory / _RECORDS_FILENAME
        self._lock_path = data_home.memory / _RECORDS_LOCK_FILENAME

    def records(self) -> list[MemoryRecord]:
        """Load every record from disk.

        Returns:
            The stored records, or an empty list when the file is absent.

        Raises:
            MemoryStoreError: When the on-disk payload is malformed.
        """
        if not self._records_path.exists():
            return []
        return _parse(self._records_path.read_bytes())

    def add(self, record: MemoryRecord) -> None:
        """Validate and persist *record*, replacing any record with its id.

        The store directory is created if absent. Re-adding a record whose id
        already exists replaces the prior entry, so the operation is idempotent
        on identity.

        Args:
            record: The record to persist.

        Raises:
            MemoryStoreError: When *record* fails schema validation.
        """
        validate_record(record.to_dict())
        self._memory_dir.mkdir(parents=True, exist_ok=True)
        # Serialize the read-modify-write window so a concurrent add cannot read
        # a stale record set and clobber the other writer's record.
        with advisory_lock(self._lock_path):
            existing = [r for r in self.records() if r.id != record.id]
            existing.append(record)
            self._write(existing)

    def contains(self, record_id: str) -> bool:
        """Report whether a record with *record_id* is stored.

        Args:
            record_id: The identifier to look up.

        Returns:
            ``True`` when a record with the id exists, else ``False``.
        """
        return any(record.id == record_id for record in self.records())

    def count(self) -> int:
        """Count the stored records.

        Returns:
            The number of records on disk.
        """
        return len(self.records())

    def ensure_initialized(self) -> Path:
        """Create the canonical records file as an empty store when absent.

        Materialization calls this so a freshly-installed target carries a
        concrete, empty memory artifact. The operation is idempotent and
        non-destructive: when the file already exists its records are left
        untouched, so re-materializing a populated store never loses data.

        Returns:
            The path to the canonical records file.
        """
        # Serialize the check-then-write under the same lock add()/import_bytes()
        # hold, so a concurrent first add() cannot create the file with a record
        # between the existence check and the empty-store write that clobbers it.
        with advisory_lock(self._lock_path):
            if not self._records_path.exists():
                self._write([])
        return self._records_path

    def export_bytes(self) -> bytes:
        """Export the store's canonical serialized bytes.

        Returns:
            The bytes on disk, or the canonical empty array when absent.
        """
        if not self._records_path.exists():
            return _EMPTY_CANONICAL
        return self._records_path.read_bytes()

    def import_bytes(self, data: bytes) -> None:
        """Replace the store's contents with the records parsed from *data*.

        Args:
            data: A canonical serialized JSON array of records.

        Raises:
            MemoryStoreError: When the payload is malformed or any record is invalid.
        """
        # Parse outside the lock (it reads only the input, never the store),
        # then serialize the full-replace write under the same advisory lock the
        # add() read-modify-write holds. Without the lock a concurrent add()
        # could interleave with this unlocked write and lose records.
        records = _parse(data)
        with advisory_lock(self._lock_path):
            self._write(records)

    def _write(self, records: Sequence[MemoryRecord]) -> None:
        """Persist *records* canonically, creating the directory if absent.

        Args:
            records: The records to write.
        """
        self._memory_dir.mkdir(parents=True, exist_ok=True)
        write_bytes_atomically(self._records_path, _serialize(records))


__all__ = [
    "MemoryRecord",
    "MemoryStore",
    "MemoryStoreError",
    "validate_record",
]
