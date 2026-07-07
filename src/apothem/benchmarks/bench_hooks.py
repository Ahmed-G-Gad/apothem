# SPDX-License-Identifier: MIT

"""Hook-handler runtime benchmark per the per-event budgets in
`src/apothem/rules/performance-discipline.md` §1.

The script declares the canonical per-event budgets and provides a measurement
hook for the dispatcher's startup overhead. Representative event-fixture
invocation is operator-editorial: when no fixture is wired for a given event,
the script reports the budget and exits with the scaffold marker (return
code 0) so the verifier surface remains usable while detailed fixtures land.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path
from typing import Final

_BUDGETS: Final[dict[str, float]] = {
    "PreToolUse": 10.0,
    "PostToolUse": 10.0,
    "UserPromptSubmit": 10.0,
    "Notification": 10.0,
    "SessionStart": 30.0,
    "PreCompact": 30.0,
    "PostCompact": 30.0,
    "Stop": 60.0,
}

# bench_hooks.py lives at <repo>/src/apothem/benchmarks/; four parents up is
# the repository root.
_REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[3]
_DISPATCHER: Final[Path] = _REPO_ROOT / "src" / "apothem" / "hooks" / "dispatch.py"


def _measure_dispatcher_startup() -> float:
    """Return wall-clock seconds for a no-op dispatcher invocation.

    Invokes the dispatcher with ``--help`` (argparse exits 0) so the elapsed
    wall-clock bounds the floor cost (interpreter spin-up + module import +
    arg parse) for any hook handler. A non-zero return code means the
    dispatcher could not be exercised; the caller raises rather than report a
    spurious sub-budget reading from a process that never ran the real code.
    """
    start = time.monotonic()
    completed = subprocess.run(  # noqa: S603 — trusted invocation: literal argv against the in-repo dispatcher
        [sys.executable, str(_DISPATCHER), "--help"],
        check=False,
        capture_output=True,
    )
    elapsed = time.monotonic() - start
    if completed.returncode != 0:
        raise RuntimeError(
            f"dispatcher invocation failed (exit {completed.returncode}); "
            f"target={_DISPATCHER} — a sub-budget reading here would be spurious"
        )
    return elapsed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="bench_hooks")
    parser.add_argument(
        "--event",
        required=True,
        choices=sorted(_BUDGETS),
        help="Hook event class to benchmark.",
    )
    args = parser.parse_args(argv)
    budget = _BUDGETS[args.event]
    if not _DISPATCHER.is_file():
        print(f"ERROR: dispatcher target not found: {_DISPATCHER}", file=sys.stderr)
        return 2
    try:
        elapsed = _measure_dispatcher_startup()
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    if elapsed <= budget:
        print(
            f"PASS: {args.event} dispatcher startup = {elapsed:.3f}s (budget {budget}s)"
        )
        return 0
    print(
        f"FAIL: {args.event} dispatcher startup = {elapsed:.3f}s exceeds budget {budget}s"
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
