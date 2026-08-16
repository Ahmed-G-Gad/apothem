---
name: "plan-amend"
version: "0.1.0"
updated: "2026-06-22"
description: "Amends, extends, refines, reverts, or weaves an existing plan suite without destroying prior resolved decisions — re-derives only the affected downstream artifacts (spec, master-plan, phases, notes), preserves the PLAN-NOTES.md decision ledger as authoritative and append-only, and routes every ambiguity through the structured-inquiry channel rather than inventing scope, identity, or decisions. The re-entrant `/plan` stage that revisits a converged-or-in-progress suite at any point in the spec → generate → review → execute chain."
argument-hint: "[amend|extend|refine|revert|weave] [suite-path] [--dry-run]"
disable-model-invocation: false
portability: "universal"
allowed-tools: "*"
---

<!-- SPDX-License-Identifier: MIT -->

# /plan-amend — Amend an Existing Plan Suite

## Role

You are the steward of an existing plan suite. Where `/plan-generate` produces a suite from scratch and `/plan-review` audits one, `/plan-amend` **modifies one in place** — applying a requested amendment mode while preserving every prior resolved decision. It loads the existing suite, treats the PLAN-NOTES.md decision ledger as authoritative and append-only, applies the amendment, and re-derives **only** the downstream artifacts the amendment actually touches. It never re-derives the whole suite, never overwrites a resolved decision, and never invents scope, identity, or decisions the operator has not supplied.

## Pipeline Contract

**Pipeline position.** **Wrapping / orthogonal.** `/plan-amend` operates on a suite that already exists at any stage of the canonical sequence `/plan-spec → /plan-generate → /plan-review → /plan-design (CONDITIONAL — architecture-bearing suites only) → /plan-execute`. Invocable at any point once a suite exists; it inspects the suite's current stage and re-derives only the affected downstream artifacts. It never executes phase implementation work — it leaves the amended suite ready for re-review.

**Consumed.** The target suite's `_spec/spec.md`, `_inputs/handoff-manifest.yml`, infrastructure files (PREAMBLE.md, MASTER-PLAN.md, PROGRESS.md, PLAN-NOTES.md), `phases/**/PHASE.md`, and any existing phase reports. The PLAN-NOTES.md decision ledger is the authoritative record of prior resolved decisions and is read first.

**Emitted.** The re-derived subset of downstream artifacts the amendment touches (spec, master-plan, phase files, notes); an appended PLAN-NOTES.md decision-ledger entry recording the amendment mode, the affected artifacts, and the rationale; and an updated handoff manifest reflecting the amended suite shape. Artifacts the amendment does not touch are left byte-unchanged.

## Sequence Gate

`/plan-amend` modifies an existing suite; it MUST NOT run without a suite to amend. Before Step 1, verify the predecessor precondition on disk:

- An existing plan suite is present at the target path — PREAMBLE.md, MASTER-PLAN.md, PROGRESS.md, PLAN-NOTES.md, and the per-phase folders under `phases/`.

When no suite exists at the target path, the stage REFUSES to run and emits the single definitive line `Blocked: run /plan-generate first` — `/plan-generate` is the predecessor that produces the suite this command amends. There is nothing to amend until a suite exists.

An explicit `--override` flag bypasses this gate. When `--override` is used, the bypass MUST be recorded as a finding in the suite's PLAN-NOTES.md (and the suite's findings surface) with the rationale and the missing precondition named, so the out-of-order run is auditable.

## Amendment Modes

| Mode | Effect | Re-derivation scope |
| ---- | ------ | ------------------- |
| **amend** | Modifies an existing surface in place (a phase task, an acceptance criterion, a scope boundary). | The touched phase file(s) plus any downstream artifact that cites the modified surface. |
| **extend** | Adds a new surface (a new phase, task, or output) without altering existing ones. | The new artifact(s) plus the index surfaces that register it (MASTER-PLAN.md phase index, PROGRESS.md tracker). |
| **refine** | Improves an existing surface's quality (clearer prose, tighter acceptance criteria) without changing its contract. | The touched surface only; downstream artifacts unchanged because the contract holds. |
| **revert** | Removes a prior amendment, restoring an earlier ratified state. | The reverted artifact(s) plus the downstream artifacts that depended on the reverted surface; the decision ledger records the revert rather than erasing the prior entry. |
| **weave** | Integrates a cross-cutting change across multiple existing surfaces coherently. | Every surface the cross-cutting change touches, re-derived together so they stay mutually consistent. |

## Workflow

### Step 1: Resolve Target and Mode

Resolve the suite from the positional argument. If absent, choose the most recently modified suite under the host project's `.apothem/plans/` directory and state that resolution explicitly. Resolve the amendment mode from the positional `[amend|extend|refine|revert|weave]` argument; when the mode is absent or ambiguous, surface the choice through the structured-inquiry channel per `rules/interactive-questions.md` with the three-segment option annotation — never silently pick a mode. `--dry-run` reports the detected suite, the resolved mode, the planned amendment scope, and the would-write targets, then stops without file writes.

### Step 2: Load the Existing Suite

Read the suite in full — the spec, the infrastructure files, every `phases/**/PHASE.md`, and the PLAN-NOTES.md decision ledger. The decision ledger is read first and treated as the authoritative record of prior resolved decisions. Build a registry of the suite's current surfaces (phases, outputs, decisions, dependency edges) so the amendment's blast radius is known before any write.

### Step 3: Preserve Prior Resolved Decisions

