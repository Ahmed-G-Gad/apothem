# SPDX-License-Identifier: MIT

"""Validator honors coherence-override marker; verdict stays PASS."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from types import ModuleType


def test_override_marker_exempts_surface(
    grep_module: ModuleType,
    write_surface: Callable[[str, str], Path],
) -> None:
    """A non-canonical surface carrying the override marker is exempted from
    the claim's coherence check; the verdict is PASS with a warning-severity
    COHERENCE_OVERRIDE_HONORED finding."""
    affirmative = (
        "# Stub Surface\n\n"
        "Every applicable new file begins with the canonical banner.\n"
    )
    overridden = (
        "# Stub Surface\n\n"
        "<!-- coherence-override: header.canonical -->\n\n"
        "This surface adopts a different stance on the claim.\n"
    )
    write_surface("AGENTS.md", affirmative)
    write_surface("CLAUDE.md", affirmative)
    write_surface(".github/copilot-instructions.md", overridden)
    # Seed an ADR file so the validator's pairing-pending advisory does
    # not fire on top of the override-honored finding.
    write_surface("docs/adr/0001-example.md", "# Example ADR\n")

    result = grep_module.check("", None)

    rules = [(f.rule, f.severity) for f in result.findings]
    assert result.passed is True
    assert ("COHERENCE_OVERRIDE_HONORED", "warning") in rules
