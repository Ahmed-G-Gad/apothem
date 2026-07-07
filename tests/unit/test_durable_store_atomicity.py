# SPDX-License-Identifier: MIT

"""Durable stores persist through the shared atomic-write utility.

Regression wall complementing ``test_store_concurrency.py`` (which proves
concurrent writers lose no record and a mid-write failure leaves prior content
intact). This suite pins the *mechanism*: each durable store MUST route its
persist through ``lib.atomic_io`` — ``write_bytes_atomically`` for the whole-file
stores (memory, contexts) and ``append_line_durably`` for the learning signal
log. A revert to a naive non-atomic write (a direct ``Path.write_bytes`` /
truncate-then-write) fails closed here because the store would no longer invoke
the atomic utility, and the no-torn / no-lost guarantees those utilities provide
would silently lapse.

Each test spies on the store module's reference to the atomic utility, drives one
persist, and asserts the utility was invoked and the persisted record round-trips
— so the spy fires only when the real atomic path runs.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import apothem.lib.contexts as contexts_mod
import apothem.lib.learning as learning_mod
import apothem.lib.memory as memory_mod
from apothem.lib.contexts import ContextFragment, ContextStore
from apothem.lib.data_home import resolve_shared_data_home
from apothem.lib.learning import LearningSignal, LearningStore
from apothem.lib.memory import MemoryRecord, MemoryStore

_CREATED = "2026-01-01T00:00:00Z"


def test_memory_add_routes_through_atomic_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A memory add persists via the shared atomic-write utility."""
    store = MemoryStore(resolve_shared_data_home(base=tmp_path).ensure())
    calls = {"n": 0}
    real = memory_mod.write_bytes_atomically

    def spy(path: Path, data: bytes) -> None:
        calls["n"] += 1
        real(path, data)

    monkeypatch.setattr(memory_mod, "write_bytes_atomically", spy)
    store.add(MemoryRecord(id="r0", title="t", body="b", kind="fact", created=_CREATED))
    assert calls["n"] >= 1, "memory add bypassed the shared atomic-write utility"
    assert [r.id for r in store.records()] == ["r0"]


def test_contexts_add_routes_through_atomic_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A context add persists via the shared atomic-write utility."""
    store = ContextStore(resolve_shared_data_home(base=tmp_path).ensure())
    calls = {"n": 0}
    real = contexts_mod.write_bytes_atomically

    def spy(path: Path, data: bytes) -> None:
        calls["n"] += 1
        real(path, data)

    monkeypatch.setattr(contexts_mod, "write_bytes_atomically", spy)
    store.add(ContextFragment(id="f0", name="n", body="b", enabled=True))
    assert calls["n"] >= 1, "context add bypassed the shared atomic-write utility"
    assert [f.id for f in store.fragments()] == ["f0"]


def test_learning_append_routes_through_durable_append(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A learning-signal append persists via the shared durable-append utility."""
    store = LearningStore(resolve_shared_data_home(base=tmp_path).ensure())
    calls = {"n": 0}
    real = learning_mod.append_line_durably

    def spy(path: Path, line: str) -> None:
        calls["n"] += 1
        real(path, line)

    monkeypatch.setattr(learning_mod, "append_line_durably", spy)
    store._append(
        LearningSignal(id="s0", kind="observation", summary="x", captured=_CREATED)
    )
    assert calls["n"] >= 1, "learning append bypassed the durable-append utility"
    assert [s.id for s in store.signals()] == ["s0"]
