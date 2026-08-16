# SPDX-License-Identifier: MIT

"""Flag magic numbers in source code.

Why this enforcement exists. The code-craft rule M13.10 forbids unnamed
numeric literals in business logic — every threshold, retry count, or
buffer size that varies by behavior is a named constant. Inline literals
hide intent, fragment the configuration surface, and resist tuning. The
pre-emission gate's mechanical bar 13 (M13.10 code craft) catches numeric literals appearing
in logical contexts and surfaces each so the operator either names the
constant or exempts it (see exemption list below).

Detection strategy. The grep walks Python source, locates every numeric
literal not in an exempt context, and reports duplicates within a single
file (two or more occurrences of the same value strongly indicate the
literal should be a named constant). Recognised literal forms are decimal
integers and floats, scientific notation, and base-prefixed hexadecimal
(``0xFF``), binary (``0b1010``), and octal (``0o17``) — the base prefixes
match as whole literals, not as a bare leading ``0``. A binary-subtraction
minus (``x - 3`` and ``x-3`` alike) is normalised so the literal keys on
``3`` symmetrically; a unary sign (``= -3``) is kept with the literal.
Exemptions: the integers 0, 1, -1, 2
(idiomatic boundary values — 0, 1, -1 are sentinel and index bounds; 2 is
the binary/pairwise constant — matching the `EXEMPT_VALUES` frozenset
below); literals inside type annotations / default-
argument constants of `Final` form; literals inside `__all__` and
similar metadata. The threshold (literal must appear at least
`MIN_OCCURRENCES_FOR_FINDING` times in a file) is a named constant.
"""

from __future__ import annotations

import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from apothem.conformity._grep_base import GrepResult, run_grep

# Numeric literals: hex, binary, octal, then decimal int / float /
# scientific. The base-prefixed alternatives lead so ``0xFF`` matches the
# whole literal rather than a bare ``0`` (the prior single-branch pattern's
# lookbehind blocked the digits after ``0x`` / ``0b`` / ``0o``, contradicting
# the docstring's hex/binary/octal claim). Each alternative's leading
# lookbehind ``(?<![A-Za-z_0-9.])`` excludes a literal glued to an
# identifier (``var1``) or the fractional tail of a longer number.
#
# The optional leading ``-`` is captured only when the minus is unary — a
# true sign, not a binary subtraction. ``_UNARY_MINUS_PREFIX`` (applied by
# the caller before matching) neutralises a subtraction ``x - 3`` /
# ``x-3`` so the literal keys on ``3`` symmetrically regardless of the
# surrounding whitespace; a genuine sign (``= -3``, ``return -3``, ``(-3``)
# survives because no operand precedes it.
_SIGN: Final[str] = r"-?"
NUMERIC_LITERAL_RE: Final[re.Pattern[str]] = re.compile(
    r"(?<![A-Za-z_0-9.])" + _SIGN + r"(?:"
    r"0[xX][0-9A-Fa-f]+"  # hexadecimal
    r"|0[bB][01]+"  # binary
    r"|0[oO][0-7]+"  # octal
    r"|\d+(?:\.\d+)?(?:[eE][+-]?\d+)?"  # decimal int / float / scientific
    r")"
)

# Keywords that syntactically introduce a unary operand context: a ``-``
# after one of these is a sign, not a subtraction. ``return -3`` /
# ``yield -3`` keep the sign; the token is excluded from binary-minus
# normalisation. Python ``re`` forbids variable-width lookbehind, so the
# keyword check is done in code (``_normalize_binary_minus``) rather than
# in the pattern.
_UNARY_KEYWORDS: Final[frozenset[str]] = frozenset(
    {
        "return",
        "yield",
        "and",
        "or",
        "not",
        "in",
        "is",
        "if",
        "elif",
        "else",
        "while",
        "assert",
        "await",
        "lambda",
    }
)

