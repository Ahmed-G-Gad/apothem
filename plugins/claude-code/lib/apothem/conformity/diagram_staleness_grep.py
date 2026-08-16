# SPDX-License-Identifier: MIT

"""Flag diagrams whose verification date is missing or stale.

Why this enforcement exists. The visual-leverage rule M9 declares that
every diagram in a structural artifact carries a `%% verified: YYYY-MM-DD %%`
metadata comment naming the date the diagram was last reconciled with the
underlying structure. A diagram without the marker, or with a marker more
than ninety days old, is structurally untrusted — readers cannot tell
whether the depiction reflects current reality or aspirational state.
The pre-emission gate's mechanical bar 9 (M9 visual leverage) catches both the missing marker
and the stale marker so the operator either refreshes the verification
or marks the diagram aspirational explicitly.

Detection strategy. The grep walks every Mermaid fence (between
` ```mermaid ` openings and the matching ` ``` ` closings) and inspects the
fence body for a `%% verified: YYYY-MM-DD %%` comment. Two failure modes:
the marker is absent, or its date is older than the freshness threshold
named at `STALENESS_THRESHOLD_DAYS`. Fence openings are recognised whether
they sit at column 0 or are indented (list-nested code blocks) and whether
the `mermaid` info-string carries a trailing init attribute
(` ```mermaid {init: {...}} `).

Time dependence. The stale-marker verdict is wall-clock relative: a fence
passes today and can fail tomorrow once `(today - verified).days` crosses
`STALENESS_THRESHOLD_DAYS`. The matcher is therefore non-deterministic
across calendar dates by design — the same input yields a different verdict
as the marker ages. `_today()` reads the UTC date and is the single seam a
test overrides to pin the reference date. This time dependence MUST be
weighed before the advisory verdict is ever promoted to blocking: a
blocking promotion would fail a previously-green artifact with no source
change, purely on the passage of time.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Final

from apothem.conformity._grep_base import GrepResult, run_grep

# Mermaid fence opening per the host's discovered Markdown convention. The
# language tag is `mermaid` for our visual-leverage rule's worked examples.
# Leading whitespace is tolerated so list-nested (indented) fences are
# inspected; anything after the `mermaid` info-word (an init attribute such
# as `{init: {...}}`) is accepted, but a longer word like `mermaidx` is not
# (the info-word must end at a boundary — whitespace, `{`, or end of line).
MERMAID_OPEN_RE: Final[re.Pattern[str]] = re.compile(r"^[ \t]*```mermaid(?:[ \t{].*)?$")
# A closing fence: three backticks, indentation tolerated, nothing else of
# substance after them (Markdown info-strings are only valid on the opener).
FENCE_CLOSE_RE: Final[re.Pattern[str]] = re.compile(r"^[ \t]*```[ \t]*$")

# Verified-date marker shape — `%% verified: 2026-04-28 %%`. The trailing
# `%%` is optional in some Mermaid dialects; we accept either form.
VERIFIED_DATE_RE: Final[re.Pattern[str]] = re.compile(
    r"%%\s*verified:\s*(\d{4}-\d{2}-\d{2})\s*(?:%%)?"
)

# Freshness threshold per the visual-leverage rule's staleness clause. A
# diagram older than this is flagged unless the operator has marked it
# aspirational explicitly. Ninety days matches the rule's recommended
# refresh cadence for structural artifacts.
STALENESS_THRESHOLD_DAYS: Final[int] = 90

GREP_NAME: Final[str] = "diagram-staleness-grep"
RULE_ANCHOR: Final[str] = "M9 visual-leverage §Fidelity"


@dataclass(frozen=True)
class Finding:
    """One stale or missing-verification diagram occurrence."""

    line: int
    issue: str
    detail: str
    rule: str = RULE_ANCHOR


def _today() -> date:
    """Return today's UTC date — separated for testability."""
    return datetime.now(tz=timezone.utc).date()


def _find_mermaid_fences(lines: list[str]) -> list[tuple[int, int]]:
    """Locate `(open_line, close_line)` pairs for every Mermaid fence.

    Lines are 1-indexed in the returned tuples. A fence whose closing
    delimiter is absent (truncated artifact) is omitted.
    """
    fences: list[tuple[int, int]] = []
    open_line: int | None = None
    for index, line in enumerate(lines, start=1):
        if open_line is None:
            if MERMAID_OPEN_RE.match(line):
                open_line = index
            continue
        if FENCE_CLOSE_RE.match(line):
            fences.append((open_line, index))
            open_line = None
    return fences


def _verified_date(fence_body: list[str]) -> date | None:
    """Parse the verified-date marker out of a Mermaid fence body."""
    for line in fence_body:
        match = VERIFIED_DATE_RE.search(line)
        if match is None:
            continue
        try:
            return date.fromisoformat(match.group(1))
        except ValueError:
            # The marker present but date unparseable — treated as missing
            # so the operator re-emits the marker in the canonical shape.
            return None
    return None


def check(content: str, path: Path | None = None) -> GrepResult:
    """Scan content; return a structured result.

    Pre-conditions: `content` is the artifact body about to be emitted.
    Post-conditions: `result.passed` is True iff every Mermaid fence
    carries a verified-date marker no older than `STALENESS_THRESHOLD_DAYS`.
    """
    lines = content.splitlines()
    today = _today()
    findings: list[Finding] = []
    for open_line, close_line in _find_mermaid_fences(lines):
        body = lines[open_line : close_line - 1]
        verified = _verified_date(body)
        if verified is None:
            findings.append(
                Finding(
                    line=open_line,
                    issue="missing verified-date marker",
                    detail=(
                        "Mermaid fence has no `%% verified: YYYY-MM-DD %%` "
                        "comment; structural artifacts require the marker "
                        "per the visual-leverage rule."
                    ),
                )
            )
            continue
        age_days = (today - verified).days
        if age_days > STALENESS_THRESHOLD_DAYS:
            findings.append(
                Finding(
                    line=open_line,
                    issue="stale verified-date marker",
                    detail=(
                        f"Verified {verified.isoformat()} ({age_days} days "
                        f"ago); freshness ceiling is "
                        f"{STALENESS_THRESHOLD_DAYS} days."
                    ),
                )
            )
    return GrepResult(
        grep=GREP_NAME,
        path=str(path) if path is not None else None,
        passed=not findings,
        findings=findings,
    )


if __name__ == "__main__":
    sys.exit(run_grep(check, sys.argv))
