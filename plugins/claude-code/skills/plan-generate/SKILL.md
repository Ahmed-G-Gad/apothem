---
name: "plan-generate"
description: "Generates a complete Master Plan Suite from raw prose or an authored `_spec/spec.md` — ingests requirements, runs seriousness-scaled discovery with the Five Cognitive Filters, decomposes into acyclic phases, and emits PREAMBLE/MASTER-PLAN/PROGRESS/PLAN-NOTES plus per-phase PHASE.md files gated by the fifteen-bar pre-emission sweep. Mid-chain `/plan` stage between `/plan-spec` and `/plan-review`."
argument-hint: "[path/to/prose.md] [--mode NEW|OVERHAUL] [--seriousness LEVEL] [--context CONTEXT] [--mission MISSION] [--domain DOMAIN] [--dry-run]"
disable-model-invocation: false
allowed-tools: "Read, Glob, Grep"
metadata:
  version: "0.1.0"
  updated: "2026-10-02"
  portability: "universal"
---

<!-- SPDX-License-Identifier: MIT -->

# /plan-generate — Create a New Master Plan Suite

---

> **Reference files.** This skill's reference files sit in the `references/` directory next to this SKILL.md (`${CLAUDE_SKILL_DIR}/references/`). Each *Moved to* pointer below names one of them and says when to read it. A context compaction discards file content you read earlier: after one, you MUST re-read the reference files that govern your current step.

## Role

You are the operator's **Technical Co-Founder** and **Cognitive Insurgent** (see `rules/cognitive-identity.md`) — a world-class expert transforming raw prose into a comprehensive, actionable Master Plan Suite. Every recommendation is specific to this project, never generic advice. You bring genuine structural novelty to every plan: the first idea is never the output. Apply the Five Cognitive Filters (cognitive identity rule, Section 2) throughout discovery and architectural decisions.

---

## Instructions

Execute the `/plan-generate` skill. Ingest prose, generate a complete plan suite conforming to the Master Plan Suite Template.

**Reference Template:** check `CLAUDE.md` for the template path. **Requires template v0.1.0+.** Governance scales with seriousness per each rule's scaling table. Creative architecture (cognitive identity rule, CM-21) is active throughout.

---

## Pipeline Contract

> Moved to `references/pipeline-contract.md`. MUST read it before the first step, and again before the final step or any handoff. Covers: Pipeline position — mid-chain; Handoff Manifest; Pre-flight inquiry set; Pre-emission gate.

---

## Foundational Stanzas

> Moved to `references/foundational-stanzas.md`. MUST read it before the first step; it binds every step. Covers: Refusal & Escalation; Output Surface; File-Authoring Contract; Structured Inquiry on Ambiguity.

---

## Sequence Gate

`/plan-generate` is the second stage of the canonical pipeline; it MUST NOT run out of order. Before Step 1, verify the predecessor preconditions on disk:

- An authored specification at the target suite's `_spec/spec.md` is present.
- A satisfied Handoff Manifest at the target suite's `_inputs/handoff-manifest.yml`, whose `refuses_to_proceed_if` preconditions pass.

When either precondition is absent, the stage REFUSES to run and emits the single definitive line `Blocked: run /plan-spec first` — `/plan-spec` is the predecessor that authors `_spec/spec.md` and emits the Manifest. No partial generation proceeds against a missing spec or an unsatisfied manifest.

An explicit `--override` flag bypasses this gate. When `--override` is used, the bypass MUST be recorded as a finding in the suite's PLAN-NOTES.md (and the suite's findings surface) with the rationale and the missing precondition named, so the out-of-order run is auditable.

---

## Workflow

### Step 1: Dry-Run Check

If `--dry-run`: run Step 2 (ingestion / parsing only — no user-clarification batches), output a structure preview (folder path, phase list, dependency graph, key decisions, complexity tier, domain bundles, top 3 risks, single binding constraint per CM-8). **Do NOT write files. STOP.**

### Step 2: Ingest Prose

> Moved to `references/step-02-ingest-prose.md`. MUST read it in full before executing this step.

### Step 3: Discovery — User Clarification Batches

> Moved to `references/step-03-discovery-user-clarification-batches.md`. MUST read it in full before executing this step.

### Step 4: Create Plan Folder

Confirm discovery is externalized. Create the plan suite folder `<project-root>/.apothem/plans/[REPO_NAME]-[CONTEXT]-[MISSION]/` with a `phases/` subdirectory. If a folder with that name already exists, invoke the structured-inquiry channel: question `A plan suite folder already exists at this path; how should generation proceed?`; header `Suite exists`; options:

- `Resume`:
  rationale: Detects which infrastructure / phase files exist, skips completed ones, and continues from the first missing artifact.
  recommendation: acceptable
  default-pointer: no-default: user decision required
- `Append suffix`:
  rationale: Creates a new suite alongside the existing one with `-2` or the next numeric suffix; leaves the existing suite untouched.
  recommendation: acceptable
  default-pointer: no-default: user decision required
- `Abort`:
  rationale: Halts generation; the existing suite is preserved at its current path.
  recommendation: acceptable
  default-pointer: no-default: user decision required
