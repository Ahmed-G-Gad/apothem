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

import ctypes
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


#: A ledger record's lifecycle kind. ``uninstall-incomplete`` records an
#: uninstall that did not finish: it leaves the install active (a reader that
#: does not know the kind skips it the same way), so a second run can finish.
RecordKind = Literal["install", "uninstall", "rollback", "uninstall-incomplete"]

#: The accepted record kinds, validated on construction.
RECORD_KINDS: tuple[RecordKind, ...] = (
    "install",
    "uninstall",
    "rollback",
    "uninstall-incomplete",
)


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
    """One file a pass wrote or backed up, with the data needed to reverse it.

    An install record lists every file the install wrote. An uninstall or
    rollback record lists the files that pass backed up before changing them,
    so retention keeps those backup sets while the record is kept. In those
    records only *path* and *backup_ref* are relied on: *mode* is the
    operation, *ownership_class* falls back to ``operator-owned``, and
    *outcome* can be ``skipped`` or ``error`` for a file the pass backed up
    but did not change.

    Attributes:
        path: Absolute on-disk path that was written (or, in an uninstall or
            rollback record, backed up).
        mode: The install entry mode (e.g. ``write_text``, ``sentinel_merge``,
            ``replace_tree``) that produced the write — selects the surgical
            reversal strategy on uninstall. In an uninstall or rollback record,
            the operation that changed the file.
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
        digest: The SHA-256 of the file as this pass left it, for a target
            that is a file; ``None`` for a folder and in older records.
            Uninstall removes the file only while it still has this content.
        files: For a target that is a folder, each file in it as this pass
            left it (a ``/``-separated path relative to the folder, mapped to
            its SHA-256; links are not followed). ``None`` for a file and in
            older records. Uninstall removes only the listed files whose
            content still matches.
    """

    path: str
    mode: str
    ownership_class: str
    backup_ref: str | None = None
    outcome: str | None = None
    created: bool | None = None
    owned: tuple[OwnedEntry, ...] | None = field(default=None)
    digest: str | None = None
    files: dict[str, str] | None = field(default=None, hash=False)

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
        if self.digest is not None:
            payload["digest"] = self.digest
        if self.files is not None:
            payload["files"] = dict(sorted(self.files.items()))
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
            digest=_text_or_none(data.get("digest")),
            files=_digest_map(data.get("files")),
        )


def _text_or_none(value: object) -> str | None:
    """Return *value* when it is a non-empty string, else ``None``."""
    return value if isinstance(value, str) and value else None


def _digest_map(value: object) -> dict[str, str] | None:
    """Return a recorded ``files`` map, keeping only string-to-string entries."""
    if not isinstance(value, dict):
        return None
    return {
        str(path): digest for path, digest in value.items() if isinstance(digest, str)
    }


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
        targets: The typed list of files the pass touched (see
            :class:`LedgerTarget` for what each kind of record lists).
        created_dirs: The directories this install pass created (they did not
            exist before it), so rollback and uninstall can remove them once
            empty. Empty for other kinds and for records written before the
            field existed.
        data_home: The shared Apothem working directory (memory, contexts,
            learning, plans) the install pass resolved and wrote its data
            stores under, as an absolute path string. Set on install records
            only; ``None`` for other kinds and for records written before the
            field existed, which reverse against the default location.
    """

    install_id: str
    timestamp: str
    harness: str
    root: str
    kind: str
    targets: tuple[LedgerTarget, ...] = ()
    created_dirs: tuple[str, ...] = ()
    data_home: str | None = None

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
        data_home: str | None = None,
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
            data_home=data_home or None,
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
        if self.data_home is not None:
            payload["data_home"] = self.data_home
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
        raw_home = data.get("data_home")
        data_home = str(raw_home) if isinstance(raw_home, str) and raw_home else None
        return cls(
            install_id=str(data["install_id"]),
            timestamp=str(data["timestamp"]),
            harness=str(data["harness"]),
            root=str(data["root"]),
            kind=str(data["kind"]),
            targets=targets,
            created_dirs=created_dirs,
            data_home=data_home,
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
        LedgerError: When the file is not UTF-8 text, when a non-final line is
            not valid JSON (nesting too deep to parse counts as invalid), or
            when any line parses to a non-object or to an object missing a
            required record field.
    """
    path = ledger_path(harness, state_root=state_root)
    if not path.is_file():
        return []
    records: list[LedgerRecord] = []
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        # Apothem writes ASCII-only lines (json.dumps escapes the rest), so a
        # byte that is not UTF-8 is damage, not a torn append.
        raise LedgerError(
            f"{path}: byte {exc.start} is not UTF-8 text: {exc.reason}"
        ) from exc
    lines = text.splitlines()
    for index, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            data = json.loads(stripped)
        except (ValueError, RecursionError) as exc:
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


