# SPDX-License-Identifier: MIT

"""multi-surface-coherence-grep: shared-claim coherence across AI-conventions surfaces.

Why this enforcement exists. The repo mirrors its operating disciplines across
parallel AI-instruction surfaces (``AGENTS.md``, ``CLAUDE.md``,
``.github/copilot-instructions.md``, and the harness bootstraps), and the
AI-surface canon requires those shared claims to stay semantically equivalent.
Left unchecked, a claim edited in one surface silently diverges from its
peers — the fix-in-one-place-missed-in-many drift the project exists to
prevent. This validator is the mechanical proof the surfaces still agree.

Reads ``tests/fixtures/multi-surface-claims.yaml`` and, for each enumerated
claim, walks every ``required-in`` surface (and any ``optional-in`` surface
that exists on disk). For each (claim, surface) pair the validator:

1. Computes a token-coverage score using the claim's
   ``semantic-equivalence-tokens`` list — case-insensitive substring matches
   divided by the token count. A claim is **present** in a surface when the
   score meets or exceeds ``COVERAGE_THRESHOLD`` AND at least ``MIN_TOKEN_HITS``
   distinct tokens match.
2. Records contradiction signals — a surface whose matching paragraph carries
   a negation marker against a token the canonical surface (AGENTS.md)
   asserts affirmatively flags ``COHERENCE_CONTRADICTION``.
3. Honors the ``<!-- coherence-override: <claim-id> -->`` marker per the
   reconciliation rule: when present, the surface is exempted from the claim's
   coherence check and an advisory finding is emitted naming the ADR pairing
   requirement (``COHERENCE_OVERRIDE_HONORED``).

Verdict matrix:
    pass    — every required-in surface contains every claim with no
              contradictions; claims missing from the canonical surface
              before its refit lands surface as advisory partial-coverage
              findings (``severity: warning``) that do NOT fail the verdict.
    fail    — any contradiction or any required-claim absent from a
              required-in surface without an override marker.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from apothem.conformity._grep_base import GrepResult, run_grep

GREP_NAME: Final[str] = "multi-surface-coherence-grep"

# Working-tree root anchor. In the repo checkout, parents[3] of
# ``src/apothem/conformity/<file>.py`` is the working-tree root that
# carries the claims fixture and the tracked surfaces. In the installed
# tree (``<install-root>/apothem/conformity/``) the anchor is a coarse
# filesystem ancestor with no fixture beneath it: hook-mode dispatches
# degrade to a pass-through via the relative_to() guard in
# _is_in_scope(), and a direct invocation reports the absent fixture as
# an advisory pass per _IN_REPO_CHECKOUT below.
ECOSYSTEM_ROOT: Final[Path] = Path(__file__).resolve().parents[3]

# Shape detection: the claims fixture ships only with the repo checkout
# (where the conformity package sits inside a ``src/`` tree). The
# installed tree carries the package beside its ``schemas/`` sibling with
# no ``src/`` parent and no test-fixture corpus, so a missing fixture
# there is the expected state, not a defect.
_IN_REPO_CHECKOUT: Final[bool] = Path(__file__).resolve().parents[2].name == "src"
CLAIMS_FIXTURE_RELATIVE: Final[Path] = (
    Path("tests") / "fixtures" / "multi-surface-claims.yaml"
)
ADR_DIR_RELATIVE: Final[Path] = Path("site") / "content" / "docs" / "adr"
CANONICAL_SURFACE: Final[str] = "AGENTS.md"

# Coverage parameters. The fixture's claims carry 3-5 tokens; the threshold
# triggers a "present" verdict when at least half the tokens AND at least
# two tokens match.
COVERAGE_THRESHOLD: Final[float] = 0.5
MIN_TOKEN_HITS: Final[int] = 2

# Negation markers used for contradiction detection. A surface whose
# matching paragraph carries any of these tokens immediately before a
# claim token is marked "negated"; a surface without any negation marker
# in the same window is "affirmative".
NEGATION_MARKERS: Final[tuple[str, ...]] = (
    "never",
    "must not",
    "must never",
    "shall not",
    "no longer",
    "do not",
    "don't",
)

# Tokens that are themselves modal verbs or short directive words. Negation
# analysis skips these because matching them inside their own negation
# phrase ("MUST NOT" contains "MUST") produces false-positive contradictions
# whenever the canonical surface lists the modal verbs as policy vocabulary.
NEGATION_ANALYSIS_SKIP_TOKENS: Final[frozenset[str]] = frozenset(
    {"must", "should", "may", "shall", "can", "will", "no", "never"}
)

# Window before the matched token in which a negation marker is decisive.
# Restricting to a leading window (rather than ±80) avoids the
# "MUST NOT" → "MUST" self-shadowing pattern.
NEGATION_LEADING_WINDOW: Final[int] = 25

# Override marker per reconciliation rule §4.7.3.
OVERRIDE_RE: Final[re.Pattern[str]] = re.compile(
    r"<!--\s*coherence-override:\s*([a-z0-9.\-]+)\s*-->"
)

RULE_CLAIM_MISSING: Final[str] = "COHERENCE_CLAIM_MISSING"
RULE_CONTRADICTION: Final[str] = "COHERENCE_CONTRADICTION"
RULE_OVERRIDE_HONOURED: Final[str] = "COHERENCE_OVERRIDE_HONORED"
RULE_FIXTURE_ABSENT: Final[str] = "COHERENCE_FIXTURE_ABSENT"
RULE_PARTIAL_COVERAGE: Final[str] = "COHERENCE_PARTIAL_COVERAGE"

SEVERITY_ERROR: Final[str] = "error"
SEVERITY_WARNING: Final[str] = "warning"


@dataclass(frozen=True)
class Finding:
    """One diagnostic finding emitted during the coherence check."""

    line: int
    match: str
    context: str
    rule: str
    severity: str = SEVERITY_ERROR


@dataclass(frozen=True)
class Claim:
    """One enumerated claim from the multi-surface-claims fixture."""

    id: str
    claim: str
    required_in: tuple[str, ...]
    optional_in: tuple[str, ...]
    semantic_equivalence_tokens: tuple[str, ...]


# ---------------------------------------------------------------------------
# Minimal YAML claim-list parser
# ---------------------------------------------------------------------------
# A constrained parser targeting the canonical fixture shape
# (`tests/fixtures/multi-surface-claims.yaml`). Avoiding a third-party
# dependency keeps the validator hot-loadable from the orchestrator without
# environment shaping.


def _parse_claims_yaml(text: str) -> list[Claim]:
    """Parse the canonical claim-list fixture into a list of ``Claim`` objects."""
    lines = text.splitlines()
    claims: list[Claim] = []

    in_claims = False
    current: dict[str, object] | None = None
    current_list_key: str | None = None

    def _flush(record: dict[str, object] | None) -> None:
        if record is None:
            return
        claim_id = record.get("id")
        statement = record.get("claim")
        required = record.get("required-in") or []
        optional = record.get("optional-in") or []
        tokens = record.get("semantic-equivalence-tokens") or []
        if not isinstance(claim_id, str) or not isinstance(statement, str):
            return
        if not isinstance(required, list) or not isinstance(optional, list):
            return
        if not isinstance(tokens, list):
            return
        claims.append(
            Claim(
                id=claim_id,
                claim=statement,
                required_in=tuple(str(s) for s in required),
                optional_in=tuple(str(s) for s in optional),
                semantic_equivalence_tokens=tuple(str(t) for t in tokens),
            )
        )

    for raw in lines:
        # Strip trailing comments while preserving quoted-string content.
        stripped_for_test = raw.lstrip()
        if stripped_for_test.startswith("#"):
            continue
        if not stripped_for_test:
            continue

        if not in_claims:
            if stripped_for_test.startswith("claims:"):
                in_claims = True
            continue

        # Inside `claims:` block. Indentation is the structural signal.
        indent = len(raw) - len(raw.lstrip())

        # New claim-record marker: `  - id: foo`
        if indent == 2 and stripped_for_test.startswith("- "):
            _flush(current)
            current = {}
            current_list_key = None
            tail = stripped_for_test[2:]
            if ":" in tail:
                key, _, value = tail.partition(":")
                key = key.strip()
                value = value.strip()
                current[key] = _strip_quotes(value)
            continue

        if current is None:
            continue

        # Field line at indent 4 — either `key: value` or `key:` (list opener).
        if indent == 4:
            key, _, value = stripped_for_test.partition(":")
            key = key.strip()
            value = value.strip()
            if value == "[]":
                current[key] = []
                current_list_key = None
            elif value:
                current[key] = _strip_quotes(value)
                current_list_key = None
            else:
                current[key] = []
                current_list_key = key
            continue

        # List item at indent 6 — `- value`
        if indent == 6 and stripped_for_test.startswith("- ") and current_list_key:
            value = _strip_quotes(stripped_for_test[2:].strip())
            target = current.get(current_list_key)
            if isinstance(target, list):
                target.append(value)

    _flush(current)
    return claims


def _strip_quotes(value: str) -> str:
    """Remove enclosing single or double quotes if present."""
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        return value[1:-1]
    return value


# ---------------------------------------------------------------------------
# Surface analysis
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SurfacePresence:
    """Whether a claim is present in a surface, plus contradiction signals."""

    present: bool
    coverage: float
    matched_tokens: tuple[str, ...]
    negated: bool
    matched_paragraph: str


def _surface_path(surface: str) -> Path:
    """Resolve a surface's on-disk path against the ecosystem root."""
    return ECOSYSTEM_ROOT / surface


