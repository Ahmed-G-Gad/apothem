# SPDX-License-Identifier: MIT

"""Verify-ecosystem-sweep runtime benchmark per the per-check budgets in
`src/apothem/rules/performance-discipline.md` §1.

Composite budget: 30 seconds for the full sweep.
Per-check budget: 5 seconds for any single subcommand.

The script invokes the verifier under `--skip-hooks` to isolate the host-tool
runtime from the bundled hook validator delegation.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path
from typing import Final

_COMPOSITE_BUDGET: Final[float] = 30.0
_PER_CHECK_BUDGET: Final[float] = 5.0
# bench file lives at <repo>/src/apothem/benchmarks/; four parents up is root.
_REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[3]
_VALIDATOR: Final[Path] = _REPO_ROOT / "scripts" / "dev" / "validate_ecosystem.py"


def _time_invocation(extra: list[str]) -> float:
    """Return wall-clock seconds for a verifier invocation.

    A non-zero return code means the verifier never ran the real sweep (a
    bogus ``--check`` argparse-errors in well under budget, for instance); the
    caller raises rather than report a spurious sub-budget reading from a
    process that never executed the measured work. Mirrors the returncode
    guard in ``bench_hooks._measure_dispatcher_startup``.
    """
    start = time.monotonic()
    completed = subprocess.run(  # noqa: S603 — trusted invocation: literal argv against the in-repo verifier
        [sys.executable, str(_VALIDATOR), "--skip-hooks", *extra],
        check=False,
        capture_output=True,
    )
    elapsed = time.monotonic() - start
    if completed.returncode != 0:
        raise RuntimeError(
            f"verifier invocation failed (exit {completed.returncode}); "
            "a sub-budget reading here would be spurious"
        )
    return elapsed


def main(argv: list[str] | None = None) -> int:
    """Run the ecosystem-validation benchmark for one check; return the exit.

    Pre-conditions: ``argv`` is the argument vector without the program name
    (``None`` reads ``sys.argv``); it must select one ``--check`` from the
    ecosystem validator's check set.

    Post-conditions: returns ``0`` when the check completes inside its budget,
    non-zero when it exceeds it.
    """
    parser = argparse.ArgumentParser(prog="bench_validate_ecosystem")
    parser.add_argument(
        "--check",
        default=None,
        help="Restrict the benchmark to a single subcommand (per-check budget applies).",
    )
    args = parser.parse_args(argv)

    if not _VALIDATOR.is_file():
        print(f"ERROR: validator target not found: {_VALIDATOR}", file=sys.stderr)
        return 2
    extra = ["--check", args.check] if args.check else []
    try:
        elapsed = _time_invocation(extra)
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    # `--check all` is a full composite run, so it earns the composite budget,
    # not the per-check budget — keying on the value, not merely arg presence.
    per_check = args.check is not None and args.check != "all"
    budget = _PER_CHECK_BUDGET if per_check else _COMPOSITE_BUDGET
    label = f"--check {args.check}" if args.check else "composite sweep"
    if elapsed <= budget:
        print(f"PASS: validate_ecosystem {label} = {elapsed:.3f}s (budget {budget}s)")
        return 0
    print(f"FAIL: validate_ecosystem {label} = {elapsed:.3f}s exceeds budget {budget}s")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
