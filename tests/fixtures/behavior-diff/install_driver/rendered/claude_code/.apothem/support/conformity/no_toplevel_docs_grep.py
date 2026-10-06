# SPDX-License-Identifier: MIT

"""Fail when a top-level ``docs/`` directory exists at the repository root.

Why this validator exists. The documentation source of truth is the
Next.js + Fumadocs site under ``site/``; the rendered reference pages live
at ``site/content/docs/``. A bare ``docs/`` directory at the
repository root is a competing documentation source — a second place a
contributor (or a generator) might write or read docs from, splitting
the single-source-of-truth invariant. Once a root ``docs/`` exists,
links, build steps, and contributor habits accrete around it and the
two trees drift. The invariant is therefore structural and hard: there
is exactly one documentation tree (``site/``), and the repository root
never carries a ``docs/`` directory.

Scope of the violation. ONLY a directory named ``docs`` directly under
the repository root is forbidden. Nested ``docs/`` directories under
other trees (for example a vendored package's own ``docs/``), the
``site/`` tree, and ``src/`` are all fine — the validator inspects the
single root-level entry, not the whole tree.

Non-advisory. Unlike the advisory matchers, this is a hard structural
invariant: ``check()`` returns ``passed=False`` and the CLI exits 2 the
moment a root ``docs/`` directory is present, so a ``--strict`` CI step
blocks the change.

Exit semantics. Exits 0 when no findings; exits 2 on any finding,
matching the conformity-gate orchestrator's EXIT_FAIL constant.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from apothem.conformity._grep_base import (
    EXIT_FAIL,
    EXIT_PASS,
    RootGrepResult,
    run_root_grep,
)

# Re-export the exit-code constants so the module's public CLI contract stays
# stable after the base-skeleton adoption — callers and the self-tests read
# ``EXIT_PASS`` / ``EXIT_FAIL`` off this module.
__all__ = ["EXIT_FAIL", "EXIT_PASS", "Finding", "check"]

GREP_NAME: Final[str] = "no-toplevel-docs-grep"
RULE_ANCHOR: Final[str] = "single-source-of-truth (docs live in site/, not root docs/)"

# The forbidden directory name at the repository root.
_FORBIDDEN_DIR: Final[str] = "docs"
# The canonical documentation tree contributors must use instead.
_CANONICAL_DOCS_TREE: Final[str] = "site/content/docs/"


@dataclass(frozen=True)
class Finding:
    """The single finding: a root-level ``docs/`` directory exists."""

    path: str
    detail: str
    rule: str = RULE_ANCHOR


def check(root: Path) -> RootGrepResult:
    """Flag a ``docs/`` directory living directly under *root*.

    The report carries the canonical ``{grep, root, passed, advisory,
    findings}`` payload with ``advisory=False`` — this is a hard structural
    invariant, not an advisory sweep.
    """
    candidate = root / _FORBIDDEN_DIR
    findings: list[Finding] = []
    if candidate.is_dir():
        findings.append(
            Finding(
                path=f"{_FORBIDDEN_DIR}/",
                detail=(
                    "a top-level docs/ directory is forbidden: the "
                    "documentation source of truth is site/ "
                    f"(rendered pages at {_CANONICAL_DOCS_TREE}); "
                    "remove the root docs/ tree and author documentation "
                    "under site/ instead"
                ),
            )
        )
    return RootGrepResult(
        grep=GREP_NAME,
        root=str(root),
        passed=not findings,
        findings=findings,
        # One location is inspected: the root's top-level ``docs/`` slot.
        inspected=1,
    )


def _main(argv: list[str]) -> int:
    return run_root_grep(check, argv)


if __name__ == "__main__":
    sys.exit(_main(sys.argv))
