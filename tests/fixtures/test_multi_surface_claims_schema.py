# SPDX-License-Identifier: MIT

"""Schema-level smoke tests for the multi-surface claim list.

Verifies the byte-exact fixture at ``tests/fixtures/multi-surface-claims.yaml``
satisfies the contract consumed by the ``multi-surface-coherence`` validator:
every entry carries the four required fields, identifiers are unique and
non-empty, claim strings are non-empty, and every surface referenced in
``required-in`` / ``optional-in`` belongs to the canonical surface vocabulary
locked by the multi-surface opt-in ratification.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

import yaml

REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[2]
FIXTURE_PATH: Final[Path] = (
    REPO_ROOT / "tests" / "fixtures" / "multi-surface-claims.yaml"
)

REQUIRED_FIELDS: Final[frozenset[str]] = frozenset(
    {"id", "claim", "required-in", "optional-in"}
)

# Mandatory surfaces from spec §0.6.3 — every shared claim MUST be
# present here.
MANDATORY_SURFACES: Final[frozenset[str]] = frozenset(
    {"AGENTS.md", "CLAUDE.md", ".github/copilot-instructions.md"}
)

# Optional surfaces from the locked Phase 04B ratification record
# (`.audit/multi-surface-opt-in.yml` — full opt-in set).
OPTIONAL_SURFACES: Final[frozenset[str]] = frozenset(
    {
        "site/content/docs/architecture/agents.mdx",
        ".cursorrules",
        ".windsurfrules",
    }
)

VALID_SURFACES: Final[frozenset[str]] = MANDATORY_SURFACES | OPTIONAL_SURFACES


def _load_claims() -> list[dict[str, object]]:
    """Load and return the claim list, asserting top-level shape."""
    assert FIXTURE_PATH.is_file(), f"missing fixture: {FIXTURE_PATH}"
    document = yaml.safe_load(FIXTURE_PATH.read_text(encoding="utf-8"))
    assert isinstance(document, dict), "fixture root must be a mapping"
    claims = document.get("claims")
    assert isinstance(claims, list), "fixture must define a `claims` list"
    return claims


def test_fixture_parses_as_yaml() -> None:
    """The fixture is valid YAML and yields a non-empty claim list."""
    claims = _load_claims()
    assert claims, "claim list is empty"


def test_every_claim_has_required_fields() -> None:
    """Every entry carries id / claim / required-in / optional-in."""
    claims = _load_claims()
    for index, entry in enumerate(claims):
        assert isinstance(entry, dict), f"claim[{index}] is not a mapping"
        missing = REQUIRED_FIELDS - entry.keys()
        assert not missing, f"claim[{index}] missing fields: {sorted(missing)}"


def test_claim_ids_are_unique() -> None:
    """No two claims share the same id."""
    claims = _load_claims()
    ids = [entry["id"] for entry in claims]
    duplicates = {claim_id for claim_id in ids if ids.count(claim_id) > 1}
    assert not duplicates, f"duplicate claim ids: {sorted(duplicates)}"


def test_claim_strings_are_non_empty() -> None:
    """Every claim entry's ``claim`` string is a non-empty string."""
    claims = _load_claims()
    for entry in claims:
        claim = entry["claim"]
        assert isinstance(claim, str), f"claim[{entry['id']}] is not a string"
        assert claim.strip(), f"claim[{entry['id']}] is empty"


def test_mandatory_surfaces_present_for_every_claim() -> None:
    """Every claim's ``required-in`` covers the mandatory surface set."""
    claims = _load_claims()
    for entry in claims:
        required = set(entry["required-in"])
        missing = MANDATORY_SURFACES - required
        assert not missing, (
            f"claim[{entry['id']}] missing mandatory surfaces in "
            f"required-in: {sorted(missing)}"
        )


def test_required_and_optional_surfaces_are_in_vocabulary() -> None:
    """Every surface reference belongs to the canonical vocabulary."""
    claims = _load_claims()
    for entry in claims:
        for field in ("required-in", "optional-in"):
            surfaces = entry.get(field, [])
            assert isinstance(surfaces, list), (
                f"claim[{entry['id']}].{field} is not a list"
            )
            unknown = set(surfaces) - VALID_SURFACES
            assert not unknown, (
                f"claim[{entry['id']}].{field} contains unknown surfaces: "
                f"{sorted(unknown)}"
            )


def test_required_and_optional_are_disjoint_per_claim() -> None:
    """A surface MUST NOT appear in both required-in and optional-in."""
    claims = _load_claims()
    for entry in claims:
        required = set(entry["required-in"])
        optional = set(entry["optional-in"])
        overlap = required & optional
        assert not overlap, (
            f"claim[{entry['id']}] surface listed in both required-in "
            f"and optional-in: {sorted(overlap)}"
        )


def test_minimum_claim_count() -> None:
    """The fixture covers at least the 16 enumerated shared claims."""
    claims = _load_claims()
    assert len(claims) >= 16, f"expected >= 16 claims; got {len(claims)}"
