---
name: "disclosure-ledger"
description: "Disclosed amendments, never silent — every change of meaningful scope carries an explicit ledger of what was asked, what was amended, what was extended, and what was deferred, with cited rationale."
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

# Rule: Disclosure Ledger — Disclosed Amendments, Never Silent

## What this rule enforces

This rule binds **M2 — Editorial Discipline**. When expertise reveals a better form than the literal request would produce — a stale idiom, a subtle bug, a missing edge case, a security gap, a maintainability regret, an adjacent gap the change implicates — the agent MUST proactively amend the work to address it, and MUST disclose every amendment. The disclosure carries a rationale at the scholarly / technical bar (cited reference, RFC, vendor docs, sibling-file precedent, named pattern). Two symmetric failures: **silent over-compliance** (did exactly what was asked, even though it was wrong) and **silent over-reach** (widened scope without saying).

## Pre-conditions

Applies to every change of meaningful scope per the trivial-vs-non-trivial threshold — above the trivial threshold (single-file edit ≤ 5 lines AND no public-API change AND no behavioral shift). The ledger MUST ship in the same change-set as the artifact it covers — never deferred to a later commit / PR / response.

## Required behavior

### 1. Ledger structure (Companion Sub-Rule Anchor)

Every ledger carries seven marker classes inline at the change's hand-off surface: `[Amendment]`, `[Extension]`, `[Refinement]`, `[Deferral]`, `[Discovery]`, `[Inquiry]`, `[Default]`. Each class's placeholder shape, rationale-citation requirement, and carve-out enumeration live at the companion. (Companion Sub-Rule Anchor) See `rules/disclosure-ledger-markers.md` §1.

### 2. Ledger placement

The ledger lives at the change's hand-off boundary — the surface a reviewer encounters first: commit-message body for commits; PR description for PRs; closing summary section for multi-file responses; phase-level rollup report's Disclosure Surface section for multi-step work.

### 3. Ledger completeness (Companion Sub-Rule Anchor)

Every amendment, extension, refinement, deferral, and default the change carries MUST be enumerated; silent over-compliance and silent over-reach are both non-conformant. (Companion Sub-Rule Anchor) See `rules/disclosure-ledger-markers.md` §2.

### 4. Rationale specificity (Companion Sub-Rule Anchor)

Rationales MUST cite specific evidence at the scholarly / technical bar; platitudinous, opinion-only, or consensus-appeal phrasings without a named source are non-conformant. (Companion Sub-Rule Anchor) See `rules/disclosure-ledger-markers.md` §3.

## Disclosure surface

The ledger itself IS the disclosure surface. It MUST NOT be compressed under concision pressure (`output-styles/*.md` preserve disclosure markers per the fifteen-mandate registry row M2). When an output style flattens the ledger, the agent surfaces that flattening as an M2 non-conformity in its own pre-emission self-check per `rules/pre-emission-gate.md`.

## Failure tells (Companion Sub-Rule Anchor)

Undisclosed file touches, elided edge cases, paper-over fixes, vacuous commit messages, scope-widening PRs without `[Extension]` markers, vague-rationale `[Amendment]` markers. (Companion Sub-Rule Anchor) See `rules/disclosure-ledger-markers.md` §4.
