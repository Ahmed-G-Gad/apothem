---
name: "clean-room-generation"
description: "Clean-room generation methodology for every output — code, prose, plans, artifacts: each is a fresh derivation from an understood specification (independently re-derivable from its inputs), never a memorized template nor a cosmetic edit of existing content. Routes CM-4 search outcomes into the Writing vs. Re-Writing protocols and gates every re-write on quality elevation against a named deficiency. Implements CM-5 / CM-7 / CM-21."
pathFilter: "**/CLAUDE.md, **/AGENTS.md, **/rules/**/*.md, **/commands/**/*.md, **/skills/**/*.md, **/agents/**/*.md, **/hooks/**/*.md, **/output-styles/**/*.md"
alwaysApply: false
paths:
  - "**/CLAUDE.md"
  - "**/AGENTS.md"
  - "**/rules/**/*.md"
  - "**/commands/**/*.md"
  - "**/skills/**/*.md"
  - "**/agents/**/*.md"
  - "**/hooks/**/*.md"
  - "**/output-styles/**/*.md"
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

Applies at every seriousness level, scaling per the table above. Implements CM-5 (Best Solution), CM-7 (Coherent Product), CM-21 (Creative Quality). Canonical specification for generation methodology, re-writing discipline, and output originality.