def _settled_records(
    harness: str, root: Path | str, state_root: Path | None
) -> list[LedgerRecord]:
    """Return *root*'s records in ledger order, less the rollbacks that changed nothing.

    A failed install that undid itself appends a rollback of an id no install
    at *root* has; it changed nothing, so it supersedes nothing.

    Raises:
        LedgerError: Propagated from :func:`read_records` on a corrupted ledger.
    """
    root_str = str(root)
    return _settled(
        [
            record
            for record in read_records(harness, state_root=state_root)
            if record.root == root_str
        ]
    )


def _settled(records: list[LedgerRecord]) -> list[LedgerRecord]:
    """Return one root's *records* less the rollbacks that changed nothing."""
    installed = {record.install_id for record in records if record.kind == "install"}
    return [
        record
        for record in records
        if record.kind != "rollback" or record.install_id in installed
    ]


def unfinished_uninstall(
    harness: str,
    *,
    root: Path | str,
    state_root: Path | None = None,
) -> LedgerRecord | None:
    """Return the ``uninstall-incomplete`` record when it is *root*'s latest.

    An install, update, rollback or finished uninstall appended after it
    supersedes it, so ``None`` then, and when *root* has no record. The
    rollback a failed install appends to undo itself (its id matches no
    install) changed nothing and supersedes nothing.

    Raises:
        LedgerError: Propagated from :func:`read_records` on a corrupted ledger.
    """
    return _unfinished(_settled_records(harness, root, state_root))


def _unfinished(records: list[LedgerRecord]) -> LedgerRecord | None:
    """Return the ``uninstall-incomplete`` record when it is one root's latest.

    The rollbacks that changed nothing are passed over (see :func:`_settled`).
    """
    settled = _settled(records)
    if settled and settled[-1].kind == "uninstall-incomplete":
        return settled[-1]
    return None


def last_uninstall_finished(
    harness: str,
    *,
    root: Path | str,
    state_root: Path | None = None,
) -> bool:
    """Return True when *root*'s latest record is a finished ``uninstall``.

    The ``uninstall-incomplete`` records after it (passes that did not
    finish) are passed over, and so is the rollback a failed install appends
    to undo itself, as :func:`unfinished_uninstall` passes it over.

    Raises:
        LedgerError: Propagated from :func:`read_records` on a corrupted ledger.
    """
    for record in reversed(_settled_records(harness, root, state_root)):
        if record.kind != "uninstall-incomplete":
            return record.kind == "uninstall"
    return False


