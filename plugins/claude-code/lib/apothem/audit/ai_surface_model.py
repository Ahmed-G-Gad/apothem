# SPDX-License-Identifier: MIT

"""Why this module exists — the three shapes the surface scan produces.

Scanning the AI-conventions surfaces yields three results in sequence: what one
surface contains, whether a pair of surfaces agrees on a shared claim, and what
should be authored to close the gap. Each stage reads the previous stage's
shape and none of them needs the others' machinery.

Scope. Pure declaration, no behavior. Holding the shapes here is what keeps the
pipeline acyclic: the scanner produces them and the renderer consumes them, so
both depend on this module and neither depends on the other.
"""

from __future__ import annotations

from dataclasses import dataclass

from apothem.audit.ai_surface_catalog import SurfaceDescriptor
from apothem.audit.ai_surface_parsing import HeadingBlock


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
