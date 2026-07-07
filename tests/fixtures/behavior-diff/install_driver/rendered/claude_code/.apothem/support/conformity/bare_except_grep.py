# SPDX-License-Identifier: MIT

"""Flag bare except clauses without typed exceptions or re-raise.

Why this enforcement exists. The code-craft rule M13.3 forbids bare
`except:` and broad `except Exception:` that swallow errors silently.
Caught exceptions are typed and either handled with rationale or
re-raised with context. The pre-emission gate's mechanical bar 13 (M13 code craft)
catches both bare-clause shapes and the broad-Exception form (without
re-raise) and surfaces each occurrence so the operator either narrows
the type or adds a `raise` so the failure propagates.

Detection strategy. The grep walks Python source for `except:` (no
type spec), `except Exception:` / `except BaseException:` (broad), and
the parenthesized-tuple form that contains a broad type
(`except (ValueError, Exception):`); within each clause's body it
inspects whether the body contains a `raise` statement. A clause that
catches broadly without re-raising is the canonical violation; bare
`except:` is always flagged. The `except*` exception-group form
(PEP 654) is recognised identically to plain `except`.

Continuation handling. A tuple clause split across physical lines
(`except (\n    ValueError,\n    Exception,\n):`) is joined onto its
opening line before matching, so a multi-line broad tuple is caught as
faithfully as a single-line one; the finding still reports the opening
line. String spans (single-line and triple-quoted) are blanked first so
an `except:` quoted inside a string literal is not mistaken for a clause.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from apothem.conformity._grep_base import GrepResult, run_grep

# Bare or broad except shapes. Bare `except:` matches with no type
# specifier; broad forms catch the root exception types either directly
# (`except Exception:`) or inside a tuple (`except (ValueError, Exception):`).
# The optional `*` after `except` accepts the PEP 654 exception-group form
# (`except* Exception:`). The match groups capture the form for the report.
BARE_EXCEPT_RE: Final[re.Pattern[str]] = re.compile(
    r"^(\s*)except\*?\s*(?:"
    r":"  # bare `except:` / `except*:`
    r"|("  # group 2: a broad spec including the trailing colon
    r"(?:Exception|BaseException)(?:\s+as\s+\w+)?\s*:"  # broad single type
    r"|\([^)]*\b(?:Exception|BaseException)\b[^)]*\)(?:\s+as\s+\w+)?\s*:"  # broad tuple
    r"))"
)

# Single- and triple-quoted string spans, blanked before matching so an
# `except:` quoted inside a string is never mistaken for a real clause.
# Triple-quoted spans lead so they win over the single-quote alternatives.
_STRING_SPAN_RE: Final[re.Pattern[str]] = re.compile(
    r"'''[\s\S]*?'''|\"\"\"[\s\S]*?\"\"\""
    r"|'(?:\\.|[^'\\])*'|\"(?:\\.|[^\"\\])*\""
)
RAISE_RE: Final[re.Pattern[str]] = re.compile(r"^\s+raise\b")
# A re-raise written inline after the `except ...:` colon — `except
# Exception: raise` or `except Exception: log(); raise`. Matched at the
# start of the inline body or immediately after a `;` statement separator,
# so an inline re-raise is recognized as faithfully as a subsequent-line one.
INLINE_RAISE_RE: Final[re.Pattern[str]] = re.compile(r"(?:^|;)\s*raise\b")
GREP_NAME: Final[str] = "bare-except-grep"
RULE_ANCHOR: Final[str] = "M13.3 error handling"


@dataclass(frozen=True)
class Finding:
    line: int
    form: str
    detail: str
    rule: str = RULE_ANCHOR


def _clause_has_raise(lines: list[str], clause_index: int, indent: int) -> bool:
    """Walk the clause body until dedent; return True iff any line is a raise."""
    body_indent_min = indent + 1
    for line in lines[clause_index + 1 :]:
        if not line.strip():
            continue
        leading = len(line) - len(line.lstrip())
        if leading < body_indent_min:
            return False
        if RAISE_RE.match(line):
            return True
    return False


def _blank_strings(content: str) -> str:
    """Replace every string span with same-length spaces, keeping newlines.

    Preserving both the character count and the line breaks keeps every
    subsequent line index and column stable against the original source, so
    an `except:` that only appears inside a string literal cannot be
    mistaken for a real clause.
    """

    def _blank(match: re.Match[str]) -> str:
        span = match.group()
        return "".join("\n" if ch == "\n" else " " for ch in span)

    return _STRING_SPAN_RE.sub(_blank, content)


def _match_lines(blanked_lines: list[str]) -> list[tuple[str, int]]:
    """Return, per line, ``(view, span)`` where a bracket-continued
    `except (` clause is joined onto its opening line.

    Each element aligns with ``blanked_lines`` by index. ``view`` is the
    line's match text — for a clause whose parenthesis does not close on the
    same physical line, the following lines up to and including the balancing
    line are appended, so the tuple form matches on one line. ``span`` is the
    number of physical lines the clause header occupies (``1`` for a normal
    line), letting the caller start the raise-walk *after* the joined header
    rather than inside its continuation lines. Line numbers still key on the
    opening physical line.
    """
    views: list[tuple[str, int]] = [(line, 1) for line in blanked_lines]
    for index, line in enumerate(blanked_lines):
        stripped = line.lstrip()
        if not (stripped.startswith("except") and "(" in line):
            continue
        depth = line.count("(") - line.count(")")
        if depth <= 0:
            continue  # closes on the same line; no join needed
        joined = line
        cursor = index + 1
        while depth > 0 and cursor < len(blanked_lines):
            nxt = blanked_lines[cursor]
            joined += " " + nxt.strip()
            depth += nxt.count("(") - nxt.count(")")
            cursor += 1
        views[index] = (joined, cursor - index)
    return views


def check(content: str, path: Path | None = None) -> GrepResult:
    """Scan content; return a structured result."""
    findings: list[Finding] = []
    lines = content.splitlines()
    blanked = _blank_strings(content).splitlines()
    match_views = _match_lines(blanked)
    for index, (view, span) in enumerate(match_views):
        match = BARE_EXCEPT_RE.match(view)
        if match is None:
            continue
        indent = len(match.group(1))
        is_bare = match.group(2) is None
        form = "bare except:" if is_bare else "broad except: " + match.group(2).strip()
        # Bare except is always a finding. Broad except is a finding only
        # when the clause body contains no `raise` — counting both a
        # subsequent indented line and an inline re-raise on the `except`
        # line itself (`except Exception: raise`), so a faithful inline
        # re-raise is not flagged as a swallow. The raise-walk starts after
        # the (possibly multi-line) clause header, using the original
        # physical lines so the body's indentation is unchanged.
        inline_body = view[match.end() :]
        has_raise = bool(INLINE_RAISE_RE.search(inline_body)) or _clause_has_raise(
            lines, index + span - 1, indent
        )
        if is_bare or not has_raise:
            detail = (
                "bare except swallows every exception class"
                if is_bare
                else "broad except without re-raise; narrow the type or add raise"
            )
            findings.append(Finding(line=index + 1, form=form, detail=detail))
    return GrepResult(
        grep=GREP_NAME,
        path=str(path) if path is not None else None,
        passed=not findings,
        findings=findings,
    )


if __name__ == "__main__":
    sys.exit(run_grep(check, sys.argv))
