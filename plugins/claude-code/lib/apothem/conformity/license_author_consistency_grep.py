# SPDX-License-Identifier: MIT

"""license-author-consistency-grep: LICENSE author-identity presence check.

Reads the project's ``LICENSE`` file at the repository root and asserts it
carries a parseable ``Copyright (c) <name>`` author line. Under the D-007
NARROW verdict the per-file authorship banner is reduced to the single
``SPDX-License-Identifier: MIT`` line and no longer carries an author name, so
the historical banner-vs-LICENSE cross-check no longer applies. The root
``LICENSE`` remains the authoritative carrier of the copyright instrument, so
this validator now verifies that the LICENSE author identity is present and
parseable. It never invents author data; when the LICENSE is absent or carries
the canonical pending placeholder it reports the pending state and warns rather
than asserting a failure.

Verdict matrix:
    pass    — LICENSE carries a parseable ``Copyright (c) <name>`` line.
    pass + warning — LICENSE absent or carries the canonical
              ``<USER-CONFIRM:license-pending>`` placeholder; the author
              identity cannot yet be asserted.
    fail    — LICENSE is present and non-pending but carries no parseable
              ``Copyright (c) <name>`` author line.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from apothem.conformity._grep_base import GrepResult, run_grep

GREP_NAME: Final[str] = "license-author-consistency-grep"

# Working-tree root anchor for the repo-root LICENSE check. In the repo
# checkout, parents[3] of ``src/apothem/conformity/<file>.py`` is the
# working-tree root where ``LICENSE`` lives. In the installed tree
# (``<install-root>/apothem/conformity/``) the anchor is a coarse
# filesystem ancestor that carries no project LICENSE: hook-mode
# dispatches degrade to a pass-through via the relative_to() guard in
# _is_in_scope(), and a direct invocation reports the pending state
# (pass + warning) rather than asserting a failure.
ECOSYSTEM_ROOT: Final[Path] = Path(__file__).resolve().parents[3]
LICENSE_RELATIVE: Final[Path] = Path("LICENSE")
LICENSE_PENDING_PLACEHOLDER: Final[str] = "<USER-CONFIRM:license-pending>"

# Match a copyright line with optional symbol, optional year tokens, and the
# author tail. Examples successfully matched:
#   "Copyright (c) 2026 Ahmed G. Gad"
#   "Copyright (C) Ahmed G. Gad"
COPYRIGHT_LINE_RE: Final[re.Pattern[str]] = re.compile(
    r"Copyright\s*\(\s*[cC©]\s*\)\s*(?P<tail>.+?)\s*$",
    re.MULTILINE,
)

# Year-token pattern stripped before name comparison; matches single year,
# year ranges, comma-separated years, and any leading copyright symbols.
YEAR_TOKEN_RE: Final[re.Pattern[str]] = re.compile(
    r"^\d{4}(?:\s*[-,]\s*\d{4})?(?:\s*,\s*\d{4})*\s+"
)

RULE_AUTHOR_ABSENT: Final[str] = "LICENSE_AUTHOR_ABSENT"
RULE_LICENSE_PENDING: Final[str] = "LICENSE_PENDING"

SEVERITY_ERROR: Final[str] = "error"
SEVERITY_WARNING: Final[str] = "warning"


@dataclass(frozen=True)
class Finding:
    """One diagnostic finding from the LICENSE author-presence check."""

    line: int
    match: str
    context: str
    rule: str
    severity: str = SEVERITY_ERROR


def _normalise_author(tail: str) -> str:
    """Strip leading year tokens from a copyright tail."""
    return YEAR_TOKEN_RE.sub("", tail).strip()


def _extract_author(text: str) -> str | None:
    """Extract the normalized author name from the first copyright line."""
    match = COPYRIGHT_LINE_RE.search(text)
    if match is None:
        return None
    return _normalise_author(match.group("tail"))


def _is_in_scope(path: Path) -> bool:
    """Return True when *path* is the LICENSE file."""
    try:
        rel = path.resolve().relative_to(ECOSYSTEM_ROOT)
    except ValueError:
        return False
    return rel == LICENSE_RELATIVE


def check(content: str, path: Path | None = None) -> GrepResult:
    """Validate that the LICENSE carries a parseable author identity.

    Hook-mode pass-through. When *path* is set and is not the LICENSE
    file, the validator returns ``passed=True`` immediately. The check
    runs on in-scope dispatches and on CLI mode without a path argument.

    Returns:
        ``GrepResult`` with ``passed=True`` when the LICENSE names an
        author (or is pending, with an advisory finding), ``passed=False``
        when the LICENSE is present and non-pending but names no author.
    """
    # `content` is unused — interface parity with the orchestrator's
    # _CheckCallable Protocol.
    _ = content
    if path is not None and not _is_in_scope(path):
        return GrepResult(
            grep=GREP_NAME,
            path=str(path),
            passed=True,
            note="check skipped (scope not resolvable)",
        )

    license_path = ECOSYSTEM_ROOT / LICENSE_RELATIVE
    findings: list[Finding] = []

    if not license_path.is_file():
        findings.append(
            Finding(
                line=0,
                match=str(LICENSE_RELATIVE.as_posix()),
                context=(
                    f"LICENSE absent at {LICENSE_RELATIVE.as_posix()};"
                    f" pending the LICENSE selection"
                ),
                rule=RULE_LICENSE_PENDING,
                severity=SEVERITY_WARNING,
            )
        )
        return GrepResult(
            grep=GREP_NAME,
            path=str(license_path),
            passed=True,
            findings=findings,
        )

    license_text = license_path.read_text(encoding="utf-8")
    if LICENSE_PENDING_PLACEHOLDER in license_text:
        findings.append(
            Finding(
                line=0,
                match=LICENSE_PENDING_PLACEHOLDER,
                context=(
                    "LICENSE carries the canonical pending placeholder;"
                    " deferred until the LICENSE is finalized"
                ),
                rule=RULE_LICENSE_PENDING,
                severity=SEVERITY_WARNING,
            )
        )
        return GrepResult(
            grep=GREP_NAME,
            path=str(license_path),
            passed=True,
            findings=findings,
        )

    license_author = _extract_author(license_text)
    if license_author is None or not license_author:
        findings.append(
            Finding(
                line=0,
                match=str(LICENSE_RELATIVE.as_posix()),
                context=(
                    f"LICENSE at {LICENSE_RELATIVE.as_posix()} has no"
                    f" parseable Copyright (c) author line"
                ),
                rule=RULE_AUTHOR_ABSENT,
                severity=SEVERITY_ERROR,
            )
        )
        return GrepResult(
            grep=GREP_NAME,
            path=str(license_path),
            passed=False,
            findings=findings,
        )

    return GrepResult(
        grep=GREP_NAME,
        path=str(license_path),
        passed=True,
        findings=[],
    )


if __name__ == "__main__":
    sys.exit(run_grep(check, sys.argv))