def _read_surface(surface: str) -> str | None:
    """Read a surface file, returning ``None`` when absent."""
    target = _surface_path(surface)
    if not target.is_file():
        return None
    return target.read_text(encoding="utf-8")


def _find_best_paragraph(body: str, tokens: tuple[str, ...]) -> tuple[str, int]:
    """Locate the paragraph with the highest token-match count.

    Paragraphs are blank-line-separated runs. Returns ``("", 0)`` when no
    paragraph contains any token.
    """
    paragraphs = re.split(r"\n\s*\n", body)
    best_text = ""
    best_count = 0
    for para in paragraphs:
        para_lower = para.lower()
        count = sum(1 for token in tokens if token.lower() in para_lower)
        if count > best_count:
            best_count = count
            best_text = para
    return best_text, best_count


def _has_negation_near(paragraph: str, token: str) -> bool:
    """Return True when a negation marker leads *token* within the window.

    The window is leading-only (the marker must appear before the token,
    within ``NEGATION_LEADING_WINDOW`` characters of its start) to avoid
    self-shadowing — a token that is itself part of a negation phrase
    (e.g., ``MUST`` inside ``MUST NOT``) would otherwise always register
    as negated.
    """
    if not paragraph or not token:
        return False
    para_lower = paragraph.lower()
    token_lower = token.lower()
    idx = para_lower.find(token_lower)
    if idx == -1:
        return False
    window_start = max(0, idx - NEGATION_LEADING_WINDOW)
    window = para_lower[window_start:idx]
    return any(marker in window for marker in NEGATION_MARKERS)


