# SPDX-License-Identifier: MIT

"""Test-suite runtime benchmark per the per-suite budgets in
`src/apothem/rules/performance-discipline.md` §1.

Full-suite budget: 60 seconds (pytest -n auto, post-xdist).
Per-test-module budget: 10 seconds.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path
from typing import Final

_FULL_BUDGET: Final[float] = 60.0
_PER_MODULE_BUDGET: Final[float] = 10.0
# bench file lives at <repo>/src/apothem/benchmarks/; four parents up is root.
_REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[3]
_TESTS_DIR: Final[Path] = _REPO_ROOT / "tests"


def _time_invocation(target: Path, *, single_module: bool) -> float:
    """Return wall-clock seconds for a pytest invocation against ``target``.

    The per-module path runs with ``-n0`` so the per-module budget measures the
    module's own runtime rather than the xdist worker-pool startup that the
    repository's ``-n auto`` default would otherwise charge to a single file.
    The full-suite path keeps the configured ``-n auto`` parallelism the
    full-suite budget assumes.
    """
    cmd = [sys.executable, "-m", "pytest", str(target), "-q"]
    if single_module:
        cmd.append("-n0")
    start = time.monotonic()
    completed = subprocess.run(  # noqa: S603 — trusted invocation: literal argv against the host pytest module
        cmd,
        check=False,
        capture_output=True,
        cwd=_REPO_ROOT,
    )
    elapsed = time.monotonic() - start
    # A non-zero pytest exit (test failure, collection error, no tests
    # collected) means the measured run did not complete cleanly; a sub-budget
    # reading for such a run would falsely attest budget compliance per the
    # rule's "exit 0 attests budget compliance" contract. Raise rather than
    # report a spurious PASS — mirrors bench_hooks' returncode guard.
    if completed.returncode != 0:
        raise RuntimeError(
            f"pytest invocation failed (exit {completed.returncode}); "
            "a sub-budget reading here would be spurious"
        )
    return elapsed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="bench_tests")
    parser.add_argument(
        "--module",
        default=None,
        help="Path (relative to the repository root) of a per-module subset; "
        "the per-module budget applies. When omitted, the full suite runs "
        "under the full-suite budget.",
    )
    args = parser.parse_args(argv)

    single_module = args.module is not None
    target = _REPO_ROOT / args.module if args.module else _TESTS_DIR
    budget = _PER_MODULE_BUDGET if single_module else _FULL_BUDGET
    label = f"module {args.module}" if single_module else "full suite"
    if single_module and not target.is_file():
        print(f"ERROR: test module not found: {target}", file=sys.stderr)
        return 2
    if not single_module and not target.is_dir():
        print(f"ERROR: tests directory not found: {target}", file=sys.stderr)
        return 2
    try:
        elapsed = _time_invocation(target, single_module=single_module)
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    if elapsed <= budget:
        print(f"PASS: pytest {label} = {elapsed:.3f}s (budget {budget}s)")
        return 0
    print(f"FAIL: pytest {label} = {elapsed:.3f}s exceeds budget {budget}s")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