# Candidate binary-subtraction minus: a ``-`` preceded by an operand token
# (identifier char, closing bracket, or ``.``) with optional whitespace on
# either side, and followed by a numeric literal. ``_normalize_binary_minus``
# additionally rejects a preceding unary-context keyword before rewriting.
_BINARY_MINUS_RE: Final[re.Pattern[str]] = re.compile(
    r"(?P<lead>[A-Za-z_0-9)\]}.])(?P<gap>\s*-\s*)(?=\d|0[xXbBoO])"
)
# The identifier token ending at a candidate ``-``; used to test whether the
# operand is actually a unary-context keyword (``return``, ``yield``, …).
_TRAILING_WORD_RE: Final[re.Pattern[str]] = re.compile(r"[A-Za-z_][A-Za-z_0-9]*$")


def _normalize_binary_minus(text: str) -> str:
    """Rewrite binary-subtraction ``-`` to a plain space so the literal keys
    on its magnitude regardless of spacing (``x - 3`` and ``x-3`` alike).

    A ``-`` preceded by a genuine operand is subtraction; the minus is
    dropped so the trailing literal is counted under its bare value. A ``-``
    that follows a unary-context keyword (``return -3``) or no operand at
    all (``= -3``) is a sign and is left attached to the literal.
    """

    def _replace(match: re.Match[str]) -> str:
        lead = match.group("lead")
        # A word operand that is actually a unary keyword is not subtraction.
        if lead.isalnum() or lead == "_":
            prefix = text[: match.start("gap")]
            word_match = _TRAILING_WORD_RE.search(prefix)
            if word_match is not None and word_match.group() in _UNARY_KEYWORDS:
                return match.group()
        return f"{lead} "

    return _BINARY_MINUS_RE.sub(_replace, text)


# Idiomatic boundary values that are exempt from the magic-number rule
# even when repeated (loop bounds, list indices, sentinel returns).
EXEMPT_VALUES: Final[frozenset[str]] = frozenset({"0", "1", "-1", "2"})
# Literals appearing only on lines that look like assignments to a
# constant-named target (UPPER_SNAKE_CASE) or a `Final` annotation are
# already named — exempt those lines.
#
# Scope: this pattern is matched per physical line (``check`` iterates
# ``content.splitlines()``), so it exempts only a single-line assignment
# whose target and ``=`` sit on the same line. A constant assignment whose
# value spans a continuation (a bracketed literal broken across lines, or a
# backslash continuation) is exempt only on its first line; literals on the
# wrapped continuation lines are still scanned. Multi-line named-constant
# exemption is intentionally out of scope — the single-line form covers the
# canonical ``NAME: Final[int] = N`` shape the rule targets.
NAMED_CONSTANT_LINE_RE: Final[re.Pattern[str]] = re.compile(
    r"^\s*[A-Z][A-Z0-9_]*\s*(?::\s*Final\b[^=]*)?\s*="
)
# Comment lines (Python `#`) are excluded since they may quote sample
# values that are not load-bearing.
COMMENT_LINE_RE: Final[re.Pattern[str]] = re.compile(r"^\s*#")
# String-literal exclusion: a number inside a quoted string is a value
# in a data context, not a logic literal. The conservative regex below
# strips single- and double-quoted spans before matching.
STRING_SPAN_RE: Final[re.Pattern[str]] = re.compile(
    r"'(?:\\.|[^'\\])*'|\"(?:\\.|[^\"\\])*\""
)
# Triple-quoted span exclusion: module / class / function docstrings and
# any other triple-quoted block live in a documentation context, not a
# logic context. The single-line STRING_SPAN_RE above does not catch
# them because triple-quoted spans cross line boundaries. The regex
# below matches a non-greedy run between matched triple-quote delimiters
# (single- or double-quote variants) across newlines via [\s\S]; the
# stripping helper preserves line breaks so finding line numbers remain
# stable against the original source.
TRIPLE_QUOTED_SPAN_RE: Final[re.Pattern[str]] = re.compile(
    r"'''[\s\S]*?'''|\"\"\"[\s\S]*?\"\"\""
)

# Minimum repeat count that triggers a finding. A single literal use
# rarely warrants a named constant; two or more uses of the same value
# is the canonical magic-number signal.
MIN_OCCURRENCES_FOR_FINDING: Final[int] = 2

