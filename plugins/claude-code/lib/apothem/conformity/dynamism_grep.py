# SPDX-License-Identifier: MIT

"""Flag static-string version embeds in dynamism-required surfaces.

Why this enforcement exists. The dynamism rule and the spec section 3.2.c
dynamism SLOs require that surfaces presented to operators — README
badges, documentation site pages, install/landing guides — resolve their
version strings through a single canonical source: ``pyproject.toml`` is
the manifest authority, surfaced at runtime through ``apothem.__version__``
and resolved publicly through GitHub Releases and the npm registry. When
a literal semver such as ``1.2.3`` or
``v1.2.3`` is hard-coded into a README badge URL or a documentation
page, the artifact drifts the moment the canonical version increments —
the badge shows yesterday's release, the docs claim a version the
codebase has surpassed, and the operator-facing surface tells two
incompatible truths.

Surfaces in scope. The validator walks the repository root and inspects
``README.md`` (top-level only — sub-tree READMEs follow their own
discipline) and every Markdown / MDX page under
``site/content/docs/``. Surfaces explicitly
out of scope: ``CHANGELOG.md`` and the documentation blog — the blog
exclusion is locale-aware, covering both the English-root blog at
``site/content/docs/blog/`` and every locale mirror at
``site/content/docs/<locale>/blog/`` (all record historical releases by
literal version, like dated release-announcement posts) — ``pyproject.toml``
(the canonical source-of-truth this rule defers to), generated reference
inventory blocks, the ``_spec/`` and ``.plans/`` trees (specification +
planning ephemera carry release identifiers in literal form), the
``tests/`` tree (fixtures must use literal versions to assert behaviour),
and ``*.py`` files outside docs (source modules consume ``__version__``
dynamically).

Detection strategy. The validator scans each in-scope file line by line
for the semver regex ``\\bv?\\d+\\.\\d+\\.\\d+\\b``. Hits inside fenced
code blocks are reported regardless — README install commands and docs
examples typically substitute via Jinja/templating and a literal version
there is still drift-prone. The operator triages each hit on one of two
paths: replace the literal with a dynamic substitution (e.g.,
site-build metadata, ``__version__`` for runtime
contexts, a shields.io endpoint badge that resolves from the npm
registry or GitHub Releases), or
demonstrate the literal is intentional and out-of-scope (a quoted
example of someone else's release, a historical reference) and migrate
the file out of the in-scope set.

Exit semantics. Exits 0 when no findings; exits 2 on any finding. The
exit-2 convention matches the conformity-gate orchestrator's EXIT_FAIL
constant.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Final

GREP_NAME: Final[str] = "dynamism-grep"
RULE_ANCHOR: Final[str] = "rules/dynamism.md (static-version embeds)"

EXIT_PASS: Final[int] = 0
EXIT_FAIL: Final[int] = 2

# Semver-shaped match: optional leading 'v', three numeric segments
# separated by dots, word boundaries on both ends. Catches `1.0.0`,
# `v1.2.3`, and the `version = "0.X.Y"` pin pattern (the literal version
# string inside the quoted value matches independently).
_SEMVER_RE: Final[re.Pattern[str]] = re.compile(r"\bv?\d+\.\d+\.\d+\b")

# Path segments that exclude a file from the in-scope sweep. The matcher
# walks every Markdown file under the root and tests its parts against
# this set; any segment match short-circuits the file as out-of-scope.
_EXCLUDED_PATH_SEGMENTS: Final[frozenset[str]] = frozenset(
    {
        "_spec",
        ".plans",
        "tests",
        "node_modules",
        ".venv",
        "venv",
        ".git",
    }
)

# Filenames that are out-of-scope even when located inside an otherwise
# in-scope directory. CHANGELOG.md records literal release-history
# release versions; pyproject.toml is the canonical version source; the
# vendoring-strategy doc's dependency-pin table mirrors those canonical
# dependency pins (literal requirement facts, not a displayed version
# surface that goes stale).
_EXCLUDED_FILENAMES: Final[frozenset[str]] = frozenset(
    {
        "CHANGELOG.md",
        "pyproject.toml",
        "vendoring-strategy.md",
    }
)

DOCS_PATH_PARTS: Final[tuple[str, ...]] = ("site", "content", "docs")
DOCS_SUFFIXES: Final[frozenset[str]] = frozenset({".md", ".mdx"})
# Docs-relative directory segments that exclude a page from the in-scope
# sweep. The exclusion is locale-aware: a ``blog`` segment anywhere below
# ``site/content/docs/`` is out of scope, covering both the English-root blog
# (``site/content/docs/blog/...``) and every locale mirror
# (``site/content/docs/<locale>/blog/...``). The blog records historical
# releases by literal version (dated release-announcement posts), exactly as
# the ``CHANGELOG.md`` exclusion above does.
_EXCLUDED_DOCS_SUBTREE_SEGMENTS: Final[frozenset[str]] = frozenset({"blog"})
# Documentation pages carry these region markers in the comment syntax of the
# host docs framework: the HTML-comment form (``<!-- ... -->``) for Markdown
# pages and the JSX-comment form (``{/* ... */}``) for MDX pages. Both forms are
# recognized so the exclusion regions fire regardless of the page's extension.
_GENERATED_REFERENCE_START: Final[frozenset[str]] = frozenset(
    {
        "<!-- apothem:generated-reference:start -->",
        "{/* apothem:generated-reference:start */}",
    }
)
_GENERATED_REFERENCE_END: Final[frozenset[str]] = frozenset(
    {
        "<!-- apothem:generated-reference:end -->",
        "{/* apothem:generated-reference:end */}",
    }
)
# The changelog page injects the root ``CHANGELOG.md`` body between these
# markers at build time. That body is literal release-history (the same
# content the root ``CHANGELOG.md`` exclusion above already covers), not a
# displayed version surface that goes stale, so its version strings are
# skipped exactly as the generated-reference block is.
_CHANGELOG_START: Final[frozenset[str]] = frozenset(
    {
        "<!-- apothem:changelog:start -->",
        "{/* apothem:changelog:start */}",
    }
)
_CHANGELOG_END: Final[frozenset[str]] = frozenset(
    {
        "<!-- apothem:changelog:end -->",
        "{/* apothem:changelog:end */}",
    }
)


@dataclass(frozen=True)
class Finding:
    """One literal semver embed in an in-scope surface."""

    path: str
    line: int
    match: str
    context: str
    rule: str = RULE_ANCHOR


@dataclass(frozen=True)
class GrepResult:
    """Aggregated walk result for a single dynamism sweep."""

    grep: str
    root: str
    scanned_count: int
    passed: bool
    findings: list[Finding] = field(default_factory=list)

    def to_json(self) -> str:
        """Return this report as a two-space-indented JSON string.

        Post-conditions: the payload carries ``{grep, root, scanned_count,
        passed, findings}``; each finding is flattened through
        ``dataclasses.asdict``.
        """
        payload = {
            "grep": self.grep,
            "root": self.root,
            "scanned_count": self.scanned_count,
            "passed": self.passed,
            "findings": [asdict(f) for f in self.findings],
        }
        return json.dumps(payload, indent=2)


def _is_in_scope(path: Path, root: Path) -> bool:
    """Return True iff *path* is a dynamism-bound surface under *root*.

    In-scope: top-level ``README.md`` and every ``*.md`` / ``*.mdx`` under
    ``site/content/docs/``.
    Out-of-scope: everything excluded by ``_EXCLUDED_PATH_SEGMENTS`` or
    ``_EXCLUDED_FILENAMES``.
    """
    if path.name in _EXCLUDED_FILENAMES:
        return False
    try:
        relative = path.relative_to(root)
    except ValueError:
        return False
    parts = relative.parts
    if any(segment in _EXCLUDED_PATH_SEGMENTS for segment in parts):
        return False
    if relative == Path("README.md"):
        return True
    under_docs = (
        parts[: len(DOCS_PATH_PARTS)] == DOCS_PATH_PARTS
        and path.suffix in DOCS_SUFFIXES
    )
    if not under_docs:
        return False
    # Locale-aware blog exclusion: a ``blog`` segment anywhere below
    # ``site/content/docs/`` is out of scope, covering both the English-root
    # blog and every ``site/content/docs/<locale>/blog/`` mirror.
    docs_relative_parts = parts[len(DOCS_PATH_PARTS) :]
    return not any(
        segment in _EXCLUDED_DOCS_SUBTREE_SEGMENTS for segment in docs_relative_parts
    )


def _scan_file(path: Path) -> list[Finding]:
    """Return every literal semver embed in *path*."""
    findings: list[Finding] = []
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return findings
    inside_generated_reference = False
    inside_changelog = False
    for line_index, line in enumerate(text.splitlines(), start=1):
        if line.strip() in _GENERATED_REFERENCE_START:
            inside_generated_reference = True
            continue
        if line.strip() in _GENERATED_REFERENCE_END:
            inside_generated_reference = False
            continue
        if line.strip() in _CHANGELOG_START:
            inside_changelog = True
            continue
        if line.strip() in _CHANGELOG_END:
            inside_changelog = False
            continue
        if inside_generated_reference or inside_changelog:
            continue
        for match in _SEMVER_RE.finditer(line):
            findings.append(
                Finding(
                    path=str(path),
                    line=line_index,
                    match=match.group(),
                    context=line.strip(),
                )
            )
    return findings


def check(root: Path) -> GrepResult:
    """Walk *root* for in-scope surfaces; flag every literal semver."""
    findings: list[Finding] = []
    scanned = 0
    candidates = sorted(p for suffix in DOCS_SUFFIXES for p in root.rglob(f"*{suffix}"))
    for candidate in candidates:
        if not candidate.is_file():
            continue
        if not _is_in_scope(candidate, root):
            continue
        scanned += 1
        findings.extend(_scan_file(candidate))
    return GrepResult(
        grep=GREP_NAME,
        root=str(root),
        scanned_count=scanned,
        passed=not findings,
        findings=findings,
    )


def main(root: Path) -> int:
    """Entry point: scan *root*, print JSON report, return exit code.

    The report carries ``inspected`` (files scanned); a scan that read no
    file fails rather than passing vacuously.
    """
    # Imported here, not at module top: ``check()`` stays stdlib-only.
    from apothem.conformity._grep_base import finish_root_report

    result = check(root)
    return finish_root_report(
        result.to_json(), passed=result.passed, inspected=result.scanned_count
    )


def _main(argv: list[str]) -> int:
    from apothem.conformity._grep_base import parse_root_args

    return main(parse_root_args(argv, prog=GREP_NAME, doc=__doc__).root)


if __name__ == "__main__":
    sys.exit(_main(sys.argv))
