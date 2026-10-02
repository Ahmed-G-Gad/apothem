# SPDX-License-Identifier: MIT

"""Agent-spawn runtime benchmark per the per-spawn budget in
`src/apothem/rules/performance-discipline.md` §1.

Spawn budget: 60 seconds for any of the four agent patterns
(research / audit / quality / generation).

Not measured. An agent spawn runs inside a host harness and costs a model
call; there is no headless, unbilled way to time one from this repository.
Until a harness fixture is wired, the driver reports ``NOT MEASURED`` with the
budget and exits ``EXIT_NOT_MEASURED`` (3). That code is distinct from pass
(0), over budget (1) and error (2), so a caller can never read the scaffold as
a pass. The ``make benchmarks`` target therefore does not run this driver.
"""

from __future__ import annotations

import argparse
from typing import Final

_BUDGET: Final[float] = 60.0
_PATTERNS: Final[tuple[str, ...]] = ("research", "audit", "quality", "generation")

EXIT_PASS: Final[int] = 0
EXIT_OVER_BUDGET: Final[int] = 1
EXIT_NOT_MEASURED: Final[int] = 3


def _representative_spawn() -> float | None:
    """Return wall-clock seconds for a representative agent spawn.

    Returns ``None`` when no harness fixture is wired; the caller then
    reports the budget without a measurement.
    """
    # A spawn needs a host harness and a model call; wire a fixture here when
    # an unbilled one exists.
    return None


def main(argv: list[str] | None = None) -> int:
    """Run the agent-spawn benchmark for one pattern; return the exit code.

    Pre-conditions: ``argv`` is the argument vector without the program name
    (``None`` reads ``sys.argv``); it must select one ``--pattern`` from the
    four supported agent patterns.

    Post-conditions: returns ``0`` when a measured spawn is inside the budget,
    ``1`` when it exceeds it, and ``3`` (not measured) when no harness fixture
    is wired.
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
            f"NOT MEASURED: agent {args.pattern} budget={_BUDGET}s "
            "(a spawn needs a host harness and a model call; no fixture is wired)"
        )
        return EXIT_NOT_MEASURED
    if elapsed <= _BUDGET:
        print(f"PASS: agent {args.pattern} = {elapsed:.3f}s (budget {_BUDGET}s)")
        return EXIT_PASS
    print(f"FAIL: agent {args.pattern} = {elapsed:.3f}s exceeds budget {_BUDGET}s")
    return EXIT_OVER_BUDGET


if __name__ == "__main__":
    raise SystemExit(main())
