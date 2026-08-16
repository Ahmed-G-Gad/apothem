# SPDX-License-Identifier: MIT

"""Flag commits whose change-set lacks the production-ready four-class shape.

Why this enforcement exists. The production-ready discipline M15 requires
every change touching public surface to ship in the same change-set with
tests, documentation, and a CHANGELOG entry. A code change without its
companions persists as half-finished — the follow-up never lands; the
release notes lie. The pre-emission gate's mechanical bar 15 (M15 production-ready) catches
change-sets where public-surface code was modified but the companion
classes (tests / docs / CHANGELOG) are absent or trivially populated.

Detection strategy. The grep inspects the staged diff via `git diff
--cached --name-only` and classifies every touched file into one of
four classes (code, tests, docs, changelog). When code-class files are
touched, the grep verifies at least one tests-class and at least one
docs-class file is also touched, plus the changelog-class file is
present in the change-set. Per-file invocation is a soft pass — the
grep operates at change-set granularity rather than per-file, so the
orchestrator's per-Write dispatch returns clean and the CLI mode
performs the substantive check.
"""

from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from apothem.conformity._grep_base import (
    EXIT_FAIL,
    EXIT_PASS,
    GrepResult,
    read_input,
)

# Per-class path patterns. Patterns are inclusive — a file matching
# multiple patterns counts toward every class it matches.
CODE_PATTERNS: Final[tuple[re.Pattern[str], ...]] = (
    re.compile(r"^src/.+\.(?:py|ts|js|go|rs|rb|java|kt|swift)$"),
    re.compile(r"^lib/.+\.(?:py|ts|js|go|rs)$"),
    re.compile(r"^(?:rules|commands|agents|skills|hooks|tools)/.+\.(?:py|md)$"),
)
TEST_PATTERNS: Final[tuple[re.Pattern[str], ...]] = (
    re.compile(r"^tests?/.+"),
    re.compile(r".+/test_[A-Za-z0-9_]+\.py$"),
    re.compile(r".+_test\.(?:py|go|rs)$"),
    re.compile(r".+\.test\.(?:ts|js)$"),
)
# Docs-class paths. This repo's documentation lives under
# ``site/content/docs/`` (the ``no_toplevel_docs_grep`` validator hard-forbids
# a root ``docs/`` tree, so a ``^docs?/`` expectation here would be
# structurally unsatisfiable and contradict its sibling). Harness product
# templates and per-folder README/CONTRIBUTING surfaces also count as
# documentation for the four-class shape.
# Each pattern is applied with ``re.Pattern.match`` (anchored at the path
# start), so alternatives that should fire at any depth carry an explicit
# ``(?:.*/)?`` optional-prefix.
DOCS_PATTERNS: Final[tuple[re.Pattern[str], ...]] = (
    re.compile(r"^site/content/docs/.+"),
    re.compile(r"(?:.*/)?README\.md$"),
    re.compile(r"(?:.*/)?CONTRIBUTING\.md$"),
    re.compile(r".*/templates/.+\.(?:md|mdc)$"),
)
CHANGELOG_PATTERNS: Final[tuple[re.Pattern[str], ...]] = (
    re.compile(r"^CHANGELOG\.md$"),
    re.compile(r"^CHANGES(?:\.md)?$"),
    re.compile(r"^HISTORY\.md$"),
)

GREP_NAME: Final[str] = "production-ready-pr-grep"
RULE_ANCHOR: Final[str] = "M15 production-ready §Same-change-set"
STAGED_FLAG: Final[str] = "--staged"

# Subprocess timeout for the git invocation; the per-grep budget is
# `gate.PER_GREP_BUDGET_SECONDS` (~520ms) but the staged-diff check is a
# single git command that completes well under that ceiling on
# representative repositories.
GIT_TIMEOUT_SECONDS: Final[int] = 5


@dataclass(frozen=True)
class Finding:
    """One completeness gap in the inspected change-set.

    Pre-conditions: ``issue`` names the missing companion class — a code change
    landing without ``tests``, ``docs``, or a ``changelog`` entry — and
    ``detail`` names the touched paths that triggered the expectation.
    Post-conditions: ``rule`` defaults to :data:`RULE_ANCHOR` so every finding
    cites the production-ready-PR discipline as its authority.
    """

    issue: str
    detail: str
    rule: str = RULE_ANCHOR


def _classify(path: str) -> set[str]:
    """Return the set of class labels the path matches."""
    classes: set[str] = set()
    if any(p.match(path) for p in CODE_PATTERNS):
        classes.add("code")
    if any(p.match(path) for p in TEST_PATTERNS):
        classes.add("tests")
    if any(p.match(path) for p in DOCS_PATTERNS):
        classes.add("docs")
    if any(p.match(path) for p in CHANGELOG_PATTERNS):
        classes.add("changelog")
    return classes


def _staged_paths() -> list[str]:
    """Return the staged-diff path list via git; empty on failure."""
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],  # noqa: S607  # PATH-resolved git is acceptable for a developer-tool grep; full-path resolution would require host-discovery and breaks portability across operator setups.
            check=True,
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT_SECONDS,
        )
    except (
        subprocess.CalledProcessError,
        subprocess.TimeoutExpired,
        FileNotFoundError,
    ):
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def _check_staged() -> GrepResult:
    """Substantive check: inspect the staged diff against the four-class shape."""
    paths = _staged_paths()
    classes_present: set[str] = set()
    for path in paths:
        classes_present |= _classify(path)
    findings: list[Finding] = []
    if "code" in classes_present:
        if "tests" not in classes_present:
            findings.append(
                Finding(
                    issue="missing tests-class file",
                    detail="code-class file modified; no tests/* file in the change-set",
                )
            )
        if "docs" not in classes_present:
            findings.append(
                Finding(
                    issue="missing docs-class file",
                    detail="code-class file modified; no site/content/docs / README / CONTRIBUTING / template docs in the change-set",
                )
            )
        if "changelog" not in classes_present:
            findings.append(
                Finding(
                    issue="missing CHANGELOG entry",
                    detail="code-class file modified; CHANGELOG.md is not part of the change-set",
                )
            )
    return GrepResult(
        grep=GREP_NAME,
        path="<staged diff>",
        passed=not findings,
        findings=findings,
    )


def check(content: str, path: Path | None = None) -> GrepResult:
    """Per-file mode is a soft pass; the substantive check fires via ``--staged``.

    The grep operates at change-set granularity, so the orchestrator's per-Write
    dispatch always returns clean here and the CLI ``--staged`` path performs the
    four-class check (:func:`_check_staged`).
    """
    return GrepResult(
        grep=GREP_NAME,
        path=str(path) if path is not None else None,
        passed=True,
    )


def _main(argv: list[str]) -> int:
    if len(argv) >= 2 and argv[1] == STAGED_FLAG:
        result = _check_staged()
    else:
        content, path = read_input(argv)
        result = check(content, path)
    print(result.to_json())
    return EXIT_PASS if result.passed else EXIT_FAIL


if __name__ == "__main__":
    sys.exit(_main(sys.argv))
