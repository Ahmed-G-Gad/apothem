# SPDX-License-Identifier: MIT

"""Flag substantial commented-out code blocks left in source.

Why this enforcement exists. The code-craft rule M13.1 forbids commented-
out source code: source control is the canonical archive. Why-not-what
comments are welcome; disabled logic is not. The pre-emission gate's
mechanical bar 13 (M13 code craft) catches multi-line runs of comment-prefixed lines that
contain code-shaped tokens and surfaces each block so the operator
restores the code or deletes the dead block.

Detection: a per-language comment-prefix table identifies the prefix; the
grep accumulates consecutive prefixed lines whose stripped bodies clear a
corroborated code-shape bar. A line counts as code only when it satisfies
at least two distinct code-shape axes (definition keyword, name=value,
name(args), arrow, subscript, attribute-call, statement terminator) — or
one control-flow keyword backed by a concrete punctuation axis. A single
incidental axis (a lone English keyword such as `if`/`for`/`from`, or a
prose parenthetical like `profile (see below)`) is prose-ambiguous and
does not qualify. A run of three or more qualifying lines is a finding;
pure prose comments (headers, citations, why-not-what explanations) pass
clean.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from apothem.conformity._grep_base import GrepResult, run_grep


@dataclass(frozen=True)
class CommentPrefix:
    """One language's line-comment prefix and the file extensions it covers."""

    label: str
    prefix: str
    extensions: tuple[str, ...]


# Per-language line-comment prefixes. The set covers the languages the
# host project commonly emits (Python, shell, YAML, TOML use `#`; the
# C-family languages and JavaScript use `//`). The label is the language
# name shown in the finding so the operator can route the cleanup.
COMMENT_PREFIXES: Final[tuple[CommentPrefix, ...]] = (
    CommentPrefix(
        "hash-prefix (Python / shell / YAML / TOML / Ruby)",
        "#",
        (".py", ".sh", ".bash", ".ps1", ".yml", ".yaml", ".toml", ".rb"),
    ),
    CommentPrefix(
        "slash-slash (JS / TS / Go / Rust / C / C++ / Java / Swift)",
        "//",
        (
            ".js",
            ".ts",
            ".tsx",
            ".jsx",
            ".go",
            ".rs",
            ".c",
            ".cpp",
            ".h",
            ".hpp",
            ".java",
            ".swift",
            ".kt",
        ),
    ),
)

# Code-shape signature classes. Each entry is one independent axis of
# "this looks like code, not prose". A prose sentence routinely trips a
# single axis — an English keyword such as `if`/`for`/`from`/`use`, or an
# incidental `name(args)` shape like `profile (see below)` — so a
# one-axis match is not evidence of commented-out code. A line is treated
# as code only when it satisfies at least ``MIN_SIGNATURE_CLASSES``
# distinct axes (or carries a control-flow keyword together with a
# code-punctuation axis). This is the false-positive class that demoted
# the matcher to advisory (gate.py:398-402): prose runs matched on a lone
# keyword. Splitting the axes lets the caller demand corroboration.
#
# The keyword axes exclude the prose-ambiguous English words (`if`, `for`,
# `from`, `with`, `type`, `use`, `else`) — those are kept only in the
# control-flow axis, which never fires alone.
_KEYWORD_CLASSES: Final[tuple[tuple[str, re.Pattern[str]], ...]] = (
    (
        "definition-keyword",
        re.compile(
            r"\b(?:def|class|import|lambda|async|await|yield|raise|assert|"
            r"function|const|let|var|require|export|module|interface|"
            r"struct|enum|impl|fn|pub|package|new|throw|delete|typeof|"
            r"instanceof|extends|implements)\b"
        ),
    ),
    ("assignment", re.compile(r"[A-Za-z_]\w*\s*=\s*[^=]")),  # `name = value`
    # `name(args)` — no space between the callee and `(`, per Python/JS/C
    # call syntax. Disallowing the space excludes prose parentheticals such
    # as `profile (see below)` (space before the paren), the canonical
    # false-positive shape this matcher was demoted over.
    ("call", re.compile(r"[A-Za-z_]\w*\([^)]*\)")),
    ("arrow", re.compile(r"->|=>")),  # arrow functions / return-type hints
    ("subscript", re.compile(r"[A-Za-z_]\w*\[[^\]]*\]")),  # `name[key]`
    ("attribute-call", re.compile(r"\.\w+\s*\(")),  # `obj.method(`
    ("statement-terminator", re.compile(r";\s*\S")),  # `stmt; stmt`
    # Comparison / augmented operators — `!=`, `==`, `>=`, `<=`, `+=` … —
    # are code punctuation that prose does not carry; the `=` axis above
    # deliberately excludes `==`, so this axis catches the comparison forms.
    ("comparison", re.compile(r"[=!<>+\-*/%&|^]=|<<|>>")),
    # A statement/expression line closing on a `:` after a code-ish token —
    # a block header (`if x:`, `for y in z:`, `def f():`) or dict/slice — is
    # a strong code signal; prose sentences do not end on a bare colon.
    ("block-colon", re.compile(r"[)\w\]]\s*:\s*$")),
)

