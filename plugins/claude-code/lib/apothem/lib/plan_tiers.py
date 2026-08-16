# SPDX-License-Identifier: MIT

"""Three-tier scalability classification for the ``/plan-<stage>`` pipeline.

Implements the small / medium / large tier framework that governs a plan
suite's validation cadence, indexing, and decomposition as it scales from a
few dozen phases to thousands of tasks. The classifier is the executable basis
the planning-pipeline commands consult at every stage; the prose framework it
mirrors lives at ``rules/canonical-layout-reporting-tiers.md`` §7.

The module is intentionally pure — classification and required-infrastructure
enumeration take counts and return values, with no filesystem side effects — so
the tier-transition behavior is deterministic and directly testable (the
500-phase medium→large smoke test exercises these functions).
"""

from __future__ import annotations

from enum import Enum


class Tier(str, Enum):
    """A plan suite's scalability tier.

    The string values are the canonical tier names used in suite metadata and
    in the ``/plan`` command's tier-classification reporting.
    """

    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"


# Boundary thresholds per ``rules/canonical-layout-reporting-tiers.md`` §7.1.
# A suite is medium at or above the lower boundary and large at or above the
# upper boundary, evaluated independently on the phase-count and spec-count
# dimensions; the more demanding dimension governs the suite's tier.
SMALL_MEDIUM_PHASE_BOUNDARY = 50
MEDIUM_LARGE_PHASE_BOUNDARY = 500
SMALL_MEDIUM_SPEC_BOUNDARY = 100
MEDIUM_LARGE_SPEC_BOUNDARY = 1000

# A count within this fraction of a boundary is borderline and routes the
# tier classification through structured inquiry rather than a silent pick.
BORDERLINE_FRACTION = 0.10

# Ordinal rank for tier comparison — the governing tier is the higher rank.
_TIER_RANK: dict[Tier, int] = {Tier.SMALL: 0, Tier.MEDIUM: 1, Tier.LARGE: 2}


def _dimension_tier(count: int, lower: int, upper: int) -> Tier:
    """Classify a single dimension (phases or specs) against its boundaries.

    Args:
        count: The dimension's count (must be non-negative).
        lower: The small→medium boundary for this dimension.
        upper: The medium→large boundary for this dimension.

    Returns:
        ``Tier.SMALL`` below ``lower``, ``Tier.MEDIUM`` in ``[lower, upper)``,
        ``Tier.LARGE`` at or above ``upper``.

    Raises:
        ValueError: If ``count`` is negative.
    """
    if count < 0:
        raise ValueError(f"count must be non-negative, got {count}")
    if count >= upper:
        return Tier.LARGE
    if count >= lower:
        return Tier.MEDIUM
    return Tier.SMALL


def classify_tier(phase_count: int, spec_count: int) -> Tier:
    """Classify a plan suite's scalability tier from its phase and spec counts.

    The governing tier is the higher of the phase-dimension tier and the
    spec-dimension tier: a suite with 40 phases but 1200 spec requirements is
    ``large`` because its spec dimension demands large-tier infrastructure even
    though its phase dimension alone would read ``small``.

    Args:
        phase_count: The number of phases in the suite (non-negative).
        spec_count: The number of spec requirements in the suite (non-negative).

    Returns:
        The governing :class:`Tier`.

    Raises:
        ValueError: If either count is negative.
    """
    phase_tier = _dimension_tier(
        phase_count, SMALL_MEDIUM_PHASE_BOUNDARY, MEDIUM_LARGE_PHASE_BOUNDARY
    )
    spec_tier = _dimension_tier(
        spec_count, SMALL_MEDIUM_SPEC_BOUNDARY, MEDIUM_LARGE_SPEC_BOUNDARY
    )
    return phase_tier if _TIER_RANK[phase_tier] >= _TIER_RANK[spec_tier] else spec_tier


def _within_borderline(count: int, boundary: int) -> bool:
    """Return ``True`` when ``count`` is within ``BORDERLINE_FRACTION`` of ``boundary``."""
    margin = boundary * BORDERLINE_FRACTION
    return boundary - margin <= count <= boundary + margin


def is_borderline(phase_count: int, spec_count: int) -> bool:
    """Report whether a suite sits within ±10% of any tier boundary.

    A borderline suite's tier is underdetermined by the counts alone; the
    ``/plan`` command routes such a suite through a tier-classification
    structured inquiry rather than silently picking a tier.

    Args:
        phase_count: The number of phases in the suite (non-negative).
        spec_count: The number of spec requirements in the suite (non-negative).

    Returns:
        ``True`` when either count is within ±10% of either of its dimension's
        two boundaries.
    """
    return any(
        (
            _within_borderline(phase_count, SMALL_MEDIUM_PHASE_BOUNDARY),
            _within_borderline(phase_count, MEDIUM_LARGE_PHASE_BOUNDARY),
            _within_borderline(spec_count, SMALL_MEDIUM_SPEC_BOUNDARY),
            _within_borderline(spec_count, MEDIUM_LARGE_SPEC_BOUNDARY),
        )
    )


# Drift-prevention infrastructure each tier requires, per §7.2. Each higher
# tier is a strict superset of the tier below it, so a transition's delta is the
# set difference between the new and old tiers' infrastructure.
_TIER_INFRASTRUCTURE: dict[Tier, frozenset[str]] = {
    Tier.SMALL: frozenset(
        {
            "trace-matrix-narrative",  # narrative trace table in PLAN-NOTES.md
            "per-phase-report",  # REPORT.md per phase
        }
    ),
    Tier.MEDIUM: frozenset(
        {
            "trace-matrix-narrative",
            "per-phase-report",
            "master-index",  # MASTER-INDEX.md suite-root index
            "stable-ids",  # R-NNNN requirement / P-NN phase IDs
            "trace-matrix-file",  # materialized TRACE-MATRIX.md
            "phase-rollup-report",  # rollup per 5-20 phase group
        }
    ),
    Tier.LARGE: frozenset(
        {
            "trace-matrix-narrative",
            "per-phase-report",
            "master-index",
            "stable-ids",
            "trace-matrix-file",
            "phase-rollup-report",
            "sub-suite-federation",  # parent + child suite decomposition
            "suite-rollup-report",  # federation aggregates child rollups
        }
    ),
}


def tier_infrastructure(tier: Tier) -> frozenset[str]:
    """Return the drift-prevention infrastructure a tier requires.

    Args:
        tier: The suite's tier.

    Returns:
        The frozen set of infrastructure-mechanism identifiers governing the
        tier per ``rules/canonical-layout-reporting-tiers.md`` §7.2.
    """
    return _TIER_INFRASTRUCTURE[tier]


def tier_transition_infrastructure(old: Tier, new: Tier) -> frozenset[str]:
    """Enumerate the infrastructure a tier transition must materialize.

    When a suite crosses a tier boundary (e.g. its 500th phase pushes it from
    ``medium`` to ``large``), the ``/plan`` command materializes the new tier's
    additional infrastructure in the same change-set so a 501-phase suite never
    exists without its large-tier surfaces. The delta is the infrastructure
    present in ``new`` but absent from ``old``.

    Args:
        old: The suite's tier before the transition.
        new: The suite's tier after the transition.

    Returns:
        The set of infrastructure-mechanism identifiers the transition must
        newly materialize. Empty when ``new`` does not exceed ``old``.
    """
    if _TIER_RANK[new] <= _TIER_RANK[old]:
        return frozenset()
    return _TIER_INFRASTRUCTURE[new] - _TIER_INFRASTRUCTURE[old]
