# SPDX-License-Identifier: MIT

"""Flag hedging vocabulary in prescriptive contexts.

Why this enforcement exists. The definitiveness rule M8 requires every
prescription to be unconditional or to carry the conditions that branch
its outcomes — silent hedges ("usually", "typically", "should probably")
soften prescriptions before they land, leaving the reader to guess at the
binding form. The mechanical row in the pre-emission gate scans for the
closed vocabulary and surfaces every occurrence. The operator triages
each hit on one of the three paths declared in the definitiveness rule:
promote to unconditional form with conditions named, demote to an
explicit conditional with branches enumerated, or remove the prescription
entirely (option set is underdetermined; route to inquiry).

Scope. Hits inside fenced code blocks (between triple-backtick fences) and
inside inline-code spans (single-backtick delimited) are excluded. Fenced
blocks typically quote external material, sample inputs, or commands;
inline-code spans typically cite a forbidden token meta-linguistically (a
doc that names the hedging vocabulary it forbids) rather than hedge a
prescription. Hits in prose are reported with line numbers; the operator
decides whether each hit is a genuine hedge or a quotation.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from apothem.conformity._grep_base import GrepResult, iter_prose_lines, run_grep

# The closed hedging vocabulary per the definitiveness rule M8 §Hedging
# vocabulary — eliminate or qualify — plus, as its last three entries, the
# hedging filler AGENTS.md and CLAUDE.md forbid in directive text. Word-boundary
# regex prevents partial matches inside larger words (`usually` matches;
# `unusually` does not; the plural noun `kinds of` is never matched).
HEDGING_VOCABULARY: Final[tuple[str, ...]] = (
    "maybe",
    "might",
    "could",
    "should probably",
    "usually",
    "generally",
    "typically",
    "mostly",
    "often",
    "perhaps",
    "possibly",
    "somewhat",
    "fairly",
    "roughly",
    "broadly",
    "basically",
    "kind of",
    "in some sense",
)

# The `kind of` filler hedges only as an adverb (`it is kind of required`).
# After a determiner or possessive it is a noun phrase naming a category
# (`what kind of project`, `this kind of change`) and is not reported.
KIND_OF: Final[str] = "kind of"
_KIND_OF_NOUN_DETERMINERS: Final[frozenset[str]] = frozenset(
    {
        "a",
        "an",
        "another",
        "any",
        "each",
        "every",
        "her",
        "his",
        "its",
        "my",
        "no",
        "one",
        "other",
        "our",
        "same",
        "some",
        "that",
        "the",
        "their",
        "these",
        "this",
        "those",
        "what",
        "whatever",
        "which",
        "whichever",
        "your",
    }
)
_LAST_WORD_RE: Final[re.Pattern[str]] = re.compile(r"([A-Za-z]+)\W*$")

# Compile a single combined regex to scan once per line. The `(?i)` makes the
# match case-insensitive — `Usually` at sentence start hedges identically.
HEDGING_RE: Final[re.Pattern[str]] = re.compile(
    r"(?i)\b(?:" + "|".join(re.escape(w) for w in HEDGING_VOCABULARY) + r")\b"
)

# Fenced code block delimiter. The standard Markdown form opens and closes
# with a triple backtick at column 0 (or with whitespace prefix in some
# dialects); we use the column-0 form per the host's discovered Markdown
# convention.
CODE_FENCE_RE: Final[re.Pattern[str]] = re.compile(r"^```")

# Inline-code span: a single-backtick-delimited run on one line. A hedge word
# quoted inside backticks is a meta-linguistic citation (a doc naming the
# vocabulary it forbids), not a prescription that hedges, so these spans are
# blanked before the prose scan. The column-preserving blank mirrors the
# inline-code exclusion in binding_reciprocity_grep.
INLINE_CODE_RE: Final[re.Pattern[str]] = re.compile(r"`[^`]*`")

GREP_NAME: Final[str] = "hedging-grep"
RULE_ANCHOR: Final[str] = "M8 definitiveness §Hedging"


@dataclass(frozen=True)
class Finding:
    """One hedge occurrence outside a fenced code block."""

    line: int
    match: str
    context: str
    rule: str = RULE_ANCHOR


def _is_kind_of_noun_phrase(match: re.Match[str], line: str) -> bool:
    """Return True when a ``kind of`` match follows a determiner (a noun phrase)."""
    if match.group().lower() != KIND_OF:
        return False
    previous = _LAST_WORD_RE.search(line[max(0, match.start() - 64) : match.start()])
    return previous is not None and previous.group(1).lower() in (
        _KIND_OF_NOUN_DETERMINERS
    )


def check(content: str, path: Path | None = None) -> GrepResult:
    """Scan content; return a structured result.

    Pre-conditions: `content` is the artifact body about to be emitted.
    Post-conditions: `result.passed` is True iff zero hedges were found
    outside fenced code blocks and inline-code spans.
    """
    findings: list[Finding] = []
    # ``iter_prose_lines`` walks the fence-toggle loop and blanks inline-code
    # spans (column-preservingly) so a hedge word cited inside backticks — a doc
    # that forbids the `usually` vocabulary — is read as a citation, not a
    # prescription that hedges. The column-0 fence form is unchanged.
    for line_index, line, scanned in iter_prose_lines(
        content.splitlines(),
        fence_re=CODE_FENCE_RE,
        inline_blank_re=INLINE_CODE_RE,
    ):
        for match in HEDGING_RE.finditer(scanned):
            if _is_kind_of_noun_phrase(match, scanned):
                continue
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