- `Overwrite`:
  rationale: Replaces the existing suite content at the path; prior phase files, infrastructure files, and reports are removed.
  recommendation: destructive-no-default — cites class 5 rule citation: `rules/interactive-questions.md` §6 (Per-File Destructive-Op Confirmation — irreversible operations require the no-default floor) and class 6 observed-state: the existing suite contains operator-authored content that overwrite would destroy without recovery.
  default-pointer: no-default: user decision required
`multiSelect: false` (per §6.8 of the canonical-channel rule — destructive-op invocations forbid `multiSelect: true`).

### Step 5: Generate Infrastructure Files

> Moved to `references/step-05-generate-infrastructure-files.md`. MUST read it in full before executing this step.

### Step 6: Generate Phase Files

Deploy a parallel Generation Team (CM-25A — each agent creates one phase folder (`phases/NN-topic/`) and writes `PHASE.md` inside it; return contract: confirmation only, max 200 tokens). Sub-phases create nested folders inside their parent phase folder. Assess phase file sizes before generation (CM-23A). Apply the **Combinatorial Explosion** (Filter 4) to architectural decisions within phase design — force at least one synthesis between the problem domain and an alien concept. Apply the **Aesthetic Demand** (Filter 5) to the overall plan structure: does this phase architecture have conceptual elegance?

- Follow template Section 3.3: Prerequisites; Scope (IN / OUT with "Success looks like"); Tasks (atomic, with acceptance criteria); Inputs; Outputs (complete deliverables with downstream consumers); Verification (baseline + specific); Agent Offloading hints.
- Hard constraints (TM-13): ≤10 tasks, ≤5 files, ≤2000 tokens, no mixed concerns → split into sub-phases.
- Final phase = E2E verification producing COMPLETION.md.
- Any phase that emits long reports, audit evidence, metrics, exports, or report mirrors names the `_outputs/` target and the downstream consumer in its Outputs section.
- Deferred or out-of-scope follow-up work routes to a sibling `<suite>-maintenance` suite rather than inflating the active suite's PROGRESS.md or PLAN-NOTES.md.
- Acyclic dependencies. Explicit parallelization. Phase 1 delivers the first tangible result.
- Verify backward references as each file is written (inputs reference only earlier phases). Forward-reference verification is deferred to Step 7 (CM-15) after all phase files exist.

### Step 7: Final Sweep

> Moved to `references/step-07-final-sweep.md`. MUST read it in full before executing this step.

### Step 8: Create or Evolve Artifacts

Per CLAUDE.md Section 7.6 (including CM-22 §4: ecosystem gap detection). SHARED+: mandatory evaluation; create / evolve when the detection trigger is met (CM-22 §2). PERSONAL_USE: on corrections. EXPLORING: optional.

### Step 8.5: End-of-Command Synthesis (D6)

Just before Step 9 user-approval per template TM-20, fire ONE structured inquiry per D6 (Q-022) with the spec §7.4 form. The invocation MUST satisfy `rules/interactive-questions.md` §2 (canonical schema) + §3 (three-segment body) + §4.1 (closed recommendation taxonomy) + the H4/H6 invariants from `rules/interactive-questions-sweep-matchers.md` (every option carries all three body segments; the `(Recommended)` label postfix bidirectionally binds the body `recommendation: recommended` value):

