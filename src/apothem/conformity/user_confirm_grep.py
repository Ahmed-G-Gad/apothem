# SPDX-License-Identifier: MIT

"""Block emission of artifacts containing unresolved authority placeholders.

Why this enforcement exists. Required-category inquiries (identity, scope
direction, security, public-surface naming) emit a `<USER-CONFIRM:id=...>`
placeholder that the operator must resolve before the artifact ships. An
unfilled placeholder reaching emission means a required-data inquiry was
never closed; the artifact would silently bind to fabricated authority data
the moment it lands. The pre-emission gate's mechanical bar 5 (M5 authority) catches the
literal placeholder shape so the operator never has to remember.

Invocation. Two surfaces: as a callable for the orchestrator (`check(content,
path)`), or as a CLI tool (`python user-confirm-grep.py <file>` / `--stdin`).
Exit code 0 indicates clean; non-zero indicates a finding. Stdout carries a
JSON report regardless of outcome — the orchestrator reads it; humans read
it for triage.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from apothem.conformity._grep_base import GrepResult, run_grep

# The canonical placeholder shape declared in the authority-inquiry rule §10.
# `<USER-CONFIRM:id=foo>`, `<USER-CONFIRM:kind=bar>`, and bare `<USER-CONFIRM>`
# all flag — the colon-id form is the documented contract; the bare form is
# rare but equally non-conformant.
PLACEHOLDER_RE: Final[re.Pattern[str]] = re.compile(r"<USER-CONFIRM(?::[^>]*)?>")

GREP_NAME: Final[str] = "user-confirm-grep"
RULE_ANCHOR: Final[str] = "M5 authority-inquiry §10"


@dataclass(frozen=True)
class Finding:
    """One placeholder occurrence in the artifact body."""

    line: int
    match: str
    rule: str = RULE_ANCHOR


def check(content: str, path: Path | None = None) -> GrepResult:
    """Scan content; return a structured result.

    Pre-conditions: `content` is the artifact body about to be emitted.
    Post-conditions: `result.passed` is True iff zero placeholders were found.
    Failure mode: malformed UTF-8 raises `UnicodeDecodeError` at the read site,
    not here — this function operates on already-decoded text.
    """
    findings: list[Finding] = []
    for match in PLACEHOLDER_RE.finditer(content):
        # Convert byte offset to a 1-indexed line number for human triage.
        line = content.count("\n", 0, match.start()) + 1
        findings.append(Finding(line=line, match=match.group()))
    return GrepResult(
        grep=GREP_NAME,
        path=str(path) if path is not None else None,
        passed=not findings,
        findings=findings,
    )


if __name__ == "__main__":
    sys.exit(run_grep(check, sys.argv))