def recorded_root(harness: str, root: Path, *, state_root: Path | None = None) -> Path:
    """Return the spelling of *root* that *harness*'s install records use.

    A record keeps its install root as a string, and every reader matches it
    exactly. The CLI resolves ``--project`` before it reads or writes a
    record, while a Python caller passes the folder as it typed it, so the
    two can name one folder two ways: through a link, or with ``~``. Use
    this before reading a record by root, so both find the same record; an
    install or update writes through :func:`install_spelling` instead. A
    spelling whose install is still active (installed and not uninstalled)
    comes first, in this order:

    1. *root* as given;
    2. *root* resolved (``~`` expanded, links followed);
    3. another recorded root that names the same folder, as recorded (see
       :func:`_same_folder_installs`); the one with the most recorded files
       in the folder wins, then the newest.

    Then a spelling whose install is no longer active, *root* as given, then
    *root* resolved; otherwise *root* resolved, so a new install records the
    folder the way the CLI does.

    Text is compared exactly, never with the case folded. In a
    case-sensitive folder (one WSL made, say) ``Proj`` and ``proj`` are two
    folders and are never taken for each other. In an ordinary Windows
    folder resolving gives both the case on disk, so they are one folder, as
    Windows treats them; resolving keeps the case as typed for a folder that
    no longer exists, so then only the spelling the record has finds it.

    Rule 3 cannot always tell two installs apart. When two installs were
    made through two links to two different folders, and one link was later
    pointed at the other folder, it takes the install with more of its files
    in that folder. If both wrote the same file names (the same release), or
    an earlier release recorded them (it did not list its files), it takes
    the newer one, whose files may be in the folder the link used to lead
    to.

    A ledger that cannot be read gives *root* resolved, without raising: the
    caller that reads the ledger next reports the error itself. A *root* that
    cannot be resolved (a link loop) is returned as given.
    """
    try:
        resolved = root.expanduser().resolve(strict=False)
    except (OSError, RuntimeError):
        return root
    try:
        records = read_records(harness, state_root=state_root)
    except (LedgerError, OSError):
        return resolved
    by_root: dict[str, list[LedgerRecord]] = {}
    for record in records:
        by_root.setdefault(record.root, []).append(record)
    live = {spelling: _live_install(group) for spelling, group in by_root.items()}
    as_given, as_resolved = str(root), str(resolved)
    if live.get(as_given) is not None:
        return root
    if live.get(as_resolved) is not None:
        return resolved
    # How many records came after each root's newest one: 0 for the newest.
    age = {record.root: len(records) - i for i, record in enumerate(records, 1)}
    unfinished = {s for s, group in by_root.items() if _unfinished(group) is not None}
    others = [
        (-present, age[spelling], spelling)
        for spelling, present in _same_folder_installs(
            live, resolved, skip=(as_given, as_resolved), unfinished=unfinished
        )
    ]
    if others:
        return Path(min(others)[2])
    if as_given in by_root:
        return root
    return resolved


def install_spelling(
    harness: str, root: Path, *, state_root: Path | None = None
) -> tuple[Path, Path | None]:
    r"""Return ``(spelling, moving)`` for an install or update into *root*.

    *spelling* is the one the install writes and records: the spelling
    :func:`recorded_root` gives, resolved, as the CLI records it, so no
    install keeps its record under a link that may later be removed (after
    which no command would find it). Resolving the recorded spelling, not
    *root*, keeps a disk-only match (a ``\\localhost\C$`` path for a
    folder recorded as ``C:\...``) on the spelling the record has, which
    every spelling of the folder still finds.

    *moving* is the spelling whose active install :func:`move_install` must
    move to *spelling* before the install writes anything, or ``None``. It is
    ``None`` when nothing is active under another spelling, and when
    *spelling* already has an active install of its own (a duplicate an
    earlier release left, or a link pointed at another installed folder):
    moving would put the older records after the newer ones, and could
    merge two folders' installs. Reads only; nothing is written.

    A relative or ``~`` recorded root with an active install (an earlier
    Python call from some folder) is kept as given, as are a *root* that
    cannot be resolved and a ledger that cannot be read: the install then
    writes under the spelling its record has, as it did before.
    """
    spelling = recorded_root(harness, root, state_root=state_root)
    try:
        resolved = spelling.expanduser().resolve(strict=False)
        records = read_records(harness, state_root=state_root)
    except (LedgerError, OSError, RuntimeError):
        return spelling, None
    if str(spelling) == str(resolved):
        return resolved, None
    by_root: dict[str, list[LedgerRecord]] = {}
    for record in records:
        by_root.setdefault(record.root, []).append(record)
    if _live_install(by_root.get(str(spelling), [])) is None:
        return resolved, None
    if not spelling.is_absolute():
        return spelling, None
    if _live_install(by_root.get(str(resolved), [])) is not None:
        return resolved, None
    return resolved, spelling


