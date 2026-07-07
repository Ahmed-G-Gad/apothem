# SPDX-License-Identifier: MIT

"""Smoke tests: every de-enforced behavior keeps a working opt-in path.

The agnostic posture ships every workflow behavior default-off and keeps
its machinery preserved and invokable — opting in must restore the
behavior intact, and a clean install must impose none of it. These smoke
tests exercise each opt-in path:

- The five enforcement toggles (sprints, agent teams, multitasking,
  continuous execution, learning loop) opt in through the shared profile's
  ``enforcement`` block; a clean install leaves every one off.
- The conformity gate is advisory by default and restores blocking only
  under the ``--strict`` flag or the ``APOTHEM_CONFORMITY_STRICT`` opt-in.

Model and effort preference carry no profile toggle by design: they are
absent-by-default request frontmatter the end user supplies in
conversation, and their absence from shipped surfaces is guarded by the
agnosticism sweep rather than a profile flag.
"""

from __future__ import annotations

from typing import Final

import pytest

from apothem.conformity import gate
from apothem.lib.profile import EnforcementFlags, coerce_profile

_ENFORCEMENT_FLAGS: Final[tuple[str, ...]] = (
    "sprints",
    "agent_teams",
    "multitasking",
    "continuous_execution",
    "learning_loop",
)


def _profile(enforcement: dict[str, bool] | None = None):
    payload: dict[str, object] = {"identity": {"name": "Smoke Operator"}}
    if enforcement is not None:
        payload["enforcement"] = enforcement
    return coerce_profile(payload)


def test_enforcement_flag_set_matches_profile_block() -> None:
    """The toggle set the profile materializes matches the declared flags."""
    assert set(EnforcementFlags().to_dict()) == set(_ENFORCEMENT_FLAGS)


def test_clean_install_defaults_every_behavior_off() -> None:
    """A profile with no enforcement block leaves every behavior off."""
    profile = _profile()
    for flag in _ENFORCEMENT_FLAGS:
        assert getattr(profile.enforcement, flag) is False, flag


@pytest.mark.parametrize("flag", _ENFORCEMENT_FLAGS)
def test_each_behavior_opt_in_path_activates(flag: str) -> None:
    """Setting one enforcement flag opts that behavior in and no other."""
    profile = _profile({flag: True})
    assert getattr(profile.enforcement, flag) is True, flag
    for other in _ENFORCEMENT_FLAGS:
        if other != flag:
            assert getattr(profile.enforcement, other) is False, other


def test_gate_advisory_by_default_does_not_block() -> None:
    """With no strict opt-in, a failing verdict still exits PASS (advisory)."""
    rest, strict = gate._resolve_strict(["gate", "."])
    assert strict is False
    assert rest == ["gate", "."]
    assert gate._gate_exit(passed=False, strict=strict) == gate.EXIT_PASS


def test_gate_strict_flag_restores_blocking() -> None:
    """The --strict flag is consumed from argv and restores blocking."""
    rest, strict = gate._resolve_strict(["gate", "--strict", "."])
    assert strict is True
    assert rest == ["gate", "."]
    assert gate._gate_exit(passed=False, strict=strict) == gate.EXIT_FAIL


def test_gate_strict_env_restores_blocking(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A truthy strict environment variable restores blocking."""
    monkeypatch.setenv(gate.STRICT_ENV, "1")
    _rest, strict = gate._resolve_strict(["gate", "."])
    assert strict is True
    assert gate._gate_exit(passed=False, strict=strict) == gate.EXIT_FAIL


def test_gate_clean_run_always_passes() -> None:
    """A clean verdict exits PASS regardless of the strict opt-in."""
    assert gate._gate_exit(passed=True, strict=False) == gate.EXIT_PASS
    assert gate._gate_exit(passed=True, strict=True) == gate.EXIT_PASS
