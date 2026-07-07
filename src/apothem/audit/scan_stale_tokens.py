# SPDX-License-Identifier: MIT

"""Detect hard-coded model identifiers, version pins, and stale dates.

Why this scan exists. Narrative artifacts that bake a specific model
identifier (``claude-3-opus-20240229``), a SemVer literal embedded in
prose ("requires foo >= 1.2.3"), or an "as of <date>" claim referring
to a date older than twelve months become stale silently. Stale claims
mislead readers and violate the visual-leverage staleness invariant
that says current-reality assertions carry their own freshness proof.
This scan surfaces every occurrence so refit phases can replace each
with a parameterised reference, a relative date, or an updated value
with a fresh verification stamp.

What this scan covers. Three regex families:

- **Model-identifier literals.** ``claude-2`` (with an optional ``.x`` and
  word suffix), ``claude-3-{opus,sonnet,haiku}`` and its ``3-5`` / ``3-7``
  minors (each with an optional ``-YYYYMMDD`` dated suffix), and the 4.x
  cohort ``{opus,sonnet,haiku}-4`` matched generically — an optional
  ``[-.]<minor>``, an optional ``-YYYYMMDD`` dated suffix, and an optional
  ``[<label>]`` bracket suffix — so a newly-minted 4.x minor is caught
  without a pattern edit. Any literal occurrence is a finding (the ecosystem
  resolves model selection through the host's settings; a baked identifier
  defeats that surface).
- **SemVer-in-prose.** A SemVer triple appearing inside narrative
  Markdown that is not adjacent to a known version-pinning surface
  (``CHANGELOG.md`` entries are exempt; lines containing ``version:``
  or ``semver:`` keys are exempt).
- **Stale "as-of" date claims.** Any of ``as of`` / ``valid as of`` /
  ``verified`` / ``last verified`` / ``last updated`` / ``updated`` followed
  by an ISO ``YYYY-MM-DD``; any matched date older than 12 months from the
  run's wall-clock is a finding.

What this scan excludes. The repository's own ``CHANGELOG.md`` (where
SemVer literals legitimately mark release entries) and lines containing
the literal phrase ``deprecated:`` (which document retirement, not
current behavior). Memory and plan-artifact records are excluded by
the shared narrative-surface filter.
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _scan_lib import (
    CONTENT_ROOT,
    NARRATIVE_CLASSES,
    SEVERITY_MEDIUM,
    Hit,
    WalkCallback,
    emit_json,
    load_inventory,
    walk_narrative_surfaces,
)

# Match Anthropic-family model identifiers including dated suffixes.
# Cover the full pre-4 family plus the 4.x cohort (opus / sonnet / haiku at a
# generic ``-4`` with an optional minor-version axis and an optional bracket
# label), so a newly-minted 4.x minor is caught without editing this pattern.
_MODEL_PATTERN = re.compile(
    r"\bclaude-("
    r"2(?:\.\d+)?(?:-\w+)*"
    r"|3-(?:opus|sonnet|haiku)(?:-\d{8})?"
    r"|3[-.]5-(?:opus|sonnet|haiku)(?:-\d{8})?"
    r"|3[-.]7-(?:opus|sonnet|haiku)(?:-\d{8})?"
    r"|(?:opus|sonnet|haiku)-4(?:[-.]\d+)?(?:-\d{8})?(?:\[[^\]]+\])?"
    r")\b"
)

# SemVer triple captured in two narrowly-scoped contexts:
#   (a) v-prefixed (`v1.2.3` / `v1.2.3-rc1`) — the canonical pin shape.
#   (b) bare triple anchored to a version-context keyword on the same
#       line (``version``, ``release``, ``upgraded to``, ``bump to``).
# A bare ``X.Y.Z`` without context is far more often a section number
# (``§4.8.6``), an issue reference (``#1.2.3``), or a regex / literal
# than a stale version pin; constraining context kills the false-positive
# class that dominated the un-constrained match.
_SEMVER_V_PREFIXED = re.compile(
    r"(?<![\w.])v(\d+\.\d+\.\d+(?:-[\w.]+)?(?:\+[\w.]+)?)\b"
)
_SEMVER_BARE = re.compile(r"(?<![\w.§#])(\d+\.\d+\.\d+(?:-[\w.]+)?(?:\+[\w.]+)?)\b")
_VERSION_CONTEXT_RE = re.compile(
    r"\b(version|release|upgrade(?:d)? to|bump(?:ed)? to|requires|"
    r"depends on|pin(?:ned)? to)\b",
    re.IGNORECASE,
)

# Phrases that anchor a date reference to a freshness claim.
_AS_OF_PATTERN = re.compile(
    r"\b(?:as of|valid as of|verified|verified:|last verified|"
    r"last updated|updated:?)\s+(\d{4}-\d{2}-\d{2})\b",
    re.IGNORECASE,
)

# Lines exempt from the SemVer-in-prose finding because they live in
# legitimate version-pinning contexts.
_SEMVER_EXEMPT_PATTERNS = (
    re.compile(r"^\s*version\s*:\s*", re.IGNORECASE),
    re.compile(r"^\s*semver\s*:\s*", re.IGNORECASE),
    re.compile(r"^\s*##\s*\[\d", re.IGNORECASE),  # CHANGELOG ## [0.1.5]
    re.compile(r"\bdeprecated:?\b", re.IGNORECASE),
)

# File-level exemption: the project's CHANGELOG legitimately enumerates
# SemVer release entries; date claims there are release dates, not
# freshness claims.
_FILE_EXEMPT_FROM_SEMVER = frozenset({"CHANGELOG.md"})

# URL prefixes that anchor version strings to legitimate references
# (badge image URLs, package-registry links, GitHub release pages, etc.).
# A SemVer match inside a URL is not narrative drift.
_URL_MARKER_RE = re.compile(r"https?://|\bshields\.io|\bbadgen\.net")

# A SemVer match is suppressed when the only context is a configuration
# surface that legitimately pins versions: lock files, manifests, hook
# configs. We restrict the SemVer-in-prose scan to Markdown files only;
# this set captures the Markdown-extension whitelist.
_SEMVER_SCAN_SUFFIXES = frozenset({".md", ".markdown"})


def _stale_date_threshold() -> date:
    """Return the cutoff date older than which 'as-of' claims are stale.

    Twelve months is the staleness window applied uniformly across the
    audit. A shorter window would over-flag legitimate stable claims;
    a longer one would let genuinely-stale assertions persist.
    """
    return datetime.now(timezone.utc).date() - timedelta(days=365)


def _scan_model_ids(rel: str, lineno: int, line: str) -> list[Hit]:
    """Emit a hit per literal model identifier on the line."""
    hits: list[Hit] = []
    for match in _MODEL_PATTERN.finditer(line):
        token = match.group(0)
        hits.append(
            Hit(
                file=rel,
                line=lineno,
                signal=f"hard-coded-model-identifier: {token}",
                severity=SEVERITY_MEDIUM,
                remediation=(
                    "Replace the literal model identifier with a reference"
                    " resolved through the host's model selection surface;"
                    " bake-in defeats the indirection that lets operators"
                    " upgrade."
                ),
            )
        )
    return hits


def _scan_semver_prose(rel: str, lineno: int, line: str) -> list[Hit]:
    """Emit a hit per SemVer literal that is not URL-anchored or
    inside a configuration-pin context.

    Two match channels: ``v``-prefixed pins (always flagged when not in
    an exempt context) and bare triples (flagged only when a
    version-context keyword appears on the same line).
    """
    if any(p.search(line) for p in _SEMVER_EXEMPT_PATTERNS):
        return []
    if _URL_MARKER_RE.search(line):
        return []
    hits: list[Hit] = []
    for match in _SEMVER_V_PREFIXED.finditer(line):
        token = match.group(0)
        hits.append(_semver_hit(rel, lineno, token))
    if _VERSION_CONTEXT_RE.search(line):
        for match in _SEMVER_BARE.finditer(line):
            token = match.group(0)
            hits.append(_semver_hit(rel, lineno, token))
    return hits


def _semver_hit(rel: str, lineno: int, token: str) -> Hit:
    """Construct the canonical SemVer-in-prose hit record."""
    return Hit(
        file=rel,
        line=lineno,
        signal=f"semver-in-prose: {token}",
        severity=SEVERITY_MEDIUM,
        remediation=(
            "Move the version pin to a configuration surface"
            " (manifest, schema, version file) or convert the"
            " prose claim into a parameterised reference."
        ),
    )


def _scan_stale_dates(
    rel: str, lineno: int, line: str, stale_cutoff: date
) -> list[Hit]:
    """Emit a hit per 'as-of' claim whose date predates the staleness
    cutoff."""
    hits: list[Hit] = []
    for match in _AS_OF_PATTERN.finditer(line):
        date_str = match.group(1)
        try:
            claim_date = date.fromisoformat(date_str)
        except ValueError:
            continue
        if claim_date >= stale_cutoff:
            continue
        # stale_cutoff is (today - 365d); re-add the window to recover the
        # claim's true age from today before the `// 30` month conversion.
        age_days = (stale_cutoff - claim_date).days + 365
        hits.append(
            Hit(
                file=rel,
                line=lineno,
                signal=(
                    f"stale-as-of-claim: {date_str} (~{age_days // 30} months old)"
                ),
                severity=SEVERITY_MEDIUM,
                remediation=(
                    "Re-verify the claim against current state and update"
                    " the date stamp, or restate the claim with a"
                    " parameterised reference that does not require"
                    " periodic re-verification."
                ),
            )
        )
    return hits


def _is_markdown(path_str: str) -> bool:
    """Return True if the file path looks like a Markdown document."""
    return Path(path_str).suffix.lower() in _SEMVER_SCAN_SUFFIXES


def _scan_callback(stale_cutoff: date) -> WalkCallback:
    """Build the per-file scanner closure."""

    def _walk(path: Path, record: dict[str, Any], content: str) -> list[Hit]:
        rel = record["path"]
        is_md = _is_markdown(rel)
        file_exempt_semver = Path(rel).name in _FILE_EXEMPT_FROM_SEMVER
        in_fence = False
        hits: list[Hit] = []
        for lineno, line in enumerate(content.splitlines(), start=1):
            if line.lstrip().startswith("```"):
                in_fence = not in_fence
                continue
            hits.extend(_scan_model_ids(rel, lineno, line))
            if is_md and not in_fence and not file_exempt_semver:
                hits.extend(_scan_semver_prose(rel, lineno, line))
            hits.extend(_scan_stale_dates(rel, lineno, line, stale_cutoff))
        return hits

    return _walk


def main(argv: list[str] | None = None) -> int:
    """Scan narrative surfaces for stale model ids, SemVer-in-prose, and aged as-of dates and write ``drift-stale-tokens.json``.

    Loads the inventory, computes the twelve-month staleness cutoff, walks
    each narrative surface for the three token families, emits the envelope,
    and prints a per-signal summary.
    """
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--inventory",
        type=Path,
        default=Path(".audit/inventory.json"),
    )
    parser.add_argument("--root", type=Path, default=CONTENT_ROOT)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(".audit/drift-stale-tokens.json"),
    )
    args = parser.parse_args(argv)

    if not args.inventory.exists():
        print(
            f"error: inventory not found at {args.inventory}",
            file=sys.stderr,
        )
        return 1

    records, sha = load_inventory(args.inventory)
    cutoff = _stale_date_threshold()
    hits = walk_narrative_surfaces(records, args.root, _scan_callback(cutoff))
    emit_json(args.output, "scan_stale_tokens", hits, sha)
    narrative_count = sum(1 for r in records if r.get("class") in NARRATIVE_CLASSES)
    by_signal: dict[str, int] = {}
    for h in hits:
        kind = h.signal.split(":", 1)[0]
        by_signal[kind] = by_signal.get(kind, 0) + 1
    summary = ", ".join(f"{k}={v}" for k, v in sorted(by_signal.items()))
    print(
        f"scan_stale_tokens: {len(hits)} hit(s) across "
        f"{narrative_count} narrative files [{summary or 'none'}]"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