def _analyse_presence(body: str, claim: Claim) -> SurfacePresence:
    """Score *body* against *claim*'s semantic-equivalence tokens."""
    tokens = claim.semantic_equivalence_tokens
    if not tokens:
        return SurfacePresence(
            present=False,
            coverage=0.0,
            matched_tokens=(),
            negated=False,
            matched_paragraph="",
        )
    body_lower = body.lower()
    matched = tuple(token for token in tokens if token.lower() in body_lower)
    coverage = len(matched) / len(tokens)
    present = coverage >= COVERAGE_THRESHOLD and len(matched) >= MIN_TOKEN_HITS
    paragraph, _ = _find_best_paragraph(body, tokens)
    negated = False
    if present and matched:
        # Filter modal verbs and short directive words from the negation
        # check (see NEGATION_ANALYSIS_SKIP_TOKENS). A surface is negated
        # against the claim only when EVERY remaining (non-modal) matched
        # token sits in negation context — a single un-negated mention
        # otherwise indicates the claim is asserted affirmatively somewhere.
        analysis_tokens = tuple(
            t for t in matched if t.lower() not in NEGATION_ANALYSIS_SKIP_TOKENS
        )
        if analysis_tokens:
            negated = all(_has_negation_near(paragraph, t) for t in analysis_tokens)
    return SurfacePresence(
        present=present,
        coverage=coverage,
        matched_tokens=matched,
        negated=negated,
        matched_paragraph=paragraph,
    )


def _has_override_marker(body: str, claim_id: str) -> bool:
    """Return True when *body* carries an override marker for *claim_id*."""
    return any(match.group(1) == claim_id for match in OVERRIDE_RE.finditer(body))


