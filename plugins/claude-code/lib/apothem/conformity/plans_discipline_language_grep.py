# SPDX-License-Identifier: MIT

"""Verify the canonical Plans Discipline language reaches every required surface.

Why this validator exists. Spec section 3 declares Plans Discipline as
multi-surface enforcement (defense-in-depth). Four surfaces MUST carry
the directive:

* ``AGENTS.md`` — the canonical project instruction surface.
* ``CLAUDE.md`` — the Claude Code mirror.
* ``src/apothem/output-styles/default.md`` — the ecosystem-default tonal floor.
* ``.github/copilot-instructions.md`` — the Copilot-side mirror.

Each surface MUST contain either (a) the byte-exact fixture sentence
at ``tests/fixtures/plans-discipline.txt``, or (b) a semantic-paraphrase
that covers the canonical token set with sufficient density. The
two-mode admission honors the multi-surface-coherence comparator's
semantic-equivalence-token approach: byte-exact reproduction is
strongest, paraphrase with token coverage is acceptable.

Detection strategy. The validator walks the four surfaces from
``--root`` (the repository root). Per surface, it first probes for
byte-exact fixture presence; on miss, it computes a token-coverage
score against the canonical token set. A coverage of ``COVERAGE_FLOOR``
(0.6) admits the surface; below the floor is a finding.

Exit semantics. Exits 0 when every surface passes; exits 2 on any
finding. The exit-2 convention matches the conformity-gate
orchestrator's EXIT_FAIL constant.
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Final

GREP_NAME: Final[str] = "plans-discipline-language-grep"
RULE_ANCHOR: Final[str] = "CLAUDE.md Plans Discipline (multi-surface language)"

EXIT_PASS: Final[int] = 0
EXIT_FAIL: Final[int] = 2

# Surfaces that MUST carry the Plans Discipline directive. Paths are
# relative to the repository root supplied at invocation.
REQUIRED_SURFACES: Final[tuple[str, ...]] = (
    "AGENTS.md",
    "CLAUDE.md",
    "src/apothem/output-styles/default.md",
    ".github/copilot-instructions.md",
)

# Path to the byte-exact fixture relative to the repository root.
FIXTURE_PATH: Final[str] = "tests/fixtures/plans-discipline.txt"

# Canonical token set the paraphrase tolerance scores against. Each entry is a
# tuple of accepted alternatives; the entry counts toward coverage when ANY of
# its alternatives appears (case-insensitive substring). The tokens capture the
# directive's load-bearing semantics: the canonical destination, the negative
# claim, the global ban, and the non-negotiability frame.
#
# The canonical-destination entry is the sole project-local plans location
# ``<project-root>/.apothem/plans/``; a legacy ``<project-root>/.plans/`` tree
# is no longer canonical — operators upgrade it via ``apothem migrate-workspace``.
CANONICAL_TOKENS: Final[tuple[tuple[str, ...], ...]] = (
    ("<project-root>/.apothem/plans/",),
    ("~/.codex/",),
    ("~/.claude/",),
    ("never",),
    ("global",),
    ("plans discipline",),
)
COVERAGE_FLOOR: Final[float] = 0.6


@dataclass(frozen=True)
class Finding:
    """One surface that lacks the directive at admission strength."""

    surface: str
    detail: str
    coverage: float
    rule: str = RULE_ANCHOR


@dataclass(frozen=True)
class SurfaceVerdict:
    """Per-surface admission record (informational; survives passing surfaces)."""

    surface: str
    mode: str
    coverage: float
    admitted: bool


@dataclass(frozen=True)
class GrepResult:
    """Aggregated multi-surface sweep result."""

    grep: str
    root: str
    fixture_present: bool
    surfaces: list[SurfaceVerdict]
    passed: bool
    findings: list[Finding] = field(default_factory=list)

    def to_json(self) -> str:
        """Return this report as a two-space-indented JSON string.

        Post-conditions: the payload carries ``{grep, root, fixture_present,
        surfaces, passed, findings}``; each finding is flattened through
        ``dataclasses.asdict``.
        """
        payload = {
            "grep": self.grep,
            "root": self.root,
            "fixture_present": self.fixture_present,
            "surfaces": [asdict(s) for s in self.surfaces],
            "passed": self.passed,
            "findings": [asdict(f) for f in self.findings],
        }
        return json.dumps(payload, indent=2)


def _read_fixture(root: Path) -> str | None:
    """Return the fixture body, or None when the fixture file is absent."""
    fixture_file = root / FIXTURE_PATH
    if not fixture_file.exists():
        return None
    return fixture_file.read_text(encoding="utf-8").strip()


def _coverage(body: str, tokens: tuple[tuple[str, ...], ...]) -> float:
    """Fraction of token entries present in body (case-insensitive substring).

    Each entry is a tuple of accepted alternatives; an entry counts when ANY of
    its alternatives appears. The canonical-destination entry admits the sole
    project-local ``<project-root>/.apothem/plans/`` phrasing.
    """
    if not tokens:
        return 1.0
    lowered = body.lower()
    matched = sum(
        1
        for alternatives in tokens
        if any(alt.lower() in lowered for alt in alternatives)
    )
    return matched / len(tokens)


def _verdict_for_surface(
    surface_path: str,
    body: str,
    fixture_text: str | None,
) -> tuple[SurfaceVerdict, Finding | None]:
    """Score one surface; return its verdict and any finding."""
    if fixture_text and fixture_text in body:
        verdict = SurfaceVerdict(
            surface=surface_path, mode="byte-exact", coverage=1.0, admitted=True
        )
        return verdict, None
    coverage = _coverage(body, CANONICAL_TOKENS)
    admitted = coverage >= COVERAGE_FLOOR
    verdict = SurfaceVerdict(
        surface=surface_path,
        mode="paraphrase",
        coverage=round(coverage, 3),
        admitted=admitted,
    )
    if admitted:
        return verdict, None
    finding = Finding(
        surface=surface_path,
        detail=(
            f"plans-discipline language insufficient: coverage "
            f"{coverage:.2f} < floor {COVERAGE_FLOOR:.2f} and "
            f"byte-exact fixture absent"
        ),
        coverage=round(coverage, 3),
    )
    return verdict, finding


def check(root: Path) -> GrepResult:
    """Sweep the four required surfaces under root for the directive."""
    fixture_text = _read_fixture(root)
    fixture_present = fixture_text is not None
    verdicts: list[SurfaceVerdict] = []
    findings: list[Finding] = []
    if not fixture_present:
        findings.append(
            Finding(
                surface=FIXTURE_PATH,
                detail=(
                    "byte-exact fixture absent at canonical path; "
                    "byte-exact admission disabled for every surface"
                ),
                coverage=0.0,
            )
        )
    for surface_path in REQUIRED_SURFACES:
        full_path = root / surface_path
        if not full_path.exists():
            verdicts.append(
                SurfaceVerdict(
                    surface=surface_path,
                    mode="absent",
                    coverage=0.0,
                    admitted=False,
                )
            )
            findings.append(
                Finding(
                    surface=surface_path,
                    detail="surface file absent at canonical path",
                    coverage=0.0,
                )
            )
            continue
        body = full_path.read_text(encoding="utf-8")
        verdict, finding = _verdict_for_surface(surface_path, body, fixture_text)
        verdicts.append(verdict)
        if finding is not None:
            findings.append(finding)
    return GrepResult(
        grep=GREP_NAME,
        root=str(root),
        fixture_present=fixture_present,
        surfaces=verdicts,
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
    return EXIT_PASS if result.passed else EXIT_FAIL


if __name__ == "__main__":
    sys.exit(_main(sys.argv))
