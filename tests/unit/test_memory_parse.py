# SPDX-License-Identifier: MIT

"""Unit tests for memory payload parsing + store-initialization edges.

The main memory suite exercises the add / record round-trip; these target the
``_parse`` validation error paths (a non-array payload, a non-object record) and
``ensure_initialized`` creating the records file when it is absent.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from apothem.lib import memory as mem
from apothem.lib.data_home import resolve_shared_data_home


def _store(tmp_path: Path) -> mem.MemoryStore:
    return mem.MemoryStore(resolve_shared_data_home(base=tmp_path).ensure())


def test_parse_rejects_non_array_payload() -> None:
    with pytest.raises(mem.MemoryStoreError, match="must be a JSON array"):
        mem._parse(b'{"not": "a list"}')


def test_parse_rejects_non_object_record() -> None:
    with pytest.raises(mem.MemoryStoreError, match="must be a JSON object"):
        mem._parse(b"[1, 2, 3]")


def test_ensure_initialized_creates_absent_records_file(tmp_path: Path) -> None:
    store = _store(tmp_path)
    path = store.ensure_initialized()  # file absent -> writes an empty array
    assert path.is_file()
    assert json.loads(path.read_text(encoding="utf-8")) == []