def move_install(
    harness: str, old: Path, new: Path, *, state_root: Path | None = None
) -> None:
    """Move *harness*'s active install recorded under *old* to *new*.

    Its active install records, and an unfinished uninstall after them, are
    appended again under *new* with every path below *old* moved below
    *new*, and an ``uninstall`` record that lists nothing closes *old*. The
    install keeps its ids, so a rollback by install id still works. It is
    one append under the ledger lock: a crash can tear only its end, which
    leaves both spellings active (two live records for one folder), never
    the install unrecorded. Nothing is appended when nothing is active
    under *old*.

    Raises:
        LedgerError: The ledger is corrupted.
        OSError: The ledger cannot be written.
    """
    path = ledger_path(harness, state_root=state_root)
    with atomic_io.advisory_lock(path.with_name(path.name + _LOCK_SUFFIX)):
        own = [
            record
            for record in read_records(harness, state_root=state_root)
            if record.root == str(old)
        ]
        moved = _moved_records(own, str(old), new)
        if moved:
            lines = "\n".join(record.to_json_line() for record in moved)
            atomic_io.append_line_durably(path, lines)


def _moved_records(
    records: list[LedgerRecord], old: str, new: Path
) -> list[LedgerRecord]:
    """Return the records that move one root's active install from *old* to *new*.

    Empty when nothing is active under *old*. Otherwise the active installs
    and an unfinished uninstall after them, each with *new* as its root and
    every path below *old* moved below *new*, then an ``uninstall`` record
    of *old* that closes it.
    """
    active_ids = active_install_ids(records)
    active = [r for r in records if r.kind == "install" and r.install_id in active_ids]
    if not active:
        return []
    unfinished = _unfinished(records)
    moved = [_rebased(record, old, new) for record in active]
    if unfinished is not None:
        moved.append(_rebased(unfinished, old, new))
    closing = LedgerRecord.create(
        harness=active[-1].harness,
        root=old,
        kind="uninstall",
        install_id=active[-1].install_id,
    )
    return [*moved, closing]


def _rebased(record: LedgerRecord, old: str, new: Path) -> LedgerRecord:
    """Return *record* with root *new* and its paths below *old* moved below *new*."""

    def moved(path: str) -> str:
        try:
            return str(new / Path(path).relative_to(old))
        except ValueError:
            return path

    return replace(
        record,
        root=str(new),
        targets=tuple(replace(t, path=moved(t.path)) for t in record.targets),
        created_dirs=tuple(moved(path) for path in record.created_dirs),
        data_home=None if record.data_home is None else moved(record.data_home),
    )


def _same_folder_installs(
    live: dict[str, LedgerRecord | None],
    resolved: Path,
    *,
    skip: tuple[str, ...],
    unfinished: set[str],
) -> list[tuple[str, int]]:
    """Return ``(recorded root, files present)`` for live installs of *resolved*.

    Only an absolute recorded root counts: a relative or ``~`` one was kept
    as typed, relative to the folder the install ran from, so it cannot be
    matched from here. A recorded root names the folder when, resolved, it
    is the same text, or when both are the same folder on disk (see
    :func:`_same_on_disk`) and at least one file the install recorded is in
    the folder: file identity alone is no proof, since some network and
    cloud drives give every folder the same ID. A root none of whose
    recorded files is in the folder is left out (its link may have been
    pointed elsewhere), unless its latest record is an unfinished uninstall
    (*unfinished*), which removed them: the next uninstall finishes it.
    *files present* counts the recorded files the folder holds.
    """
    found: list[tuple[str, int]] = []
    for spelling, install in live.items():
        if install is None or spelling in skip:
            continue
        match = _names_folder(spelling, resolved)
        if match is None:
            continue
        missing, counted = _file_counts(spelling, install, resolved)
        if counted and missing == counted and spelling not in unfinished:
            continue
        if match == "disk" and not counted:
            continue
        found.append((spelling, counted - missing))
    return found


