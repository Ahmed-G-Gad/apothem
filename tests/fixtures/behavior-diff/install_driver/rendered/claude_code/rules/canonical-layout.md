---
name: "canonical-layout"
description: "Non-trivial multi-step work emits two-tier reporting (per-sub-phase report + phase-level rollup that aggregates rather than concatenates) and lays generated outputs at the host's discovered canonical layout with reciprocal producer / consumer cross-references and provenance. Orphan outputs (generated artifacts with no consumer / no index entry / no producer attribution) are structural failures."
pathFilter: "**/.apothem/plans/**, **/.plans/**, **/phases/**, **/REPORT.md, **/PHASE.md, **/MASTER-PLAN.md, **/PROGRESS.md, **/migrations/**"
alwaysApply: false
paths:
  - "**/.apothem/plans/**"
  - "**/.plans/**"
  - "**/phases/**"
  - "**/REPORT.md"
  - "**/PHASE.md"
  - "**/MASTER-PLAN.md"
  - "**/PROGRESS.md"
  - "**/migrations/**"
---

<!-- SPDX-License-Identifier: MIT -->

# Rule: Phase / Sub-Phase Reporting & Canonical Layout of Generated Outputs

## What this rule enforces

Binds **M12 — Phase / Sub-Phase Reporting & Canonical Layout of Generated Outputs**. Non-trivial multi-step work MUST emit two-tier reporting (working + reviewing tiers) and MUST lay every generated output at a host-discovered canonical location with reciprocal producer / consumer cross-references and provenance. An orphan output — no consumer, OR no index entry, OR no producer attribution — is a structural failure, not a deferral candidate.

## Pre-conditions

Applies whenever the agent undertakes non-trivial multi-step work per the trivial-vs-non-trivial threshold. Trivial-scope work skips two-tier reporting. Single-sub-phase work collapses the tier (the sub-phase report IS the rollup) but still honors the canonical-layout discipline.

## Required behavior

Operational bodies live at the (Companion Sub-Rule Anchor) sibling rule, demand-loaded on plan-suite / phase / REPORT.md / PHASE.md / MASTER-PLAN.md / PROGRESS.md / migrations touches.

(Companion Sub-Rule Anchor) §1 — two-tier reporting) Working tier (per-sub-phase REPORT.md with Summary / Tasks / Outputs / Verification / Disclosure ledger / gate attestation / Bindings) plus reviewing tier (rollup REPORT.md aggregating rather than concatenating — uniform template, aggregated metrics, pattern surfacing, phase self-check, outward declarations); single-sub-phase phases collapse the tier. See `rules/canonical-layout-reporting-tiers.md` §1.

(Companion Sub-Rule Anchor) §2 — canonical layout) Outputs sit at predictable host-discovered locations per `rules/host-discovery.md`; every output carries canonical directory + sibling-convention filename + provenance record + index entry. Cross-phase artifacts sit at the host's cross-phase deliverable location with reciprocal back-references. See `rules/canonical-layout-reporting-tiers.md` §2.

(Companion Sub-Rule Anchor) §2.1 — numeric-prefix discipline) Numeric prefixes (`NN-`, `NNL-`) convey ordering and apply only where sequence is intrinsic — phase folders, sub-phase folders, host-ratified migration scripts. Forbidden on root-level singletons and any class without a sibling sequence; decorative prefixes are structural failures. See `rules/canonical-layout-reporting-tiers.md` §2.1.

(Companion Sub-Rule Anchor) §2.2 — plan-suite `_outputs/` surface) Durable generated emissions from plan workflows sit under each suite's `_outputs/` sibling, not in inflated PROGRESS.md / PLAN-NOTES.md narrative and not in ad-hoc root files. See `rules/canonical-layout-reporting-tiers.md` §2.2.

(Companion Sub-Rule Anchor) §2.3 — anti-inflation reporting discipline) PROGRESS.md and PLAN-NOTES.md remain bounded, index-first state ledgers; detailed reports, audit traces, metrics, and bulky evidence move to REPORT.md or `_outputs/` with backlinks. See `rules/canonical-layout-reporting-tiers.md` §2.3.

(Companion Sub-Rule Anchor) §2.4 — `*-maintenance` suite pattern) Deferred or out-of-scope plan work is routed to a sibling maintenance suite with source-suite anchors and rationale; it is not buried in the originating suite's progress narrative. See `rules/canonical-layout-reporting-tiers.md` §2.4.

(Companion Sub-Rule Anchor) §3 — orphan-output prevention) Orphan = no consumer OR no index entry OR no producer attribution; HIGH-severity at pre-emission gate row 12; mechanical matcher at `conformity/orphan_output_grep.py`; recovery via add-consumer / add-index / add-attribution / retire — all in the same change-set. See `rules/canonical-layout-reporting-tiers.md` §3.

(Companion Sub-Rule Anchor) §4 — reciprocal producer / consumer cross-references) Producer-side declares artifact + consumer(s) + binding direction in `Outputs emitted`; consumer-side references the output explicitly per `rules/bidirectional-binding.md`; stale producer reports are findings. See `rules/canonical-layout-reporting-tiers.md` §4.

(Companion Sub-Rule Anchor) §5 — surface imposition) Discipline lands across CLAUDE.md, skills, agents, commands, .apothem/plans/, and tools/conformity. See `rules/canonical-layout-reporting-tiers.md` §5 for the per-surface obligation table.

(Companion Sub-Rule Anchor) §6 — M11 ↔ M12 correspondence) Sprint apparatus per `rules/agile-sprints.md` and layout / reporting discipline are mutually reinforcing — Goal / Backlog / DoR / DoD / Review / Retrospective / Velocity each ↔ a layout-tier surface. See `rules/canonical-layout-reporting-tiers.md` §6 for the full table.

(Companion Sub-Rule Anchor) §7 — three-tier scalability (D7)) `small` (<50 phases / <100 specs) — full-suite validation each pass, in-line refs, monolithic single suite. `medium` (50–500 / 100–1000) — incremental + sampled-rollup validation, suite-root `MASTER-INDEX.md`, phase-grouped decomposition (groups of 5–20). `large` (≥500 / ≥1000) — index-driven + on-demand drilldown validation, queryable index, sub-suite federation. Drift-prevention mechanisms (trace matrix all-tier; stable IDs / MASTER-INDEX.md / phase-rollup verification at medium+; sub-suite federation / suite-rollup at large) per the templates at `src/apothem/templates/master-index-template.md` and `src/apothem/templates/trace-matrix-template.md`. Borderline-tier (±10% of a boundary) routes through the structured-inquiry channel per `rules/authority-inquiry.md` rather than silent-pick. See `rules/canonical-layout-reporting-tiers.md` §7 for tier table, drift-prevention table, and small-tier worked example.

## Disclosure surface

Every layout / reporting emission lands in the disclosure ledger per `rules/disclosure-ledger.md` — `[Output — emitted: …]`, `[Report — sub-phase: …]`, `[Report — rollup: …]`, `[Output — orphan-resolved: …]`. Full marker schemas live at the (Companion Sub-Rule Anchor) sibling rule's Disclosure surface.

## Failure tells

Flat `report1.md` / `report2.md` at ad-hoc paths. A rollup that merely concatenates sub-phase report links instead of aggregating. Cross-phase synthesis buried inside one phase folder. Missing producer attribution. Tests at the project root; docs inlined into README; a CI workflow with no CONTRIBUTING entry. Heterogeneous rollups. A stale producer report claiming a vanished consumer. An emission with no `orphan-output-grep` clearance recorded.
