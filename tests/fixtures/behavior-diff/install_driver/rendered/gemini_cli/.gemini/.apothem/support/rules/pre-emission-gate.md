---
name: "pre-emission-gate"
description: "Fifteen-bar pre-emission gate — every host-project artifact passes M1 through M15 before emission, with a recorded YAML attestation and explicit n/a reasoning where a bar does not apply."
pathFilter: ""
alwaysApply: true
---

<!-- SPDX-License-Identifier: MIT -->

# Rule: Pre-Emission Gate — Fifteen-Bar Self-Application

## What this rule enforces

This rule binds **M4 — Self-Application: Every Artifact Passes the Same Bar Before Emission**. Every artifact the ecosystem emits in a host project — commit, diff, file, PR description, comment, response, doc page, diagram, test, example, migration script, config entry — MUST itself clear all fifteen mandates. Quality is a pre-emission concern, never a downstream "the user can revise it" concern. The bar is **fifteen**: the ten dimensions of M3 plus M5, M6, M7, M8, M9, M10, M11, M12, M13, M14, M15. An artifact that fails any single bar MUST be revised before it leaves the agent's hands.

## Pre-conditions

Applies before any meaningful-scope emission per the trivial-vs-non-trivial threshold. Trivial emissions (single-file edit ≤ 5 lines AND no public-API change AND no behavioral shift) run an abbreviated gate covering **M4** (attestation present) and **M5** (no `<USER-CONFIRM:…>` placeholders) only.

## Required behavior

### The Fifteen Bars (one-line summary)

Each bar MUST pass individually before emission:

- **M1** Host agnosticism · **M2** Editorial disclosure · **M3** Ten dimensions · **M4** Self-application · **M5** Authority · **M6** Expertise · **M7** Option annotation · **M8** Definitiveness · **M9** Visual leverage · **M10** Bidirectional binding · **M11** Agile sprints · **M12** Phase reporting & layout · **M13** Code craft · **M14** Systemicity · **M15** Production-ready.

Mechanical-fraction bars (M2, M5, M7, M8, M10, M13, M15) carry executable matchers at `conformity/*-grep.py` orchestrated by `conformity/gate.py`; reasoned bars (M1, M3, M6, M9, M11, M12, M14) are agent-evaluated and recorded in the attestation.

(Companion Sub-Rule Anchor) See `rules/pre-emission-gate-bars.md` §1 for the per-bar Check + Failure→action table.

### Attestation Schema

The attestation is appended to the artifact's working trace (commit body, PR description, change ledger, or a dedicated `attestation.yml`): one `pass | n/a (with reason)` line per bar, plus the `surfaced-gaps`, `unresolved-inquiries`, and `amendments-disclosed` arrays, an `artifact` identifier, an `ecosystem-version` SHA, and an ISO-8601 `date`. Every `n/a` MUST carry a reason — silent skips are non-conformant. (Companion Sub-Rule Anchor) See `rules/pre-emission-gate-bars.md` §2 for the YAML schema.

### Iteration on failure

A single bar failure blocks emission. Revise per that bar's "Failure → action" rule, then re-run the gate; repeat until every bar passes. (Companion Sub-Rule Anchor) See `rules/pre-emission-gate-bars.md` §3.

## Disclosure surface

The attestation block IS the disclosure surface. Surfaced gaps (M6), unresolved inquiries (M5), and disclosed amendments (M2) populate three named arrays; empty arrays are written explicitly (`surfaced-gaps: []`), never elided.

## Failure tells

A commit that breaks the host's lint. A PR description with a dead link. A doc page citing a phantom URL. A diagram describing a flow the code does not implement. An attestation marked `pass` while a checked condition demonstrably fails. A bar marked `n/a` with no reason. An attestation missing the `date` or `ecosystem-version` field. A `pass` attestation on an artifact a mechanical `conformity/*-grep.py` flags as failing.

