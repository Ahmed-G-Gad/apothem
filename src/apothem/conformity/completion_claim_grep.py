# SPDX-License-Identifier: MIT

"""Flag unsupported completion / guarantee claims in cohort prose.

Why this enforcement exists. Spec §4.2 (Output Honesty, Validity, and
Determinism) demands evidence that requirements are truly complete, including
checks against "done" claims that would require a rerun to prove. A command,
agent, or skill that promises an absolute, unconditional outcome — "guaranteed
to pass", "always works", "100% complete", "cannot fail" — asserts a result the
prose cannot back with evidence; the claim reads as honest completion when it is
actually an unprovable guarantee. This matcher detects a closed set of such
absolute-guarantee phrases so the dishonest-completion pattern surfaces before
emission.

What this is NOT. This is a deliberately narrow guard against *absolute,
unconditional* guarantees, not a ban on the words "done" or "complete".
Evidence-gated completion language ("complete when every verification passes",
"not complete until zero findings remain", "declare complete once the suite is
verified") is correct and is not matched. Distinguishing a merely-unsupported
"done" from an evidence-gated one requires judgment beyond a mechanical grep;
that broader class is documented as out of scope per the spec's
"detected or documented as out of scope" acceptance, and this grep covers the
mechanically-detectable absolute-guarantee subset.

Scope. Only cohort prose (`.md` under commands / agents / skills / rules /
output-styles / hooks messages) is scanned; code, schemas, and plan-suite
artifacts are skipped. Files that define this discipline (quoting the phrases as
anti-pattern examples) are excluded by path, and hits inside fenced code blocks
are excluded — a fenced block quotes commands or anti-pattern examples rather
than carrying the artifact's own directive prose (mirroring hedging_grep).
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from apothem.conformity._grep_base import GrepResult, iter_prose_lines, run_grep

# Closed set of absolute / unconditional completion-or-guarantee claims. Each is
# unprovable in directive prose: proving it would require a rerun, and even then
# the universal quantifier ("always", "never", "100%", "cannot") cannot be
# discharged. The patterns are anchored to the guarantee structure to keep the
# false-positive rate near zero.
_CLAIM_PATTERNS: Final[tuple[tuple[str, re.Pattern[str]], ...]] = (
    (
        "guaranteed-outcome",
        re.compile(r"guaranteed to (?:pass|work|succeed|complete)", re.IGNORECASE),
    ),
    (
        "absolute-percentage",
        re.compile(
            r"100%\s+(?:complete|guaranteed|certain|reliable|done|airtight)",
            re.IGNORECASE,
        ),
    ),
    ("cannot-fail", re.compile(r"\bcannot (?:fail|possibly fail)\b", re.IGNORECASE)),
    ("will-never-fail", re.compile(r"\bwill never (?:fail|break)\b", re.IGNORECASE)),
    (
        "always-succeeds",
        re.compile(r"\balways (?:passes|works|succeeds)\b", re.IGNORECASE),
    ),
    ("never-fails", re.compile(r"\bnever (?:fails|breaks)\b", re.IGNORECASE)),
    (
        "definitely-works",
        re.compile(r"\bdefinitely (?:works|passes|complete)\b", re.IGNORECASE),
    ),
)

# Cohort-prose directories whose `.md` files carry directive / output prose.
_COHORT_DIRS: Final[tuple[str, ...]] = (
    "commands",
    "agents",
    "skills",
    "rules",
    "output-styles",
    "hooks",
)

# `.md` cohort files that define the completion-honesty discipline and quote
# the banned phrases as anti-pattern examples; excluded so the definition is
# not flagged as a finding. Scoped to `.md` basenames because `_in_scope`
# rejects non-`.md` paths first — a `.py` entry (the grep's own module) could
# never reach this check, so only `.md` discipline sources belong here. The
# rule that anchors this matcher (`RULE_ANCHOR`) is the canonical such source.
_EXCLUDED_BASENAMES: Final[frozenset[str]] = frozenset(
    {
        "session-closure.md",
    }
)

# Fenced code block delimiter (triple backtick at column 0), mirroring
# hedging_grep.CODE_FENCE_RE. A claim inside a fenced block is a quoted command
# or anti-pattern example, not the artifact's own prescriptive prose, so it is
# excluded from the scan.
_CODE_FENCE_RE: Final[re.Pattern[str]] = re.compile(r"^```")

GREP_NAME: Final[str] = "completion-claim-grep"
RULE_ANCHOR: Final[str] = "rules/session-closure.md (verifiable-close output honesty)"


@dataclass(frozen=True)
class Finding:
    """One unsupported-completion-claim occurrence."""

    line: int
    kind: str
    text: str
    rule: str = RULE_ANCHOR


def _in_scope(path: Path | None) -> bool:
    """Return True when *path* is cohort prose subject to the scan.

    A None path (stdin) is in scope so direct invocations are checked; a
    concrete path must be a `.md` under a cohort directory and not excluded.
    """
    if path is None:
        return True
    if path.suffix.lower() != ".md":
        return False
    if path.name in _EXCLUDED_BASENAMES:
        return False
    parts = set(path.parts)
    return any(directory in parts for directory in _COHORT_DIRS)


def check(content: str, path: Path | None = None) -> GrepResult:
    """Scan *content* for absolute-guarantee completion claims.

    Pre-conditions: *content* is the artifact body about to be emitted; *path*
    is its destination (used for cohort-scope restriction and exclusion).
    Post-conditions: ``result.passed`` is True when no absolute-guarantee phrase
    from the closed set appears, or when *path* is out of scope.
    """
    if not _in_scope(path):
        return GrepResult(grep=GREP_NAME, path=_path_str(path), passed=True)

    findings: list[Finding] = []
    # ``iter_prose_lines`` walks the fence-toggle loop; a claim inside a fenced
    # block is a quoted command, not a prescription. No inline-code blanking —
    # this matcher scans raw prose lines, unchanged. The column-0 fence form is
    # preserved.
    for line_number, line, _scanned in iter_prose_lines(
        content.splitlines(), fence_re=_CODE_FENCE_RE
    ):
        for kind, pattern in _CLAIM_PATTERNS:
            match = pattern.search(line)
            if match:
                findings.append(
                    Finding(line=line_number, kind=kind, text=match.group(0))
                )
    return GrepResult(
        grep=GREP_NAME,
        path=_path_str(path),
        passed=not findings,
        findings=findings,
    )


def _path_str(path: Path | None) -> str | None:
    return str(path) if path is not None else None


if __name__ == "__main__":
    sys.exit(run_grep(check, sys.argv))
