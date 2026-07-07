# SPDX-License-Identifier: MIT

"""Flag binding declarations using non-canonical arrow notation.

Why this enforcement exists. The bidirectional-binding rule M10 declares
five canonical arrows — `→` (Drives), `←` (Driven by), `↑` (Established by),
`↓` (rare downward; reserved), and `↔` (Cross-bound with) — that every
Bindings section uses verbatim. ASCII substitutes (`->`, `<-`, `<->`, `<=`,
`=>`) are notation drift; they break sibling-convergence and the mechanical
reciprocity walk that future cross-file matchers will perform. This grep
enforces the arrow notation inside the Bindings section: when a Bindings
section is present, no forbidden ASCII arrow may appear in the Bindings
region. A file with no Bindings section passes vacuously.

Cross-file reciprocity check (full half-edge detection across the rule set)
is out of scope for this per-file grep — it requires a corpus walk that
the orchestrator at `gate.py` will assemble. The per-file
contribution here is the notation discipline within each Bindings section.

Code is excluded from the arrow scan: fenced code blocks and inline-code spans
inside a Bindings section legitimately quote ASCII arrows (a Python return
annotation, a shell pipe, a CLI usage snippet), which are quotations rather than
Bindings notation.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from apothem.conformity._grep_base import GrepResult, iter_prose_lines, run_grep

# The canonical Bindings section heading per the §0.j five-direction notation.
# Rule files use `## Bindings (§0.j five-direction)`; some siblings drop the
# parenthetical. Both are accepted as valid section markers; the grep starts
# scanning at the first match and stops at the next H1/H2 heading.
BINDINGS_HEADING_RE: Final[re.Pattern[str]] = re.compile(
    r"^##\s+Bindings(?:\s+\(§0\.j\s+five-direction\))?\s*$"
)
NEXT_HEADING_RE: Final[re.Pattern[str]] = re.compile(r"^##?\s+\S")

# ASCII substitute arrows that are notation drift. The rule's spec lists
# them explicitly as forbidden alternatives.
FORBIDDEN_ARROWS: Final[tuple[str, ...]] = (
    "->",
    "<-",
    "<->",
    "<=",
    "=>",
)
FORBIDDEN_ARROW_RE: Final[re.Pattern[str]] = re.compile(
    "|".join(re.escape(a) for a in FORBIDDEN_ARROWS)
)

# The canonical arrow alphabet. Any character outside this set inside an arrow
# context is suspect, but we only flag the explicit ASCII substitutes since
# free-form prose may legitimately contain any Unicode character.
CANONICAL_ARROWS: Final[frozenset[str]] = frozenset({"→", "←", "↑", "↓", "↔"})

# Code spans inside the Bindings section legitimately quote ASCII arrows — a
# Python return annotation (`f() -> str`), a shell pipe, a CLI usage snippet —
# so fenced blocks and inline-code spans are excluded from the arrow scan.
_CODE_FENCE_RE: Final[re.Pattern[str]] = re.compile(r"^```")
_INLINE_CODE_RE: Final[re.Pattern[str]] = re.compile(r"`[^`]*`")

GREP_NAME: Final[str] = "binding-reciprocity-grep"
RULE_ANCHOR: Final[str] = "M10 bidirectional-binding §Notation"


@dataclass(frozen=True)
class Finding:
    """One notation-drift occurrence inside the Bindings section."""

    line: int
    match: str
    context: str
    rule: str = RULE_ANCHOR


def _bindings_region(lines: list[str]) -> tuple[int, int] | None:
    """Locate the Bindings section as a (start, end) line-range pair.

    Returns a 1-indexed inclusive start line and exclusive end line, or
    None if no Bindings section is present in the artifact.
    """
    start: int | None = None
    for i, line in enumerate(lines):
        if start is None:
            if BINDINGS_HEADING_RE.match(line):
                start = i + 1  # First content line after the heading.
            continue
        # Past the heading; the section ends at the next heading.
        if NEXT_HEADING_RE.match(line):
            return start, i
    if start is not None:
        return start, len(lines)
    return None


def check(content: str, path: Path | None = None) -> GrepResult:
    """Scan content; return a structured result.

    Pre-conditions: `content` is the artifact body about to be emitted.
    Post-conditions: `result.passed` is True when either the Bindings
    section is absent (not every artifact has one) or the section uses
    only canonical arrow notation.
    """
    lines = content.splitlines()
    region = _bindings_region(lines)
    if region is None:
        return GrepResult(
            grep=GREP_NAME,
            path=str(path) if path is not None else None,
            passed=True,
        )
    findings: list[Finding] = []
    start, end = region
    # ``iter_prose_lines`` walks the fence-toggle loop and blanks inline-code
    # spans (column-preservingly) so a quoted ASCII arrow inside backticks — a
    # Python return annotation, a shell pipe — is not read as notation drift.
    # The scan is confined to the Bindings region via the pre-sliced lines and
    # ``start`` offset, preserving the reported line numbers exactly.
    for offset, line, scanned in iter_prose_lines(
        lines[start - 1 : end],
        fence_re=_CODE_FENCE_RE,
        inline_blank_re=_INLINE_CODE_RE,
        start=start,
    ):
        for match in FORBIDDEN_ARROW_RE.finditer(scanned):
            findings.append(
                Finding(
                    line=offset,
                    match=match.group(),
                    context=line.strip(),
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