## Bindings (§0.j five-direction)

- **Drives →** Every host-project artifact emission across every ecosystem surface (the gate is the literal last step before emission). The mechanical-fraction enforcement at `conformity/*-grep.py` orchestrated by `conformity/gate.py`. The gate-attestation requirement at every `commands/*.md` Step N closing emission. The gate-attestation block at every `agents/*.md` return format.
- **Satisfies →** the fifteen-mandate registry row **M4 — Self-Application**. the Pre-Emission Gate (this rule is the canonical operationalization). the Pre-Emission Gate Attestation Schema.
- **Established by ↑** the fifteen-mandate registry (ratifies M4). the Pre-Emission Gate (the gate table this rule mirrors at full body bar). the Pre-Emission Gate attestation schema (the attestation schema this rule reproduces).
- **Gated by ←** The §8.1 trivial-vs-non-trivial threshold (trivial emissions run the abbreviated gate). `CLAUDE.md` always-loaded preamble.
- **Cross-bound with ↔** `rules/pre-emission-gate-bars.md` (path-filtered companion sub-rule carrying the full Fifteen-Bars table, the Attestation Schema YAML block, and the iteration-on-failure protocol). Every M-rule named in the gate's "Failure → action" column (`rules/host-discovery.md`, `rules/disclosure-ledger.md`, `rules/ten-dimension-check.md`, `rules/authority-inquiry.md`, `rules/expertise-posture.md`, `rules/option-annotation.md`, `rules/definitiveness.md`, `rules/visual-leverage.md`, `rules/bidirectional-binding.md`, `rules/agile-sprints.md`, `rules/canonical-layout.md`, `rules/code-craft-python.md` and sibling per-language code-craft rules, `rules/systemic-participation.md`, `rules/production-ready-prs.md`). `rules/operational-mandates.md` §CM-1 Critical Evaluation × §CM-7 Coherent Product (M4 is the composite outward-projection form of these two CM-N mandates). `rules/dynamism.md` (bar 8 fires the `static-version-grep` matcher and consumes its verdict). `rules/recommend-next-step.md` (M4 — block presence is a gated bar at terminal-surface emission). `rules/token-efficiency-rewrite.md` (bar inspection of L3 anchor-diff zero-drift and L2-preservation attestation). `rules/agnostic-posture.md` (under the host-agnostic posture the gate's bars surface as advisories, not blocks). `rules/determinism.md` (the gate consumes the determinism matcher's verdict on byte-stable materialized outputs). `rules/session-closure.md` (M4 — the formal session close's verification-attestation element is the session-scale analog of the gate's per-bar attestation; a close's "checked" column mirrors the gate's bar attestation at the session boundary). ↔ `rules/agile-sprints-elements.md` (M4 — bar 11 of the gate enforces sprint-apparatus instantiation; §2 Inspection pillar operationalizes per-increment gate inspection). ↔ `rules/authority-inquiry-categories.md` (M4 — bar 5 of the gate enforces this companion's `<USER-CONFIRM:…>`-placeholder absence and unresolved-inquiry array population). ↔ `rules/canonical-layout-reporting-tiers.md` (M4 — bar 12 enforces this rule's two-tier + canonical-layout + orphan-prevention invariants). ↔ `rules/definitiveness-virtues.md` (M4 — bar 8 of the gate operationalizes the hedging-vocabulary scan and the pre / post / failure-condition presence check). ↔ `rules/disclosure-ledger-markers.md` (M4 — `amendments-disclosed` array population). ↔ `rules/expertise-posture-elements.md` (M4 — bar 6 of the gate enforces the seven sub-elements at §1). ↔ `rules/surgical-manipulation.md` (the golden-corpus attestation is verified at the gate). ↔ `rules/ten-dimension-check-dimensions.md` (M4 — bar 3 of the fifteen-bar gate inspects each of the ten verbatim per-dimension bodies enumerated here).
