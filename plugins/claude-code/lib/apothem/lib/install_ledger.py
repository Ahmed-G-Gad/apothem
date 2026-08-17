# SPDX-License-Identifier: MIT

"""Append-only per-install state ledger — the source of truth for uninstall.

Every install pass appends one self-contained JSON record to
``~/.apothem/state/<harness>/ledger.jsonl`` describing exactly what was written
(per-target path, install mode, ownership class, and backup reference). Uninstall
and rollback read the latest record rather than re-deriving intent from the live
manifest, so manifest drift after install cannot strand or over-remove operator
files.

Durability model (mirrors :mod:`apothem.lib.atomic_io`):

- Each record is appended as one ``O_APPEND`` + ``fsync`` line via
  :func:`apothem.lib.atomic_io.append_line_durably` under an advisory lock — the
  whole file is never rewritten, so a crash mid-append can lose at most the final
  partial line, never a prior record.
- The reader tolerates and drops only a torn FINAL line — the one artifact the
  crash-during-append model can produce — so every complete prior record stays
  recoverable. A malformed line anywhere earlier cannot be a tear; it means the
  uninstall source of truth is corrupted and raises :class:`LedgerError` rather
  than being silently skipped.

This module depends only on :mod:`apothem.lib.atomic_io`; the projection from a
materialization pass to :class:`LedgerRecord` lives in the install driver to keep
the ledger free of an import cycle.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from apothem.lib import atomic_io

#: Root of the per-harness state ledgers: ``~/.apothem/state/<harness>/``.
STATE_ROOT: Path = Path.home() / ".apothem" / "state"

#: The per-harness ledger filename under ``STATE_ROOT/<harness>/``.
LEDGER_FILENAME = "ledger.jsonl"

#: Suffix for the sibling advisory-lock file serializing concurrent appends.
_LOCK_SUFFIX = ".lock"

#: Crockford base32 alphabet (excludes ``I``, ``L``, ``O``, ``U``). Its symbols
#: are in ascending ASCII order, so a ULID's lexical string order matches its
#: numeric order — and therefore its time order.
_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


class LedgerError(ValueError):
    """A ledger line other than a torn final append is unreadable.

    The ledger is the source of truth for uninstall and rollback, so a
    malformed record anywhere before the final line means the file was
    corrupted or hand-edited — masking it could strand or over-remove operator
    files. Only the final line may legitimately be unparseable: a crash
    mid-append tears at most that one record.
    """


#: A ledger record's lifecycle kind.
RecordKind = Literal["install", "uninstall", "rollback"]

#: The accepted record kinds, validated on construction.
RECORD_KINDS: tuple[RecordKind, ...] = ("install", "uninstall", "rollback")


def generate_ulid() -> str:
    """Return a fresh 26-character Crockford-base32 ULID.

    A ULID is a 128-bit value — 48 bits of millisecond timestamp in the high
    bits followed by 80 bits of randomness — encoded most-significant-first. The
    timestamp prefix makes ULIDs minted in different milliseconds sort lexically
    in time order; within a single millisecond order is undefined (the random
    suffix is unordered). The ledger establishes recency by append position, not
    by sorting install-ids, so within-millisecond monotonicity is not required.
    """
    timestamp_ms = time.time_ns() // 1_000_000
    randomness = int.from_bytes(os.urandom(10), "big")
    value = (timestamp_ms << 80) | randomness
    chars = [""] * 26
    for index in range(25, -1, -1):
        chars[index] = _CROCKFORD[value & 0x1F]
        value >>= 5
    return "".join(chars)


def _utc_now_iso() -> str:
    """Return the current UTC instant as an ISO-8601 string with a ``Z`` suffix."""
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
    )


@dataclass(frozen=True)
class LedgerTarget:
    """One file an install pass wrote, with the data needed to reverse it.

    Attributes:
        path: Absolute on-disk path that was written.
        mode: The install entry mode (e.g. ``write_text``, ``sentinel_merge``,
            ``replace_tree``) that produced the write — selects the surgical
            reversal strategy on uninstall.
        ownership_class: One of the five
            :data:`apothem.lib.propagation.OWNERSHIP_CLASSES` (``apothem-owned``,
            ``operator-owned``, ``vendor-reserved``, ``generated``,
            ``immutable``) — governs whether uninstall strips only the managed
            contribution or removes the whole file.
        backup_ref: Absolute path of the pre-write backup captured under
            ``BACKUP_ROOT`` (defined in
            :mod:`apothem.harnesses._shared.install_driver_types`), or ``None``
            when the target did not previously exist (nothing to restore;
            reversal is a delete).
    """

    path: str
    mode: str
    ownership_class: str
    backup_ref: str | None = None

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable representation, omitting an absent ref."""
        payload: dict[str, object] = {
            "path": self.path,
            "mode": self.mode,
            "ownership_class": self.ownership_class,
        }
        if self.backup_ref is not None:
            payload["backup_ref"] = self.backup_ref
        return payload

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> LedgerTarget:
        """Reconstruct a target from its serialized form.

        Raises:
            KeyError: When a required field is missing.
        """
        backup_ref = data.get("backup_ref")
        return cls(
            path=str(data["path"]),
            mode=str(data["mode"]),
            ownership_class=str(data["ownership_class"]),
            backup_ref=None if backup_ref is None else str(backup_ref),
        )


