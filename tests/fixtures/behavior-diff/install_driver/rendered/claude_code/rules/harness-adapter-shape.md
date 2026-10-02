---
name: "harness-adapter-shape"
description: "Per-harness adapter discipline — discovery walk per harness, sibling-convention convergence, per-harness pre-emission gate adaptation, 7-column adapter-test matrix shape, cross-harness redundancy elimination, and the per-harness STANDARD CONVENTION PIN schema (vendor doc URL + commit-SHA + snapshot date + canonical filename + canonical schema). Demand-loaded on adapter-sub-package touches, co-triggering with its schemas companion."
pathFilter: "**/src/apothem/harnesses/**, **/_inputs/harness-*"
alwaysApply: false
paths:
  - "**/src/apothem/harnesses/**"
  - "**/_inputs/harness-*"
---

<!-- SPDX-License-Identifier: MIT -->

# Rule: Harness Adapter Shape

## Obligations

Every adapter in the 17-harness cohort MUST perform host discovery, converge on the sibling adapter shape, declare its divergences, carry adapter tests, and ship a co-resident `STANDARD-CONVENTION-PIN.md`.

### 1. Discovery walk per harness (Companion Sub-Rule Anchor)

Walk the harness's ratified config schemas, adapter paths, and convention surfaces per `rules/host-discovery.md`. Full schema catalog at `rules/harness-adapter-shape-schemas.md` §1.

### 2. Sibling-convention convergence (Companion Sub-Rule Anchor)

Converge on `HarnessAdapter`, the sibling action modules, `materializer.py` placement, and entry-point registration. Every per-harness divergence MUST be declared; details live at `rules/harness-adapter-shape-schemas.md` §2.

### 3. Gate, test, and pin floor

Adapters MUST pass the fifteen-bar gate, carry the 7-column adapter-test matrix, hoist logic recurring across three or more adapters, and keep `STANDARD-CONVENTION-PIN.md` current. The pin names `vendor-doc-url`, `commit-sha` or archive ID, `snapshot-date`, `canonical-filename`, and `canonical-schema`; a stale or branch-pointed pin is a finding. Templates and adaptation tables live in `rules/harness-adapter-shape-schemas.md` §§3-6.

## Disclosure surface

Record adapter discovery, pin refreshes, and sibling divergences in `rules/disclosure-ledger.md`.

## Failure tells

A missing pin, a stale pin, a branch-pointed vendor reference, an undeclared divergence, a missing canonical action module, duplicate cross-adapter logic, or an incomplete 7-column matrix.

## Bindings (§0.j five-direction)

- **Drives →** Every adapter sub-package authoring / modification / retirement under `src/apothem/harnesses/`. Every per-harness STANDARD CONVENTION PIN refresh. Cross-harness redundancy sweeps.
- **Satisfies →** Per-harness adapter discipline, adapter-test matrix discipline, STANDARD CONVENTION PIN freshness, and the capability-coverage test matrix shape.
- **Established by ↑** `CLAUDE.md` Harness Adapter Pattern section and the adapter cohort's standard pin discipline.
- **Gated by ←** This rule's own pathFilter (`**/src/apothem/harnesses/**, **/_inputs/harness-*`) gates its demand-load, co-triggering with the companion's identical pathFilter for the per-harness schemas.
- **Cross-bound with ↔** `rules/harness-adapter-shape-schemas.md` (path-filtered companion carrying per-harness schema bodies + pin templates + 7-column matrix template + convergence-vs-divergence table). `rules/host-discovery.md` (M1 — per-harness discovery is the M1 walk for adapter conventions; §4 discovery-record provenance schema underwrites the PIN schema at §6). `rules/systemic-participation.md` (M14 — sibling-convention convergence at §2 is the M14 silo-prevention surface for adapters). `rules/canonical-layout.md` (M12 — adapter sub-packages and STANDARD-CONVENTION-PIN.md sit at the canonical layout per the §1 directory shape). `rules/disclosure-ledger.md` (M2 — every discovery, pin refresh, and declared divergence is recorded in the ledger). `rules/agent-capability-discipline.md` (co-resident PIN discipline — the STANDARD CONVENTION PIN at §6 mirrors the agent-capability PIN pattern for cross-cohort consistency). ↔ `rules/agent-capability-discipline-matrix.md` (co-resident STANDARD CONVENTION PIN discipline at §6; per-cell evidence chain anchors to the same pin).
