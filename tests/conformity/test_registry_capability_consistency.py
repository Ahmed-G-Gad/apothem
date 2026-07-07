# SPDX-License-Identifier: MIT

"""Behaviour contract for the registry-capability-consistency validator.

The validator (``apothem.conformity.registry_capability_consistency_grep``)
asserts that every registry capability cell whose status is not exempt
(``unsupported`` / ``not-applicable`` / ``discovery-pending``) is backed by
evidence: a propagation-manifest install entry, a materializer that authors the
surface, or a documented projection. These tests give it a passing corpus (the
corrected post-CT-3 matrix, swept against the real repository) and a failing
corpus (the same matrix with exactly one over-claimed cell injected), so the
gate's verdict has a regression anchor in both directions.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Final

import pytest

from apothem.conformity import registry_capability_consistency_grep as rccg
from apothem.lib import harness_registry

_REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[2]


# --------------------------------------------------------------------------- #
# Passing corpus: the corrected matrix sweeps the real repository clean.
# --------------------------------------------------------------------------- #


def test_passing_corpus_corrected_matrix_is_clean() -> None:
    """Every non-exempt cell across all 17 harnesses is backed by evidence."""
    result = rccg.check(_REPO_ROOT)

    assert result.passed is True, [
        f"{f.harness}:{f.capability}={f.status} ({f.evidence_class})"
        for f in result.findings
    ]
    assert result.findings == []


def test_passing_corpus_sweeps_full_cohort() -> None:
    """The sweep covers all 17 harnesses and a non-trivial cell count."""
    result = rccg.check(_REPO_ROOT)

    assert result.harnesses_checked == harness_registry.SUPPORTED_HARNESS_COUNT
    assert result.cells_checked > 0


def test_result_json_round_trips() -> None:
    """The GrepResult serialises to JSON the gate can parse."""
    import json

    result = rccg.check(_REPO_ROOT)
    payload = json.loads(result.to_json())

    assert payload["grep"] == rccg.GREP_NAME
    assert payload["passed"] is True
    assert payload["harnesses_checked"] == harness_registry.SUPPORTED_HARNESS_COUNT


# --------------------------------------------------------------------------- #
# Failing corpus: one over-claimed cell injected into the registry matrix.
# --------------------------------------------------------------------------- #


def _registry_with_overclaim(
    public_id: str, capability: str, status: str
) -> tuple[harness_registry.HarnessRegistryEntry, ...]:
    """Return the registry with one cell of *public_id* flipped to *status*."""
    tampered: list[harness_registry.HarnessRegistryEntry] = []
    for entry in harness_registry.HARNESS_REGISTRY:
        if entry.public_id == public_id:
            new_matrix = dict(entry.capability_status)
            new_matrix[capability] = status  # type: ignore[assignment]
            tampered.append(dataclasses.replace(entry, capability_status=new_matrix))
        else:
            tampered.append(entry)
    return tuple(tampered)


def test_failing_corpus_mcp_native_without_materializer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Re-introducing mcp 'native' on a non-authoring harness trips the gate."""
    # claude-code recognizes an operator-owned MCP surface but authors none.
    monkeypatch.setattr(
        harness_registry,
        "HARNESS_REGISTRY",
        _registry_with_overclaim("claude-code", "mcp_servers", "native"),
    )

    result = rccg.check(_REPO_ROOT)

    assert result.passed is False
    over_claims = [
        f
        for f in result.findings
        if f.harness == "claude-code" and f.capability == "mcp_servers"
    ]
    assert len(over_claims) == 1
    finding = over_claims[0]
    assert finding.status == "native"
    assert finding.evidence_class == "materializer"


def test_failing_corpus_cohort_without_install_entry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Claiming a cohort class with no manifest install source trips the gate."""
    # cursor delivers the rules surface only; claiming a 'native' skills cohort
    # has no backing skills/ install source for cursor.
    monkeypatch.setattr(
        harness_registry,
        "HARNESS_REGISTRY",
        _registry_with_overclaim("cursor", "skills", "native"),
    )

    result = rccg.check(_REPO_ROOT)

    assert result.passed is False
    over_claims = [
        f for f in result.findings if f.harness == "cursor" and f.capability == "skills"
    ]
    assert len(over_claims) == 1
    assert over_claims[0].evidence_class == "manifest-install-entry"


# --------------------------------------------------------------------------- #
# Classifier-level unit coverage of the evidence classes.
# --------------------------------------------------------------------------- #


def test_classify_cohort_backed_by_install_source() -> None:
    """A cohort class with its source directory present is backed."""
    assert (
        rccg._classify_cell(
            harness="opencode",
            capability="skills",
            status="native",
            sources={"skills/", "commands/"},
            template_sources=set(),
            authors_mcp=True,
        )
        is None
    )


def test_classify_rules_backed_by_template_source() -> None:
    """A rules cell with no rules/ dir but a declared template is backed."""
    assert (
        rccg._classify_cell(
            harness="windsurf",
            capability="rules",
            status="native",
            sources={"harnesses/windsurf/templates/apothem-rules.md"},
            template_sources={"harnesses/windsurf/templates/apothem-rules.md"},
            authors_mcp=False,
        )
        is None
    )


def test_classify_sub_agent_dispatch_is_projection_backed() -> None:
    """sub_agent_dispatch is a documented projection, always backed when present."""
    assert (
        rccg._classify_cell(
            harness="claude-code",
            capability="sub_agent_dispatch",
            status="native",
            sources=set(),
            template_sources=set(),
            authors_mcp=False,
        )
        is None
    )


def test_materializer_detection_against_real_authoring_harnesses() -> None:
    """The three authoring harnesses are detected; a rules-only one is not."""
    assert rccg._materializer_authors_mcp(_REPO_ROOT, "opencode") is True
    assert rccg._materializer_authors_mcp(_REPO_ROOT, "qwen_code") is True
    assert rccg._materializer_authors_mcp(_REPO_ROOT, "hermes") is True
    assert rccg._materializer_authors_mcp(_REPO_ROOT, "cursor") is False
