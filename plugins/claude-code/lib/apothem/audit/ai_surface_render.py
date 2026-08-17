# SPDX-License-Identifier: MIT

"""Why this module exists — turning surface scans into documents.

The surface sweep ends in two artifacts: ``ai-surfaces.json`` for the passes
that consume it and ``ai-surfaces.md`` for the person reading the result. Both
are built from the same scans, coherence map, and authoring plan, and neither
makes any judgement about what those say.

Scope. Presentation only. The judgements this module does make are about
rendering: which values get their pipes escaped before entering a markdown
table cell, how far a digest or a renamed heading is truncated before it would
widen a table past reading, and what an empty section says instead of nothing.

Note that ``render_markdown`` takes its timestamp as an argument rather than
reading the clock. That is what makes the document reproducible for a given
input, and testable without freezing time.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from apothem.audit.ai_surface_catalog import (
    ALL_SECTIONS_FOR_PRESENCE,
    CANDIDATE_SURFACES,
    COHERENCE_CONTRADICTS,
    PRESENCE_ABSENT,
    PRESENCE_PRESENT,
    PRESENCE_RENAMED_PREFIX,
    SHARED_SECTIONS_FOR_COHERENCE,
    SURFACE_ABSENT,
    SURFACE_PRESENT,
)
from apothem.audit.ai_surface_model import PlanAction, SurfaceScan

__all__ = [
    "emit_json",
    "render_markdown",
    "serialise_scan",
]


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
