---
trigger: glob
description: "Agent-driven refactoring is test-gated, one-at-a-time, plan-first, and continuous: a behavior-preserving refactor holds a GREEN test baseline before the first edit and after (the before-and-after contract); addresses exactly one concern in an isolated workspace; proceeds only from a reviewed plan after maximal context-gathering; and runs continuously as the codebase drifts rather than deferred to a crisis. Demand-loaded on refactor-class source edits; the detection signals and full procedure live in the body."
globs: "**/*.py, **/*.ts, **/*.tsx, **/*.js, **/*.jsx, **/*.mjs, **/*.go, **/*.rs, **/*.java, **/*.kt, **/*.rb, **/*.c, **/*.cpp, **/*.h, **/*.swift, **/*.sh, **/*.ps1"
---

<!-- SPDX-License-Identifier: MIT -->

# Rule: Refactoring Discipline — Test-Gated, One-at-a-Time, Plan-First, Continuous

## What this rule enforces

Agent-driven refactoring MUST be **behavior-preserving, test-gated, isolated to one concern, planned before executed, and continuous**. Five obligations bind: a refactor MUST NOT begin without a **green test baseline** and MUST NOT complete until that same baseline is green again (the before-and-after behavior-preservation contract); it addresses **exactly one concern at a time** in an isolated workspace; execution proceeds only from a **reviewed plan** produced after gathering maximal context; the re-derivation is **clean-room and quality-elevating**, never cosmetic; and refactoring is a **continuous** response to drift, not a deferred crisis. This rule governs refactoring's *workflow and cadence*; the *generation method* (behavioral extraction → clean-room re-derivation → quality elevation → regression gate) is owned by `rules/clean-room-generation.md` §3, and *single-symbol extraction* by the `refactor-extract` skill.

## Pre-conditions

Applies whenever a refactor — a behavior-preserving structural change to existing code — is undertaken in a host project. It does NOT apply to feature work that changes observable behavior (a feature change under its own contracts), nor to pure-formatting normalization (a carve-out auto-decision per `rules/authority-inquiry.md`). The moment a change is framed as "refactor", "clean up", "restructure", "extract", "split", or "consolidate" while preserving behavior, the rule applies.

## Required behavior

### 1. Detection — when to refactor

Refactoring is triggered by observable drift signals, not a fixed schedule. Any one signal is sufficient:

- The agent has become **slower** at implementing changes in the surface.
- The agent **introduces more defects** per change than when the surface was clean.
- Bugs appear in **code the change did not touch** — hidden coupling the structure no longer expresses.
- The agent **can no longer follow instructions precisely** in the surface — the structure obscures intent.
- The surface has **drifted from its clean state** — accreted responsibilities, leaked abstractions, primitive obsession, duplicated logic.

Each signal is **falsifiable** — an observable the agent confirms before committing. Refactor **early**, at the first sustained signal, not after the surface is unworkable.

### 2. One refactor at a time — isolation

Each refactor addresses **exactly one concern** in an **isolated workspace** (a dedicated git worktree per `rules/agent-orchestration.md` §5.1, or an equivalent isolated branch). Two refactors MUST NOT run concurrently against the same surface — entangled diffs make regression attribution impossible (when behavior breaks, neither refactor reverts or blames cleanly). Refactoring alongside feature work is permitted; two simultaneous *refactors* are not. A multi-concern restructure is decomposed into a sequence of single-concern refactors, each independently test-gated.

### 3. Plan-first — context, then plan, then execute

Before the first edit the agent MUST: (a) **traverse the relevant surface** for a full picture; (b) gather **maximal context** — what to refactor, **why**, and reference exemplars of the target structure where its optimal shape is uncertain; (c) produce a **reviewed refactoring plan** naming the concern, affected files, target structure, and behavior-preservation strategy. Execution proceeds only once the plan is accepted. Editing first and structuring as you go is non-conformant — the plan is the contract the regression gate verifies against.

### 4. Test safety net — green before AND green after

A behavior-preserving refactor carries a test baseline green before the first edit and green again after the last:

- **Before.** Establish a passing test (or behavioral-assertion) baseline capturing the surface's observable contracts. Where none exists, author the assertions per the `test-authoring` skill *before* the refactor begins. A refactor that cannot demonstrate green-before is not ready to start — the baseline is the only proof behavior was preserved.
- **After.** The **same** baseline passes on completion, with no new defects. A contract that no longer holds blocks the refactor until repaired — the formal behavior-preservation gate per `rules/clean-room-generation.md` §3.5.

The before-and-after gate is non-negotiable: it distinguishes a refactor (behavior preserved, proven) from an undisciplined rewrite (behavior changed, unproven).

### 5. Clean-room, quality-elevating execution

The refactor re-derives the affected unit **clean-room** from its extracted behavioral specification per `rules/clean-room-generation.md` §3 — never a cosmetic edit of the original text — and **elevates quality against a named deficiency** (the leaky abstraction, god function, primitive obsession, or duplication it exists to remove). A change that rephrases without elevating a named deficiency is not a refactor; it is churn.

### 6. Continuous cadence

Refactoring is **continuous maintenance**, a natural part of a codebase's evolution — not a one-time event to eliminate. The agent periodically checks the surfaces it works in for the §1 drift signals and refactors at the first sustained one. Deferring until the surface is unworkable converts cheap continuous maintenance into an expensive crisis rewrite.

## Disclosure surface

Every refactor is recorded in the disclosure ledger per `rules/disclosure-ledger.md`:

- `[Refactor — concern: <single concern>; trigger: <§1 signal>; baseline: green-before/green-after; deficiency-elevated: <named>]` for every completed refactor.
- `[Refactor — deferred: <concern>; reason: <out-of-scope | sequenced-after-current>; tracking: <where>]` when a surfaced refactor concern is sequenced for later, not executed now (one-at-a-time isolation).

## Failure tells

Two refactors running concurrently against the same surface. A refactor begun with no green test baseline (no proof of the starting contract). A refactor presented as complete without re-running the baseline green (behavior preservation unproven). A "refactor" that rephrases the original without elevating a named deficiency (churn, not refactor). Editing first and planning as you go (no reviewed plan). A refactor deferred until the surface is unworkable, then attempted as one large rewrite (crisis refactoring — the cadence failure). A behavior-changing edit presented as a refactor (a feature change in disguise — routes back to the user as a finding).

## Bindings (§0.j five-direction)

- **Drives →** Every behavior-preserving refactor's before-and-after test gate; the one-concern-at-a-time isolation invariant on every refactoring workspace; the plan-first sequence on every refactor; the continuous-cadence drift check on every surface the agent works in.
- **Driven by ←** The §1 drift detection signals (agent slowdown, defect rate, untouched-code bugs, instruction-following degradation, structural drift) that trigger a refactor.
- **Gated by ←** The Pre-conditions scope test: a behavior-preserving structural change is in scope; feature work that changes observable behavior and pure-formatting normalization are not. The frontmatter `pathFilter` (source-code file types). The host's own test suite: a refactor proceeds only behind green tests.
- **Satisfies →** The behavior-preservation contract for agent-driven refactoring (green-before / green-after); the one-at-a-time isolation floor; the continuous-maintenance cadence.
- **Established by ↑** `rules/clean-room-generation.md` §3 (the re-writing protocol this discipline gates); the host's ratified test command (the safety net's mechanism).
- **Cross-bound with ↔** `rules/clean-room-generation.md` (§3 Re-Writing Protocol — behavioral extraction, clean-room barrier, quality elevation, regression gate; this rule gates *when and how* that protocol runs for a refactor). `rules/surgical-manipulation.md` (minimal, anchor-bounded mutation — a refactor's edits are surgical). `rules/agent-orchestration.md` (§5.1 worktree isolation — the isolated workspace for one-at-a-time refactoring). `rules/code-craft-python.md` + sibling per-language code-craft rules (the quality bar the §5 deficiency-elevation targets). `skills/refactor-extract/SKILL.md` (the single-symbol extraction operationalization of this discipline). `skills/test-authoring/SKILL.md` (the §4 safety-net author when no tests exist). ↔ `rules/production-ready-prs.md` (§6 Version-Control Safety cites §2 as the refactor analogue — refactor-scoped workspace isolation under the same one-concern-per-unit granularity).
