# SPDX-License-Identifier: MIT

"""Flag freshness-narrative phrases on shipped public surfaces.

Why this enforcement exists. The freshness-facade rule
(``rules/freshness-facade.md``) keeps every shipped public surface a
current-version-only facade: no AI-disclosure, no backward / legacy /
obsolete replacement narrative, no placeholder / deferral, no
fix-and-refinement story-of-becoming. This matcher is the freshness analogue
of ``plain_language_grep`` — a distinct, non-overlapping token-class on the same
shipped-surface scope. ``plain_language_grep`` forbids mechanistic vocabulary
(``AI`` / ``agent`` / harness brands); this matcher forbids the narrative
PHRASES that mark a surface telling the story of its own becoming.

High-precision PHRASES, never bare words. Bare common words — ``legacy``,
``deprecated``, ``retired``, ``placeholder``, ``backward`` — have legitimate
uses (a Keep-a-Changelog ``Deprecated`` heading, a documented deprecation
policy, a ``placeholder identity`` product feature) and are deliberately NOT
denylisted. Only the narrative phrase forms ("replaces the legacy …",
"coming soon", "AI-generated") are flagged, so the matcher catches the
story-of-becoming without flagging the dictionary word. The forbidden phrases
live in the package-relative denylist data file, never in this module.

Scope. Corpus-level standalone validator. Walks the working tree under the
supplied root and inspects ONLY shipped public surfaces: the repository
root ``README.md`` and every ``*.md`` / ``*.mdx`` under
``site/content/docs/``. Developer-only surfaces (rules, commands,
matchers, plans, adapter modules) are out of scope — their process
vocabulary is load-bearing, exactly as the plain-language boundary draws it.

Detection. Each denylist phrase is matched case-insensitively. Pure-alpha
phrases anchor at word boundaries; punctuation- or space-bearing phrases
match as escaped literals. Matches inside fenced code blocks (triple
backtick) are excluded — docs legitimately quote a forbidden phrase inside a
sample or tool-output fence.

Posture. The result carries an advisory flag, honoring apothem's agnostic
gate posture; CI opts into strict enforcement separately. Per the gate's
advisory contract (``gate.py`` ``Advisory validators exit 0 even when they
report findings``), ``_main`` always exits 0 — the verdict travels in the
JSON ``passed`` field, which the orchestrator reads via
``gate._advisory_verdict`` and surfaces as ``advisory_findings_present``
without failing the ``gate --all`` run.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Final

from apothem.conformity._grep_base import iter_prose_lines

GREP_NAME: Final[str] = "freshness-token-grep"
RULE_ANCHOR: Final[str] = "rules/freshness-facade.md"

EXIT_PASS: Final[int] = 0
EXIT_FAIL: Final[int] = 2

# The denylist data file is package-relative: the conformity package ships
# beside its ``schemas/`` sibling in both the repo checkout
# (``src/apothem/{conformity,schemas}``) and the installed tree, so one parent
# hop reaches it in either shape. The data file holds the forbidden phrases so
# this module never names them.
_DENYLIST_PATH: Final[Path] = (
    Path(__file__).resolve().parents[1] / "schemas" / "freshness-token-denylist.txt"
)

# Shipped-surface scope. The root README and the documentation tree are the
# user-facing release facade the freshness mandate holds to the current-version
# bar.
_README_FILENAME: Final[str] = "README.md"
_DOCS_DIR: Final[str] = "site/content/docs"
_TEXT_SUFFIXES: Final[frozenset[str]] = frozenset({".md", ".mdx"})

# Fenced code-block delimiter — a line whose first non-whitespace content is
# ```. Opening and closing fences both match; the scanner toggles state.
_CODE_FENCE_RE: Final[re.Pattern[str]] = re.compile(r"^[ \t]*```")


@dataclass(frozen=True)
class Finding:
    """One freshness-narrative phrase on a shipped public surface."""

    surface: str
    kind: str
    detail: str
    rule: str = RULE_ANCHOR


@dataclass(frozen=True)
class GrepResult:
    """Aggregated walk result for a single corpus sweep."""

    grep: str
    root: str
    files_inspected: int
    passed: bool
    findings: list[Finding] = field(default_factory=list)

    def to_json(self) -> str:
        payload = {
            "grep": self.grep,
            "root": self.root,
            "files_inspected": self.files_inspected,
            "passed": self.passed,
            "findings": [asdict(f) for f in self.findings],
            "advisory": True,
        }
        return json.dumps(payload, indent=2)


def _load_tokens() -> list[str]:
    """Parse the denylist data file into a list of forbidden phrases.

    Pre-conditions: the package-relative denylist file exists.
    Post-conditions: returns every non-empty, non-comment line, stripped.
    """
    try:
        raw = _DENYLIST_PATH.read_text(encoding="utf-8")
    except OSError:
        return []
    tokens: list[str] = []
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        tokens.append(stripped)
    return tokens


def _compile_tokens(tokens: list[str]) -> re.Pattern[str] | None:
    """Compile the denylist into one case-insensitive alternation regex.

    Pure-alphabetic phrases anchor at word boundaries (``\\bphrase\\b``) so a
    larger word is not flagged. Space- or punctuation-bearing phrases are
    escaped literals — word boundaries do not apply cleanly across spaces and
    ``-`` characters. Returns None when the denylist is empty. Longer phrases
    are ordered first so the alternation prefers the most specific match.
    """
    if not tokens:
        return None
    alternatives: list[str] = []
    for token in sorted(tokens, key=len, reverse=True):
        if token.isalpha():
            alternatives.append(r"\b" + re.escape(token) + r"\b")
        else:
            alternatives.append(re.escape(token))
    return re.compile(r"(?i)(?:" + "|".join(alternatives) + r")")


def _is_in_scope(rel_posix: str) -> bool:
    """Return True iff a relative POSIX path is a shipped public surface.

    In scope: the repository root ``README.md`` and any ``.md`` / ``.mdx``
    under ``site/content/docs/``. Every other path is out of scope.
    """
    if rel_posix == _README_FILENAME:
        return True
    return rel_posix.startswith(_DOCS_DIR + "/")


def _scan_file(path: Path, rel_posix: str, pattern: re.Pattern[str]) -> list[Finding]:
    """Scan one text file; return findings outside fenced code blocks."""
    try:
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    findings: list[Finding] = []
    # ``iter_prose_lines`` walks the fence-toggle loop; a token inside a fence is
    # a version-sample or tool-output block, not shipped narrative. No inline
    # blanking. The indent-tolerant fence form (``^[ \t]*```) is preserved via
    # this matcher's own ``_CODE_FENCE_RE``.
    for line_index, line, _scanned in iter_prose_lines(
        content.splitlines(), fence_re=_CODE_FENCE_RE
    ):
        for match in pattern.finditer(line):
            findings.append(
                Finding(
                    surface=rel_posix,
                    kind="freshness-token",
                    detail=f"line {line_index}: '{match.group()}'",
                )
            )
    return findings


def check(root: Path) -> GrepResult:
    """Walk the corpus under ``root``; flag freshness-narrative phrases.

    Pre-conditions: ``root`` is the repository root (or an arbitrary subtree).
    Post-conditions: ``result.passed`` is True iff every shipped public
    surface contained zero denylisted phrases outside fenced code blocks.
    """
    tokens = _load_tokens()
    pattern = _compile_tokens(tokens)
    findings: list[Finding] = []
    inspected = 0
    root_resolved = root.resolve()
    if pattern is not None:
        for suffix in sorted(_TEXT_SUFFIXES):
            for path in root.rglob(f"*{suffix}"):
                if not path.is_file():
                    continue
                try:
                    rel_posix = path.resolve().relative_to(root_resolved).as_posix()
                except ValueError:
                    continue
                if not _is_in_scope(rel_posix):
                    continue
                inspected += 1
                findings.extend(_scan_file(path, rel_posix, pattern))
    return GrepResult(
        grep=GREP_NAME,
        root=str(root),
        files_inspected=inspected,
        passed=not findings,
        findings=findings,
    )


def _read_input(argv: list[str]) -> Path:
    if len(argv) >= 2:
        return Path(argv[1])
    return Path.cwd()


def _main(argv: list[str]) -> int:
    root = _read_input(argv)
    result = check(root)
    print(result.to_json())
    # Advisory posture: ``to_json`` declares ``advisory: true``, so ``_main``
    # must exit 0 even when findings are present (gate.py: "Advisory
    # validators exit 0 even when they report findings"). The verdict rides
    # the JSON ``passed`` field; the orchestrator surfaces it as
    # ``advisory_findings_present`` without failing ``gate --all``.
    return EXIT_PASS


if __name__ == "__main__":
    sys.exit(_main(sys.argv))
