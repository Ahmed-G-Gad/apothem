---
name: "sota-elevation-exemplars"
description: "Path-filtered companion to `sota-elevation.md` carrying the eight-surface SOTA evaluation lens, the named-exemplar catalogue (cpython / shadcn-ui / Bun / Fumadocs / vite / vitest), per-surface exemplar walks, the upper-bound calibration binding, the Filter-5 aesthetic-demand binding, the gap-surfacing protocol, the disclosure markers, and the failure tells; demand-loaded on README / docs / `.github/` / `site/` touches."
pathFilter: "**/README.md, **/docs/**, **/.github/**, **/site/**"
alwaysApply: false
---

<!-- SPDX-License-Identifier: MIT -->

# Rule: SOTA Elevation — Exemplar Catalogue & Eight-Surface Walks (Companion Sub-Rule)

## Purpose

Carry the operational detail the parent rule `rules/sota-elevation.md` anchors: the eight SOTA evaluation surfaces, the named-exemplar catalogue, the per-surface exemplar walks, the upper-bound calibration, the Filter-5 binding, the gap-surfacing protocol, the disclosure markers, and the failure tells. Path-filtered to OSS-distribution user-facing surfaces (README, docs site, CI workflows, site/ scaffold); the parent's always-on payload stays lean while this companion preserves full exemplar fidelity at the demand-load surface.

## Obligations

### 1. The Eight SOTA Evaluation Surfaces

Every user-facing change MUST be audited across all eight surfaces. A change that lands one surface while leaving the others below SOTA is partial-SOTA, not SOTA:

| # | Surface | What "SOTA" means here |
|---|---|---|
| 1 | **README modernization** | Centered logo + tagline + badge row + nav strip + Quick-start; depth matching cpython / shadcn-ui / Bun headers. Cites `rules/production-ready-prs-surfaces.md` §6.5. |
| 2 | **Visibility surfaces** | All seven per `rules/production-ready-prs-surfaces.md` §1 present, current, badge-rendered. |
| 3 | **Supply-chain producer-pipeline** | Actions pinned to commit-SHA, minimum permissions, ratified release signing, SBOM where applicable, OIDC trust where the registry supports it. |
| 4 | **CI/CD modernization** | Generic SOTA workflow naming (cpython / django / react / vue pattern); matrix-tested; cache-keyed; concurrency-grouped; reusable workflow composition. |
| 5 | **Test rigor** | Coverage gate; parametrized; behavior-named; AAA-shaped; cross-platform matrix where the product targets cross-platform. |
| 6 | **Packaging / type-safety** | Modern manifest schema; `py.typed` marker or equivalent; strict type-check on public API; dynamic version rendering. |
| 7 | **Observability** | Structured logging (`logging.getLogger(__name__)` / structlog / pino equivalents); deliberate log levels; no `print()` for operational output. |
| 8 | **Docs SOTA** | Documentation tooling at current SOTA (Fumadocs / VitePress / Docusaurus); folded sidebar; landing distinct from docs; OG cards; mobile-first responsive. |

### 2. Named-Exemplar Catalogue

Every SOTA citation names a **currently-shipping** exemplar as concrete-driver class 6 per `rules/interactive-questions-canonical-shapes.md` §3.2.1. Vague "industry standard" / "best practice" appeals without a named source are non-conformant per `rules/interactive-questions-canonical-shapes.md` §3.2.2.

| Exemplar | Anchors surface(s) | What to copy |
|---|---|---|
| **cpython** | 1, 4 | CONTRIBUTING shape; release-engineering rigor; workflow naming (`tests.yml`, `build.yml`); dev-guide depth |
| **shadcn-ui** | 1, 8 | README header centered pattern; dark-mode-first aesthetic; copy-paste-component documentation; landing-page polish |
| **Bun** | 1, 8 | performance-first landing; folded sidebar; marketing-quality OG cards; bold typography |
| **Fumadocs** | 8 | Docs-site IA; MDX-rich pages; Next.js App Router; dedicated landing distinct from docs root; localized routing |
| **vite** | 8 | VitePress sibling-class clean IA; minimal nav; fast TTFB |
| **vitest** | 5, 8 | Behavior-named tests; clean docs/test parity; fast-feedback CLI surface |

