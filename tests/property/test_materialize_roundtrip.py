# SPDX-License-Identifier: MIT

"""Property tests: profile -> materialize -> parse round-trip fidelity.

The JSON/YAML materializer adapters render the shared profile's MCP inventory
into a harness-native config document. The MCP server NAME is a value-bearing
field rendered verbatim as an object key in every covered adapter's output:

* opencode  -> `json.loads(...)["mcp"][name]`
* qwen_code -> `json.loads(...)["mcpServers"][name]`
* hermes    -> `yaml.safe_load(...)["auxiliary"]["mcp"][name]`

(open_claw is intentionally NOT covered: its materializer renders an empty `{}`
and projects no profile field, so there is no field to round-trip.)

The round-trip invariant: a safe-Unicode server name survives
profile -> materialize_native_config -> parse byte-intact. An escaping or
truncation bug in either the JSON or the YAML rendering surfaces as a Hypothesis
counterexample.

Input shaping: the profile normalizer (`_normalize_scalar`) strips and
newline-normalizes the server name before it reaches the materializer, so the
generated name excludes surrogates / control characters (categories Cs, Cc, the
JSON/YAML-unsafe set) AND is constrained to survive `.strip()` (no leading or
trailing whitespace). What remains is the genuine rendering surface: any
escaping or encoding loss in the materializer is still caught.

`derandomize=True` pins the inputs for deterministic CI runs; `deadline=None`
removes per-example timing flakiness.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import pytest
import yaml
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from apothem.harnesses.hermes.materializer import (
    materialize_native_config as hermes_materialize,
)
from apothem.harnesses.opencode.materializer import (
    materialize_native_config as opencode_materialize,
)
from apothem.harnesses.qwen_code.materializer import (
    materialize_native_config as qwen_materialize,
)

TEST_SETTINGS = settings(
    max_examples=200,
    deadline=None,
    derandomize=True,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.filter_too_much],
)

# Safe-Unicode text excluding surrogates (Cs) and control characters (Cc); the
# JSON/YAML structural delimiters that the parsers would mishandle in an
# unquoted scalar are also excluded. Constrained to be non-empty and to survive
# the normalizer's strip() so the test exercises rendering, not normalization.
safe_names = (
    st.text(
        alphabet=st.characters(
            blacklist_categories=("Cs", "Cc"),
            blacklist_characters="\x7f",
        ),
        min_size=1,
        max_size=24,
    )
    .map(lambda s: s.strip())
    .filter(lambda s: bool(s) and s == s.strip())
)


def _profile_with_server_name(name: str) -> dict[str, Any]:
    """Build a minimal schema-valid profile carrying one MCP server named *name*.

    The server uses an http transport so it satisfies the schema's
    transport-conditional `url` requirement without a command. The name is the
    field under round-trip test.
    """
    return {
        "identity": {"name": "Operator"},
        "mcp_servers": {
            name: {
                "transport": "http",
                "url": "https://example.invalid/mcp",
            },
        },
    }


def _opencode_names(rendered: str) -> dict[str, Any]:
    return dict(json.loads(rendered).get("mcp", {}))


def _qwen_names(rendered: str) -> dict[str, Any]:
    return dict(json.loads(rendered).get("mcpServers", {}))


def _hermes_names(rendered: str) -> dict[str, Any]:
    doc = yaml.safe_load(rendered) or {}
    return dict((doc.get("auxiliary") or {}).get("mcp", {}))


# (materializer, parse-to-name-map) pairs for the adapters that render the field.
ADAPTERS: list[tuple[str, Callable[[dict[str, Any]], str], Callable[[str], dict]]] = [
    ("opencode", opencode_materialize, _opencode_names),
    ("qwen_code", qwen_materialize, _qwen_names),
    ("hermes", hermes_materialize, _hermes_names),
]


@pytest.mark.parametrize(
    ("adapter_id", "materialize", "parse_names"),
    ADAPTERS,
    ids=[item[0] for item in ADAPTERS],
)
@given(name=safe_names)
@TEST_SETTINGS
def test_server_name_round_trips_byte_intact(
    adapter_id: str,
    materialize: Callable[[dict[str, Any]], str],
    parse_names: Callable[[str], dict],
    name: str,
) -> None:
    """A safe-Unicode MCP server name round-trips through materialize+parse."""
    profile = _profile_with_server_name(name)
    rendered = materialize(profile)
    names = parse_names(rendered)
    assert name in names, (
        f"{adapter_id}: server name {name!r} did not round-trip; "
        f"parsed names were {sorted(names)!r}"
    )
