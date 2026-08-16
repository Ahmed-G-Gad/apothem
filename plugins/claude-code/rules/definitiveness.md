---
name: "definitiveness"
description: "Every emitted statement is definitive and airtight — hedging vocabulary is eliminated where binding prescription is possible; every contract carries pre / post / failure conditions; every TBD / TODO / FIXME is closed in place or surfaced as an inquiry; the family of rigorous-systems virtues governs every artifact."
pathFilter: ""
alwaysApply: true
---

<!-- SPDX-License-Identifier: MIT -->

# Rule: Definitiveness, Airtightness, and the Family of Rigorous-Systems Virtues

## What this rule enforces

Binds **M8 — Definitiveness, Airtightness, and the Family of Rigorous-Systems Virtues**. Every statement in every emitted host-project artifact — instruction, rule, description, contract, schema, matcher, directive, comment, runbook step — MUST be **definitive** (no hedging where binding prescription is possible; no "it depends" without dependencies enumerated; no unstated scope; no implicit defaults; no vague thresholds) and **airtight** (no gaps in declared domains; no loopholes where literal-honoring violates intent; no unstated assumptions; no precedence ties; no silent fallbacks in authoritative territory; no "edge cases we'll figure out later"). The broader family — completeness, closure, strong non-contradiction, determinism, exhaustiveness of enumerations, specificity over vagueness, pre / post / failure conditions on every contract — is the family of rigorous-systems virtues this rule enforces collectively.

## Pre-conditions

Applies to every host-project artifact emission, including trivial-scope work per the trivial-vs-non-trivial threshold — the airtightness floor does not relax with scope. A two-line comment, a five-line shell snippet, and a multi-thousand-line architectural specification carry the same definitiveness obligation.

## Required behavior

### Hedging vocabulary — eliminate or qualify

Closed list, detected and eliminated when binding prescription is possible: **maybe, might, could, should probably, usually, generally, typically, mostly, often, perhaps, possibly, somewhat, fairly, roughly, broadly**. Each occurrence MUST resolve on one of three paths — **Promote** (unconditional with conditions named), **Demote** (explicit conditional with branches enumerated), or **Remove** (route to inquiry surface). The mechanical hedging-grep at `conformity/hedging_grep.py` operationalizes the detection at `rules/pre-emission-gate.md` row 8.

(Companion Sub-Rule Anchor) See `rules/definitiveness-virtues.md` §1 for the three resolution paths with worked examples.

### The family of rigorous-systems virtues

Every emitted artifact passes a seven-virtue floor: **(1) Completeness**, **(2) Closure**, **(3) Strong non-contradiction**, **(4) Determinism**, **(5) Exhaustiveness of enumerations**, **(6) Specificity over vagueness**, **(7) Pre / post / failure conditions on every contract**.

(Companion Sub-Rule Anchor) See `rules/definitiveness-virtues.md` §2 for the seven-virtue numbered list with full prose.

### Definitive form — examples

(Companion Sub-Rule Anchor) See `rules/definitiveness-virtues.md` §3 for Right/Wrong worked examples.

### Airtightness checks beyond hedging

Hedging elimination is the surface signal; airtightness reaches deeper into four checks: **no silent fallbacks**, **no precedence ties**, **no edge cases for later**, **no literal-honoring loopholes**. Intent is the contract; literal text is the carrier.

(Companion Sub-Rule Anchor) See `rules/definitiveness-virtues.md` §4 for the four-check bullet body.

## Disclosure surface

Hedge promotions land as `[Refinement — improvement: definitiveness; from: <hedged>; to: <definitive>; rationale: <driver>]` in the ledger per `rules/disclosure-ledger.md`. Removed prescriptions land as `[Deferral — out-of-scope: prescription removed; tracking: <id>]`. Closed `TBD` / `TODO` / `FIXME` markers carry closure rationale inline.

## Failure tells

(Companion Sub-Rule Anchor) See `rules/definitiveness-virtues.md` §5 for the failure-tells full prose enumeration.

## Bindings (§0.j five-direction)

- **Drives →** Every emitted host-project artifact's pre-emission definiteness check (the seven-virtue floor and the hedging-vocabulary scan). The mechanical hedging-grep at `conformity/hedging_grep.py`. Every `commands/*.md` Step-N closing emission's prose pass. Every `rules/*.md` body shape (every ratified rule sibling honors the same definiteness floor on its own prescriptive prose). The closure clause at every `skills/*/SKILL.md` (every `TBD` / `TODO` / `FIXME` is closed in place or surfaced as an inquiry).
- **Satisfies →** the fifteen-mandate registry row **M8 — Definitiveness, Airtightness**.
- **Established by ↑** the fifteen-mandate registry (ratifies M8). `rules/operational-mandates.md` §CM-10 Brutal Honesty (the inward-axis analog M8 cross-maps to; brutal honesty's outward projection is the definiteness floor enforced here).
- **Gated by ←** `CLAUDE.md` always-loaded preamble. The pre-emission gate at `rules/pre-emission-gate.md` row 8 (M8 mechanical bar; the hedging grep operationalizes this rule's vocabulary list).
- **Cross-bound with ↔** `rules/definitiveness-virtues.md` (path-filtered companion sub-rule carrying the three hedge-resolution paths with worked examples, the seven-virtue numbered list with full prose, the definitive-form Right/Wrong examples, the airtightness-checks-beyond-hedging bullet body, and the failure-tells full prose). `rules/operational-mandates.md` §CM-10 Brutal Honesty (M8 ↔ CM-10 cross-mapping). `rules/disclosure-ledger.md` (M2 — every hedge promotion / removal is recorded in the ledger). `rules/ten-dimension-check.md` (M3 — dimension 2 consistency / coherence + dimension 6 structurality enforce airtightness across artifacts; this rule enforces it within the artifact). `rules/pre-emission-gate.md` (M4 — bar 8 of the gate operationalizes the hedging-vocabulary scan and the pre / post / failure-condition presence check). `rules/authority-inquiry.md` (M5 — removed-prescription cases route to the inquiry surface). `rules/recommend-next-step.md` (M8 — the named action carries no hedging vocabulary; the next-move declaration is binding). `rules/token-efficiency-rewrite.md` (M8 — closed-enumeration exhaustiveness is an L2 invariant of token-efficient rewrites). `rules/determinism.md` (the determinism virtue in M8's rigorous-systems family is the dedicated subject of that rule's byte-stable-output discipline). ↔ `rules/agile-sprints.md` (M8 — Sprint Goal definitiveness floor). ↔ `rules/agile-sprints-elements.md` (M8 — Sprint Goal must satisfy the definitiveness floor per §1.1). ↔ `rules/bidirectional-binding.md` (M8 — placeholder bindings like `Drives → TBD` violate both this rule's reciprocity discipline and M8's closure-of-open-markers discipline). ↔ `rules/code-craft-markdown.md` (M8 — hedge-elimination discipline applies in full to Markdown prescriptive prose). ↔ `rules/pre-emission-gate-bars.md` (this rule is among the M-rules named in the gate's "Failure → action" column; the bar-level catalog cross-binds each). ↔ `rules/token-efficiency-rewrite-protocol.md` (M8 — L1.4 hedge-padding is the no-information subset; binding-prescription hedging is the M8 defect).
