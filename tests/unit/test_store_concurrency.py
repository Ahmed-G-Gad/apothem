# SPDX-License-Identifier: MIT

"""Concurrency + failure-injection tests for the durable stores.

Each store's read-modify-write window is advisory-lock-guarded and writes
atomically via ``lib.atomic_io``, so concurrent writers never lose an update or
tear a file, and a mid-write failure leaves the prior content intact.
"""

from __future__ import annotations

import threading
from pathlib import Path

import pytest

import apothem.lib.contexts as contexts_mod
import apothem.lib.memory as memory_mod
from apothem.lib.contexts import ContextFragment, ContextStore
from apothem.lib.data_home import resolve_shared_data_home
from apothem.lib.learning import LearningSignal, LearningStore
from apothem.lib.memory import MemoryRecord, MemoryStore

_CREATED = "2026-01-01T00:00:00Z"


def _run(target, count: int = 20) -> None:
    threads = [threading.Thread(target=target, args=(i,)) for i in range(count)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()


def test_memory_concurrent_add_loses_no_record(tmp_path: Path) -> None:
    store = MemoryStore(resolve_shared_data_home(base=tmp_path).ensure())

    def add_one(i: int) -> None:
        store.add(
            MemoryRecord(id=f"r{i}", title="t", body="b", kind="fact", created=_CREATED)
        )

    _run(add_one)
    assert store.count() == 20
    assert {r.id for r in store.records()} == {f"r{i}" for i in range(20)}


def test_memory_write_failure_leaves_prior_records_intact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = MemoryStore(resolve_shared_data_home(base=tmp_path).ensure())
    store.add(
        MemoryRecord(id="keep", title="t", body="b", kind="fact", created=_CREATED)
    )

    def _boom(_path: object, _data: object) -> None:
        raise OSError("injected store write failure")

    monkeypatch.setattr(memory_mod, "write_bytes_atomically", _boom)
    with pytest.raises(OSError, match="injected store write failure"):
        store.add(
            MemoryRecord(id="new", title="t", body="b", kind="fact", created=_CREATED)
        )

    monkeypatch.undo()
    assert [r.id for r in store.records()] == ["keep"]


def test_contexts_concurrent_add_loses_no_fragment(tmp_path: Path) -> None:
    store = ContextStore(resolve_shared_data_home(base=tmp_path).ensure())

    def add_one(i: int) -> None:
        store.add(ContextFragment(id=f"f{i}", name="n", body="b", enabled=True))

    _run(add_one)
    assert len(store.fragments()) == 20
    assert {f.id for f in store.fragments()} == {f"f{i}" for i in range(20)}


def test_contexts_write_failure_leaves_prior_fragments_intact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = ContextStore(resolve_shared_data_home(base=tmp_path).ensure())
    store.add(ContextFragment(id="keep", name="n", body="b", enabled=True))

    def _boom(_path: object, _data: object) -> None:
        raise OSError("injected store write failure")

    monkeypatch.setattr(contexts_mod, "write_bytes_atomically", _boom)
    with pytest.raises(OSError, match="injected store write failure"):
        store.add(ContextFragment(id="new", name="n", body="b", enabled=True))

    monkeypatch.undo()
    assert [f.id for f in store.fragments()] == ["keep"]


def test_learning_concurrent_append_produces_no_torn_line(tmp_path: Path) -> None:
    store = LearningStore(resolve_shared_data_home(base=tmp_path).ensure())

    def append_one(i: int) -> None:
        store._append(
            LearningSignal(
                id=f"s{i}", kind="observation", summary="x", captured=_CREATED
            )
        )

    _run(append_one)
    # Every JSONL line parses (no torn record) and all 20 signals are present.
    signals = store.signals()
    assert len(signals) == 20
    assert {s.id for s in signals} == {f"s{i}" for i in range(20)}