### 3. Upper-Bound Calibration

When the operator's directive carries `MAXIMAL` (or "best possible", "world-class", "no expense spared", "ALL diversified dimensions"), the calibration ladder at `rules/expertise-posture-elements.md` §2 escalates to the **architectural-rework** rung. Every surface in §1 is inspected; no surface is skipped under time pressure. Mid-tier "production-ready" is the floor `rules/production-ready-prs.md` enforces; SOTA-elevation lifts the ceiling.

### 4. Filter-5 Aesthetic-Demand Binding

SOTA elevation is the outward projection of cognitive-identity Filter 5 (aesthetic demand) per `rules/cognitive-identity-techniques.md` §1. A surface that passes every mechanical bar but lacks conceptual elegance, texture, soul — the "feels inevitable once seen" property — has not yet reached SOTA. Filter 5 is the gate beyond mechanical conformity.

### 5. Gap-Surfacing Protocol

When the host's current state falls short of SOTA on any of the eight surfaces, the gap MUST be surfaced as a finding per `rules/authority-inquiry.md` with options annotated per `rules/option-annotation.md` — never silently entrenched, never deferred without a tracking record. The recommended-option rationale MUST cite a concrete exemplar from §2.

### 6. Disclosure Markers

Outcomes recorded in the disclosure ledger per `rules/disclosure-ledger.md`:

- `[SOTA — elevated: <surface>; exemplar: <project>; from: <prior-state>; to: <new-state>]` for every SOTA-lift.
- `[SOTA — gap-surfaced: <surface>; current-state: <description>; exemplar-target: <project>; tracking: <inquiry-id | task>]` for every gap.
- `[SOTA — floor-honored: <surface>]` for surfaces already at SOTA where the change preserves the elevation.

### 7. Failure Tells

A README rewrite that adopts a single SOTA element (e.g., a logo) without the surrounding header pattern (partial-SOTA). A "SOTA" citation that names no exemplar. A workflow renamed to a generic name without the surrounding security-and-permissions polish (surface 4 partial). Docs migrated to a SOTA framework but left at the default theme (surface 8 partial). `MAXIMAL` directive answered with mid-tier "production-ready" output (calibration miss). A gap on any of the eight surfaces entrenched silently instead of surfaced. Aesthetic dismissal ("it's fine") on a surface where Filter 5 has not yet been applied.

## Bindings (§0.j five-direction)

- **Drives →** Every OSS-distribution user-facing surface emission under the path-filter; the eight-surface audit at every README / docs / `.github/` / `site/` touch; the named-exemplar citation requirement at every `[SOTA — …]` marker; the architectural-rework rung escalation on `MAXIMAL` directives.
- **Satisfies →** `rules/sota-elevation.md` companion anchors (the parent rule's pointers to this companion's eight-surface table, exemplar catalogue, calibration binding, Filter-5 binding, gap-surfacing protocol, disclosure markers, and failure tells).
- **Established by ↑** `rules/sota-elevation.md` (parent-rule anchor). Exemplar attestation, SOTA-elevation meta-mandate, and README + workflow SOTA directives.
- **Gated by ←** The path-filter (`**/README.md`, `**/docs/**`, `**/.github/**`, `**/site/**`) — this rule demand-loads only on OSS-distribution user-facing surface touches. `rules/sota-elevation.md` always-on baseline (parent rule must be live for this companion's anchors to surface coherently).
- **Cross-bound with ↔** `rules/sota-elevation.md` (parent rule; companion anchors bind here). `rules/production-ready-prs-surfaces.md` (§6.5 modern-README escalation cites the parent; this companion's surface 1 + surface 2 materialise the SOTA tier above the production-ready floor). `rules/cognitive-identity-techniques.md` §1 (Filter 5 aesthetic-demand binding at §4). `rules/expertise-posture-elements.md` §2 (calibration ladder at §3). `rules/interactive-questions-canonical-shapes.md` §3.2.1 (concrete-driver class 6 citation requirement) + §3.2.2 (vague-rationale forbid list). `rules/persistent-conventions-vigilance.md` §4 (gap-detection surface). `rules/disclosure-ledger.md` (M2 — disclosure markers at §6).
