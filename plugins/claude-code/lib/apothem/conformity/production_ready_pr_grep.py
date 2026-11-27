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

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from apothem.conformity._git import run_git, split_names
from apothem.conformity._grep_base import (
    EXIT_FAIL,
    EXIT_PASS,
    GitCheckError,
    GitFailedError,
    GitTimeoutError,
    GrepResult,
    in_checkout,
    make_parser,
    parse_path_input,
)

# Per-class path patterns. Patterns are inclusive — a file matching
# multiple patterns counts toward every class it matches. Each pattern must
# match the whole name (see :func:`_classify`), and ``re.DOTALL`` lets ``.``
# cross a line break, which a staged name may hold.
CODE_PATTERNS: Final[tuple[re.Pattern[str], ...]] = (
    re.compile(r"^src/.+\.(?:py|ts|js|go|rs|rb|java|kt|swift)$", re.DOTALL),
    re.compile(r"^lib/.+\.(?:py|ts|js|go|rs)$", re.DOTALL),
    re.compile(
        r"^(?:rules|commands|agents|skills|hooks|tools)/.+\.(?:py|md)$", re.DOTALL
    ),
)
TEST_PATTERNS: Final[tuple[re.Pattern[str], ...]] = (
    re.compile(r"^tests?/.+", re.DOTALL),
    re.compile(r".+/test_[A-Za-z0-9_]+\.py$", re.DOTALL),
    re.compile(r".+_test\.(?:py|go|rs)$", re.DOTALL),
    re.compile(r".+\.test\.(?:ts|js)$", re.DOTALL),
)
# Docs-class paths. This repo's documentation lives under
# ``site/content/docs/`` (the ``no_toplevel_docs_grep`` validator hard-forbids
# a root ``docs/`` tree, so a ``^docs?/`` expectation here would be
# structurally unsatisfiable and contradict its sibling). Harness product
# templates and per-folder README/CONTRIBUTING surfaces also count as
# documentation for the four-class shape.
# Each pattern is applied with ``re.Pattern.fullmatch`` (anchored at both
# ends of the path), so alternatives that should fire at any depth carry an
# explicit ``(?:.*/)?`` optional-prefix.
DOCS_PATTERNS: Final[tuple[re.Pattern[str], ...]] = (
    re.compile(r"^site/content/docs/.+", re.DOTALL),
    re.compile(r"(?:.*/)?README\.md$", re.DOTALL),
    re.compile(r"(?:.*/)?CONTRIBUTING\.md$", re.DOTALL),
    re.compile(r".*/templates/.+\.(?:md|mdc)$", re.DOTALL),
)
CHANGELOG_PATTERNS: Final[tuple[re.Pattern[str], ...]] = (
    re.compile(r"^CHANGELOG\.md$", re.DOTALL),
    re.compile(r"^CHANGES(?:\.md)?$", re.DOTALL),
    re.compile(r"^HISTORY\.md$", re.DOTALL),
)

GREP_NAME: Final[str] = "production-ready-pr-grep"
RULE_ANCHOR: Final[str] = "M15 production-ready §Same-change-set"
STAGED_FLAG: Final[str] = "--staged"

# Subprocess timeout for the git invocation; the per-grep budget is
# `gate.PER_GREP_BUDGET_SECONDS` (~520ms) but the staged-diff check is a
# single git command that completes well under that ceiling on
# representative repositories. The time limit is for a git that stalls, not
# that budget. A timeout does not pass: the change set was not read, which is
# not the same as an empty one. So the limit leaves room for a large index on a
# slow or busy machine, since reading the index takes longer as it grows.
GIT_TIMEOUT_SECONDS: Final[int] = 60


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
    """Return the set of class labels the path matches.

    A pattern must match the whole name: with ``match``, ``$`` also matches
    before a final line break, so ``CHANGELOG.md`` followed by one would
    count as the changelog.
    """
    classes: set[str] = set()
    if any(p.fullmatch(path) for p in CODE_PATTERNS):
        classes.add("code")
    if any(p.fullmatch(path) for p in TEST_PATTERNS):
        classes.add("tests")
    if any(p.fullmatch(path) for p in DOCS_PATTERNS):
        classes.add("docs")
    if any(p.fullmatch(path) for p in CHANGELOG_PATTERNS):
        classes.add("changelog")
    return classes


def _staged_paths() -> list[str]:
    """Return the staged-diff path list via git; empty when there is none.

    The list is empty when git is missing or the current folder is not a
    checkout. git runs through :func:`run_git`, so the repository's own
    settings cannot make it start a program. ``-z`` ends each name with NUL,
    unquoted, and the output is read as file names, so a name comes back with
    every byte it holds (a carriage return, a byte that is not UTF-8).
    :func:`run_git` turns ``diff.relative`` off, so git lists every staged
    name from the top of the work tree, as the class patterns expect, even
    when the user's setting is on and the check runs in a subfolder. Raises
    :class:`~apothem.conformity._grep_base.GitTimeoutError` when git runs past
    ``GIT_TIMEOUT_SECONDS`` (the repository's own configuration can make git
    wait for ever), and :class:`~apothem.conformity._grep_base.GitFailedError`
    when git fails inside a checkout (a ``.git`` entry in the current folder or
    one above it): a change set that was not read is not an empty one.
    """
    try:
        result = run_git(
            ["diff", "--cached", "--name-only", "-z"],
            check=True,
            timeout=GIT_TIMEOUT_SECONDS,
            file_names=True,
        )
    except subprocess.TimeoutExpired as exc:
        raise GitTimeoutError("git diff --cached", GIT_TIMEOUT_SECONDS) from exc
    except subprocess.CalledProcessError as exc:
        if in_checkout(Path.cwd()):
            raise GitFailedError("git diff --cached", exc.returncode) from exc
        return []
    except FileNotFoundError:
        return []
    return split_names(result.stdout)


def _check_staged() -> GrepResult:
    """Substantive check: inspect the staged diff against the four-class shape.

    A staged list that git did not deliver, within ``GIT_TIMEOUT_SECONDS`` or
    at all in a checkout, does not pass: the result carries the reason as
    ``check_error``.
    """
    try:
        paths = _staged_paths()
    except GitCheckError as exc:
        return GrepResult(
            grep=GREP_NAME,
            path="<staged diff>",
            passed=False,
            check_error=str(exc),
        )
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
    def _configure(parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            STAGED_FLAG,
            dest="staged",
            action="store_true",
            help="check the staged change set instead of one file",
        )

    if STAGED_FLAG in argv[1:]:
        parser = make_parser(GREP_NAME, __doc__)
        _configure(parser)
        parser.parse_args(argv[1:])
        result = _check_staged()
    else:
        _args, content, path = parse_path_input(
            argv, prog=GREP_NAME, doc=__doc__, configure=_configure
        )
        result = check(content, path)
    print(result.to_json())
    return EXIT_PASS if result.passed else EXIT_FAIL


if __name__ == "__main__":
    sys.exit(_main(sys.argv))
