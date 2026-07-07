# SPDX-License-Identifier: MIT

"""500-phase tier-transition smoke test for the decomposed ``/plan-<stage>`` pipeline.

Drives a simulated plan suite through the medium→large tier transition at 500
phases and asserts two invariants:

1. **Tier transition recorded** — the governing tier is ``medium`` across the
   medium range and flips to ``large`` exactly at the 500th phase, and the
   transition materializes the large-tier infrastructure delta.
2. **Zero dropped gates** — the decomposition into seven first-class
   ``commands/plan-<stage>.md`` commands preserves every stage's gate set; each
   stage command is present, independently invocable, and carries its known
   gates, so no gate was dropped when the unified dispatcher was retired.
"""

from __future__ import annotations

from pathlib import Path

from apothem.lib.plan_tiers import (
    Tier,
    classify_tier,
    tier_transition_infrastructure,
)

_COMMANDS_DIR = Path(__file__).parents[2] / "src" / "apothem" / "commands"

# Each planning stage and a known gate keyword its command body MUST still carry
# after the decomposition. A dropped gate (or a missing stage command) fails the
# zero-dropped-gates assertion below.
_EXPECTED_STAGE_GATES: dict[str, tuple[str, ...]] = {
    "spec": ("G0", "G4", "G5"),
    "generate": ("scorecard", "fifteen-bar pre-emission gate"),
    "review": ("scorecard", "Blind Review"),
    "design": (
        "Applicability gate",
        "Bidirectional Binding",
        "fifteen-bar pre-emission gate",
    ),
    "audit": ("remediation", "zero-finding"),
    "execute": ("quality gates", "end-of-phase commit gate"),
    "status": ("read-only",),
}

# A scaled run spanning the medium range up to and just past the 500-phase
# medium→large boundary, holding the spec count in the medium band so the phase
# dimension governs the transition.
_SCALED_PHASE_COUNTS = (50, 100, 250, 499, 500, 501)
_MEDIUM_SPEC_COUNT = 500


def _stage_text(stage: str) -> str:
    """Return the body of the first-class ``commands/plan-<stage>.md`` command."""
    path = _COMMANDS_DIR / f"plan-{stage}.md"
    assert path.is_file(), f"stage command file missing at {path}"
    return path.read_text(encoding="utf-8")


def test_medium_to_large_transition_recorded_at_500_phases() -> None:
    """The governing tier flips medium→large exactly at the 500th phase."""
    # Arrange: a scaled run, recording the tier at each sampled phase count.
    tiers = {
        count: classify_tier(count, _MEDIUM_SPEC_COUNT)
        for count in _SCALED_PHASE_COUNTS
    }

    # Assert: medium below the boundary, large at and above it.
    assert tiers[499] is Tier.MEDIUM
    assert tiers[500] is Tier.LARGE
    assert tiers[501] is Tier.LARGE

    # Assert: the transition materializes the large-tier infrastructure delta.
    delta = tier_transition_infrastructure(tiers[499], tiers[500])
    assert delta == {"sub-suite-federation", "suite-rollup-report"}


def test_full_scaled_run_completes_without_a_tier_gap() -> None:
    """Every sampled phase count classifies to a defined tier (run completes)."""
    # Act: drive the full scaled run.
    classified = [classify_tier(c, _MEDIUM_SPEC_COUNT) for c in range(1, 502)]

    # Assert: the run completes and the tier sequence is monotonic
    # (never regresses as the suite grows).
    ranks = [list(Tier).index(t) for t in classified]
    assert ranks == sorted(ranks)
    assert classified[-1] is Tier.LARGE


def test_zero_dropped_gates_across_the_seven_stages() -> None:
    """Each decomposed stage command preserves its gate set — no gate dropped."""
    for stage, gates in _EXPECTED_STAGE_GATES.items():
        body = _stage_text(stage)
        for gate in gates:
            assert gate in body, (
                f"stage '{stage}' dropped gate keyword '{gate}' in the decomposition"
            )


def test_all_seven_stages_present_and_dispatchable() -> None:
    """Every stage is a first-class, independently invocable command."""
    for stage in _EXPECTED_STAGE_GATES:
        body = _stage_text(stage)
        # Frontmatter declares the invocable command name and keeps invocation on.
        assert f'name: "plan-{stage}"' in body, (
            f"stage '{stage}' does not declare its command name"
        )
        assert "disable-model-invocation: true" not in body, (
            f"stage '{stage}' must remain invocable"
        )