@dataclass(frozen=True)
class LedgerRecord:
    """One lifecycle event (install, uninstall, or rollback) for a harness+root.

    Attributes:
        install_id: The ULID identifying the originating install pass. An
            uninstall or rollback record carries the install-id it acted on.
        timestamp: ISO-8601 UTC instant the record was created.
        harness: The harness identifier (e.g. ``claude-code``).
        root: The install root the pass targeted, as a string.
        kind: One of :data:`RECORD_KINDS`.
        targets: The typed list of files the pass touched.
    """

    install_id: str
    timestamp: str
    harness: str
    root: str
    kind: str
    targets: tuple[LedgerTarget, ...] = ()

    @classmethod
    def create(
        cls,
        *,
        harness: str,
        root: Path | str,
        kind: RecordKind,
        targets: tuple[LedgerTarget, ...] = (),
        install_id: str | None = None,
    ) -> LedgerRecord:
        """Build a record, stamping a fresh ULID and UTC timestamp.

        Pass *install_id* to bind an uninstall/rollback record to the install
        pass it reverses; omit it on an install record to mint a new ULID.

        Raises:
            ValueError: When *kind* is not a recognized record kind.
        """
        if kind not in RECORD_KINDS:
            raise ValueError(f"unknown ledger record kind: {kind!r}")
        return cls(
            install_id=install_id if install_id is not None else generate_ulid(),
            timestamp=_utc_now_iso(),
            harness=harness,
            root=str(root),
            kind=kind,
            targets=tuple(targets),
        )

    def to_json_line(self) -> str:
        """Return the single-line JSON encoding appended to the ledger.

        Keys are sorted and separators compact so the line is deterministic and
        free of embedded newlines (the append primitive adds the terminator).
        """
        payload = {
            "install_id": self.install_id,
            "timestamp": self.timestamp,
            "harness": self.harness,
            "root": self.root,
            "kind": self.kind,
            "targets": [target.to_dict() for target in self.targets],
        }
        return json.dumps(payload, sort_keys=True, separators=(",", ":"))

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> LedgerRecord:
        """Reconstruct a record from its parsed JSON form.

        Raises:
            KeyError: When a required field is missing.
        """
        raw_targets = data.get("targets")
        entries = raw_targets if isinstance(raw_targets, list) else []
        targets = tuple(
            LedgerTarget.from_dict(entry)
            for entry in entries
            if isinstance(entry, dict)
        )
        return cls(
            install_id=str(data["install_id"]),
            timestamp=str(data["timestamp"]),
            harness=str(data["harness"]),
            root=str(data["root"]),
            kind=str(data["kind"]),
            targets=targets,
        )


def ledger_path(harness: str, *, state_root: Path | None = None) -> Path:
    """Return the ledger path for *harness* under *state_root*.

    *state_root* defaults to the live module-level :data:`STATE_ROOT` resolved at
    call time (not bound once at import), so a test or the install driver can
    redirect every ledger write by monkeypatching ``install_ledger.STATE_ROOT``
    — the same isolation pattern the install driver's ``BACKUP_ROOT`` uses.
    """
    root = STATE_ROOT if state_root is None else state_root
    return root / harness / LEDGER_FILENAME