The PLAN-NOTES.md decision ledger is authoritative and append-only; prior resolved decisions are NEVER silently overwritten. When an amendment would contradict a prior resolved decision, the contradiction surfaces through the structured-inquiry channel per `rules/interactive-questions.md` — the operator ratifies the change, and the ledger records the new decision as an appended entry that supersedes the prior one (the prior entry remains in the ledger as the audit trail). A `revert` mode appends a revert entry rather than deleting the original decision row.

### Step 4: Apply the Amendment Mode

Apply the resolved mode per the Amendment Modes table. Each applied change is scoped to the surfaces the mode names — the amendment touches the smallest surface that achieves the requested change. Changed prose is re-derived from the amended specification under the clean-room barrier per `rules/clean-room-generation.md` §3, not patched cosmetically. Surfaces the amendment does not touch are left byte-unchanged.

### Step 5: Re-Derive Only the Affected Downstream Artifacts

Trace the amendment's blast radius from Step 2's registry. Re-derive only the downstream artifacts the amendment actually affects — the spec when the amendment changes a requirement, MASTER-PLAN.md when it changes the phase index or dependency graph, the touched phase files, and PLAN-NOTES.md to append the decision-ledger entry. Re-deriving the whole suite when only a subset is affected is a defect. Verify that every re-derived artifact stays mutually consistent with the surfaces the amendment left unchanged.

### Step 6: Route Every Ambiguity Through Structured Inquiry

Every ambiguity — scope direction, identity, naming, an undeclared decision, a contradiction with a prior resolved decision — routes through the structured-inquiry channel per `rules/interactive-questions.md` (canonical channel; three-segment option annotation; never free-form prose as primary input). The command NEVER invents scope, identity, or decisions. Required-category gaps block the amendment until the operator resolves them; optional-category gaps fall back to the recommended option and record the fallback as a finding in PLAN-NOTES.md.

### Step 7: Persist and Attest

Write the re-derived subset of artifacts. Append the decision-ledger entry to PLAN-NOTES.md recording the amendment mode, the affected artifacts, and the rationale. Update the handoff manifest and PROGRESS.md Phase Output Registry to reflect the amended suite shape. The amended suite is left ready for re-review; the command emits no codebase commits and does not execute phases.

## Disciplines

- **Decision-ledger preservation:** PLAN-NOTES.md is authoritative and append-only; prior resolved decisions are never silently overwritten.
- **Minimal re-derivation:** only the affected downstream artifacts are re-derived; untouched surfaces stay byte-unchanged.
- **No invention:** every ambiguity routes through structured inquiry; scope, identity, and decisions are never fabricated.
- **Clean-room re-derivation:** changed prose is re-derived from the amended specification, not patched cosmetically.
- **Anti-inflation:** the decision ledger appends; it does not accumulate long chronological narrative that belongs in REPORT.md or `_outputs/`.
- **Human-only authorship:** any git surface uses human authorship, conventional commits, and no AI attribution.

## Verification Recipe

1. `rg -nP '^name: "plan-amend"$' src/apothem/commands/plan-amend.md` returns one hit.
2. On a suite with a prior resolved decision, an `amend` run re-derives only the touched phase file and appends — never overwrites — the decision ledger.
3. On a suite missing PROGRESS.md, the Sequence Gate emits `Blocked: run /plan-generate first` and writes nothing unless `--override` is supplied (recorded as a finding).
4. `/plan-review` consumes the amended suite and re-audits it before any downstream execution.

## Recommended Next Step

**Invoke `/plan-review` on the amended suite.** `/plan-review` re-audits the amended suite from scratch under the Blind Review Mandate, confirming the amendment introduced no regression before any downstream execution — it is the canonical successor to every amendment.

## Bindings (§0.j five-direction)

- **Drives →** ● The re-derived subset of downstream artifacts (spec, master-plan, phase files, notes). ● The appended PLAN-NOTES.md decision-ledger entry recording each amendment. ● The updated handoff manifest reflecting the amended suite shape. ● The re-review verdict consumed by `/plan-review`.
- **Satisfies →** ● The plan-suite amendment discipline — modifying a suite in place without destroying prior resolved decisions and re-deriving only the affected downstream artifacts. ● `rules/clean-room-generation.md` §3 by re-deriving changed prose from the amended specification under the clean-room barrier.
- **Established by ↑** ● The `/plan` stage cohort. ● `rules/context-management-scratch.md` `_inputs/` / `_outputs/` suite-locality convention. ● `rules/interactive-questions.md` (the canonical channel every ambiguity routes through).
- **Gated by ←** ● An existing plan suite at the target path. ● `rules/interactive-questions.md` for every ambiguity and every contradiction with a prior resolved decision. ● The append-only decision-ledger invariant at Step 3.
- **Cross-bound with ↔** ↔ `commands/plan-generate.md` (generate produces the suite this command amends). ↔ `commands/plan-spec.md` (spec amendments re-derive the suite's `_spec/spec.md`). ↔ `commands/plan-review.md` (review re-audits the amended suite). ↔ `commands/plan-design.md` (design re-runs when an amendment touches an architecture-bearing surface). ↔ `commands/plan-audit.md` (audit wraps amendment findings into a closed remediation loop). ↔ `commands/plan-execute.md` (execute consumes the amended suite after re-review). ↔ `commands/plan-status.md` (read-only sibling reports the amended suite state). ↔ `rules/clean-room-generation.md`, `rules/interactive-questions.md`, and `rules/context-management-scratch.md` (re-derivation discipline, inquiry channel, and output placement).
