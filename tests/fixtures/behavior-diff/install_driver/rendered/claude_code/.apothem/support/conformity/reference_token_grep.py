# SPDX-License-Identifier: MIT

"""Flag leaked reference-platform branding tokens on authored surfaces.

Why this enforcement exists. Apothem reimplements a peer platform's
feature-set in its own voice; the own-voice discipline requires that no
authored surface — rules, commands, skills, agents, documentation, brand
assets — leak the reference platform's slug or brand vocabulary. A
mechanical sweep proves zero in-scope hits so the product narrative reads
as its own work rather than as a paraphrase of the reference platform.

Scope. Corpus-level standalone validator. Walks the working tree under the
supplied root and inspects ONLY authored in-scope surfaces (the rules,
commands, skills, agents directories, the documentation tree, and the
brand-asset tree). The denylist data file, the conformity machinery, the
schemas directory, the test tree, and the plan-suite scratch are all
exempt — they are not the authored product narrative the discipline holds
to the zero-leak bar.

Detection. The forbidden tokens live in the package-relative denylist data
file, never in this module. Pure-alpha slugs match at word boundaries to
avoid false positives on larger words; punctuation-bearing tokens match as
escaped literals. All matching is case-insensitive.

Posture. The result is advisory: the sweep surfaces findings and never
silent-blocks by default, honoring apothem's agnostic gate posture. CI
opts into strict enforcement separately. Per the gate's advisory contract
(``gate.py`` ``Advisory validators exit 0 even when they report
findings``), ``_main`` always exits 0 — the verdict travels in the JSON
``passed`` field, which the orchestrator reads via
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

GREP_NAME: Final[str] = "reference-token-grep"
RULE_ANCHOR: Final[str] = "rules/own-voice-reimplementation.md"

EXIT_PASS: Final[int] = 0
EXIT_FAIL: Final[int] = 2

# The denylist data file is package-relative: the conformity package ships
# beside its ``schemas/`` sibling in both supported layouts — the repo
# checkout (``src/apothem/{conformity,schemas}``) and the installed tree
# (``<install-root>/apothem/{conformity,schemas}``) — so one parent hop
# from this module reaches it in either shape. The data file holds the
# forbidden tokens so this module never names them.
_DENYLIST_PATH: Final[Path] = (
    Path(__file__).resolve().parents[1] / "schemas" / "reference-token-denylist.txt"
)

# Authored in-scope surface roots (relative to the supplied root). Only text
# files under these directories are scanned.
_IN_SCOPE_DIRS: Final[tuple[str, ...]] = (
    "src/apothem/rules",
    "src/apothem/commands",
    "src/apothem/skills",
    "src/apothem/agents",
    "site/content/docs",
    "assets",
)

# Text-file suffixes scanned under the in-scope roots.
_TEXT_SUFFIXES: Final[frozenset[str]] = frozenset(
    {".md", ".mdx", ".txt", ".svg", ".json", ".yaml", ".yml"}
)

# Exempt path fragments. A candidate whose POSIX-relative path contains any
# of these fragments is never scanned — the conformity machinery, the
# schemas data files (the denylist itself), the test tree, and the
# plan-suite scratch all legitimately reference or carry the tokens.
_EXEMPT_FRAGMENTS: Final[tuple[str, ...]] = (
    ".plans/",
    "tests/",
    "src/apothem/conformity/",
    "src/apothem/schemas/",
)


@dataclass(frozen=True)
class Finding:
    """One leaked reference-platform token on an authored surface."""

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
    """Parse the denylist data file into a list of forbidden tokens.

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

    Pure-alphabetic tokens are anchored at word boundaries (``\\btoken\\b``)
    so a larger word merely containing the substring is not flagged.
    Punctuation-bearing tokens are escaped literals — word boundaries do not
    apply cleanly across ``.`` / ``-`` characters, so the escaped literal is
    matched as-is. Returns None when the denylist is empty.
    """
    if not tokens:
        return None
    alternatives: list[str] = []
    for token in tokens:
        if token.isalpha():
            alternatives.append(r"\b" + re.escape(token) + r"\b")
        else:
            alternatives.append(re.escape(token))
    return re.compile(r"(?i)(?:" + "|".join(alternatives) + r")")


def _is_in_scope(rel_posix: str) -> bool:
    """Return True iff a relative POSIX path is an authored in-scope surface."""
    for fragment in _EXEMPT_FRAGMENTS:
        if fragment in rel_posix or rel_posix.startswith(fragment.rstrip("/")):
            return False
    return any(rel_posix == d or rel_posix.startswith(d + "/") for d in _IN_SCOPE_DIRS)


def _scan_file(path: Path, rel_posix: str, pattern: re.Pattern[str]) -> list[Finding]:
    """Scan one text file; return one Finding per token match."""
    try:
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    findings: list[Finding] = []
    for line_index, line in enumerate(content.splitlines(), start=1):
        for match in pattern.finditer(line):
            findings.append(
                Finding(
                    surface=rel_posix,
                    kind="reference-token",
                    detail=f"line {line_index}: '{match.group()}'",
                )
            )
    return findings


def check(root: Path) -> GrepResult:
    """Walk the corpus under ``root``; flag leaked reference-platform tokens.

    Pre-conditions: ``root`` is the repository root (or an arbitrary subtree).
    Post-conditions: ``result.passed`` is True iff every authored in-scope
    text file contained zero denylisted tokens.
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
