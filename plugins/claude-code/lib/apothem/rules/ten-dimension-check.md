---
name: "ten-dimension-check"
description: "Ten quality dimensions every host-project artifact passes before emission — rigor, coherence, configurability, readability, orphanism, structurality, architecture, naming, scholarly referencing, examples / tests / docs."
pathFilter: ""
alwaysApply: true
---

<!-- SPDX-License-Identifier: MIT -->

# Rule: Ten Quality Dimensions

## What this rule enforces

This rule binds **M3 — The Ten Quality Dimensions Applied to Every Artifact**. Every artifact the ecosystem produces in a host project MUST be evaluated against ten quality dimensions, maximally meticulously, before emission. The check is a discrete pre-emission step (per `rules/pre-emission-gate.md`) recorded in the working trace — never implicit, never delegated downstream.

Multiple-dimension failure is **multiplicative, not additive**: an artifact that is stale AND orphan AND inconsistently named AND undocumented is a candidate for retraction, not repair.

## Pre-conditions

Applies to every host-project artifact above the trivial threshold per the trivial-vs-non-trivial threshold. Trivial work runs an abbreviated check covering dimensions 4 (readability), 5 (orphanism / staleness), and 8 (naming) only.

## Required behavior

### The Ten Dimensions (Companion Sub-Rule Anchor)

Every artifact MUST pass each dimension individually before emission. The ten dimensions, in canonical order:

1. Scientific rigor.
2. Consistency · Coherence · Integration · Validity.
3. Configurability · Irredundancy · Consolidation.
4. Readability · Intuition · Cleanness.
5. Orphanism · Staleness.
6. Structurality · Systemicity · Uniformity · Comprehensiveness.
7. Architecture.
8. Naming conventions & uniformity.
9. Scholarly / technical referencing.
10. Examples · Tests · Docstrings · Documentation.

(Companion Sub-Rule Anchor) See `rules/ten-dimension-check-dimensions.md` §The Ten Dimensions — Per-Dimension Bodies for the verbatim per-dimension bodies and per-dimension failure tells. The companion demand-loads on artifact-emission surfaces (Markdown, Python, shell, PowerShell under the rules / commands / skills / agents / docs trees and the root `CLAUDE.md`).

### Self-check at emission

Before emitting / committing / handing off, the ten-bar self-check is recorded in the working trace as part of the fifteen-bar pre-emission gate attestation per `rules/pre-emission-gate.md`. Each dimension MUST be marked `pass` or `n/a (with reason)` — never silent, never aspirational.

## Disclosure surface

A failed dimension is either fixed before emission (the standard path) or, when the failure is structural and exceeds the change's scope, surfaced via `rules/disclosure-ledger.md` as a `[Deferral — out-of-scope: dimension N — <description>; tracking: <where>]` marker. A deferred dimension MUST NOT carry a `pass` marking — it carries an explicit `defer` marking with the deferral's tracking location.

## Failure tells

Per-dimension failure tells live at the companion. Cross-cutting tells: a `pass` marking while a checked condition demonstrably fails (an **M4** self-application breach); an attestation block missing the ten-dimension entries; a dimension marked `n/a` without a reason; a `pass` recorded without corresponding evidence in the working trace; an artifact compounding multiple failed dimensions (stale + orphan + mis-named + undocumented) emitted as repaired rather than retracted.

## Bindings (§0.j five-direction)

- **Drives →** Every artifact's pre-emission gate attestation per `rules/pre-emission-gate.md` (the ten-dimension entries are operationalized here as bar 3 of the fifteen-bar gate). Every code-craft surface check at `rules/code-craft-{python,shell,markdown,conventions}.md` (per-language code-craft rules apply dimensions 4, 7, 8, 10 with language-specific failure tells). Every doc-emission step at `skills/*/SKILL.md` and `commands/*.md`.
- **Satisfies →** the fifteen-mandate registry row **M3 — Ten Quality Dimensions**. the Pre-Emission Gate row 3 (M3 ten-dimensions check).
- **Established by ↑** the fifteen-mandate registry (ratifies M3). the Pre-Emission Gate (the gate row 3 anchors the dimension check).
- **Gated by ←** The §8.1 trivial-vs-non-trivial threshold (trivial work runs the abbreviated check). `CLAUDE.md` always-loaded preamble.
- **Cross-bound with ↔** `rules/ten-dimension-check-dimensions.md` (path-filtered companion sub-rule carrying the verbatim per-dimension bodies and per-dimension failure tells). `rules/pre-emission-gate.md` (M4 — the ten-dimension check is bar 3 of the fifteen-bar gate). `rules/disclosure-ledger.md` (M2 — deferred dimensions surface as deferrals). `rules/operational-mandates.md` §CM-5 Best Solution (the dimension check is the outward-projection form of CM-5's "expert-grade" requirement). `rules/code-craft-python.md` and sibling per-language code-craft rules (per-dimension materialization for code). `rules/etc-extension.md` (dimension 6 Comprehensiveness — the etc.-extension obligation is the upstream behavior this dimension verifies at emission). `rules/source-accessibility.md` (dimension 9 Scholarly / technical referencing — source-trust selection is the upstream behavior this dimension verifies). `rules/authoritative-referencing.md` (dimension 9 — the authoritative-referencing standing mandate outward-projects this referencing dimension). ↔ `rules/authoritative-referencing-homes.md` (dimension 9 Scholarly / technical referencing — the first per-surface home this companion catalogs). ↔ `rules/definitiveness.md` (M3 — dimension 2 consistency / coherence + dimension 6 structurality enforce airtightness across artifacts; this rule enforces it within the artifact). ↔ `rules/definitiveness-virtues.md` (M3 — dimension 2 consistency / coherence + dimension 6 structurality enforce airtightness across artifacts; this rule enforces it within the artifact). ↔ `rules/disclosure-ledger-markers.md` (M3 — rationale citations meet dimension 9). ↔ `rules/expertise-posture.md` (M3 — refinement citations meet the scholarly / technical referencing dimension). ↔ `rules/option-annotation.md` (M3 — rationale specificity meets dimension 9 scholarly / technical referencing). ↔ `rules/option-annotation-form.md` (M3 dimension 9 scholarly / technical referencing — rationale specificity meets it). ↔ `rules/pre-emission-gate-bars.md` (this rule is among the M-rules named in the gate's "Failure → action" column; the bar-level catalog cross-binds each).
