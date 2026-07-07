# SPDX-License-Identifier: MIT

"""copilot-instructions-presence-grep: GitHub Copilot surface presence check.

Why this enforcement exists. GitHub Copilot is one of the three canonical
AI-instruction surfaces the repo mirrors (alongside ``AGENTS.md`` and
``CLAUDE.md``), so a missing or structurally-drifted
``.github/copilot-instructions.md`` silently breaks the cross-surface parity the
AI-surface canon requires. This check is the presence-and-structure floor that
keeps Copilot a faithful mirror of the shared disciplines.

Asserts that ``.github/copilot-instructions.md`` exists at the GitHub-canonical
path, begins with a canonical Markdown banner (the single-line SPDX header or
the HTML-comment authorship block), and carries the nine canonical level-2
sections in the prescribed order with exact heading text. The check is invoked
at orchestrator dispatch time (the orchestrator passes ``content`` and
``path``); when ``path`` is absent the check reads
``.github/copilot-instructions.md`` from the ecosystem root directly. The
validator is non-mutating; it only reports. Outside a repo checkout (e.g. the
installed conformity tree), hook-mode dispatches degrade to a pass-through —
there is no working-tree Copilot surface to assert against.

Verdict matrix:
    pass    — file exists, banner is a canonical Markdown variant, all
              nine canonical sections present in order with exact headings.
    fail    — any of: file absent, banner absent or not a Markdown variant,
              any canonical section absent, sections out of order, or a
              section's heading text differs from the canonical form.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from apothem.conformity._grep_base import GrepResult, run_grep

GREP_NAME: Final[str] = "copilot-instructions-presence-grep"

# Working-tree root anchor for the repo-root Copilot surface. In the repo
# checkout, parents[3] of ``src/apothem/conformity/<file>.py`` is the
# working-tree root where ``.github/copilot-instructions.md`` lives. In
# the installed tree (``<install-root>/apothem/conformity/``) the anchor
# is a coarse filesystem ancestor with no Copilot surface beneath it:
# hook-mode dispatches degrade to a pass-through via the relative_to()
# guard in _is_target_path(), and the surface check itself only runs when
# directly invoked against the target.
ECOSYSTEM_ROOT: Final[Path] = Path(__file__).resolve().parents[3]
TARGET_RELATIVE: Final[Path] = Path(".github") / "copilot-instructions.md"

# The nine canonical level-2 sections, in prescribed order, with their exact
# heading text. The order matches the canonical Copilot-instructions spec
# and the file as shipped on disk.
CANONICAL_SECTIONS: Final[tuple[str, ...]] = (
    "Project Context",
    "Coding Conventions",
    "File Headers",
    "Plans Discipline",
    "Structured Inquiry Behavior",
    "Forbidden Patterns",
    "Output Format",
    "Review Checklist",
    "Pointers",
)

# The canonical Markdown banner comes in two accepted forms: the single-line
# SPDX header (``<!-- SPDX-License-Identifier: MIT -->`` — the per-file
# authorship form ratified at the File Headers discipline) and the
# HTML-comment block whose body is the hash-form authorship banner (open
# delimiter on its own line, AUTHOR_MARK between, close delimiter within the
# scan budget).
AUTHOR_MARK: Final[str] = "Copyright (c) Ahmed G. Gad"
SPDX_MARK: Final[str] = "SPDX-License-Identifier:"
HTML_OPEN: Final[str] = "<!--"
HTML_CLOSE: Final[str] = "-->"
BANNER_SCAN_LINE_BUDGET: Final[int] = 20

H2_LINE_RE: Final[re.Pattern[str]] = re.compile(r"^##\s+(.+?)\s*$")

RULE_FILE_ABSENT: Final[str] = "COPILOT_FILE_ABSENT"
RULE_BANNER_ABSENT: Final[str] = "COPILOT_BANNER_ABSENT"
RULE_SECTION_ABSENT: Final[str] = "COPILOT_SECTION_ABSENT"
RULE_SECTION_OUT_OF_ORDER: Final[str] = "COPILOT_SECTION_OUT_OF_ORDER"


@dataclass(frozen=True)
class Finding:
    """One diagnostic finding for the presence check."""

    line: int
    match: str
    context: str
    rule: str


def _anchor_relative(path: Path) -> Path | None:
    """Return *path* relative to the repo root or its matched hook scope, else None.

    The apothem repo root is tried first; when the path is outside it, the
    configured conformity scopes (hook-capable harness roots, via
    ``gate.scope_relative_path``) are tried. ``None`` means the path is under no
    anchor — there is no scope to resolve the Copilot surface against.
    """
    abs_path = path.resolve()
    try:
        return abs_path.relative_to(ECOSYSTEM_ROOT)
    except ValueError:
        pass
    from apothem.conformity.gate import scope_relative_path

    scoped = scope_relative_path(abs_path)
    return scoped[1] if scoped is not None else None


def _is_target_path(path: Path) -> bool:
    """Return True when *path* is the GitHub-canonical Copilot surface.

    Scope-aware: the surface is recognised whether the path is under the apothem
    repo root or under a hook scope (e.g. ``~/.claude/.github/copilot-instructions.md``).
    """
    rel = _anchor_relative(path)
    return rel is not None and rel == TARGET_RELATIVE


def _check_banner(content_lines: list[str]) -> Finding | None:
    """Verify the file opens with a canonical Markdown banner variant.

    Two forms pass: the single-line SPDX header
    (``<!-- SPDX-License-Identifier: MIT -->``) and the HTML-comment
    block carrying the AUTHOR_MARK between its delimiters.
    """
    if not content_lines:
        return Finding(
            line=1,
            match="",
            context="file is empty; expected canonical Markdown banner at line 1",
            rule=RULE_BANNER_ABSENT,
        )
    first_line = content_lines[0].strip()
    if (
        first_line.startswith(HTML_OPEN)
        and first_line.endswith(HTML_CLOSE)
        and SPDX_MARK in first_line
    ):
        # Single-line SPDX header form — canonical per the File Headers
        # discipline; no block scan needed.
        return None
    if content_lines[0].strip() != HTML_OPEN:
        return Finding(
            line=1,
            match=content_lines[0],
            context=(
                f"first line is not the canonical Markdown variant opener {HTML_OPEN!r}"
            ),
            rule=RULE_BANNER_ABSENT,
        )
    scan_end = min(len(content_lines), BANNER_SCAN_LINE_BUDGET)
    saw_author_mark = False
    saw_close = False
    for idx in range(1, scan_end):
        line = content_lines[idx]
        if AUTHOR_MARK in line:
            saw_author_mark = True
        if line.strip() == HTML_CLOSE:
            saw_close = True
            break
    if not saw_author_mark:
        return Finding(
            line=1,
            match=content_lines[0],
            context=(
                f"banner opener present but {AUTHOR_MARK!r} not found within"
                f" the first {BANNER_SCAN_LINE_BUDGET} lines"
            ),
            rule=RULE_BANNER_ABSENT,
        )
    if not saw_close:
        return Finding(
            line=1,
            match=content_lines[0],
            context=(
                f"banner opener present but {HTML_CLOSE!r} not found within"
                f" the first {BANNER_SCAN_LINE_BUDGET} lines"
            ),
            rule=RULE_BANNER_ABSENT,
        )
    return None


def _extract_h2_sequence(content_lines: list[str]) -> list[tuple[int, str]]:
    """Return the (1-based line number, heading text) of every level-2 heading."""
    headings: list[tuple[int, str]] = []
    for idx, line in enumerate(content_lines, start=1):
        match = H2_LINE_RE.match(line)
        if match:
            headings.append((idx, match.group(1)))
    return headings


def _check_sections(content_lines: list[str]) -> list[Finding]:
    """Verify every canonical section is present in the prescribed order."""
    headings = _extract_h2_sequence(content_lines)
    findings: list[Finding] = []

    # Pass 1 — every canonical section must be present.
    seen_lines: dict[str, int] = {text: line for line, text in headings}
    for section in CANONICAL_SECTIONS:
        if section not in seen_lines:
            findings.append(
                Finding(
                    line=0,
                    match="",
                    context=f"canonical section {section!r} absent",
                    rule=RULE_SECTION_ABSENT,
                )
            )

    # Pass 2 — the canonical sections must appear in the prescribed order.
    # Filter the heading sequence to canonical members and check the order.
    canonical_seen = [
        (line, text) for line, text in headings if text in CANONICAL_SECTIONS
    ]
    expected_order = [t for _, t in canonical_seen]
    canonical_present = [s for s in CANONICAL_SECTIONS if s in seen_lines]
    if expected_order != canonical_present:
        first_mismatch_line = canonical_seen[0][0] if canonical_seen else 0
        findings.append(
            Finding(
                line=first_mismatch_line,
                match=", ".join(expected_order),
                context=(
                    f"canonical sections out of order; observed "
                    f"{expected_order!r} but expected the order "
                    f"{canonical_present!r}"
                ),
                rule=RULE_SECTION_OUT_OF_ORDER,
            )
        )

    return findings


def check(content: str, path: Path | None = None) -> GrepResult:
    """Validate Copilot-surface presence and section structure.

    Hook-mode pass-through. When *path* is set and does not name the
    GitHub-canonical Copilot surface, the validator returns ``passed=True``
    without reading anything else. The full structural check runs only on
    direct dispatch against the target surface or on CLI mode without a
    path argument (where the validator reads the on-disk surface).

    Args:
        content: In-flight body of the target surface (orchestrator
            dispatch). When the orchestrator dispatches with no content
            but the path matches the target, the on-disk body is read.
        path: Absolute path of the file under dispatch; ``None`` in
            ``--stdin`` mode.

    Returns:
        ``GrepResult`` with ``passed=True`` when the surface is
        well-formed (or out-of-scope for this dispatch), ``passed=False``
        with one ``Finding`` per defect otherwise.
    """
    target_path = ECOSYSTEM_ROOT / TARGET_RELATIVE

    if path is not None and not _is_target_path(path):
        if _anchor_relative(path) is None:
            # Out-of-anchor write: no repo root or hook scope resolves the
            # Copilot surface — record a visible skip, not a silent pass.
            return GrepResult(
                grep=GREP_NAME,
                path=str(path),
                passed=True,
                note="check skipped (scope not resolvable)",
            )
        # In-anchor but not the Copilot surface: legitimately not applicable.
        return GrepResult(grep=GREP_NAME, path=str(path), passed=True)

    if path is not None and _is_target_path(path):
        if content:
            body = content
        elif target_path.is_file():
            body = target_path.read_text(encoding="utf-8")
        else:
            body = ""
        report_path = path
    else:
        if not target_path.is_file():
            return GrepResult(
                grep=GREP_NAME,
                path=str(target_path),
                passed=False,
                findings=[
                    Finding(
                        line=0,
                        match="",
                        context=(
                            f"{TARGET_RELATIVE.as_posix()} absent at the"
                            f" GitHub-canonical path"
                        ),
                        rule=RULE_FILE_ABSENT,
                    )
                ],
            )
        body = target_path.read_text(encoding="utf-8")
        report_path = target_path

    content_lines = body.split("\n")

    findings: list[Finding] = []
    banner_finding = _check_banner(content_lines)
    if banner_finding is not None:
        findings.append(banner_finding)
    findings.extend(_check_sections(content_lines))

    return GrepResult(
        grep=GREP_NAME,
        path=str(report_path),
        passed=not findings,
        findings=findings,
    )


if __name__ == "__main__":
    sys.exit(run_grep(check, sys.argv))
