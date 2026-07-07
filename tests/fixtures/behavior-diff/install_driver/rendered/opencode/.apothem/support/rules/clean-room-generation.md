---
name: "clean-room-generation"
description: "Clean-room generation methodology for every output — code, prose, plans, artifacts: each is a fresh derivation from an understood specification (independently re-derivable from its inputs), never a memorized template nor a cosmetic edit of existing content. Routes CM-4 search outcomes into the Writing vs. Re-Writing protocols and gates every re-write on quality elevation against a named deficiency. Implements CM-5 / CM-7 / CM-21."
pathFilter: ""
alwaysApply: true
---

<!-- SPDX-License-Identifier: MIT -->

# Rule: Clean-Room Generation

## Purpose

Govern the generation methodology for every output — code, prose, documentation, plans, artifacts. Each output MUST be a fresh derivation from an understood specification, never a reproduction of memorized patterns nor a cosmetic transformation of existing content.

## Obligations

### 1. The Clean-Room Invariant

**Every output MUST be independently derivable from its inputs.** Given the specification, context, and constraints, a competent professional with zero access to prior implementations produces substantially the same output.

Corollaries:

- No output relies on memorized templates or boilerplate for its structure.
- Every structural choice is justifiable from the current context.
- Re-generating from the same specification MAY differ in expression while solving the same problem.
- Convention is a starting point for evaluation, never an autopilot for structure.

**1.1 — Interaction with CM-4 (Search Before Implement).** CM-4 search determines *what* to build; clean-room governs *how*. After CM-4 search, route by coverage:

- **(a) Existing code fully satisfies** — reuse as-is; no generation or re-writing.
- **(b) Existing code partially satisfies** — reuse the covered portion as-is; treat the uncovered portion as the Writing-Protocol (§2) specification.
- **(c) Existing code needs integration changes** — Re-Writing Protocol (§3) on the modified portion only, scoped to the changed behavioral contracts.
- **(d) Existing code fundamentally unsuitable** — Writing Protocol (§2) for the full requirement; document why reuse was rejected.

### 2-6. Protocols (Companion Sub-Rule Anchor)

Full protocols — §2 Writing, §3 Re-Writing, §4 Code Generation, §5 Prose and Documentation, §6 Plan and Artifact Generation — plus the CM-4 Decision Tree and six Anti-Patterns live at `rules/clean-room-generation-protocols.md`. The companion demand-loads on code, prose, plan, or artifact-surface touches.

## Seriousness Scaling

| Level | Clean-Room Discipline |
| ----- | --------------------- |
| EXPLORING | Intent-first derivation (2.2) and contextual precision (2.4). Quality elevation on explicit re-write requests |
| PERSONAL_USE | Full Writing Protocol (Section 2) + Code Generation (Section 4). Re-Writing Protocol on re-write/refactor requests |
| SHARED | Full Sections 2–6. Quality elevation mandatory on all re-writes. Sentence-level justification on documentation |
| PUBLIC_LAUNCH | Full enforcement. Re-writing requires documented behavioral extraction (written to scratch/notes, not just mental). Structural choices annotated with rationale on all non-trivial artifacts. Completeness Gate (2.5) verified with explicit checklist |

## Enforcement

Always-on at every seriousness level, scaling per the table above. Implements CM-5 (Best Solution), CM-7 (Coherent Product), CM-21 (Creative Quality). Canonical specification for generation methodology, re-writing discipline, and output originality.

## Bindings (§0.j five-direction)

- **Drives →** ● Every code, prose, plan, and artifact emission across the ecosystem (the Writing Protocol §2 + Re-Writing Protocol §3 are the generation-method floor). ● Every `/plan` stage's artifact production (plan-suite emissions adopt the §6 fresh-derivation discipline). ● Every refactor-class agent task (Re-Writing Protocol §3 quality-elevation mandate gates the re-write). ◐ The CM-7 plan-internal isolation invariant on every codebase artifact (the §1 clean-room invariant operationalizes CM-7's natural-domain-language requirement). ◐ The CM-4 search-before-implement four-outcome routing (§1.1 mirrors CM-4's outcomes).
- **Satisfies →** ● CM-5 / CM-7 / CM-21 (rule-delegated mandates). ● the rules registry row "Clean-Room Generation".
- **Established by ↑** ● `rules/cognitive-identity.md` (clean-room generation is the methodology arm of the cognitive-identity declaration). ● CM-5 + CM-7 + CM-21 inline definitions. ● `rules/cognitive-identity.md` §1 seven-axs-of-breadth taxonomy (re-writing protocol's quality-elevation mandate cites that taxonomy).
- **Gated by ←** ● `rules/operational-mandates.md` (CM-4 search-before-implement gate fires before §1.1 routes to a Writing/Re-Writing path). ● `rules/cognitive-identity.md` Filter 1 + Filter 5 always-on baseline.
- **Cross-bound with ↔** ↔ `rules/clean-room-generation-protocols.md` (path-filtered companion sub-rule carrying the §2-§6 protocols, Decision Tree, and Anti-Patterns specifications). ↔ `rules/cognitive-identity.md` (Filter 5 aesthetic-demand ↔ §3.4 quality elevation; both implement CM-21's facets). ↔ `rules/operational-mandates.md` (CM-4/CM-5/CM-7 are inline-defined there; this rule is the methodology specification). ↔ `rules/planning-techniques.md` (third co-implementer of CM-21; planning-technique facet over there, generation-methodology facet here). ↔ `rules/persistent-conventions-vigilance.md` (clean-room generation produces ecosystem-coherent artifacts; convention vigilance maintains ecosystem coherence). ↔ `rules/plain-language.md` (Writing Protocol §2 produces narrative honoring plain-language; plain-language is the post-emission scan). ↔ `rules/token-efficiency-rewrite.md` (token-efficiency specialisation of §3 re-writing protocol with L2/L3 tiers made explicit). ↔ `rules/large-file-reading.md` (CM-4 Search Before Implement uses Grep/Glob first; large-file-reading canonicalizes locate-before-read). ↔ `rules/refactoring-discipline.md` (gates when and how the §3 re-writing protocol runs for a behaviour-preserving refactor). ↔ `rules/clean-architecture-layers.md` (clean-room generation produces layer-correct artifacts; §2 Writing Protocol respects layer boundaries). ↔ `rules/code-craft-markdown.md` (this rule is the per-language projection of §5; sentence-level justification, precision over politeness, active-voice construction are inherited from §5.1–§5.4). ↔ `rules/code-craft-python.md` (Python code emission passes the Writing Protocol §2 + Code Generation §4 before this rule's path-filtered guardrails apply). ↔ `rules/code-craft-shell.md` (Code Generation §4 governs initial shell emission before this rule's path-filtered guardrails apply). ↔ `rules/cognitive-identity-techniques.md` (Filter 5 aesthetic-demand ↔ §3.4 quality elevation mandate; both implement CM-21's facets). ↔ `rules/large-file-generation.md` (§2 Writing Protocol governs *what* to write; this rule governs *how* to safely write it when the size exceeds the single-write band). ↔ `rules/operational-mandates-expanded.md` (CM-4 §1.1 four-outcome mirror cited in the CM-4 Recovery sub-block). ↔ `rules/surgical-manipulation.md` (governs green-field authoring; this rule governs mutation of existing artifacts). ↔ `rules/token-efficiency-rewrite-protocol.md` (§3 re-writing protocol + §5 prose discipline — L1 elimination is the token-efficiency projection of §5's sentence-level justification).
