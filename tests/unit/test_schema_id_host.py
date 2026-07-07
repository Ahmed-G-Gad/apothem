# SPDX-License-Identifier: MIT

"""Every packaged JSON schema resolves under the canonical ``$id`` host."""

from __future__ import annotations

import json
from pathlib import Path

import apothem.schemas as schemas_pkg

_CANONICAL_ID_PREFIX = "https://apothem.ahmedgad.com/schemas/"
_SCHEMAS_DIR = Path(schemas_pkg.__file__).resolve().parent


def test_every_schema_id_uses_canonical_host() -> None:
    schema_files = sorted(_SCHEMAS_DIR.glob("*.schema.json"))
    assert schema_files, "expected packaged *.schema.json files to exist"

    for schema_file in schema_files:
        schema = json.loads(schema_file.read_text(encoding="utf-8"))
        schema_id = schema.get("$id")
        assert schema_id is not None, f"{schema_file.name} is missing $id"
        assert schema_id.startswith(_CANONICAL_ID_PREFIX), (
            f"{schema_file.name} $id {schema_id!r} does not use the canonical "
            f"host {_CANONICAL_ID_PREFIX!r}"
        )
        assert schema_id == f"{_CANONICAL_ID_PREFIX}{schema_file.name}", (
            f"{schema_file.name} $id {schema_id!r} should preserve the filename segment"
        )
