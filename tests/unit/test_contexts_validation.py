# SPDX-License-Identifier: MIT

"""Unit tests for context-fragment validation + store edge branches.

The main contexts suite exercises the add / enable / read round-trip; these
target the reconstruction and store-read error paths directly: ContextFragment
.from_dict on a missing field and a wrong-typed field, ContextStore._read_raw
on a non-array fragments file, and ensure_initialized creating the file when it
is absent.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from apothem.lib import contexts as ctx
from apothem.lib.data_home import resolve_shared_data_home


def _store(tmp_path: Path) -> ctx.ContextStore:
    return ctx.ContextStore(resolve_shared_data_home(base=tmp_path).ensure())


def test_from_dict_rejects_missing_field() -> None:
    with pytest.raises(ctx.ContextError, match="missing required field"):
        ctx.ContextFragment.from_dict({"id": "x", "name": "n", "body": "b"})


def test_from_dict_rejects_wrong_typed_field() -> None:
    with pytest.raises(ctx.ContextError, match="wrong type"):
        # enabled must be a bool, not the string "yes"
        ctx.ContextFragment.from_dict(
            {"id": "x", "name": "n", "body": "b", "enabled": "yes"}
        )


def test_read_raw_rejects_non_array_file(tmp_path: Path) -> None:
    store = _store(tmp_path)
    path = store.ensure_initialized()
    path.write_text('{"not": "an array"}', encoding="utf-8")  # a JSON object
    with pytest.raises(ctx.ContextError, match="does not hold a JSON array"):
        store.fragments()


def test_ensure_initialized_creates_absent_file(tmp_path: Path) -> None:
    store = _store(tmp_path)
    path = store.ensure_initialized()  # file absent -> writes an empty array
    assert path.is_file()
    assert json.loads(path.read_text(encoding="utf-8")) == []