# Control-flow keywords that read as ordinary English words in prose
# (`if the value ...`, `return early`, `from the loop`). They corroborate
# a code shape but never establish one on their own — a control-flow hit
# counts only when a non-keyword axis also fires on the same line.
_CONTROL_FLOW_RE: Final[re.Pattern[str]] = re.compile(
    r"\b(?:return|if|elif|else|for|while|try|except|finally|with|from|"
    r"type|use)\b"
)

# Minimum distinct code-shape axes a commented line must satisfy to count
# as code rather than prose. A single incidental axis (one keyword, or a
# lone parenthetical) is prose-ambiguous; two independent axes — or one
# control-flow keyword backed by a punctuation axis — is code.
MIN_SIGNATURE_CLASSES: Final[int] = 2

# Minimum consecutive commented-code lines that constitute a block. Two-line
# runs are typically a TODO + a code snippet; three or more is a definitive
# block per the rule's intent.
MIN_BLOCK_LINES: Final[int] = 3

GREP_NAME: Final[str] = "commented-out-code-grep"
RULE_ANCHOR: Final[str] = "M13.1 why-not-what comments"


@dataclass(frozen=True)
class Finding:
    """One commented-out-code block occurrence."""

    start_line: int
    end_line: int
    language: str
    line_count: int
    rule: str = RULE_ANCHOR


def _select_prefix(path: Path | None) -> CommentPrefix:
    """Return the comment prefix matching the file extension, or hash by default.

    Stdin input has no extension — the hash prefix is the conservative default
    since it covers the largest surface in this ecosystem.
    """
    if path is not None:
        suffix = path.suffix.lower()
        for entry in COMMENT_PREFIXES:
            if suffix in entry.extensions:
                return entry
    return COMMENT_PREFIXES[0]


def _is_commented_code(stripped_body: str) -> bool:
    """Decide whether a commented line's body looks like code rather than prose.

    A line counts as code only when it satisfies at least
    ``MIN_SIGNATURE_CLASSES`` distinct code-shape axes, or one control-flow
    keyword corroborated by at least one non-keyword axis. A lone axis — one
    keyword, or an incidental parenthetical such as ``profile (see below)`` —
    is prose-ambiguous and does not qualify, closing the false-positive class
    that demoted this matcher to advisory.
    """
    non_keyword_hits = sum(
        1 for _label, pattern in _KEYWORD_CLASSES if pattern.search(stripped_body)
    )
    if non_keyword_hits >= MIN_SIGNATURE_CLASSES:
        return True
    has_control_flow = _CONTROL_FLOW_RE.search(stripped_body) is not None
    # A control-flow keyword is code only when a concrete code-shape axis
    # (assignment, call, arrow, subscript, terminator) also fires — prose
    # sentences carry the keyword alone.
    return has_control_flow and non_keyword_hits >= 1


def check(content: str, path: Path | None = None) -> GrepResult:
    """Scan content; return a structured result.

    Pre-conditions: `content` is the source body about to be emitted.
    Post-conditions: `result.passed` is True iff no run of
    `MIN_BLOCK_LINES` or more consecutive commented lines contains
    code-shaped tokens.
    """
    prefix = _select_prefix(path)
    findings: list[Finding] = []
    run_start: int | None = None
    run_length = 0

    def flush(end_line: int) -> None:
        if run_start is not None and run_length >= MIN_BLOCK_LINES:
            findings.append(
                Finding(
                    start_line=run_start,
                    end_line=end_line,
                    language=prefix.label,
                    line_count=run_length,
                )
            )

    for line_index, line in enumerate(content.splitlines(), start=1):
        stripped = line.lstrip()
        is_comment = stripped.startswith(prefix.prefix)
        body = stripped[len(prefix.prefix) :].strip() if is_comment else ""
        if not is_comment or not _is_commented_code(body):
            flush(line_index - 1)
            run_start = None
            run_length = 0
            continue
        if run_start is None:
            run_start = line_index
            run_length = 1
        else:
            run_length += 1
    if run_start is not None:
        flush(run_start + run_length - 1)
    return GrepResult(
        grep=GREP_NAME,
        path=str(path) if path is not None else None,
        passed=not findings,
        findings=findings,
    )


if __name__ == "__main__":
    sys.exit(run_grep(check, sys.argv))
