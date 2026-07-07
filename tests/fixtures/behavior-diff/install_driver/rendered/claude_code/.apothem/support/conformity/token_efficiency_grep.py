# SPDX-License-Identifier: MIT

"""Flag filler phrases, throat-clearing openers, and content-free qualifiers.

Why this enforcement exists. The clean-room generation rule §5 (Prose and
Documentation) and the token-efficiency rewrite rule require every sentence
to advance the artifact's purpose. Filler ("In this section, we will…"),
throat-clearing ("Before diving in…"), restatement openers, and
content-free qualifiers ("very", "quite", "rather", "fairly") consume
tokens without carrying semantic load. The mechanical matcher surfaces
each occurrence so the operator can either delete the phrase, replace it
with substantive content, or — for qualifiers — substitute a measured
form ("twice as fast" rather than "very fast").

Scope. Hits inside fenced code blocks (between triple-backtick fences),
inline-code spans (single-backtick delimited), quoted blocks (lines
starting `>`), and HTML comment regions are excluded. These typically carry
external material, sample inputs, preserved conversation, or — for inline
code — a forbidden phrase cited meta-linguistically (a doc that names the
filler vocabulary it forbids) rather than the artifact's own prescriptive
prose.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from apothem.conformity._grep_base import GrepResult, run_grep

# Multi-word filler phrases and throat-clearing openers. Matched
# case-insensitively against the line text. These patterns are
# multi-word, so word-boundary anchors at the ends suffice.
FILLER_PHRASES: Final[tuple[str, ...]] = (
    r"In this section, we will",
    r"It is important to note",
    r"As mentioned earlier",
    r"Before diving in",
    r"Without further ado",
    r"Let's begin by",
    r"Before we discuss",
    r"To begin with",
    r"First and foremost",
    r"kind of",
)

# Single-word content-free qualifiers that flag unconditionally. Separated
# from the multi-word phrases so each carries word-boundary anchors and
# matches only when standing alone (not as a substring of a larger word).
# "rather" is intentionally NOT here: it needs a context exclusion (see
# RATHER_QUALIFIER_RE) because the comparative "rather than" carries
# semantic load and is not a content-free qualifier.
QUALIFIER_WORDS: Final[tuple[str, ...]] = (
    "very",
    "quite",
    "somewhat",
    "fairly",
)

FILLER_RE: Final[re.Pattern[str]] = re.compile(
    r"(?i)(?:" + "|".join(FILLER_PHRASES) + r")"
)

QUALIFIER_RE: Final[re.Pattern[str]] = re.compile(
    r"(?i)\b(?:" + "|".join(QUALIFIER_WORDS) + r")\b"
)

# "rather" is a content-free qualifier as a bare intensifier ("rather slow",
# "rather large") but carries semantic load in the comparative construction
# "rather than" ("X rather than Y" expresses a deliberate contrast — the kind
# of measured form §5 endorses, not filler). The negative lookahead excludes
# the comparative form so legitimate comparative prose is not flagged; the
# bare-intensifier form still matches.
RATHER_QUALIFIER_RE: Final[re.Pattern[str]] = re.compile(r"(?i)\brather\b(?!\s+than\b)")

# Every qualifier regex contributes findings. The order is fixed so the
# matcher's output is deterministic across runs.
QUALIFIER_RES: Final[tuple[re.Pattern[str], ...]] = (
    QUALIFIER_RE,
    RATHER_QUALIFIER_RE,
)

CODE_FENCE_RE: Final[re.Pattern[str]] = re.compile(r"^```")
# Inline-code span: a single-backtick-delimited run on one line. A filler
# phrase or qualifier quoted inside backticks is a meta-linguistic citation
# (a doc naming the vocabulary it forbids), not prose that uses it, so these
# spans are blanked before the scan. The column-preserving blank mirrors the
# inline-code exclusion in binding_reciprocity_grep.
INLINE_CODE_RE: Final[re.Pattern[str]] = re.compile(r"`[^`]*`")
QUOTE_LINE_RE: Final[re.Pattern[str]] = re.compile(r"^\s*>")
HTML_COMMENT_OPEN_RE: Final[re.Pattern[str]] = re.compile(r"<!--")
HTML_COMMENT_CLOSE_RE: Final[re.Pattern[str]] = re.compile(r"--!?>")

GREP_NAME: Final[str] = "token-efficiency-grep"
RULE_ANCHOR: Final[str] = "clean-room-generation §5 + token-efficiency-rewrite"


@dataclass(frozen=True)
class Finding:
    """One filler or qualifier occurrence outside an excluded region."""

    line: int
    match: str
    context: str
    rule: str = RULE_ANCHOR


def check(content: str, path: Path | None = None) -> GrepResult:
    """Scan content; return a structured result.

    Pre-conditions: `content` is the artifact body about to be emitted.
    Post-conditions: `result.passed` is True iff zero filler phrases and
    zero content-free qualifiers were found outside fenced code blocks,
    inline-code spans, quoted lines, or HTML comment regions.
    """
    findings: list[Finding] = []
    inside_fence = False
    inside_html_comment = False
    for line_index, line in enumerate(content.splitlines(), start=1):
        if CODE_FENCE_RE.match(line):
            inside_fence = not inside_fence
            continue
        if inside_fence:
            continue
        # Track HTML comment span. A single-line comment opens and closes
        # on the same line; a multi-line comment spans several lines.
        working = line
        if inside_html_comment:
            close = HTML_COMMENT_CLOSE_RE.search(working)
            if close is None:
                continue
            inside_html_comment = False
            working = working[close.end() :]
        # Strip inline comments and detect a trailing open.
        while True:
            open_match = HTML_COMMENT_OPEN_RE.search(working)
            if open_match is None:
                break
            close_match = HTML_COMMENT_CLOSE_RE.search(working, open_match.end())
            if close_match is None:
                working = working[: open_match.start()]
                inside_html_comment = True
                break
            working = working[: open_match.start()] + working[close_match.end() :]
        # Blank inline-code spans (same-length spaces preserve columns) so a
        # filler phrase or qualifier cited inside backticks — a doc that
        # forbids the `kind of` phrasing — is read as a citation, not prose.
        working = INLINE_CODE_RE.sub(lambda m: " " * len(m.group(0)), working)
        if QUOTE_LINE_RE.match(working):
            continue
        if not working.strip():
            continue
        for match in FILLER_RE.finditer(working):
            findings.append(
                Finding(
                    line=line_index,
                    match=match.group(),
                    context=line.strip(),
                )
            )
        for qualifier_re in QUALIFIER_RES:
            for match in qualifier_re.finditer(working):
                findings.append(
                    Finding(
                        line=line_index,
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
