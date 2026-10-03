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
- :func:`compact_records` is the one rewrite: retention drops records older
  than the newest kept installs, writing the remainder through a sibling temp
  file and an atomic replace under the same lock, so a crash leaves either the
  old or the new ledger, never a partial one.
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
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, cast

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


#: The kinds of entry Apothem can own inside a structured (JSON / YAML) config.
#: ``key``: a mapping key Apothem added with a scalar value (removed on
#: uninstall while it still holds that value). ``item``: one list item Apothem
#: appended. ``container``: a mapping or list Apothem created (removed on
#: uninstall only once it is empty, so operator entries added to it survive).
OwnedKind = Literal["key", "item", "container"]

#: The accepted owned-entry kinds, validated on construction.
OWNED_KINDS: tuple[OwnedKind, ...] = ("key", "item", "container")


@dataclass(frozen=True)
class OwnedEntry:
    """One entry Apothem added to an operator-owned structured config.

    Attributes:
        path: The mapping keys from the document root to the entry (for an
            ``item``, the path of the list that holds it).
        kind: One of :data:`OWNED_KINDS`.
        value: The scalar value (``key``) or list item (``item``) Apothem
            wrote; ``None`` for a ``container``.
    """

    path: tuple[str, ...]
    kind: str
    value: object = None

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable representation."""
        payload: dict[str, object] = {"path": list(self.path), "kind": self.kind}
        if self.kind != "container":
            payload["value"] = self.value
        return payload

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> OwnedEntry:
        """Reconstruct an entry from its serialized form.

        Raises:
            KeyError: When a required field is missing.
            ValueError: When the kind is not one of :data:`OWNED_KINDS`.
        """
        kind = str(data["kind"])
        if kind not in OWNED_KINDS:
            raise ValueError(f"unknown owned-entry kind: {kind!r}")
        raw_path = data["path"]
        path = (
            tuple(str(part) for part in raw_path) if isinstance(raw_path, list) else ()
        )
        return cls(path=path, kind=kind, value=data.get("value"))


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
        outcome: What this pass did to the target (``created``, ``updated``,
            or ``unchanged``); ``None`` in records written before the field
            existed.
        created: Whether Apothem created the file in the current install cycle
            (this pass or an earlier install since the last uninstall), carried
            forward from record to record; ``None`` when unknown (older
            records).
        owned: The entries Apothem added to this structured config (see
            :class:`OwnedEntry`), carried forward from record to record;
            ``None`` when not recorded (a non-structured target, or an older
            record).
    """

    path: str
    mode: str
    ownership_class: str
    backup_ref: str | None = None
    outcome: str | None = None
    created: bool | None = None
    owned: tuple[OwnedEntry, ...] | None = field(default=None)

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable representation, omitting absent fields."""
        payload: dict[str, object] = {
            "path": self.path,
            "mode": self.mode,
            "ownership_class": self.ownership_class,
        }
        if self.backup_ref is not None:
            payload["backup_ref"] = self.backup_ref
        if self.outcome is not None:
            payload["outcome"] = self.outcome
        if self.created is not None:
            payload["created"] = self.created
        if self.owned is not None:
            payload["owned"] = [entry.to_dict() for entry in self.owned]
        return payload

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> LedgerTarget:
        """Reconstruct a target from its serialized form.

        Raises:
            KeyError: When a required field is missing.
        """
        backup_ref = data.get("backup_ref")
        outcome = data.get("outcome")
        created = data.get("created")
        raw_owned = data.get("owned")
        owned = (
            tuple(
                OwnedEntry.from_dict(cast("dict[str, object]", entry))
                for entry in raw_owned
                if isinstance(entry, dict)
            )
            if isinstance(raw_owned, list)
            else None
        )
        return cls(
            path=str(data["path"]),
            mode=str(data["mode"]),
            ownership_class=str(data["ownership_class"]),
            backup_ref=None if backup_ref is None else str(backup_ref),
            outcome=None if outcome is None else str(outcome),
            created=created if isinstance(created, bool) else None,
            owned=owned,
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
        created_dirs: The directories this install pass created (they did not
            exist before it), so rollback and uninstall can remove them once
            empty. Empty for other kinds and for records written before the
            field existed.
    """

    install_id: str
    timestamp: str
    harness: str
    root: str
    kind: str
    targets: tuple[LedgerTarget, ...] = ()
    created_dirs: tuple[str, ...] = ()

    @classmethod
    def create(
        cls,
        *,
        harness: str,
        root: Path | str,
        kind: RecordKind,
        targets: tuple[LedgerTarget, ...] = (),
        install_id: str | None = None,
        created_dirs: tuple[str, ...] = (),
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
            created_dirs=tuple(created_dirs),
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
        if self.created_dirs:
            payload["created_dirs"] = list(self.created_dirs)
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
        raw_dirs = data.get("created_dirs")
        created_dirs = (
            tuple(str(entry) for entry in raw_dirs)
            if isinstance(raw_dirs, list)
            else ()
        )
        return cls(
            install_id=str(data["install_id"]),
            timestamp=str(data["timestamp"]),
            harness=str(data["harness"]),
            root=str(data["root"]),
            kind=str(data["kind"]),
            targets=targets,
            created_dirs=created_dirs,
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


def active_install_records(
    harness: str,
    *,
    root: Path | str,
    state_root: Path | None = None,
) -> list[LedgerRecord]:
    """Return the install records whose changes are still in place at *root*.

    Replays the harness+root history in append order: an ``install`` record
    joins the stack; an ``uninstall`` clears it; a ``rollback`` of install *X*
    drops *X* and every later install (their changes were undone). A
    ``rollback`` with no install-id (a failed install that undid itself)
    changes nothing. Oldest first; empty when nothing is installed at *root*.

    Raises:
        LedgerError: Propagated from :func:`read_records` on a corrupted ledger.
    """
    root_str = str(root)
    installs: list[LedgerRecord] = []
    for record in read_records(harness, state_root=state_root):
        if record.root != root_str:
            continue
        if record.kind == "install":
            installs.append(record)
        elif record.kind == "uninstall":
            installs.clear()
        elif record.kind == "rollback":
            for index in range(len(installs) - 1, -1, -1):
                if installs[index].install_id == record.install_id:
                    del installs[index:]
                    break
    return installs


def current_install_record(
    harness: str,
    *,
    root: Path | str,
    state_root: Path | None = None,
) -> LedgerRecord | None:
    """Return the install record that describes *root*'s current state.

    The newest of :func:`active_install_records`; ``None`` when nothing is
    installed at *root*.

    Raises:
        LedgerError: Propagated from :func:`read_records` on a corrupted ledger.
    """
    installs = active_install_records(harness, root=root, state_root=state_root)
    return installs[-1] if installs else None


def _active_ids(records: list[LedgerRecord]) -> set[str]:
    """Return the install-ids still active in one root's *records* (replayed)."""
    installs: list[str] = []
    for record in records:
        if record.kind == "install":
            installs.append(record.install_id)
        elif record.kind == "uninstall":
            installs.clear()
        elif record.kind == "rollback" and record.install_id in installs:
            del installs[installs.index(record.install_id) :]
    return set(installs)


def _retained(records: list[LedgerRecord], keep_installs: int) -> list[LedgerRecord]:
    """Return the records retention keeps, per root, in ledger order.

    For each root the kept records are a contiguous tail starting at the
    oldest of the newest *keep_installs* active installs, so replaying the tail
    gives the same active installs as replaying the whole history. The
    directories older dropped installs created are folded into the first kept
    install, so uninstall still removes them. A root with no active install
    keeps only its last record.
    """
    by_root: dict[str, list[int]] = {}
    for index, record in enumerate(records):
        by_root.setdefault(record.root, []).append(index)
    kept: dict[int, LedgerRecord] = {}
    for indices in by_root.values():
        active = _active_ids([records[index] for index in indices])
        active_positions = [
            index
            for index in indices
            if records[index].kind == "install" and records[index].install_id in active
        ]
        if not active_positions:
            kept[indices[-1]] = records[indices[-1]]
            continue
        start = active_positions[-keep_installs:][0]
        for index in indices:
            if index >= start:
                kept[index] = records[index]
        dropped_dirs = {
            path
            for index in active_positions
            if index < start
            for path in records[index].created_dirs
        }
        if dropped_dirs:
            first = records[start]
            kept[start] = replace(
                first,
                created_dirs=tuple(sorted(dropped_dirs | set(first.created_dirs))),
            )
    return [kept[index] for index in sorted(kept)]


def compact_records(
    harness: str,
    *,
    keep_installs: int,
    state_root: Path | None = None,
    dry_run: bool = False,
) -> list[LedgerRecord]:
    """Drop *harness* ledger records retention no longer needs; return the rest.

    Keeps, per install root, the newest *keep_installs* installs whose changes
    are still in place and every record after the oldest of them (see
    :func:`_retained`). Older installs can no longer be rolled back by id. The
    ledger is rewritten atomically under its lock, and only when something is
    dropped. With *dry_run* the ledger is left untouched and the records a
    real compaction would keep are returned.

    Raises:
        LedgerError: Propagated from :func:`read_records` on a corrupted ledger.
    """
    if dry_run:
        return _retained(
            read_records(harness, state_root=state_root), max(1, keep_installs)
        )
    path = ledger_path(harness, state_root=state_root)
    lock = path.with_name(path.name + _LOCK_SUFFIX)
    with atomic_io.advisory_lock(lock):
        records = read_records(harness, state_root=state_root)
        kept = _retained(records, max(1, keep_installs))
        if kept != records:
            text = "".join(record.to_json_line() + "\n" for record in kept)
            atomic_io.write_bytes_atomically(path, text.encode("utf-8"))
    return kept


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
    "OWNED_KINDS",
    "RECORD_KINDS",
    "STATE_ROOT",
    "LedgerError",
    "LedgerRecord",
    "LedgerTarget",
    "OwnedEntry",
    "OwnedKind",
    "RecordKind",
    "active_install_records",
    "append_record",
    "compact_records",
    "current_install_record",
    "find_record",
    "generate_ulid",
    "latest_record",
    "ledger_path",
    "read_records",
]