def _live_install(records: list[LedgerRecord]) -> LedgerRecord | None:
    """Return the newest install of one root's *records* that is still active."""
    active = active_install_ids(records)
    for record in reversed(records):
        if record.kind == "install" and record.install_id in active:
            return record
    return None


def _file_counts(spelling: str, install: LedgerRecord, folder: Path) -> tuple[int, int]:
    """Return ``(missing, counted)`` for *install*'s recorded files under *spelling*.

    Each target the install wrote (a file with a digest, or a folder with
    its file list) under its root *spelling* is counted and looked for at
    the same place under *folder*; *missing* is how many *folder* lacks.
    Targets outside the root (shared folders in the home) and targets
    without that proof (every target an earlier release recorded) are not
    counted.
    """
    base = Path(spelling)
    missing = counted = 0
    for target in install.targets:
        if target.digest is None and target.files is None:
            continue
        try:
            relative = Path(target.path).relative_to(base)
            exists = os.path.lexists(folder / relative)
        except (OSError, ValueError):
            continue
        counted += 1
        missing += not exists
    return missing, counted


def _names_folder(recorded: str, resolved: Path) -> str | None:
    """Return how the recorded root *recorded* names the folder *resolved*.

    ``"text"`` when *recorded*, resolved, is the same text as *resolved*;
    ``"disk"`` when the text differs but both are the same folder on disk
    (see :func:`_same_on_disk`); ``None`` when it names another folder or
    none. Path equality is not used: on Windows it ignores case, and a
    case-sensitive folder can hold ``Proj`` and ``proj`` as two folders. A
    relative recorded root (``~`` included, which the driver never expanded)
    names no folder. One on a network share (see :func:`_share`) other than
    *resolved*'s is not looked up: a share that cannot be reached stalls for
    many seconds.
    """
    path = Path(recorded)
    if not path.is_absolute():
        return None
    share = _share(path)
    if share is not None and share != (
        _share(resolved) or os.path.normcase(resolved.drive)
    ):
        return None
    try:
        candidate = path.resolve(strict=False)
        if str(candidate) == str(resolved):
            return "text"
        return "disk" if _same_on_disk(candidate, resolved) else None
    except (OSError, RuntimeError, ValueError):
        return None


#: ``GetDriveTypeW``'s answer for a drive letter mapped to a network share.
_DRIVE_REMOTE = 4


def _share(path: Path) -> str | None:
    r"""Return the network share *path* is on, case folded, or ``None``.

    A ``\\server\share`` path (``\\?\UNC\server\share`` too) gives its
    ``\\server\share``; server and share names ignore case. On Windows a
    drive letter mapped to a share gives the share it is connected to, or
    the letter itself when it is not connected now. Windows answers both
    from its own tables, without reaching the server.
    """
    drive = path.drive.replace("/", "\\")
    if drive[:4] in {"\\\\?\\", "\\\\.\\"}:
        unc = drive[4:8].upper() == "UNC\\"
        return os.path.normcase("\\\\" + drive[8:]) if unc else None
    if drive[:2] == "\\\\":
        return os.path.normcase(drive)
    if len(drive) == 2 and drive[1] == ":" and _drive_type(drive) == _DRIVE_REMOTE:
        return os.path.normcase(_mapped_share(drive) or drive)
    return None


