# SPDX-License-Identifier: MIT

"""Detailed AI-conventions surface presence and coherence map.

Why this tool exists. The ecosystem ships its AI-assistant directive
prose across multiple surfaces — ``AGENTS.md`` (canonical project voice),
``CLAUDE.md`` (Claude Code mirror), ``.github/copilot-instructions.md``
(GitHub Copilot voice), and optional siblings
(``site/content/docs/architecture/agents.mdx``, ``.cursorrules``,
``.windsurfrules``) per the operator's opt-in. Each surface MUST carry
the same shared discipline claims (Plans Discipline, ambiguity
resolution, authorship header, naming, anti-patterns, modal hierarchy)
and SHOULD carry the canonical nine-section structure (Project Context,
Coding Conventions, File Headers, Plans Discipline, structured-inquiry Equivalent Behavior, Forbidden Patterns, Output Format, Review
Checklist, Pointers). The coarse pre-scan at the prior audit step
records bare presence; this deeper scan walks every present surface,
parses level-two headings, tests for the nine canonical sections by a
heading-and-body heuristic, computes the pairwise shared-section
coherence map across present surfaces, and emits a per-surface
authoring / refinement plan that the downstream Copilot-instructions
author, optional-surface generator, and instruction-surface refit consume.

What the tool captures. For every candidate surface in scope:
``path``, ``presence`` (``present`` / ``absent`` / ``partial``),
``sha256``, ``line-count``, parsed level-two headings, and a section-
presence map naming each canonical section's status (``present`` /
``absent`` / ``renamed-to:<heading-text>``). The coherence map carries
one entry per ordered pair of present surfaces; each entry records, for
every shared section (Plans Discipline, Structured Inquiry,
File Headers, Forbidden Patterns, Naming, Anti-Patterns, Modal
Hierarchy), one of four verdicts: ``coherent``, ``contradicts``,
``partial``, ``n/a``. The authoring / refinement plan is an array of
per-surface action items naming the missing-section template to
install, the present-but-drifted section delta to apply, or the
contradiction reconciliation path (default: ``AGENTS.md`` is the
canonical project voice; the divergent surface mirrors).

What the tool reports. ``ai-surfaces.json`` (machine-readable) and
``ai-surfaces.md`` (human-readable mirror) at ``.audit/``. The deeper
authoring passes consume the plan; the coherence-validator's fixture
template is informed by this map's structure.

Scope boundary. The tool ONLY reads the candidate surface files; it
NEVER writes to them. The semantic-equivalence test on shared sections
is heuristic (key-token overlap and claim-pattern matching); the
rigorous test lives at the multi-surface coherence validator and is
fixture-driven.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _scan_lib import load_inventory, read_text_safely

# ---------------------------------------------------------------------------
# The candidate-surface catalog, the canonical-section table, and the
# status vocabularies live in ``ai_surface_catalog`` — pure declaration,
# held apart from the scanning that reads it. Re-exported here because
# this module is the entry point for the surface-coherence pass.
# ---------------------------------------------------------------------------
from apothem.audit.ai_surface_catalog import (
    ALL_SECTIONS_FOR_PRESENCE,
    CANDIDATE_SURFACES,
    COHERENCE_COHERENT,
    COHERENCE_CONTRADICTS,
    COHERENCE_NOT_APPLICABLE,
    COHERENCE_PARTIAL,
    PRESENCE_ABSENT,
    PRESENCE_PRESENT,
    PRESENCE_RENAMED_PREFIX,
    SHARED_SECTIONS_FOR_COHERENCE,
    SURFACE_ABSENT,
    SURFACE_AGENTS_ROOT,
    SURFACE_CLAUDE_NESTED,
    SURFACE_CLAUDE_ROOT,
    SURFACE_COPILOT,
    SURFACE_PARTIAL,
    SURFACE_PRESENT,
    CanonicalSection,
    SurfaceDescriptor,
)

# ---------------------------------------------------------------------------
# Heading parsing and section detection live in ``ai_surface_parsing`` —
# pure functions over strings, held apart from the scan state that reads
# their verdict. Re-exported here; see ``__all__`` for the full facade.
# ---------------------------------------------------------------------------
from apothem.audit.ai_surface_parsing import (
    HeadingBlock,
    body_signature_count,
    detect_section_presence,
    heading_text_matches,
    parse_headings,
)

# ---------------------------------------------------------------------------
# Per-surface scan.
# ---------------------------------------------------------------------------


@dataclass
class SurfaceScan:
    """The full result of scanning one candidate surface.

    Carries the surface-level ``presence`` verdict, content digest, parsed
    headings, and the per-section presence map the coherence and authoring
    passes read.
    """

    descriptor: SurfaceDescriptor
    presence: str
    sha256: str | None
    line_count: int
    headings: list[HeadingBlock]
    section_presence: dict[str, str]
    raw_content: str


def scan_surface(descriptor: SurfaceDescriptor, root: Path) -> SurfaceScan:
    """Scan one candidate surface and return its full presence record.

    A missing file yields ``absent``; an empty file yields ``partial``; a
    present file is hashed, its headings parsed, and each canonical section's
    presence detected.
    """
    target = root / descriptor.path
    if not target.exists() or not target.is_file():
        return SurfaceScan(
            descriptor=descriptor,
            presence=SURFACE_ABSENT,
            sha256=None,
            line_count=0,
            headings=[],
            section_presence={
                s.slug: PRESENCE_ABSENT for s in ALL_SECTIONS_FOR_PRESENCE
            },
            raw_content="",
        )
    content = read_text_safely(target)
    if not content:
        return SurfaceScan(
            descriptor=descriptor,
            presence=SURFACE_PARTIAL,
            sha256=None,
            line_count=0,
            headings=[],
            section_presence={
                s.slug: PRESENCE_ABSENT for s in ALL_SECTIONS_FOR_PRESENCE
            },
            raw_content="",
        )
    raw = target.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    headings = parse_headings(content)
    line_count = len(content.splitlines())
    presence_map: dict[str, str] = {}
    for section in ALL_SECTIONS_FOR_PRESENCE:
        presence_map[section.slug] = detect_section_presence(section, headings, content)
    return SurfaceScan(
        descriptor=descriptor,
        presence=SURFACE_PRESENT,
        sha256=sha,
        line_count=line_count,
        headings=headings,
        section_presence=presence_map,
        raw_content=content,
    )


# ---------------------------------------------------------------------------
# Coherence map. For every ordered pair of present surfaces and every
# shared section we record one verdict.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CoherenceVerdict:
    """One shared-section coherence verdict for a pair of surfaces.

    ``verdict`` is one of ``coherent`` / ``contradicts`` / ``partial`` /
    ``n/a``; ``rationale`` records the heuristic that produced it.
    """

    section_slug: str
    section_display: str
    verdict: str
    rationale: str


def section_present_in_scan(scan: SurfaceScan, slug: str) -> bool:
    """True when the section is present (either canonical or renamed)."""
    status = scan.section_presence.get(slug, PRESENCE_ABSENT)
    return status != PRESENCE_ABSENT


def shared_claim_overlap(
    section: CanonicalSection,
    scan_a: SurfaceScan,
    scan_b: SurfaceScan,
) -> tuple[int, int, int]:
    """Return ``(both, only_a, only_b)`` body-signature counts.

    A shared signature appearing in both surfaces' bodies counts toward
    ``both``; a signature appearing in only one counts toward the
    asymmetric bucket. The triple drives the verdict heuristic.
    """
    both = 0
    only_a = 0
    only_b = 0
    for signature in section.body_signatures:
        in_a = signature in scan_a.raw_content
        in_b = signature in scan_b.raw_content
        if in_a and in_b:
            both += 1
        elif in_a:
            only_a += 1
        elif in_b:
            only_b += 1
    return both, only_a, only_b


def coherence_verdict_for(
    section: CanonicalSection,
    scan_a: SurfaceScan,
    scan_b: SurfaceScan,
) -> CoherenceVerdict:
    """Return the coherence verdict for one shared section across two surfaces.

    ``n/a`` when either surface lacks the section; otherwise the verdict is
    derived from the shared / asymmetric body-signature overlap — matching
    signatures on both sides read as ``coherent``, one-sided claims as
    ``partial``, and two-sided asymmetric claims as a candidate ``contradicts``.
    """
    if not section_present_in_scan(scan_a, section.slug) or not section_present_in_scan(
        scan_b, section.slug
    ):
        return CoherenceVerdict(
            section_slug=section.slug,
            section_display=section.display,
            verdict=COHERENCE_NOT_APPLICABLE,
            rationale=(
                "At least one surface lacks the section; coherence is undefined "
                "until both surfaces author the section."
            ),
        )
    both, only_a, only_b = shared_claim_overlap(section, scan_a, scan_b)
    total_signatures = len(section.body_signatures)
    if both == 0 and only_a == 0 and only_b == 0:
        return CoherenceVerdict(
            section_slug=section.slug,
            section_display=section.display,
            verdict=COHERENCE_PARTIAL,
            rationale=(
                "Both surfaces carry the section heading but neither body shows "
                "the canonical claim signatures; the rigorous coherence test "
                "lives at the multi-surface coherence validator."
            ),
        )
    if both > 0 and only_a == 0 and only_b == 0:
        return CoherenceVerdict(
            section_slug=section.slug,
            section_display=section.display,
            verdict=COHERENCE_COHERENT,
            rationale=(
                f"Both surfaces share {both} of {total_signatures} canonical "
                "claim signatures; no asymmetric claim was detected."
            ),
        )
    if (only_a > 0 and only_b == 0) or (only_a == 0 and only_b > 0):
        return CoherenceVerdict(
            section_slug=section.slug,
            section_display=section.display,
            verdict=COHERENCE_PARTIAL,
            rationale=(
                f"Shared claims: {both}; asymmetric claims: {only_a + only_b}. "
                "One surface carries claims absent from the other; reconcile "
                "by mirroring the canonical project voice."
            ),
        )
    # Both surfaces carry asymmetric claims — the heuristic flags this
    # as a candidate contradiction; the validator's fixture confirms.
    return CoherenceVerdict(
        section_slug=section.slug,
        section_display=section.display,
        verdict=COHERENCE_CONTRADICTS,
        rationale=(
            f"Each surface carries asymmetric claims (only-A={only_a}, "
            f"only-B={only_b}, shared={both}); the heuristic flags a candidate "
            "contradiction for the validator's fixture-driven confirmation."
        ),
    )


def build_coherence_map(scans: list[SurfaceScan]) -> dict[str, list[dict[str, str]]]:
    """Return the pairwise coherence map keyed by ``A__vs__B``."""
    present_scans = [s for s in scans if s.presence == SURFACE_PRESENT]
    coherence: dict[str, list[dict[str, str]]] = {}
    for index_a, scan_a in enumerate(present_scans):
        for scan_b in present_scans[index_a + 1 :]:
            pair_key = f"{scan_a.descriptor.path}__vs__{scan_b.descriptor.path}"
            verdicts: list[dict[str, str]] = []
            for section in SHARED_SECTIONS_FOR_COHERENCE:
                verdict = coherence_verdict_for(section, scan_a, scan_b)
                verdicts.append(asdict(verdict))
            coherence[pair_key] = verdicts
    return coherence


# ---------------------------------------------------------------------------
# Authoring / refinement plan. One action item per surface; items name
# the missing-section template, the present-but-drifted delta, or the
# contradiction reconciliation path.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PlanAction:
    """One authoring / refinement action item for a single surface.

    ``action`` names the operation (author, install-missing-section,
    rename-or-mirror, reconcile-contradiction); ``target_phase_hint`` routes
    it to the downstream pass that carries it out.
    """

    surface: str
    action: str
    detail: str
    target_phase_hint: str


def template_for_section(section: CanonicalSection) -> str:
    """Return a one-line template summary for the named section."""
    return (
        f"Author '{section.display}' section per the canonical nine-section "
        f"structure; body covers: {', '.join(section.body_signatures[:3])}."
    )


def build_authoring_plan(
    scans: list[SurfaceScan],
    coherence_map: dict[str, list[dict[str, str]]],
) -> list[PlanAction]:
    """Derive the per-surface authoring / refinement plan from the scans.

    Absent mandatory surfaces get an author-from-template action, absent
    optional ones a defer-to-opt-in action; present surfaces get one action per
    missing or renamed section, and each ``contradicts`` coherence verdict adds
    a reconciliation action mirroring the canonical project voice.
    """
    actions: list[PlanAction] = []
    for scan in scans:
        if scan.presence == SURFACE_ABSENT:
            if scan.descriptor.mandatory:
                actions.append(
                    PlanAction(
                        surface=scan.descriptor.path,
                        action="author-from-template",
                        detail=(
                            "Mandatory surface absent; author the full nine-section "
                            "structure with the canonical authorship banner header. "
                            f"Audience: {scan.descriptor.role}."
                        ),
                        target_phase_hint=(
                            "Copilot-instructions author pass / instruction-surface refit pass"
                            if scan.descriptor.path == SURFACE_COPILOT
                            else "instruction-surface refit pass"
                        ),
                    )
                )
            else:
                actions.append(
                    PlanAction(
                        surface=scan.descriptor.path,
                        action="defer-to-opt-in",
                        detail=(
                            "Optional surface absent; author only when the operator "
                            f"opts in via the multi-surface opt-in inquiry. Audience: "
                            f"{scan.descriptor.role}."
                        ),
                        target_phase_hint="Optional-surface opt-in inquiry / generator",
                    )
                )
            continue
        # Present surface — emit one action per absent / renamed section.
        for section in ALL_SECTIONS_FOR_PRESENCE:
            status = scan.section_presence[section.slug]
            if status == PRESENCE_ABSENT:
                actions.append(
                    PlanAction(
                        surface=scan.descriptor.path,
                        action="install-missing-section",
                        detail=template_for_section(section),
                        target_phase_hint=(
                            "instruction-surface refit pass"
                            if scan.descriptor.path
                            in (
                                SURFACE_AGENTS_ROOT,
                                SURFACE_CLAUDE_ROOT,
                                SURFACE_CLAUDE_NESTED,
                            )
                            else "Copilot-instructions author pass"
                            if scan.descriptor.path == SURFACE_COPILOT
                            else "Optional-surface generator"
                        ),
                    )
                )
            elif status.startswith(PRESENCE_RENAMED_PREFIX):
                renamed_to = status[len(PRESENCE_RENAMED_PREFIX) :]
                actions.append(
                    PlanAction(
                        surface=scan.descriptor.path,
                        action="rename-or-mirror-section",
                        detail=(
                            f"Section '{section.display}' is present under heading "
                            f"'{renamed_to}'; either rename to the canonical heading "
                            "or add the canonical heading and migrate the body."
                        ),
                        target_phase_hint="instruction-surface refit pass",
                    )
                )
    # Contradiction reconciliation actions per coherence map entry.
    for pair_key, verdicts in coherence_map.items():
        for verdict in verdicts:
            if verdict["verdict"] == COHERENCE_CONTRADICTS:
                surface_a, surface_b = pair_key.split("__vs__")
                # The default reconciliation mirrors the canonical project
                # voice into the divergent surface. AGENTS.md is canonical.
                if surface_a == SURFACE_AGENTS_ROOT:
                    canonical, divergent = surface_a, surface_b
                elif surface_b == SURFACE_AGENTS_ROOT:
                    canonical, divergent = surface_b, surface_a
                elif surface_a == SURFACE_CLAUDE_ROOT:
                    canonical, divergent = surface_a, surface_b
                elif surface_b == SURFACE_CLAUDE_ROOT:
                    canonical, divergent = surface_b, surface_a
                else:
                    canonical, divergent = surface_a, surface_b
                actions.append(
                    PlanAction(
                        surface=divergent,
                        action="reconcile-contradiction",
                        detail=(
                            f"Section '{verdict['section_display']}' contradicts the "
                            f"corresponding section in '{canonical}'. Default "
                            f"reconciliation: rewrite '{divergent}' to mirror "
                            f"'{canonical}' semantics in surface-appropriate framing."
                        ),
                        target_phase_hint="Multi-surface coherence reconciliation",
                    )
                )
    return actions


# ---------------------------------------------------------------------------
# JSON envelope.
# ---------------------------------------------------------------------------


def serialise_scan(scan: SurfaceScan) -> dict:
    """Convert one surface scan into its JSON-envelope dict."""
    return {
        "path": scan.descriptor.path,
        "role": scan.descriptor.role,
        "mandatory": scan.descriptor.mandatory,
        "presence": scan.presence,
        "sha256": scan.sha256,
        "line-count": scan.line_count,
        "headings": [
            {
                "level": h.level,
                "text": h.text,
                "line-start": h.line_start,
                "line-end": h.line_end,
            }
            for h in scan.headings
        ],
        "section-presence": scan.section_presence,
    }


def emit_json(
    out_path: Path,
    scans: list[SurfaceScan],
    coherence_map: dict[str, list[dict[str, str]]],
    plan: list[PlanAction],
    inventory_sha: str,
    coarse_sha: str | None,
) -> None:
    """Write the machine-readable ``ai-surfaces.json`` envelope to disk.

    Bundles the candidate-surface catalog, per-surface scans, coherence map,
    authoring plan, and a summary block, anchored to the inventory and coarse
    scan SHA-256 digests.
    """
    payload = {
        "generated": datetime.now(timezone.utc).isoformat(),
        "scanner": "scan_ai_surfaces",
        "inventory-source-sha256": inventory_sha,
        "coarse-source-sha256": coarse_sha,
        "candidate-surfaces": [
            {
                "path": d.path,
                "role": d.role,
                "mandatory": d.mandatory,
            }
            for d in CANDIDATE_SURFACES
        ],
        "canonical-sections": [
            {"slug": s.slug, "display": s.display, "is-shared": s.is_shared}
            for s in ALL_SECTIONS_FOR_PRESENCE
        ],
        "shared-sections-for-coherence": [
            {"slug": s.slug, "display": s.display}
            for s in SHARED_SECTIONS_FOR_COHERENCE
        ],
        "surfaces": [serialise_scan(s) for s in scans],
        "coherence-map": coherence_map,
        "authoring-plan": [asdict(p) for p in plan],
        "summary": {
            "candidate-count": len(scans),
            "present-count": sum(1 for s in scans if s.presence == SURFACE_PRESENT),
            "absent-count": sum(1 for s in scans if s.presence == SURFACE_ABSENT),
            "mandatory-absent": [
                s.descriptor.path
                for s in scans
                if s.presence == SURFACE_ABSENT and s.descriptor.mandatory
            ],
            "pair-count": len(coherence_map),
            "plan-action-count": len(plan),
        },
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(payload, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# Markdown render.
# ---------------------------------------------------------------------------


def render_markdown(
    scans: list[SurfaceScan],
    coherence_map: dict[str, list[dict[str, str]]],
    plan: list[PlanAction],
    inventory_sha: str,
    coarse_sha: str | None,
    generated_at: str,
) -> str:
    """Render the human-readable ``ai-surfaces.md`` mirror.

    Emits the surface-presence table, per-surface section-presence and
    heading inventories, the pairwise coherence map, the authoring plan, and a
    reconciliation summary.
    """
    parts: list[str] = []
    parts.append("# AI-Conventions Surfaces — Presence and Coherence Map\n")
    parts.append("")
    parts.append(
        "> Per-surface presence detection plus pairwise shared-section "
        "coherence verdicts plus authoring / refinement plan. Heuristic at "
        "this layer; the rigorous fixture-driven test lives at the "
        "multi-surface coherence validator.\n"
    )
    parts.append("")
    parts.append(f"- **Generated:** `{generated_at}`")
    parts.append(f"- **Inventory SHA-256:** `{inventory_sha}`")
    if coarse_sha is not None:
        parts.append(f"- **Coarse-scan SHA-256:** `{coarse_sha}`")
    parts.append("")
    # Surface presence table.
    parts.append("## Surface Presence")
    parts.append("")
    parts.append("| Path | Role | Mandatory | Presence | SHA-256 | Lines |")
    parts.append("|------|------|-----------|----------|---------|-------|")
    for scan in scans:
        sha_display = scan.sha256[:12] + "…" if scan.sha256 else "—"
        parts.append(
            f"| `{scan.descriptor.path}` | {scan.descriptor.role} | "
            f"{'**MUST**' if scan.descriptor.mandatory else 'opt-in'} | "
            f"{scan.presence} | `{sha_display}` | {scan.line_count} |"
        )
    parts.append("")
    # Per-surface section-presence map.
    parts.append("## Section Presence")
    parts.append("")
    section_headers = " | ".join(s.display for s in ALL_SECTIONS_FOR_PRESENCE)
    section_separators = " | ".join("---" for _ in ALL_SECTIONS_FOR_PRESENCE)
    parts.append(f"| Surface | {section_headers} |")
    parts.append(f"|---------|{section_separators}|")
    for scan in scans:
        if scan.presence == SURFACE_ABSENT:
            cells = " | ".join("—" for _ in ALL_SECTIONS_FOR_PRESENCE)
            parts.append(f"| `{scan.descriptor.path}` | {cells} |")
            continue
        cells = []
        for section in ALL_SECTIONS_FOR_PRESENCE:
            status = scan.section_presence[section.slug]
            if status == PRESENCE_PRESENT:
                cells.append("present")
            elif status == PRESENCE_ABSENT:
                cells.append("**absent**")
            else:
                renamed_to = status[len(PRESENCE_RENAMED_PREFIX) :]
                cells.append(f"renamed-to `{renamed_to[:24]}`")
        cells_joined = " | ".join(cells)
        parts.append(f"| `{scan.descriptor.path}` | {cells_joined} |")
    parts.append("")
    # Per-surface heading inventory (level-2 only, for present surfaces).
    parts.append("## Per-Surface Heading Inventory (level-2)")
    parts.append("")
    for scan in scans:
        if scan.presence != SURFACE_PRESENT:
            continue
        parts.append(f"### `{scan.descriptor.path}`")
        parts.append("")
        level_two = [h for h in scan.headings if h.level == 2]
        if not level_two:
            parts.append(
                "_No level-two headings detected; the surface is either flat "
                "prose or uses a different heading depth._\n"
            )
            parts.append("")
            continue
        parts.append("| # | Heading | Lines |")
        parts.append("|---|---------|-------|")
        for index, heading in enumerate(level_two, start=1):
            parts.append(
                f"| {index} | {heading.text} | "
                f"{heading.line_start}-{heading.line_end} |"
            )
        parts.append("")
    # Coherence map.
    parts.append("## Coherence Map")
    parts.append("")
    if not coherence_map:
        parts.append(
            "_No pairs of present surfaces; the coherence map is empty by "
            "construction. The map's structure is preserved for the post-"
            "authoring re-run when at least two surfaces are present._\n"
        )
        parts.append("")
    else:
        for pair_key, verdicts in coherence_map.items():
            surface_a, surface_b = pair_key.split("__vs__")
            parts.append(f"### `{surface_a}` ↔ `{surface_b}`")
            parts.append("")
            parts.append("| Section | Verdict | Rationale |")
            parts.append("|---------|---------|-----------|")
            for verdict in verdicts:
                rationale = verdict["rationale"].replace("|", "\\|")
                parts.append(
                    f"| {verdict['section_display']} | "
                    f"{verdict['verdict']} | {rationale} |"
                )
            parts.append("")
    # Authoring / refinement plan.
    parts.append("## Authoring / Refinement Plan")
    parts.append("")
    if not plan:
        parts.append(
            "_No authoring / refinement actions emitted; every surface in "
            "scope is fully canonical._\n"
        )
        parts.append("")
    else:
        parts.append("| # | Surface | Action | Target Phase Hint | Detail |")
        parts.append("|---|---------|--------|-------------------|--------|")
        for index, action in enumerate(plan, start=1):
            detail = action.detail.replace("|", "\\|")
            parts.append(
                f"| {index} | `{action.surface}` | {action.action} | "
                f"{action.target_phase_hint} | {detail} |"
            )
        parts.append("")
    # Reconciliation summary.
    contradictions = [
        verdict
        for verdicts in coherence_map.values()
        for verdict in verdicts
        if verdict["verdict"] == COHERENCE_CONTRADICTS
    ]
    parts.append("## Reconciliation Summary")
    parts.append("")
    if not contradictions:
        parts.append(
            "_No candidate contradictions detected at this heuristic layer. "
            "The fixture-driven validator confirms the verdict at a later "
            "phase._\n"
        )
        parts.append("")
    else:
        parts.append(
            "Default reconciliation: `AGENTS.md` is the canonical project voice; "
            "any divergent surface is rewritten to mirror its semantics in "
            "surface-appropriate framing. Surface-specific overrides require "
            "an in-file `<!-- coherence-override: <claim-id> -->` marker "
            "pointing at an architectural decision record.\n"
        )
        parts.append("")
        parts.append("| Section | Surfaces | Default Reconciliation |")
        parts.append("|---------|----------|------------------------|")
        for verdict in contradictions:
            parts.append(
                f"| {verdict['section_display']} | (see plan) | "
                f"Rewrite divergent surface to mirror `AGENTS.md`. |"
            )
        parts.append("")
    return "\n".join(parts) + "\n"


# ---------------------------------------------------------------------------
# Entry point.
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    """Scan every candidate surface, build the coherence map and authoring plan, and emit both output documents.

    Loads the inventory (for its SHA-256 anchor), scans each surface,
    computes the pairwise coherence map, derives the authoring plan, writes
    ``ai-surfaces.json`` / ``ai-surfaces.md``, and prints a one-line summary.
    """
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--inventory",
        type=Path,
        default=Path(".audit/inventory.json"),
        help="Inventory snapshot whose SHA-256 anchors the scan output.",
    )
    parser.add_argument(
        "--coarse",
        type=Path,
        default=Path(".audit/drift-ai-surfaces-coarse.json"),
        help="Optional coarse pre-scan output; its SHA-256 is recorded.",
    )
    parser.add_argument("--root", type=Path, default=Path())
    parser.add_argument(
        "--out-json",
        type=Path,
        default=Path(".audit/ai-surfaces.json"),
    )
    parser.add_argument(
        "--out-md",
        type=Path,
        default=Path(".audit/ai-surfaces.md"),
    )
    args = parser.parse_args(argv)
    if not args.inventory.exists():
        print(
            f"error: inventory not found at {args.inventory}",
            file=sys.stderr,
        )
        return 1
    _, inventory_sha = load_inventory(args.inventory)
    coarse_sha: str | None = None
    if args.coarse.exists():
        coarse_sha = hashlib.sha256(args.coarse.read_bytes()).hexdigest()
    scans = [scan_surface(d, args.root) for d in CANDIDATE_SURFACES]
    coherence_map = build_coherence_map(scans)
    plan = build_authoring_plan(scans, coherence_map)
    generated_at = datetime.now(timezone.utc).isoformat()
    emit_json(args.out_json, scans, coherence_map, plan, inventory_sha, coarse_sha)
    args.out_md.parent.mkdir(parents=True, exist_ok=True)
    args.out_md.write_text(
        render_markdown(
            scans,
            coherence_map,
            plan,
            inventory_sha,
            coarse_sha,
            generated_at,
        ),
        encoding="utf-8",
    )
    present_count = sum(1 for s in scans if s.presence == SURFACE_PRESENT)
    absent_count = sum(1 for s in scans if s.presence == SURFACE_ABSENT)
    mandatory_absent = [
        s.descriptor.path
        for s in scans
        if s.presence == SURFACE_ABSENT and s.descriptor.mandatory
    ]
    print(
        f"scan_ai_surfaces: candidates={len(scans)}, present={present_count}, "
        f"absent={absent_count}, mandatory-absent={len(mandatory_absent)}, "
        f"pairs={len(coherence_map)}, plan-actions={len(plan)}"
    )
    if mandatory_absent:
        print(
            f"  mandatory-absent: {', '.join(mandatory_absent)}",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# ---------------------------------------------------------------------------
# Public surface. This module is the entry point for the header-coverage
# pipeline; the names below are re-exported from the sibling modules that own
# them (``header_vocabulary`` / ``header_banner`` / ``header_variants`` /
# ``header_detect``). Declaring them here keeps the unused-import rule from
# deleting a re-export whose importers live in other files.
# ---------------------------------------------------------------------------
__all__ = [
    "ALL_SECTIONS_FOR_PRESENCE",
    "COHERENCE_COHERENT",
    "COHERENCE_CONTRADICTS",
    "COHERENCE_NOT_APPLICABLE",
    "COHERENCE_PARTIAL",
    "PRESENCE_ABSENT",
    "PRESENCE_PRESENT",
    "PRESENCE_RENAMED_PREFIX",
    "SURFACE_ABSENT",
    "SURFACE_PARTIAL",
    "SURFACE_PRESENT",
    "CanonicalSection",
    "CoherenceVerdict",
    "HeadingBlock",
    "PlanAction",
    "SurfaceDescriptor",
    "SurfaceScan",
    "body_signature_count",
    "build_authoring_plan",
    "build_coherence_map",
    "coherence_verdict_for",
    "detect_section_presence",
    "emit_json",
    "heading_text_matches",
    "main",
    "parse_headings",
    "render_markdown",
    "scan_surface",
    "section_present_in_scan",
    "serialise_scan",
    "shared_claim_overlap",
    "template_for_section",
]