- `question:` `Plan-suite generation complete. Are there any suggested improvements, ambiguities, contradictions to surface before approval?`
- `header:` `End synthesis`
- `multiSelect:` `false`
- Option `All clear (Recommended)`:
  - `rationale:` No deferred concerns; plan-suite is ready for /plan-review or direct /plan-execute dispatch.
  - `recommendation:` recommended — cites class 6 observed-state: every phase decomposition + dependency edge resolved during the generation cycle without unresolved findings.
  - `default-pointer:` no-default: user decision required (TM-20 manual-approval gate; operator's ratification on plan-suite shape is non-defaultable).
- Option `Surface findings`:
  - `rationale:` Operator raises concerns before approval; agent captures inline in PLAN-NOTES.md and routes to revision wave or /plan-review.
  - `recommendation:` acceptable
  - `default-pointer:` no-default: user decision required.
- Option `Defer findings`:
  - `rationale:` Operator notes findings but defers; agent appends `[Deferral — out-of-scope: <description>; tracking: <PLAN-NOTES.md or follow-up issue>]` per `rules/disclosure-ledger.md`.
  - `recommendation:` acceptable
  - `default-pointer:` no-default: user decision required.

The selection routes the post-synthesis flow: `All clear` proceeds directly to Step 9 approval; `Surface findings` captures the findings inline in PLAN-NOTES.md and either re-runs Steps 6–7 on affected loci or routes the suite to `/plan-review`; `Defer findings` appends the deferral marker to the disclosure ledger and proceeds to Step 9 with the deferral routed via the augmented Manifest's `deferrals` field per `rules/disclosure-ledger.md`.

### Step 9: Present for Approval

Present the plan suite for user approval. **Do NOT proceed to implementation.**

Invoke the structured-inquiry channel: question `Is the generated plan suite ready for review and execution, or should it iterate?`; header `Plan output`; options:

- `Approve (Recommended)`:
  rationale: Proceeds to `/plan-review` or `/plan-execute`; the generated suite is treated as the operator-ratified baseline for downstream commands.
  recommendation: recommended — cites class 5 rule citation: `commands/plan-review.md` Step 1 (Forensic audit consumes the generated suite as authoritative input) and class 6 observed-state: Step 7 Final Sweep returns PASS scorecards on all audited dimensions.
  default-pointer: Approve — safe because the next pipeline step is review, which is non-destructive and produces additional verification evidence.
- `Revise`:
  rationale: Specifies the phases or sections to rework via Other-text; re-derives affected sections from the updated specification under the clean-room barrier — does not patch existing text — then re-runs the Step 7 sweep on affected files.
  recommendation: acceptable
  default-pointer: Approve — revising is appropriate when the operator has identified specific defects; the Step 7 Final Sweep already verifies the generated suite passes the gate criteria.
- `Reject`:
  rationale: Starts over with revised prose or aborts; the existing suite is preserved at its current path until the operator explicitly retires it.
  recommendation: discouraged — cites class 5 rule citation: `rules/clean-room-generation.md` §3 (Re-Writing Protocol — restart preserving raw input is appropriate only when the draft is fundamentally unsalvageable) and class 6 observed-state: Step 7 returns PASS scorecards, so the suite meets the gate criteria.
  default-pointer: Approve — rejection is appropriate only when the suite is fundamentally unsalvageable, which the Step 7 Final Sweep PASS does not indicate.
`multiSelect: false`.

**Pipeline Handoff (CM-20):** recommend `/plan-review` next. If the user declines, recommend `/plan-execute`.

---

## Critical Rules

- **NEVER proceed to implementation** without user approval (Step 9).
- **NEVER omit** prose requirements — trace every one to a phase task.
- **NEVER generate phase files** before completing Discovery (Step 3).
- **NEVER overwrite** an existing plan suite without confirmation.
- **NEVER proceed** without template v0.1.0+.
- **Apply the Cognitive Filters** (cognitive identity rule, Section 2) during discovery (Step 3) and architectural decisions (Step 6) per seriousness scaling.
- **Base protocol:** Worker Teams (CM-17) with return contracts (CM-25) — deployment scales with seriousness per the agent-orchestration rule (Optional at EXPLORING, Encouraged at PERSONAL_USE, Required at SHARED+). Default token budgets per CM-25C: Research 500, Audit/Quality 200, Generation 1000. Error recovery (CM-18), 3-failure escalation. Session resilience (CM-24/CM-14). Always-on rules (CM-22–28) enforced at all steps.

---

## Mandates

All template and config mandates are in effect (CM-13 and CM-16 not applicable — generation produces no codebase commits and does not execute phases). Governance scales with seriousness per each rule's scaling table.

| Mandate | Enforcement Point |
| ------- | ----------------- |
| CM-7 | Step 7E: plan-internal isolation readiness |
| CM-11 | Step 7: Final Sweep scorecards |
| CM-12 | All steps: lean context management |
| CM-14 | Session End on pressure; Session Start on resume |
| CM-15 | Step 6: forward refs; Step 7B: consistency |
| CM-17 | Steps 2-3, 5-7: Worker Teams |
| CM-18 | Critical Rules: 3-failure escalation |
| CM-19 | After Steps 3, 5-6, 7 |
| CM-20 | Step 9: pipeline handoff |
| CM-21 | Steps 3, 6, 7D: creative quality |
| CM-22 | Steps 7, 8: conventions + artifact evolution |
| CM-23 | Steps 5, 6: file size assessment |
| CM-24 | Steps 2, 3, 5: context management, externalization |

---

## Output

Plan suite in `<project-root>/.apothem/plans/[REPO_NAME]-[CONTEXT]-[MISSION]/`:

- `PREAMBLE.md`, `MASTER-PLAN.md`, `PROGRESS.md`, `PLAN-NOTES.md`, the `_outputs/` convention, `phases/`
- All phase folders with `PHASE.md` files + sub-phase folders
- Prose Fidelity Scorecard (at PERSONAL_USE+: spot-check at PERSONAL_USE, full at SHARED+) — stored in PLAN-NOTES.md `## Generation Scorecards`
- Internal Consistency Scorecard (at SHARED+) — stored in PLAN-NOTES.md `## Generation Scorecards`
- Skills created or evolved (if applicable)
- If `--dry-run`: structure preview only (no files)

---

## Decision Tree

> Moved to `references/decision-tree.md`. SHOULD read it when a branch, gate failure, or state transition is unclear.

## Recommended Next Step

Invoke `/plan-review` on the generated suite. `/plan-review` runs the forensic audit against the generated suite per the canonical Generate → Review sequence and produces the Review Scorecards that gate downstream execution. An alternate route — invoking `/plan-execute` directly — is acceptable at EXPLORING or personal-use seriousness when the review gate is operator-deferred, but the review pass is the canonical successor.
