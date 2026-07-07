# SPDX-License-Identifier: MIT

"""A write to the Apothem source repo's own ``.apothem/plans/`` tree from
the Apothem source repo working tree itself is allowed (recursion-self case).

When the operator is editing the Apothem source repo itself (resolved
project root IS the Apothem source repo), the source repo's
``.apothem/plans/`` tree IS the canonical destination. The plan-write-guard
hook context declares the recursion-self allow path so the discipline does
not break for source-repo self-edits.
"""

from __future__ import annotations


def test_recursion_self_class_declared(write_plan_guard_text: str) -> None:
    """The verdict matrix declares the recursion-self allow class."""
    assert "**Recursion-self (allow)**" in write_plan_guard_text


def test_recursion_self_predicate_named(write_plan_guard_text: str) -> None:
    """The recursion-self predicate explicitly names the project-root identity."""
    assert (
        "Resolved project root IS the Apothem source repo itself"
        in write_plan_guard_text
    )


def test_recursion_self_passes_silently(write_plan_guard_text: str) -> None:
    """The recursion-self verdict is silent passthrough — no structured inquiry."""
    assert "Pass through silently with no" in write_plan_guard_text
    assert "structured inquiry" in write_plan_guard_text


def test_recursion_self_is_only_allowed_path(write_plan_guard_text: str) -> None:
    """The hook declares recursion-self as the ONLY allowed write path under the source-repo .apothem/plans/ tree."""
    assert "ONLY allowed write path" in write_plan_guard_text
    assert "apothem" in write_plan_guard_text


def test_bash_companion_inherits_recursion_self(bash_plan_guard_text: str) -> None:
    """The Bash companion guard preserves the recursion-self carve-out for shell redirects."""
    assert "ONLY allowed shell-redirect path" in bash_plan_guard_text
    assert "apothem-source-repo" in bash_plan_guard_text
