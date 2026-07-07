# SPDX-License-Identifier: MIT

"""Unit tests for the append-only per-install state ledger.

Covers ULID ordering/uniqueness, record round-trip through the durable append,
the torn-line policy (only a torn FINAL line is tolerated; a malformed line
anywhere else raises ``LedgerError``), and the latest/by-install-id lookups
uninstall and rollback depend on.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from apothem.lib import install_ledger
from apothem.lib.install_ledger import (
    LedgerError,
    LedgerRecord,
    LedgerTarget,
    append_record,
    find_record,
    generate_ulid,
    latest_record,
    ledger_path,
    read_records,
)


def _target(
    path: str, *, mode: str = "write_text", backup: str | None = None
) -> LedgerTarget:
    return LedgerTarget(
        path=path,
        mode=mode,
        ownership_class="operator-owned",
        backup_ref=backup,
    )


def test_generate_ulid_is_26_crockford_chars() -> None:
    ulid = generate_ulid()
    assert len(ulid) == 26
    assert set(ulid) <= set(install_ledger._CROCKFORD)


def test_ulids_are_unique_in_a_tight_loop() -> None:
    # 80 bits of randomness per ULID — same-millisecond minting stays unique.
    ulids = [generate_ulid() for _ in range(500)]
    assert len(set(ulids)) == len(ulids)


def test_ulids_sort_by_timestamp_across_milliseconds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Stub the clock to ascending millisecond ticks; the timestamp prefix must
    # then make the ULIDs sort lexically in creation order.
    ticks = iter(range(1_000, 1_050))
    monkeypatch.setattr(install_ledger.time, "time_ns", lambda: next(ticks) * 1_000_000)
    ulids = [generate_ulid() for _ in range(50)]
    assert ulids == sorted(ulids)
    assert len(set(ulids)) == len(ulids)


def test_target_round_trips_through_dict() -> None:
    target = _target("/root/AGENTS.md", mode="sentinel_merge", backup="/bk/AGENTS.md")
    assert LedgerTarget.from_dict(target.to_dict()) == target


def test_target_omits_absent_backup_ref() -> None:
    assert "backup_ref" not in _target("/root/x").to_dict()


def test_record_create_validates_kind() -> None:
    with pytest.raises(ValueError, match="unknown ledger record kind"):
        LedgerRecord.create(harness="claude-code", root="/r", kind="bogus")  # type: ignore[arg-type]


def test_append_then_read_round_trips_record(tmp_path: Path) -> None:
    record = LedgerRecord.create(
        harness="claude-code",
        root=tmp_path / "proj",
        kind="install",
        targets=(
            _target("/root/AGENTS.md"),
            _target("/root/settings.json", mode="sentinel_merge"),
        ),
    )
    append_record(record, state_root=tmp_path / "state")

    read = read_records("claude-code", state_root=tmp_path / "state")
    assert len(read) == 1
    assert read[0] == record  # full structural equality, including the ULID
    assert read[0].install_id == record.install_id
    assert [t.path for t in read[0].targets] == [
        "/root/AGENTS.md",
        "/root/settings.json",
    ]


def test_ledger_path_is_per_harness(tmp_path: Path) -> None:
    path = ledger_path("gemini-cli", state_root=tmp_path)
    assert path == tmp_path / "gemini-cli" / "ledger.jsonl"


def test_two_installs_produce_two_records(tmp_path: Path) -> None:
    state = tmp_path / "state"
    first = LedgerRecord.create(
        harness="codex", root="/r", kind="install", targets=(_target("/a"),)
    )
    second = LedgerRecord.create(
        harness="codex", root="/r", kind="install", targets=(_target("/b"),)
    )
    append_record(first, state_root=state)
    append_record(second, state_root=state)

    read = read_records("codex", state_root=state)
    assert len(read) == 2
    assert [r.install_id for r in read] == [first.install_id, second.install_id]


def test_latest_record_filters_by_root_and_kind(tmp_path: Path) -> None:
    state = tmp_path / "state"
    install_a = LedgerRecord.create(harness="cursor", root="/proj-a", kind="install")
    install_b = LedgerRecord.create(harness="cursor", root="/proj-b", kind="install")
    uninstall_a = LedgerRecord.create(
        harness="cursor",
        root="/proj-a",
        kind="uninstall",
        install_id=install_a.install_id,
    )
    for rec in (install_a, install_b, uninstall_a):
        append_record(rec, state_root=state)

    # Default kind=install, scoped to /proj-a, skips the later uninstall marker.
    latest_a = latest_record("cursor", root="/proj-a", state_root=state)
    assert latest_a is not None
    assert latest_a.install_id == install_a.install_id
    assert latest_a.kind == "install"

    # kind=None returns the most recent record of any kind for the root.
    any_a = latest_record("cursor", root="/proj-a", kind=None, state_root=state)
    assert any_a is not None
    assert any_a.kind == "uninstall"

    # A different root is unaffected.
    latest_b = latest_record("cursor", root="/proj-b", state_root=state)
    assert latest_b is not None
    assert latest_b.install_id == install_b.install_id


def test_find_record_by_install_id(tmp_path: Path) -> None:
    state = tmp_path / "state"
    record = LedgerRecord.create(
        harness="qwen", root="/r", kind="install", targets=(_target("/x"),)
    )
    append_record(record, state_root=state)

    found = find_record("qwen", record.install_id, state_root=state)
    assert found is not None
    assert found == record
    assert find_record("qwen", "NONEXISTENTULID0000000000", state_root=state) is None


def test_truncated_trailing_line_keeps_prior_records(tmp_path: Path) -> None:
    state = tmp_path / "state"
    good_one = LedgerRecord.create(
        harness="claude-code", root="/r", kind="install", targets=(_target("/a"),)
    )
    good_two = LedgerRecord.create(
        harness="claude-code", root="/r", kind="install", targets=(_target("/b"),)
    )
    append_record(good_one, state_root=state)
    append_record(good_two, state_root=state)

    # Simulate a crash mid-append: a partial, unterminated JSON fragment.
    path = ledger_path("claude-code", state_root=state)
    with path.open("a", encoding="utf-8") as handle:
        handle.write('{"install_id":"01PARTIAL","harness":"claude-co')

    read = read_records("claude-code", state_root=state)
    assert [r.install_id for r in read] == [good_one.install_id, good_two.install_id]


def test_garbage_interior_line_raises(tmp_path: Path) -> None:
    # A non-JSON line before the final line cannot be a crash-mid-append tear —
    # the source of truth for uninstall is corrupted, so the reader raises
    # instead of masking it.
    state = tmp_path / "state"
    record = LedgerRecord.create(harness="codex", root="/r", kind="install")
    append_record(record, state_root=state)
    path = ledger_path("codex", state_root=state)
    with path.open("a", encoding="utf-8") as handle:
        handle.write("not json at all\n")
    append_record(
        LedgerRecord.create(
            harness="codex", root="/r", kind="uninstall", install_id=record.install_id
        ),
        state_root=state,
    )
    with pytest.raises(LedgerError, match="line 2 is not valid JSON"):
        read_records("codex", state_root=state)


def test_blank_interior_lines_are_skipped(tmp_path: Path) -> None:
    # A blank line carries no record and is unambiguous — the reader skips it
    # without treating it as corruption.
    state = tmp_path / "state"
    record = LedgerRecord.create(harness="codex", root="/r", kind="install")
    append_record(record, state_root=state)
    path = ledger_path("codex", state_root=state)
    with path.open("a", encoding="utf-8") as handle:
        handle.write("\n   \n")
    append_record(
        LedgerRecord.create(
            harness="codex", root="/r", kind="uninstall", install_id=record.install_id
        ),
        state_root=state,
    )
    read = read_records("codex", state_root=state)
    assert [r.kind for r in read] == ["install", "uninstall"]


def test_absent_ledger_reads_empty(tmp_path: Path) -> None:
    assert read_records("never-installed", state_root=tmp_path) == []
    assert latest_record("never-installed", state_root=tmp_path) is None


def test_json_line_is_single_line_and_deterministic() -> None:
    record = LedgerRecord(
        install_id="01TEST",
        timestamp="2026-06-13T00:00:00.000000Z",
        harness="claude-code",
        root="/r",
        kind="install",
        targets=(_target("/a"),),
    )
    line = record.to_json_line()
    assert "\n" not in line
    # Deterministic: re-encoding the parsed form yields identical bytes.
    assert json.loads(line)["install_id"] == "01TEST"
    assert LedgerRecord.from_dict(json.loads(line)) == record


def test_read_records_raises_on_valid_json_that_is_not_an_object(
    tmp_path: Path,
) -> None:
    # A complete line that parses as JSON but is not a mapping cannot be a
    # torn append (a strict prefix of a one-line JSON object never parses) —
    # it is corruption of the uninstall source of truth and raises.
    state = tmp_path / "state"
    record = LedgerRecord.create(harness="codex", root="/r", kind="install")
    append_record(record, state_root=state)
    path = ledger_path("codex", state_root=state)
    with path.open("a", encoding="utf-8") as handle:
        handle.write("[1, 2, 3]\n")
    append_record(
        LedgerRecord.create(harness="codex", root="/r", kind="install"),
        state_root=state,
    )

    with pytest.raises(LedgerError, match="line 2 is not a record object"):
        read_records("codex", state_root=state)


def test_read_records_raises_on_object_missing_record_fields(tmp_path: Path) -> None:
    # A mid-file JSON object lacking a required record field fails
    # LedgerRecord.from_dict; masking it could strand or over-remove operator
    # files on uninstall, so the reader raises.
    state = tmp_path / "state"
    record = LedgerRecord.create(harness="codex", root="/r", kind="install")
    append_record(record, state_root=state)
    path = ledger_path("codex", state_root=state)
    with path.open("a", encoding="utf-8") as handle:
        handle.write('{"unrelated": "object", "no": "record fields"}\n')
    append_record(
        LedgerRecord.create(harness="codex", root="/r", kind="install"),
        state_root=state,
    )

    with pytest.raises(LedgerError, match="line 2 is not a well-formed record"):
        read_records("codex", state_root=state)


def test_complete_but_invalid_final_line_raises(tmp_path: Path) -> None:
    # Only an UNPARSEABLE final line is a tear artifact; a final line that
    # parses cleanly but is not a valid record is corruption and raises even
    # in last position.
    state = tmp_path / "state"
    record = LedgerRecord.create(harness="codex", root="/r", kind="install")
    append_record(record, state_root=state)
    path = ledger_path("codex", state_root=state)
    with path.open("a", encoding="utf-8") as handle:
        handle.write('{"unrelated": "object"}\n')

    with pytest.raises(LedgerError, match="line 2 is not a well-formed record"):
        read_records("codex", state_root=state)


def test_find_record_root_guard_rejects_a_different_root(tmp_path: Path) -> None:
    # An install-id is unique per pass, but the root guard rejects a record
    # resolved from a different install root outright.
    state = tmp_path / "state"
    record = LedgerRecord.create(harness="cursor", root="/proj-a", kind="install")
    append_record(record, state_root=state)

    assert (
        find_record("cursor", record.install_id, root="/proj-a", state_root=state)
        == record
    )
    assert (
        find_record("cursor", record.install_id, root="/proj-b", state_root=state)
        is None
    )


def test_find_record_kind_guard_rejects_a_different_kind(tmp_path: Path) -> None:
    # find_record defaults to the originating install kind; an explicit
    # non-matching kind rejects the record even when the install-id matches,
    # while kind=None matches any kind.
    state = tmp_path / "state"
    record = LedgerRecord.create(harness="qwen", root="/r", kind="install")
    append_record(record, state_root=state)

    assert (
        find_record("qwen", record.install_id, kind="install", state_root=state)
        == record
    )
    assert (
        find_record("qwen", record.install_id, kind="rollback", state_root=state)
        is None
    )
    assert find_record("qwen", record.install_id, kind=None, state_root=state) == record