def _drive_type(drive: str) -> int:
    """Return ``GetDriveTypeW`` of the drive letter *drive*; 0 off Windows.

    ``ctypes.WinDLL`` exists only on Windows, so the ignores below cover mypy
    on POSIX hosts and the ``unused-ignore`` code covers mypy on Windows.
    """
    if os.name != "nt":
        return 0
    try:
        kernel32 = ctypes.WinDLL("kernel32")  # type: ignore[attr-defined, unused-ignore]
        return int(kernel32.GetDriveTypeW(drive + "\\"))
    except (AttributeError, OSError):
        return 0


def _mapped_share(drive: str) -> str | None:
    """Return the share the drive letter *drive* is connected to, or ``None``.

    ``None`` too when the mapping is remembered but not connected now.
    """
    try:
        mpr = ctypes.WinDLL("mpr")  # type: ignore[attr-defined, unused-ignore]
        name = ctypes.create_unicode_buffer(1024)
        size = ctypes.c_ulong(1024)
        if mpr.WNetGetConnectionW(drive, name, ctypes.byref(size)) != 0:
            return None
    except (AttributeError, OSError):
        return None
    return str(name.value) or None


def _same_on_disk(left: Path, right: Path) -> bool:
    r"""Return True when the existing folders *left* and *right* are one folder.

    They are one when their volume and file ID match. A volume that reports
    an ID of 0 (some network, WebDAV and cloud drives) cannot tell its
    folders apart, so a 0 never matches. A cloned or restored volume
    attached beside the original keeps its volume serial number and file
    IDs, so on Windows the two volumes' names (``\\?\Volume{...}``) must
    match too when both can be read.
    """
    try:
        first, second = left.stat(), right.stat()
    except OSError:
        return False
    if not (first.st_ino and first.st_dev and second.st_ino and second.st_dev):
        return False
    if not os.path.samestat(first, second):
        return False
    names = _volume_name(left), _volume_name(right)
    return None in names or names[0] == names[1]


def _volume_name(path: Path) -> str | None:
    r"""Return the name (``\\?\Volume{GUID}\``) of the volume *path* is on.

    ``None`` off Windows, and when Windows gives none (a network share). The
    name differs between two volumes even when one is a clone of the other.
    """
    if os.name != "nt":
        return None
    try:
        kernel32 = ctypes.WinDLL("kernel32")  # type: ignore[attr-defined, unused-ignore]
        mount = ctypes.create_unicode_buffer(1024)
        if not kernel32.GetVolumePathNameW(ctypes.c_wchar_p(str(path)), mount, 1024):
            return None
        name = ctypes.create_unicode_buffer(1024)
        if not kernel32.GetVolumeNameForVolumeMountPointW(mount, name, 1024):
            return None
    except (AttributeError, OSError):
        return None
    return str(name.value)


def active_install_ids(records: list[LedgerRecord]) -> set[str]:
    """Return the install-ids still active in one root's *records* (replayed).

    *records* are one harness+root's records in ledger order, as
    :func:`read_records` returns them grouped by ``root``.
    """
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
    keeps every record from its last finished uninstall on (its last record
    when none finished), so the next uninstall there still finds that
    finished one behind the unfinished ones that follow it.
    """
    by_root: dict[str, list[int]] = {}
    for index, record in enumerate(records):
        by_root.setdefault(record.root, []).append(index)
    kept: dict[int, LedgerRecord] = {}
    for indices in by_root.values():
        active = active_install_ids([records[index] for index in indices])
        active_positions = [
            index
            for index in indices
            if records[index].kind == "install" and records[index].install_id in active
        ]
        if active_positions:
            start = active_positions[-keep_installs:][0]
        else:
            finished = [
                index for index in indices if records[index].kind == "uninstall"
            ]
            start = finished[-1] if finished else indices[-1]
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
    "active_install_ids",
    "active_install_records",
    "append_record",
    "compact_records",
    "current_install_record",
    "find_record",
    "generate_ulid",
    "install_spelling",
    "last_uninstall_finished",
    "latest_record",
    "ledger_path",
    "move_install",
    "read_records",
    "recorded_root",
    "unfinished_uninstall",
]