def append_record(record: LedgerRecord, *, state_root: Path | None = None) -> Path:
    """Durably append *record* to its harness ledger and return the ledger path.

    The append runs under an advisory lock on a sibling ``.lock`` file so
    concurrent install passes into the same harness serialize their writes, and
    through :func:`apothem.lib.atomic_io.append_line_durably` so the record is
    fsynced without rewriting prior records.
    """
    path = ledger_path(record.harness, state_root=state_root)
    lock = path.with_name(path.name + _LOCK_SUFFIX)
    with atomic_io.advisory_lock(lock):
        atomic_io.append_line_durably(path, record.to_json_line())
    return path


def read_records(harness: str, *, state_root: Path | None = None) -> list[LedgerRecord]:
    """Return every complete record for *harness*, oldest first.

    Torn-line policy: under the ``O_APPEND`` + ``fsync`` durability model a
    crash mid-append can tear at most the FINAL line, so an unparseable final
    line is tolerated and dropped — every prior complete record is still
    recovered. Any other malformed line — invalid JSON before the final line,
    or a line anywhere that parses to something other than a record object
    carrying the required fields (a strict prefix of a one-line JSON object
    never parses, so a complete-but-invalid line is not a tear) — means the
    uninstall source of truth is corrupted and raises instead of being
    silently skipped. An absent ledger yields an empty list.

    Raises:
        LedgerError: When a non-final line is not valid JSON, or when any line
            parses to a non-object or to an object missing a required record
            field.
    """
    path = ledger_path(harness, state_root=state_root)
    if not path.is_file():
        return []
    records: list[LedgerRecord] = []
    lines = path.read_text(encoding="utf-8").splitlines()
    for index, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            data = json.loads(stripped)
        except ValueError as exc:
            # Only the final line can be a torn crash-mid-append artifact.
            if index == len(lines) - 1:
                break
            raise LedgerError(
                f"{path}: line {index + 1} is not valid JSON: {exc}"
            ) from exc
        if not isinstance(data, dict):
            raise LedgerError(f"{path}: line {index + 1} is not a record object")
        try:
            records.append(LedgerRecord.from_dict(data))
        except (KeyError, TypeError, ValueError) as exc:
            raise LedgerError(
                f"{path}: line {index + 1} is not a well-formed record: {exc!r}"
            ) from exc
    return records


def latest_record(
    harness: str,
    *,
    root: Path | str | None = None,
    kind: RecordKind | None = "install",
    state_root: Path | None = None,
) -> LedgerRecord | None:
    """Return the most recent matching record for *harness*, or ``None``.

    Filters by *root* (when given) and *kind* (default ``install``; pass
    ``None`` to match any kind). The last matching record in append order is the
    most recent.

    Raises:
        LedgerError: Propagated from :func:`read_records` on a corrupted ledger.
    """
    root_str = None if root is None else str(root)
    match: LedgerRecord | None = None
    for record in read_records(harness, state_root=state_root):
        if root_str is not None and record.root != root_str:
            continue
        if kind is not None and record.kind != kind:
            continue
        match = record
    return match


def find_record(
    harness: str,
    install_id: str,
    *,
    root: Path | str | None = None,
    kind: RecordKind | None = "install",
    state_root: Path | None = None,
) -> LedgerRecord | None:
    """Return the record with *install_id* for *harness*, or ``None``.

    Defaults to the originating ``install`` record so rollback resolves an
    install-id to what was written; pass ``kind=None`` to match any kind. A
    harness's ledger holds records for every install root, so pass *root* to
    bind the lookup to one install root (an install-id is unique per pass, but
    the *root* guard rejects a record from a different root outright).

    Raises:
        LedgerError: Propagated from :func:`read_records` on a corrupted ledger.
    """
    root_str = None if root is None else str(root)
    for record in read_records(harness, state_root=state_root):
        if record.install_id != install_id:
            continue
        if root_str is not None and record.root != root_str:
            continue
        if kind is not None and record.kind != kind:
            continue
        return record
    return None


__all__ = [
    "LEDGER_FILENAME",
    "RECORD_KINDS",
    "STATE_ROOT",
    "LedgerError",
    "LedgerRecord",
    "LedgerTarget",
    "RecordKind",
    "append_record",
    "find_record",
    "generate_ulid",
    "latest_record",
    "ledger_path",
    "read_records",
]