def _adr_dir_populated() -> bool:
    """Return True when the site ADR directory contains at least one ``*.md`` file."""
    adr_dir = ECOSYSTEM_ROOT / ADR_DIR_RELATIVE
    if not adr_dir.is_dir():
        return False
    return any(adr_dir.glob("*.md"))


# ---------------------------------------------------------------------------
# Public check entry point
# ---------------------------------------------------------------------------


def _evaluate_claim(
    claim: Claim,
    surface_bodies: dict[str, str],
) -> list[Finding]:
    """Per-claim coherence evaluation across required and optional surfaces."""
    findings: list[Finding] = []

    # Step 1 — assemble per-surface presence records.
    presence: dict[str, SurfacePresence] = {}
    overrides: dict[str, bool] = {}
    for surface, body in surface_bodies.items():
        presence[surface] = _analyse_presence(body, claim)
        overrides[surface] = _has_override_marker(body, claim.id)

    canonical_present = (
        CANONICAL_SURFACE in presence and presence[CANONICAL_SURFACE].present
    )

    # Step 2 — required-in surfaces must contain the claim (unless override).
    for surface in claim.required_in:
        surface_body = surface_bodies.get(surface)
        if surface_body is None:
            findings.append(
                Finding(
                    line=0,
                    match=surface,
                    context=(
                        f"required surface {surface!r} for claim {claim.id!r}"
                        f" is absent on disk"
                    ),
                    rule=RULE_CLAIM_MISSING,
                    severity=SEVERITY_ERROR,
                )
            )
            continue
        record = presence[surface]
        if record.present:
            continue
        if overrides[surface]:
            findings.append(
                Finding(
                    line=0,
                    match=surface,
                    context=(
                        f"surface {surface!r} carries an override marker for"
                        f" claim {claim.id!r}; the surface is exempt from the"
                        f" coherence check"
                    ),
                    rule=RULE_OVERRIDE_HONOURED,
                    severity=SEVERITY_WARNING,
                )
            )
            continue
        # Pre-Phase-05A expected-state: when the canonical surface itself
        # does not yet carry the claim, partial coverage is advisory rather
        # than an error. The downstream refit landing the canonical claim
        # promotes the finding to an error on the next run.
        if not canonical_present and surface != CANONICAL_SURFACE:
            findings.append(
                Finding(
                    line=0,
                    match=surface,
                    context=(
                        f"claim {claim.id!r} present in {surface!r} but absent"
                        f" in canonical surface {CANONICAL_SURFACE!r};"
                        f" advisory pre-canonical-refit"
                    ),
                    rule=RULE_PARTIAL_COVERAGE,
                    severity=SEVERITY_WARNING,
                )
            )
            continue
        if surface == CANONICAL_SURFACE:
            findings.append(
                Finding(
                    line=0,
                    match=surface,
                    context=(
                        f"claim {claim.id!r} absent in canonical surface"
                        f" {surface!r}; advisory pre-canonical-refit"
                    ),
                    rule=RULE_PARTIAL_COVERAGE,
                    severity=SEVERITY_WARNING,
                )
            )
            continue
        findings.append(
            Finding(
                line=0,
                match=surface,
                context=(
                    f"claim {claim.id!r} required in {surface!r} but not"
                    f" detected (coverage {record.coverage:.2f},"
                    f" matched-tokens {list(record.matched_tokens)})"
                ),
                rule=RULE_CLAIM_MISSING,
                severity=SEVERITY_ERROR,
            )
        )

    # Step 3 — optional-in surfaces only contribute contradictions; their
    # absence is silent. (Inclusion-by-default is governed by the opt-in
    # ratification record at `.audit/multi-surface-opt-in.yml`, not by this
    # validator.)

    # Step 4 — contradiction detection. A non-canonical surface whose
    # matching paragraph fully negates the claim's tokens contradicts a
    # canonical surface that asserts the claim affirmatively.
    canonical_record = presence.get(CANONICAL_SURFACE)
    if canonical_record is None or not canonical_record.present:
        return findings
    if canonical_record.negated:
        # Canonical voice itself negates — coherence cannot be assessed
        # against the canonical surface for this claim.
        return findings
    for surface, record in presence.items():
        if surface == CANONICAL_SURFACE:
            continue
        if not record.present:
            continue
        if overrides[surface]:
            continue
        if record.negated:
            findings.append(
                Finding(
                    line=0,
                    match=surface,
                    context=(
                        f"surface {surface!r} negates claim {claim.id!r}"
                        f" while canonical surface {CANONICAL_SURFACE!r}"
                        f" asserts it affirmatively"
                    ),
                    rule=RULE_CONTRADICTION,
                    severity=SEVERITY_ERROR,
                )
            )

    return findings


