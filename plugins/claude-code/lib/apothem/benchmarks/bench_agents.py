# SPDX-License-Identifier: MIT

"""Agent-spawn runtime benchmark per the per-spawn budget in
`src/apothem/rules/performance-discipline.md` §1.

Spawn budget: 60 seconds for any of the four agent patterns
(research / audit / quality / generation).

Agent spawns are exercised through the host harness rather than via a
direct subprocess call; the script stands as a budget anchor with a
representative-invocation hook that operators wire to their harness.
When no harness fixture is provided, the script reports the budget and
exits with the scaffold marker (return code 0) so the verifier surface
remains usable while detailed fixtures land.
"""

from __future__ import annotations

import argparse
from typing import Final

_BUDGET: Final[float] = 60.0
_PATTERNS: Final[tuple[str, ...]] = ("research", "audit", "quality", "generation")


def _representative_spawn() -> float | None:
    """Return wall-clock seconds for a representative agent spawn.

    Returns ``None`` when no harness fixture is wired; the caller then
    reports the budget without a measurement.
    """
    # Harness fixtures are operator-editorial; without one wired, no
    # measurement is attempted. Wire a representative spawn through the
    # host harness here when one becomes available.
    return None


def main(argv: list[str] | None = None) -> int:
    """Run the agent-spawn benchmark for one pattern; return the exit code.

    Pre-conditions: ``argv`` is the argument vector without the program name
    (``None`` reads ``sys.argv``); it must select one ``--pattern`` from the
    four supported agent patterns.

    Post-conditions: returns ``0`` when the measured spawn is inside the
    per-spawn budget, or when no harness fixture is wired and the run degrades
    to reporting the budget alone; returns non-zero when a measured spawn
    exceeds it.
    """
    parser = argparse.ArgumentParser(prog="bench_agents")
    parser.add_argument(
        "--pattern",
        required=True,
        choices=_PATTERNS,
        help="Agent pattern to benchmark.",
    )
    args = parser.parse_args(argv)

    elapsed = _representative_spawn()
    if elapsed is None:
        print(
            f"SCAFFOLD: pattern={args.pattern} budget={_BUDGET}s "
            "(no harness fixture wired; measurement skipped)"
        )
        return 0
    if elapsed <= _BUDGET:
        print(f"PASS: agent {args.pattern} = {elapsed:.3f}s (budget {_BUDGET}s)")
        return 0
    print(f"FAIL: agent {args.pattern} = {elapsed:.3f}s exceeds budget {_BUDGET}s")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