# Documentation file suffixes excluded from the magic-number sweep.
# M13.10 is a code-craft rule scoped to source-language artifacts;
# Markdown / reST / plain-text files carry list indices, dates, version
# pins, and other numerals that are values in a documentation context,
# not logic literals. The exclusion mirrors the rule's semantic scope
# (the docstring already declares "walks Python source"). Configuration
# files (JSON / YAML / TOML) carry values by definition and are
# similarly exempt.
NON_CODE_SUFFIXES: Final[frozenset[str]] = frozenset(
    {
        ".md",
        ".markdown",
        ".rst",
        ".txt",
        ".json",
        ".yaml",
        ".yml",
        ".toml",
    }
)

# Documentation / data-manifest basenames excluded from the magic-number
# sweep where the file carries no recognized suffix. Mirrors the
# NON_CODE_SUFFIXES rationale: numerals are values in a manifest context,
# not logic literals.
NON_CODE_BASENAMES: Final[frozenset[str]] = frozenset(
    {
        ".SRCINFO",
    }
)

GREP_NAME: Final[str] = "magic-number-grep"
RULE_ANCHOR: Final[str] = "M13.10 magic numbers"


@dataclass(frozen=True)
class Finding:
    """One unnamed numeric literal repeated across the inspected file.

    Pre-conditions: ``value`` is the literal as written (so ``3`` and ``-3``
    are distinct findings); ``occurrences`` lists every 1-based line the
    literal appears on, and its length is what crosses the repetition
    threshold. Post-conditions: ``rule`` defaults to :data:`RULE_ANCHOR`,
    which points at the named-constant discipline the literal should satisfy.
    """

    value: str
    occurrences: list[int]
    rule: str = RULE_ANCHOR


def _strip_strings_and_comments(line: str) -> str:
    """Remove quoted string spans; return empty if the line is a comment.

    After stripping strings, a binary-subtraction minus (``x - 3``, ``x-3``)
    is normalised to a single space so the trailing literal keys on ``3``
    regardless of surrounding whitespace — closing the asymmetry where the
    two spacings counted the same subtraction under ``3`` versus ``-3``.
    """
    if COMMENT_LINE_RE.match(line):
        return ""
    stripped = STRING_SPAN_RE.sub("", line)
    return _normalize_binary_minus(stripped)


def _strip_triple_quoted_spans(content: str) -> str:
    """Remove triple-quoted spans, preserving line breaks for stable line numbers.

    Replaces every triple-quoted span with a string of newlines equal to
    the number of newlines the span covered, so line indices in the
    post-strip content align with line indices in the original source.
    """
    return TRIPLE_QUOTED_SPAN_RE.sub(
        lambda m: "\n" * m.group().count("\n"),
        content,
    )


def check(content: str, path: Path | None = None) -> GrepResult:
    """Scan content; return a structured result.

    Documentation and configuration-file suffixes (per ``NON_CODE_SUFFIXES``)
    are exempt — the rule scopes to source-language artifacts; numerals
    appearing in documentation indices, dates, version pins, and config
    values are values in a non-code context, not logic literals.

    Triple-quoted spans (module / class / function docstrings, multi-line
    string literals) are stripped before line iteration so numerals in
    documentation prose do not surface as logic-literal findings.
    """
    if path is not None and (
        path.suffix.lower() in NON_CODE_SUFFIXES or path.name in NON_CODE_BASENAMES
    ):
        return GrepResult(grep=GREP_NAME, path=str(path), passed=True)
    content = _strip_triple_quoted_spans(content)
    occurrences: dict[str, list[int]] = defaultdict(list)
    for index, raw_line in enumerate(content.splitlines(), start=1):
        if NAMED_CONSTANT_LINE_RE.match(raw_line):
            continue
        cleaned = _strip_strings_and_comments(raw_line)
        for match in NUMERIC_LITERAL_RE.finditer(cleaned):
            value = match.group()
            if value in EXEMPT_VALUES:
                continue
            occurrences[value].append(index)
    findings: list[Finding] = [
        Finding(value=value, occurrences=lines)
        for value, lines in sorted(occurrences.items())
        if len(lines) >= MIN_OCCURRENCES_FOR_FINDING
    ]
    return GrepResult(
        grep=GREP_NAME,
        path=str(path) if path is not None else None,
        passed=not findings,
        findings=findings,
    )


if __name__ == "__main__":
    sys.exit(run_grep(check, sys.argv))
