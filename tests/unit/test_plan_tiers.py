# SPDX-License-Identifier: MIT

"""Unit tests for the three-tier scalability classifier (`apothem.lib.plan_tiers`).

Covers tier classification on both the phase and spec dimensions, the
governing-tier rule, boundary behavior at 50 / 500 phases and 100 / 1000 specs,
borderline detection within ±10%, the per-tier infrastructure sets, and the
tier-transition delta enumeration.
"""

from __future__ import annotations

import pytest

from apothem.lib.plan_tiers import (
    Tier,
    classify_tier,
    is_borderline,
    tier_infrastructure,
    tier_transition_infrastructure,
)


class TestClassifyTier:
    """Tier classification from phase and spec counts."""

    @pytest.mark.parametrize(
        ("phases", "specs", "expected"),
        [
            (0, 0, Tier.SMALL),
            (49, 99, Tier.SMALL),
            (50, 99, Tier.MEDIUM),  # phase dimension crosses to medium
            (49, 100, Tier.MEDIUM),  # spec dimension crosses to medium
            (200, 500, Tier.MEDIUM),
            (499, 999, Tier.MEDIUM),
            (500, 999, Tier.LARGE),  # phase dimension crosses to large
            (499, 1000, Tier.LARGE),  # spec dimension crosses to large
            (1200, 5000, Tier.LARGE),
        ],
    )
    def test_classifies_each_dimension(
        self, phases: int, specs: int, expected: Tier
    ) -> None:
        # Arrange / Act
        result = classify_tier(phases, specs)

        # Assert
        assert result is expected

    def test_governing_tier_is_the_higher_dimension(self) -> None:
        # Arrange: 40 phases (small) but 1200 specs (large)

        # Act
        result = classify_tier(40, 1200)

        # Assert: the more demanding spec dimension governs
        assert result is Tier.LARGE

    @pytest.mark.parametrize("count", [-1, -50])
    def test_negative_phase_count_raises(self, count: int) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            classify_tier(count, 0)

    @pytest.mark.parametrize("count", [-1, -50])
    def test_negative_spec_count_raises(self, count: int) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            classify_tier(0, count)


class TestIsBorderline:
    """Borderline detection within ±10% of any boundary."""

    @pytest.mark.parametrize(
        ("phases", "specs"),
        [
            (45, 0),  # phase small/medium boundary lower edge (50 - 10%)
            (55, 0),  # phase small/medium boundary upper edge (50 + 10%)
            (450, 0),  # phase medium/large boundary lower edge
            (550, 0),  # phase medium/large boundary upper edge
            (0, 90),  # spec small/medium boundary lower edge
            (0, 1100),  # spec medium/large boundary upper edge
        ],
    )
    def test_borderline_counts_detected(self, phases: int, specs: int) -> None:
        assert is_borderline(phases, specs) is True

    @pytest.mark.parametrize(
        ("phases", "specs"),
        [
            (10, 10),  # comfortably small
            (200, 400),  # comfortably medium
            (800, 2000),  # comfortably large
            (44, 0),  # just outside the 50 ±10% band
        ],
    )
    def test_non_borderline_counts_not_flagged(self, phases: int, specs: int) -> None:
        assert is_borderline(phases, specs) is False


class TestTierInfrastructure:
    """Per-tier drift-prevention infrastructure and transition deltas."""

    def test_each_tier_is_a_superset_of_the_one_below(self) -> None:
        small = tier_infrastructure(Tier.SMALL)
        medium = tier_infrastructure(Tier.MEDIUM)
        large = tier_infrastructure(Tier.LARGE)

        assert small < medium < large

    def test_small_to_medium_transition_materializes_index_and_stable_ids(
        self,
    ) -> None:
        delta = tier_transition_infrastructure(Tier.SMALL, Tier.MEDIUM)

        assert delta == {
            "master-index",
            "stable-ids",
            "trace-matrix-file",
            "phase-rollup-report",
        }

    def test_medium_to_large_transition_materializes_federation(self) -> None:
        delta = tier_transition_infrastructure(Tier.MEDIUM, Tier.LARGE)

        assert delta == {"sub-suite-federation", "suite-rollup-report"}

    def test_non_advancing_transition_has_empty_delta(self) -> None:
        assert tier_transition_infrastructure(Tier.LARGE, Tier.MEDIUM) == frozenset()
        assert tier_transition_infrastructure(Tier.MEDIUM, Tier.MEDIUM) == frozenset()
