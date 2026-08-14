# SPDX-License-Identifier: MIT

"""Why this catalog exists — the surfaces, sections, and verdicts, as data.

The AI-surface scanner answers three questions that each need a shared
vocabulary: which files are candidate instruction surfaces, which sections
those surfaces are expected to carry, and what verdicts a comparison can
produce. Those declarations are long — the canonical-section table alone runs
to a couple of hundred lines — and holding them in the scanner buried the
scanning logic beneath the data it operates on.

Scope. Pure declaration and no behavior: the candidate-surface catalog with
each entry's role and mandatory/opt-in disposition, the canonical-section
table with the keyword and body-signature heuristics that detect each section,
and the presence / surface / coherence status vocabularies. A function that
*interprets* any of this belongs to the stage that owns the interpretation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

# ---------------------------------------------------------------------------
# Candidate surface catalog. Each entry names the canonical relative
# path, the surface's role in the ecosystem, and whether the surface is
# mandatory or opt-in. The order is the canonical reading order for
# every output table.
# ---------------------------------------------------------------------------
SURFACE_AGENTS_ROOT: Final[str] = "AGENTS.md"
SURFACE_CLAUDE_ROOT: Final[str] = "CLAUDE.md"
SURFACE_CLAUDE_NESTED: Final[str] = ".claude/CLAUDE.md"
SURFACE_COPILOT: Final[str] = ".github/copilot-instructions.md"
SURFACE_AGENTS_DOC: Final[str] = "site/content/docs/architecture/agents.mdx"
SURFACE_CURSOR: Final[str] = ".cursorrules"
SURFACE_WINDSURF: Final[str] = ".windsurfrules"


@dataclass(frozen=True)
class SurfaceDescriptor:
    """One candidate surface plus its mandatory / opt-in disposition."""

    path: str
    role: str
    mandatory: bool


CANDIDATE_SURFACES: Final[tuple[SurfaceDescriptor, ...]] = (
    SurfaceDescriptor(SURFACE_AGENTS_ROOT, "Canonical project instructions", True),
    SurfaceDescriptor(SURFACE_CLAUDE_ROOT, "Claude Code mirror", True),
    SurfaceDescriptor(SURFACE_CLAUDE_NESTED, "Claude (mirror layout)", False),
    SurfaceDescriptor(SURFACE_COPILOT, "GitHub Copilot", True),
    SurfaceDescriptor(SURFACE_AGENTS_DOC, "Multi-agent platforms", False),
    SurfaceDescriptor(SURFACE_CURSOR, "Cursor", False),
    SurfaceDescriptor(SURFACE_WINDSURF, "Windsurf", False),
)


# ---------------------------------------------------------------------------
# Canonical nine-section catalog. Each section carries:
# - ``slug`` — stable identifier used as the JSON key.
# - ``display`` — human-readable section title (matches the spec body).
# - ``heading_keywords`` — case-insensitive substrings any one of which,
#   present in a level-two heading, qualifies the heading as the section.
# - ``body_signatures`` — substrings whose presence in the body of a
#   heading signals the canonical content is there even when the
#   heading text is renamed.
# - ``is_shared`` — whether the section participates in the cross-
#   surface coherence contract.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CanonicalSection:
    """One canonical section plus the heuristics that detect it.

    ``heading_keywords`` match a section by heading text; ``body_signatures``
    detect it by content even when renamed; ``is_shared`` marks the sections
    that participate in the cross-surface coherence contract.
    """

    slug: str
    display: str
    heading_keywords: tuple[str, ...]
    body_signatures: tuple[str, ...]
    is_shared: bool


CANONICAL_SECTIONS: Final[tuple[CanonicalSection, ...]] = (
    CanonicalSection(
        slug="project-context",
        display="Project Context",
        heading_keywords=(
            "project context",
            "context",
            "about this",
            "what this is",
            "overview",
            "introduction",
        ),
        body_signatures=("repository", "ecosystem", "purpose", "scope"),
        is_shared=False,
    ),
    CanonicalSection(
        slug="coding-conventions",
        display="Coding Conventions",
        heading_keywords=(
            "coding conventions",
            "conventions",
            "code style",
            "style",
            "naming",
        ),
        body_signatures=(
            "kebab-case",
            "snake_case",
            "PascalCase",
            "RFC 2119",
            "MUST",
            "modal",
        ),
        is_shared=False,
    ),
    CanonicalSection(
        slug="file-headers",
        display="File Headers",
        heading_keywords=(
            "file headers",
            "file header",
            "authorship header",
            "authorship banner",
            "header banner",
            "banner",
        ),
        body_signatures=(
            "Copyright (c)",
            "All rights reserved",
            "inject-header",
            "authorship-header",
            "five canonical lines",
        ),
        is_shared=True,
    ),
    CanonicalSection(
        slug="plans-discipline",
        display="Plans Discipline",
        heading_keywords=(
            "plans discipline",
            "plans-discipline",
            "planning artifacts",
            ".plans/",
        ),
        body_signatures=(
            "<project-root>/.plans/",
            "project-root/.plans",
            "~/.claude/.plans/",
            "no-global-plans",
            ".plans/ at the project root",
            "ephemeral working memory",
        ),
        is_shared=True,
    ),
    CanonicalSection(
        slug="Structured Inquiry",
        display="Structured Inquiry Behavior",
        heading_keywords=(
            "structured inquiry",
            "ask user",
            "ambiguity",
            "clarification",
            "interactive question",
            "structured inquiry",
            "todo(clarify)",
        ),
        body_signatures=(
            "structured inquiry",
            "TODO(clarify)",
            "never invent",
            "no silent",
            "structured-inquiry",
            "interactive-questions",
        ),
        is_shared=True,
    ),
    CanonicalSection(
        slug="forbidden-patterns",
        display="Forbidden Patterns",
        heading_keywords=(
            "forbidden patterns",
            "forbidden",
            "anti-patterns",
            "anti patterns",
            "do not",
            "never do",
            "prohibitions",
        ),
        body_signatures=(
            "no marketing",
            "no hedging",
            "console.log",
            "absolute path",
            "do not commit",
            "never commit",
            "MUST NOT",
        ),
        is_shared=True,
    ),
    CanonicalSection(
        slug="output-format",
        display="Output Format",
        heading_keywords=(
            "output format",
            "output conventions",
            "output discipline",
            "response format",
            "generation format",
        ),
        body_signatures=(
            "definitiveness",
            "uniform sectioning",
            "summary discipline",
            "citations",
            "typed",
            "documented public surface",
        ),
        is_shared=False,
    ),
    CanonicalSection(
        slug="review-checklist",
        display="Review Checklist",
        heading_keywords=(
            "review checklist",
            "checklist",
            "before approving",
            "review before",
            "pr review",
            "merge checklist",
        ),
        body_signatures=(
            "header present",
            "naming compliant",
            "no .plans/ writes",
            "validators green",
            "no contradictions",
        ),
        is_shared=False,
    ),
    CanonicalSection(
        slug="pointers",
        display="Pointers",
        heading_keywords=(
            "pointers",
            "references",
            "see also",
            "links",
            "further reading",
            "registry",
            "registries",
        ),
        body_signatures=(
            "site/content/docs/reference/plans-discipline",
            "site/content/docs/reference/authorship-header",
            "site/content/docs/reference/ai-conventions",
            "CONTRIBUTING.md",
        ),
        is_shared=False,
    ),
)


# Naming and Modal Hierarchy are sub-claims of Coding Conventions per
# the canonical nine-section list, but the coherence contract enumerates
# them as discrete shared sections. Each carries its own keyword and
# body signature so the cross-surface diff can attribute a contradiction
# to the right axis.
EXTRA_SHARED_SECTIONS: Final[tuple[CanonicalSection, ...]] = (
    CanonicalSection(
        slug="naming",
        display="Naming",
        heading_keywords=(
            "naming",
            "file naming",
            "directory naming",
            "kebab-case",
        ),
        body_signatures=(
            "kebab-case",
            "snake_case",
            "PascalCase",
            "UPPER_SNAKE_CASE",
        ),
        is_shared=True,
    ),
    CanonicalSection(
        slug="modal-hierarchy",
        display="Modal Hierarchy",
        heading_keywords=(
            "modal hierarchy",
            "modal",
            "RFC 2119",
            "RFC2119",
            "MUST / SHOULD",
        ),
        body_signatures=(
            "RFC 2119",
            "MUST",
            "MUST NOT",
            "SHOULD",
            "SHOULD NOT",
            "MAY",
        ),
        is_shared=True,
    ),
)

ALL_SECTIONS_FOR_PRESENCE: Final[tuple[CanonicalSection, ...]] = CANONICAL_SECTIONS

SHARED_SECTIONS_FOR_COHERENCE: Final[tuple[CanonicalSection, ...]] = (
    *(s for s in CANONICAL_SECTIONS if s.is_shared),
    *EXTRA_SHARED_SECTIONS,
)


# ---------------------------------------------------------------------------
# Coherence verdict taxonomy.
# ---------------------------------------------------------------------------
COHERENCE_COHERENT: Final[str] = "coherent"
COHERENCE_CONTRADICTS: Final[str] = "contradicts"
COHERENCE_PARTIAL: Final[str] = "partial"
COHERENCE_NOT_APPLICABLE: Final[str] = "n/a"


# Section-presence verdict prefixes.
PRESENCE_PRESENT: Final[str] = "present"
PRESENCE_ABSENT: Final[str] = "absent"
PRESENCE_RENAMED_PREFIX: Final[str] = "renamed-to:"

# Surface-presence (top-level) verdicts.
SURFACE_PRESENT: Final[str] = "present"
SURFACE_ABSENT: Final[str] = "absent"
SURFACE_PARTIAL: Final[str] = "partial"
