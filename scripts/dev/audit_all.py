# SPDX-License-Identifier: MIT

"""One-shot quality orchestrator for the apothem ecosystem.

Runs, in order:

* ``ruff check``
* ``ruff format --check``
* ``mypy``
* ``pytest``
* ``validate_ecosystem``
* ``chaos_pass``

Each stage is a :class:`Stage` with a toggle flag. By default the first
failing stage aborts the run; pass ``--continue-on-error`` to run all stages
and aggregate failures.

Exit codes: 0 when every stage that ran passed, 1 otherwise.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

_ECOSYSTEM_ROOT: Final[Path] = Path(__file__).resolve().parent.parent.parent


@dataclass(frozen=True)
class Stage:
    """A single audit stage."""

    slug: str
    title: str
    command: tuple[str, ...]
    suite_aware: bool = False


@dataclass
class StageResult:
    """Outcome of running a :class:`Stage`."""

    stage: Stage
    returncode: int

    @property
    def passed(self) -> bool:
        return self.returncode == 0


def _python(*args: str) -> tuple[str, ...]:
    return (sys.executable, *args)


_STAGES: Final[tuple[Stage, ...]] = (
    Stage("ruff-check", "Ruff (lint)", _python("-m", "ruff", "check", ".")),
    Stage(
        "ruff-format",
        "Ruff (format check)",
        _python("-m", "ruff", "format", "--check", "."),
    ),
    Stage("mypy", "Mypy", _python("-m", "mypy")),
    Stage("pytest", "Pytest", _python("-m", "pytest", "--color=yes")),
    Stage(
        "validate-ecosystem",
        "Ecosystem validator",
        _python("scripts/dev/validate_ecosystem.py", "--content-root", "src/apothem"),
        suite_aware=True,
    ),
    Stage(
        "chaos-pass",
        "Chaos sweep",
        _python("scripts/dev/chaos_pass.py", "--content-root", "src/apothem"),
    ),
)


def _stage_slugs() -> list[str]:
    return [s.slug for s in _STAGES]


def run_stage(stage: Stage, cwd: Path, suite_name: str | None = None) -> StageResult:
    """Execute ``stage`` under ``cwd`` and return its result."""
    sys.stdout.write(f"\n==> {stage.title}\n")
    sys.stdout.flush()
    command = list(stage.command)
    if stage.suite_aware and suite_name:
        command.extend(["--suite", suite_name])
    proc = subprocess.run(command, cwd=str(cwd), check=False)
    return StageResult(stage=stage, returncode=proc.returncode)


def run(
    stages: Iterable[Stage],
    *,
    cwd: Path,
    continue_on_error: bool,
    suite_name: str | None,
) -> list[StageResult]:
    """Run each stage in order, honoring the fail-fast policy."""
    results: list[StageResult] = []
    for stage in stages:
        result = run_stage(stage, cwd, suite_name=suite_name)
        results.append(result)
        if not result.passed and not continue_on_error:
            break
    return results


def report(results: Sequence[StageResult]) -> int:
    """Emit a final summary; return 0 on success, 1 otherwise."""
    sys.stdout.write("\n=== Summary ===\n")
    fails = 0
    for result in results:
        marker = "[PASS]" if result.passed else "[FAIL]"
        sys.stdout.write(
            f"{marker} {result.stage.slug:<20} (exit={result.returncode})\n"
        )
        if not result.passed:
            fails += 1
    sys.stdout.write(f"Stages run: {len(results)}, failures: {fails}\n")
    return 0 if fails == 0 else 1


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        prog="audit_all",
        description=(
            "Run the full quality gate: ruff, mypy, pytest, "
            "validate_ecosystem, chaos_pass."
        ),
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=_ECOSYSTEM_ROOT,
        help="Ecosystem root (defaults to the repository containing this script).",
    )
    parser.add_argument(
        "--continue-on-error",
        action="store_true",
        help="Run every stage even after a failure.",
    )
    parser.add_argument(
        "--suite",
        help="Restrict suite-aware stages to one .apothem/plans/{suite} tree.",
    )
    for slug in _stage_slugs():
        parser.add_argument(
            f"--no-{slug}",
            action="store_true",
            help=f"Skip the {slug!r} stage.",
        )
    return parser.parse_args(argv)


def _select_stages(args: argparse.Namespace) -> list[Stage]:
    selected: list[Stage] = []
    for stage in _STAGES:
        flag = "no_" + stage.slug.replace("-", "_")
        if not getattr(args, flag, False):
            selected.append(stage)
    return selected


def main(argv: list[str] | None = None) -> int:
    """Entry point."""
    args = parse_args(argv)
    stages = _select_stages(args)
    if not stages:
        sys.stdout.write("No stages selected; nothing to do.\n")
        return 0
    results = run(
        stages,
        cwd=args.root,
        continue_on_error=args.continue_on_error,
        suite_name=args.suite,
    )
    return report(results)


if __name__ == "__main__":
    sys.exit(main())
