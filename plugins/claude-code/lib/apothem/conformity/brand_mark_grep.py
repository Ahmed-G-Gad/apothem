# SPDX-License-Identifier: MIT

"""Flag brand-mark display/identifier form drift on brand-touched surfaces.

Why this enforcement exists. The brand-mark convention sub-mandate (the
display brand ``Apothem`` PascalCase versus the identifier
``apothem`` lowercase) carries a per-surface canonical form: human-
readable display surfaces render PascalCase; machine-resolved identifier
surfaces honor ecosystem-normalized lowercase (PEP-503, URL conventions,
package-manager naming). A wordmark spelled lowercase on a display
surface, or a Python distribution name spelled PascalCase, is drift the
M9 visual leverage + M14 sibling convergence + M3 ten-dimension
consistency bars catch at the pre-emission gate.

Detection strategy. Per-line scan over the brand-touched glob set. Each
occurrence of ``\\b(apothem|Apothem)\\b`` is classified against two
high-confidence pattern sets: an identifier-context set (URL paths,
package-manager install commands, environment variables, file basenames,
Python imports, suite folder, repo path) and a display-context set
(Markdown H1 with brand-name, site-title metadata, frontmatter title:,
alt-text, OG/Twitter meta-title, SVG title/desc). Drift findings emit
only when the classification is high-confidence: PascalCase form on an
identifier-context line, or lowercase form on a display-context line.
Unclassified occurrences pass; the unclassified occurrences are cataloged in the operator's normalization review pass.

Path filter. The matcher early-exits on out-of-scope paths so tooling,
tests, rules, hooks, plan-suite scratch, and the ecosystem's own
internal Markdown corpus are not inspected. In-scope paths are the
brand-touched globs enumerated at ``IN_SCOPE_PREFIXES`` and
``IN_SCOPE_FILENAMES``.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from apothem.conformity._grep_base import GrepResult, run_grep

# Brand-mark occurrence regex. Word-boundary anchors prevent partial
# matches inside identifiers like ``ahmed-g-gad/apothem-internals`` (which
# remains a single match starting at the canonical token).
BRAND_RE: Final[re.Pattern[str]] = re.compile(r"\b(apothem|Apothem)\b")

# Identifier-context line patterns. When a line matches one of these,
# the canonical form on that line is lowercase ``apothem``. A
# PascalCase ``Apothem`` occurrence on such a line is identifier-on-
# display-surface drift.
IDENTIFIER_CONTEXT_PATTERNS: Final[tuple[re.Pattern[str], ...]] = tuple(
    re.compile(pat, re.IGNORECASE)
    for pat in (
        # URL paths
        r"github\.com/[\w-]+/apothem",
        r"apothem\.ahmedgad\.com",
        # Package-manager install commands
        r"\bbrew\s+install\s+\S*apothem",
        r"\bscoop\s+install\s+\S*apothem",
        r"\bwinget\s+install\s+\S*apothem",
        r"\bpacman\s+-S\s+\S*apothem",
        r"\b(apt|dnf|yum)\s+install\s+\S*apothem",
        # CLI invocations
        r"\$\s*apothem\b",
        r"\bapothem\s+--",
        # Python module references
        r"\bimport\s+apothem\b",
        r"\bfrom\s+apothem\b",
        # Versioned/typed file basenames
        r"\bapothem-v?\d",
        r"\bapothem[_.]\d",
        r"\bapothem\.(rb|json|ya?ml|toml|spec|whl|tar|deb|rpm)\b",
        # Env-var prefix (upper-snake identifier form)
        r"\bAPOTHEM_\w+",
        # Suite folder path
        r"/.plans/[\w-]*apothem",
        # Repo path under owner
        r"\bahmed-g-gad/[\w-]*apothem",
        # PEP-621 distribution name field
        r'^\s*name\s*=\s*"apothem"',
        # Homebrew formula filename
        r"/Formula/apothem",
        # Scoop manifest filename
        r"/bucket/apothem\.json",
        # Winget package-identifier segment
        r"ahmed-g-gad\.apothem",
        # PKGBUILD pkgname
        r"\bpkgname=apothem",
        # Docker image
        r"\bahmed-g-gad/apothem",
    )
)

# Display-context line patterns. When a line matches one of these, the
# canonical form on that line is PascalCase ``Apothem``. A lowercase
# ``apothem`` occurrence on such a line (outside URL/identifier sub-
# expressions also on the line) is display-form drift.
DISPLAY_CONTEXT_PATTERNS: Final[tuple[re.Pattern[str], ...]] = tuple(
    re.compile(pat)
    for pat in (
        # Markdown H1/H2 referencing the brand
        r"^#{1,6}\s+.*(?:Apothem|apothem)",
        # Site metadata fields
        r"^\s*site_name\s*:",
        r"^\s*site_description\s*:",
        # YAML frontmatter title field
        r'^\s*title\s*:\s*["\']?(?:Apothem|apothem)',
        # alt-text attribute
        r'\balt\s*=\s*["\'][^"\']*(?:Apothem|apothem)',
        # SVG accessibility elements
        r"<(?:title|desc|text)[^>]*>(?:Apothem|apothem)",
        # OG / Twitter meta tags
        r"\b(?:og:title|og:site_name|twitter:title|twitter:image:alt)\b",
        # JSON-LD name field
        r'"name"\s*:\s*"(?:Apothem|apothem)"',
        # CLI banner H1 wording
        r"\bApothem\s+v\d",
        # Homebrew formula desc field
        r'^\s*desc\s+"',
        # PEP-621 description field
        r'^\s*description\s*=\s*"',
        # AUR pkgdesc / .deb Description / .rpm Summary
        r"^\s*pkgdesc\s*=",
        r"^\s*Description\s*:",
        r"^\s*Summary\s*:",
        # Winget ShortDescription / Description
        r"^\s*(?:ShortDescription|Description|PackageName)\s*:",
    )
)

# In-scope path prefixes (relative to project root). The matcher's
# classification only fires when the inspected path starts with one of
# these or matches one of the IN_SCOPE_FILENAMES bare basenames.
IN_SCOPE_PREFIXES: Final[tuple[str, ...]] = (
    "site/",
    "assets/",
    ".github/",
    "bin/",
)

# In-scope bare filenames (root-level singletons).
IN_SCOPE_FILENAMES: Final[frozenset[str]] = frozenset(
    {
        "README.md",
        "CHANGELOG.md",
        "SUPPORT.md",
        "SECURITY.md",
        "LICENSE",
        "pyproject.toml",
        "scripts/installer/install.sh",
        "scripts/installer/install.ps1",
        "scripts/installer/update.sh",
        "scripts/installer/update.ps1",
        "scripts/installer/uninstall.sh",
        "scripts/installer/uninstall.ps1",
    }
)

GREP_NAME: Final[str] = "brand-mark-grep"
RULE_ANCHOR: Final[str] = (
    "rules/plain-language.md (brand-mark display/identifier casing)"
)
DISPLAY_FORM: Final[str] = "Apothem"
IDENTIFIER_FORM: Final[str] = "apothem"


@dataclass(frozen=True)
class Finding:
    """One brand-mark form-drift occurrence."""

    line: int
    match: str
    drift: str  # "display-form-on-identifier-surface" | "identifier-form-on-display-surface"
    context: str
    rule: str = RULE_ANCHOR


def _in_scope(path: Path | None) -> bool:
    """Decide whether the path is a brand-touched surface.

    Pre-conditions: `path` is the artifact's emission destination (or
    None when scanning stdin without a target path).
    Post-conditions: returns True iff the path matches an in-scope
    prefix or an in-scope bare filename.
    """
    if path is None:
        return True  # CLI use without a target path; classify by content alone.
    # Normalize to forward-slash for cross-platform glob match.
    rel = path.as_posix()
    if path.name in IN_SCOPE_FILENAMES:
        return True
    for prefix in IN_SCOPE_PREFIXES:
        if rel.startswith(prefix) or f"/{prefix}" in rel:
            return True
    return False


def _classify(line: str, match_text: str) -> str | None:
    """Return a drift label when the occurrence is high-confidence drift.

    Returns None when the occurrence is acceptable or unclassifiable.
    """
    is_identifier_context = any(p.search(line) for p in IDENTIFIER_CONTEXT_PATTERNS)
    is_display_context = any(p.search(line) for p in DISPLAY_CONTEXT_PATTERNS)

    if is_identifier_context and not is_display_context:
        # Lowercase form is canonical; PascalCase is drift.
        if match_text == DISPLAY_FORM:
            return "display-form-on-identifier-surface"
        return None
    if is_display_context and not is_identifier_context:
        # PascalCase form is canonical; lowercase is drift.
        if match_text == IDENTIFIER_FORM:
            return "identifier-form-on-display-surface"
        return None
    # Mixed or unclassified: do not flag (catalog in normalization walk).
    return None


def check(content: str, path: Path | None = None) -> GrepResult:
    """Scan content for per-surface brand-mark form drift.

    Pre-conditions: `content` is the artifact body about to be emitted;
    `path` is its destination relative to the project root (or None for
    stdin without a target).
    Post-conditions: `result.passed` is True iff zero high-confidence
    drift occurrences are found on in-scope paths.
    """
    if not _in_scope(path):
        return GrepResult(
            grep=GREP_NAME,
            path=str(path) if path is not None else None,
            passed=True,
            findings=[],
        )

    findings: list[Finding] = []
    inside_fence = False
    for line_index, line in enumerate(content.splitlines(), start=1):
        if line.startswith("```"):
            inside_fence = not inside_fence
            continue
        if inside_fence:
            continue
        for occurrence in BRAND_RE.finditer(line):
            drift = _classify(line, occurrence.group())
            if drift is None:
                continue
            findings.append(
                Finding(
                    line=line_index,
                    match=occurrence.group(),
                    drift=drift,
                    context=line.strip()[:200],
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
