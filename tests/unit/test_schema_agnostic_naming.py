# SPDX-License-Identifier: MIT

"""The memory, contexts, and learning schemas carry zero harness-name references.

The data-surface schemas are harness-agnostic by contract.
A grep over the three schema files asserts that no registered harness
identifier — neither a public id, a package key, nor a brand segment of either
— appears anywhere in the schema text. Tokens are derived from the live harness
registry, so the guarantee extends automatically to every registered harness.
"""

from __future__ import annotations

import re

from apothem.lib.harness_registry import (
    SUPPORTED_HARNESS_IDS,
    SUPPORTED_PACKAGE_KEYS,
)
from apothem.schemas import (
    context_fragment_schema_path,
    learning_signal_schema_path,
    memory_record_schema_path,
)

_SCHEMA_PATHS = (
    memory_record_schema_path,
    context_fragment_schema_path,
    learning_signal_schema_path,
)


def _harness_tokens() -> set[str]:
    """Return harness identifiers and their brand segments from the registry."""
    tokens: set[str] = set()
    for identifier in (*SUPPORTED_HARNESS_IDS, *SUPPORTED_PACKAGE_KEYS):
        tokens.add(identifier)
        tokens.update(segment for segment in re.split(r"[-_]", identifier) if segment)
    return tokens


def test_registry_tokens_are_non_empty() -> None:
    # A guard so the grep below is never vacuously satisfied.
    tokens = _harness_tokens()
    assert "claude" in tokens
    assert len(tokens) >= 15


def test_data_surface_schemas_carry_no_harness_name() -> None:
    tokens = _harness_tokens()
    offenders: list[str] = []
    for path_fn in _SCHEMA_PATHS:
        path = path_fn()
        text = path.read_text(encoding="utf-8")
        for token in tokens:
            if re.search(rf"\b{re.escape(token)}\b", text, re.IGNORECASE):
                offenders.append(f"{path.name}: {token}")
    assert offenders == [], f"harness-name references in schemas: {offenders}"
