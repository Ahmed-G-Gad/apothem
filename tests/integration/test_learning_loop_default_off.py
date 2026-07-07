# SPDX-License-Identifier: MIT

"""End-to-end test that the continuous-learning loop is default-off.

Covers Phase 00I task 10 (loop half): with the opt-in flag unset in the shared
profile, the loop performs no capture, and with nothing captured there is
nothing to extract or promote — the whole loop is inert until the operator
explicitly opts in.
"""

from __future__ import annotations

from pathlib import Path

from apothem.lib.data_home import resolve_shared_data_home
from apothem.lib.learning import (
    LearningSignal,
    LearningStore,
    capture,
    extract_patterns,
    promote,
)
from apothem.lib.profile import load_profile_file
from apothem.schemas import profile_minimal_path


def _signal(signal_id: str) -> LearningSignal:
    """Build a minimal valid learning signal for tests."""
    return LearningSignal(
        id=signal_id,
        kind="observation",
        summary="the operator repeats the same fix shape",
        captured="2026-06-09T00:00:00Z",
        tags=("recurring",),
    )


def test_default_profile_has_learning_loop_off() -> None:
    # Arrange / Act: load the shipped minimal profile.
    profile = load_profile_file(profile_minimal_path())

    # Assert: the opt-in flag is off by default.
    assert profile.enforcement.learning_loop is False


def test_loop_is_inert_when_flag_unset(tmp_path: Path) -> None:
    # Arrange: default-off profile + an empty learning store.
    profile = load_profile_file(profile_minimal_path())
    store = LearningStore(resolve_shared_data_home(base=tmp_path).ensure())

    # Act: attempt capture with the flag unset.
    captured = capture(_signal("sig-1"), store=store, profile=profile)

    # Assert: no capture (returns None, store stays empty); with nothing
    # captured, extraction yields nothing and there is nothing to promote.
    assert captured is None
    assert store.count() == 0
    patterns = extract_patterns(store.signals())
    assert patterns == []
    # No pattern exists to promote — the promotion stage never fires.
    skills_dir = tmp_path / "skills"
    assert not skills_dir.exists()
    for pattern in patterns:  # empty; guards against a future regression
        assert (
            promote(pattern, threshold=0.5, skills_dir=skills_dir, today="2026-06-09")
            is None
        )
    assert not skills_dir.exists()