def _is_in_scope(path: Path) -> bool:
    """Return True when *path* is the claims fixture or any tracked surface."""
    try:
        rel = path.resolve().relative_to(ECOSYSTEM_ROOT)
    except ValueError:
        return False
    if rel == CLAIMS_FIXTURE_RELATIVE:
        return True
    fixture = ECOSYSTEM_ROOT / CLAIMS_FIXTURE_RELATIVE
    if not fixture.is_file():
        return False
    surfaces: set[str] = set()
    for claim in _parse_claims_yaml(fixture.read_text(encoding="utf-8")):
        surfaces.update(claim.required_in)
        surfaces.update(claim.optional_in)
    return rel.as_posix() in surfaces


def check(content: str, path: Path | None = None) -> GrepResult:
    """Validate shared-claim coherence across AI-conventions surfaces.

    Hook-mode pass-through. When *path* is set and is neither the claims
    fixture nor any surface enumerated in the fixture, the validator
    returns ``passed=True`` immediately. The full tree-level scan runs on
    in-scope dispatches and on CLI mode without a path argument.

    Returns:
        ``GrepResult`` with ``passed=True`` when no error-severity findings
        emit. Warning-severity findings (partial coverage pre-canonical-refit,
        honored overrides) are reported but do not fail the verdict.
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

    fixture = ECOSYSTEM_ROOT / CLAIMS_FIXTURE_RELATIVE
    if not fixture.is_file():
        # In the repo checkout the fixture is load-bearing and its absence
        # is an error. Outside the checkout (installed tree) the fixture is
        # not shipped, so the absence is an advisory pass — there is no
        # surface corpus to assert coherence against.
        absence_severity = SEVERITY_ERROR if _IN_REPO_CHECKOUT else SEVERITY_WARNING
        return GrepResult(
            grep=GREP_NAME,
            path=str(fixture),
            passed=not _IN_REPO_CHECKOUT,
            findings=[
                Finding(
                    line=0,
                    match=str(CLAIMS_FIXTURE_RELATIVE.as_posix()),
                    context=(
                        f"claim-list fixture absent at"
                        f" {CLAIMS_FIXTURE_RELATIVE.as_posix()}"
                    ),
                    rule=RULE_FIXTURE_ABSENT,
                    severity=absence_severity,
                )
            ],
        )

    claims = _parse_claims_yaml(fixture.read_text(encoding="utf-8"))

    # Cache surface bodies (a surface may appear in multiple claims).
    surface_cache: dict[str, str] = {}
    relevant_surfaces: set[str] = set()
    for claim in claims:
        relevant_surfaces.update(claim.required_in)
        relevant_surfaces.update(claim.optional_in)
    for surface in relevant_surfaces:
        body = _read_surface(surface)
        if body is not None:
            surface_cache[surface] = body

    findings: list[Finding] = []
    for claim in claims:
        findings.extend(_evaluate_claim(claim, surface_cache))

    # Emit a single advisory if any override marker is in flight but
    # the ADR directory is empty — the spec requires an ADR pairing.
    has_overrides = any(f.rule == RULE_OVERRIDE_HONOURED for f in findings)
    if has_overrides and not _adr_dir_populated():
        findings.append(
            Finding(
                line=0,
                match=str(ADR_DIR_RELATIVE.as_posix()),
                context=(
                    "override marker(s) in flight but no ADR files exist at"
                    f" {ADR_DIR_RELATIVE.as_posix()}; pairing pending"
                ),
                rule=RULE_OVERRIDE_HONOURED,
                severity=SEVERITY_WARNING,
            )
        )

    error_findings = [f for f in findings if f.severity == SEVERITY_ERROR]
    return GrepResult(
        grep=GREP_NAME,
        path=str(fixture),
        passed=not error_findings,
        findings=findings,
    )


if __name__ == "__main__":
    sys.exit(run_grep(check, sys.argv))
