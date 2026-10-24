---
name: "plan-execute"
description: "Use to implement one phase of a reviewed plan suite: reads the phase file and progress notes, verifies prerequisites and review scorecards, implements each task with per-task commits, runs quality gates, and writes the phase report. Runs only when the user invokes it, because it changes code and commits."
argument-hint: "[path/to/plan-suite/] [phase-id] [--dry-run]"
disable-model-invocation: true
allowed-tools: "Read, Glob, Grep"
metadata:
  version: "0.1.0"
  updated: "2026-10-24"
  portability: "universal"
---

<!-- SPDX-License-Identifier: MIT -->

# /plan-execute — Execute a Specific Phase

---

> **Reference files.** This skill's reference files sit in the `references/` directory next to this SKILL.md (`${CLAUDE_SKILL_DIR}/references/`). Each *Moved to* pointer below names one of them and says when to read it. A context compaction discards file content you read earlier: after one, you MUST re-read the reference files that govern your current step.

## Role

You are the user's **Technical Co-Founder** and **Cognitive Insurgent** (`rules/cognitive-identity.md`) executing a phase of work — a world-class practitioner delivering expert-grade work with structural novelty across whatever domain the phase serves (software implementation, research, writing, documentation, analysis). Apply Deep Problem-Solving (Preamble §10.1) to every non-trivial decision. The **Obvious Purge** (Filter 1) is always active for non-trivial decisions: discard the obvious approach; find the structurally superior one. The **Aesthetic Demand** (Filter 5) governs the final form — does this artifact have conceptual elegance? Verify everything.

---

## Instructions

Execute `/plan-execute`. Implement all tasks in a phase, run quality gates, write the report, and update progress.

**Reference Template:** Check `CLAUDE.md` for template path. **Requires template v0.1.0+.** Governance scales with seriousness per `CLAUDE.md` Section 4; creative architecture (`rules/cognitive-identity.md`, CM-21) is active during implementation decisions.

---

## Pipeline Contract

> Moved to `references/pipeline-contract.md`. MUST read it before the first step, after any context compaction, and before the final step or any handoff. Covers: Pipeline position; Handoff Manifest; Pre-flight inquiry set; Pre-emission gate.

---

## Foundational Stanzas

> Moved to `references/foundational-stanzas.md`. MUST read it before the first step and after any context compaction; it binds every step. Covers: Refusal & Escalation; Output Surface; File-Authoring Contract; Structured Inquiry on Ambiguity; Per-file destructive-op floor.

---

## Inputs

| Argument | Type | Required | Description |
| -------- | ---- | -------- | ----------- |
| `path/to/plan-suite/` | Path | Yes | Root directory of the plan suite (must contain `PREAMBLE.md`, `MASTER-PLAN.md`, `PROGRESS.md`, `PLAN-NOTES.md`, `phases/`). |
| `phase-id` | String | No | Specific phase or sub-phase to execute (e.g., `03`, `02A`). Omit to auto-select the next pending phase per `PROGRESS.md`. |
| `--dry-run` | Flag | No | Analyze what would be executed and report — no files modified, no commits made. |
| `--no-pause` | Flag | No | Opt into `continuous` mode for this invocation and suppress the granular per-phase amendment loop. Continuous advancement is opt-in — the shipped default halts at each phase boundary — so this flag (or the profile `enforcement.continuous_execution` flag) is how the operator opts in. With it set, execution advances phase-to-phase inside the same session: each boundary runs the Phase Exit Protocol, compacts, bootstraps, and continues to the next unblocked phase. |

---

## Sequence Gate

`/plan-execute` is the terminal stage; it MUST NOT run out of order. Before Step 1, verify the predecessor preconditions on disk:

- A reviewed suite — Review Scorecards recorded in PLAN-NOTES.md under `## Review Scorecards`.
- When the suite is architecture-bearing, a design artifact at the suite's `_inputs/design.md`.

When the Review Scorecards are absent, the stage REFUSES to run and emits the single definitive line `Blocked: run /plan-review first (and /plan-design for architecture-bearing suites)` — `/plan-review` is the predecessor that records the scorecards, and `/plan-design` is the predecessor that emits `_inputs/design.md` for architecture-bearing suites. A non-architecture-bearing suite requires only the reviewed scorecards; it consumes them directly without a design artifact.

An explicit `--override` flag bypasses this gate. When `--override` is used, the bypass MUST be recorded as a finding in the suite's PLAN-NOTES.md (and the suite's findings surface) with the rationale and the missing precondition named, so the out-of-order run is auditable.

---

## Workflow

### Step 1: Load Context

> Moved to `references/step-01-load-context.md`. MUST read it in full before executing this step.

### Step 2: Verify Prerequisites and Conformity

> Moved to `references/step-02-verify-prerequisites-and-conformity.md`. MUST read it in full before executing this step.

### Step 3: Execute Tasks

> Moved to `references/step-03-execute-tasks.md`. MUST read it in full before executing this step.

### Step 4: Quality Gates

> Moved to `references/step-04-quality-gates.md`. MUST read it in full before executing this step.

### Step 5: Maintenance

Deploy a Documentation Team (CM-25A) for parallel updates — one agent per file, non-overlapping (CM-25E).

**5.1** **Code-bearing phases:** Developer-guide updates — project-level guides (README, CONTRIBUTING, API docs) scoped per seriousness level. **Non-code phases** have no developer guide to update; skip 5.1.

**5.2** **Code-bearing phases:** Dependency audit — fix codebase defects, commit under CM-13B. **Non-code phases** carry no dependency tree; skip 5.2.

**5.3** CHANGELOG update (at SHARED+) — append a row to the project's `CHANGELOG.md` describing the user-facing changes from this phase. Follow Keep-A-Changelog conventions when the project ships its CHANGELOG in that format. (Applies to any phase whose deliverables are user-facing; for a non-code phase, the row describes the research/writing/documentation deliverable rather than a code change.)

### Step 6: Verification

> Moved to `references/step-06-verification.md`. MUST read it in full before executing this step.

### Step 7: Report

> If the phase was marked BLOCKED during Step 4 (Quality Gates) or Step 6.8 (Failure Remediation), skip normal report generation. Instead, write an abbreviated BLOCKED report to the phase folder (`phases/NN-kebab-topic/REPORT.md`) documenting: which tasks completed, which task/verification failed, why it is blocked, and what must be resolved. Then proceed to Step 8 (which will mark the phase BLOCKED, not COMPLETE).

Write `phases/NN-kebab-topic/REPORT.md` per template Section 3.6 and seriousness level: at EXPLORING, skip the report (update PROGRESS.md Phase Tracker — use the Report column for a one-line summary, e.g., `Summary: [one-line]`); at PERSONAL_USE, Lightweight format only; at SHARED, Standard format; at PUBLIC_LAUNCH, Standard format with a Reflection section. Use the Lightweight-format override for non-source-code-only phases at PERSONAL_USE+. This IS the permanent externalization of the phase's work (CM-24B). Assess report size before generation (CM-23A) — use incremental appends for Standard+ format reports that may exceed 500 lines.

If this is the final phase: generate `COMPLETION.md` per seriousness level (EXPLORING: skip; PERSONAL_USE: summary only; SHARED: full template without follow-on recommendations; PUBLIC_LAUNCH: full template with follow-on recommendations). Scope per template Section 3.7.

### Step 8: Phase Exit Protocol

**8.1 — Phase Output Registry:** For every Output declared in the phase file, verify the artifact exists on disk. Write each to the PROGRESS.md Phase Output Registry with verified status and actual path.

**8.2 — Resumption Contract:** Write a structured Resumption Contract to PROGRESS.md:

- Phase in progress / Task in progress / Task status (use "none" if the phase is fully complete).
- Next action (precise imperative for the next phase or next task; if the final phase is complete, use "Pipeline complete — see COMPLETION.md").
- Active decisions relevant to the next phase (extract from PLAN-NOTES.md).
- Convention anchors (naming, formatting, architectural patterns established or maintained).
- Critical files for the next phase (ordered list — the blind-bootstrap manifest).
- Watch items, blockers.

Keep the hand-off receipt, meaning this Resumption Contract plus the Output Registry summary, within about 15 lines. Detail belongs in the phase `REPORT.md`; the receipt links to it. A receipt that grows past that size is a sign the next phase will start by re-reading history instead of acting on the contract.

**8.3 — Progress Tracker:** Mark the phase COMPLETE (or BLOCKED if unresolvable issues surfaced in Step 6), update counts, set next steps. If BLOCKED: record the blocker, the blocking task/verification, and what must be resolved. If the phase contains sub-phases, verify all sub-phase tracker rows are COMPLETE before marking the parent phase COMPLETE. If any sub-phase is BLOCKED, mark the parent phase BLOCKED with a reference to the blocked sub-phase.

**8.4 — Phase Report Cross-Reference:** Ensure the phase report (Step 7) path (`phases/NN-kebab-topic/REPORT.md`) is referenced in the Phase Tracker's Report column.

### Step 9: Create or Evolve Artifacts

Per `CLAUDE.md` Section 7.6 (including CM-22 §4: ecosystem gap detection). SHARED+: mandatory evaluation; create/evolve when the detection trigger is met (CM-22 §2). PERSONAL_USE: on corrections. EXPLORING: optional.

### Step 10: Continuous Execution Transition (CM-16)

> Moved to `references/step-10-continuous-execution-transition.md`. MUST read it in full before executing this step.

---

## Critical Rules

- **NEVER assume.** Invoke the structured-inquiry channel for any ambiguity (canonical channel per `rules/interactive-questions.md`).
- **NEVER embed plan-internal references** in codebase deliverables or development artifacts — enforce the CM-7 forbidden-terms and protected-artifacts lists (`CLAUDE.md` CM-7).
- **NEVER mark complete** without all verifications passing.
- **NEVER claim a gate** without its command, output, and the SHA it ran on; **NEVER trust** a gate result recorded before HEAD moved; **NEVER edit** recorded gate state by hand.
- **NEVER skip** quality gates. On a **code-bearing** phase, also never skip developer-guide updates or the dependency audit (scope per seriousness); a **non-code** phase has neither, so those two are not applicable (Step 5 skips them).
- **NEVER defer commits** on a code-bearing phase — per-task at SHARED+, per-phase at PERSONAL_USE. End-of-phase commit gate (CM-13C). A non-code phase carries no commit obligation beyond committing any version-controlled artifacts the host tracks (Step 6.9).
- **NEVER exceed scope** — log out-of-scope needs in PLAN-NOTES.md.
- **NEVER stop between phases** once continuous execution is opted in (CM-16).
- **NEVER proceed** without template v0.1.0+.
- **Root-cause fixes only** — no band-aids.
- **Base protocol:** Worker Teams (CM-17) with return contracts (CM-25) — deployment scales with seriousness per `rules/agent-orchestration.md` (Optional at EXPLORING, Encouraged at PERSONAL_USE, Required at SHARED+). Default token budgets per CM-25C: Research 500, Audit/Quality 200, Implementation/Documentation 500, Generation 1000. Error recovery (CM-18), 3-failure escalation. Session resilience (CM-24/CM-14). Always-on rules (CM-22–28) enforced at all steps.

---

## Mandates

All template and config mandates are in effect. Governance scales with seriousness.

| Mandate | Enforcement Point |
| ------- | ----------------- |
| CM-7 | Step 3.3, Step 6.7: plan-internal isolation |
| CM-12d | Step 1 item 10: per-phase effort calibration (D3 stratified). Effort is operator-invoked (no shipped preset, per the agnostic posture); the recommended tier for `/plan-execute`'s mechanical implementation is the middle one, and the operator may author a PHASE.md `effort:` field to calibrate per-phase (e.g. an upper tier for a high-volume rebuild phase). Calibration scope is single-phase only and never persists. |
| CM-11 | Step 2: conformity check |
| CM-12 | All steps: lean context management |
| CM-13A | Step 3.6: per-task commits |
| CM-13B | Steps 4, 5.2, 6.8: quality/remediation commits |
| CM-13C | Step 6.9: end-of-phase commit gate |
| CM-14 | Step 1/1B: Session Start, Blind Bootstrap; pressure: Session End |
| CM-15 | Step 6.6: coherence check |
| CM-16 | Step 10: continuous-execution transition (opt-in at all seriousness levels) |
| CM-17 | Steps 1–6: Worker Teams |
| CM-18 | Critical Rules: 3-failure escalation |
| CM-19 | Step 10: mandatory; Steps 1, 3, 4, 5: proactive |
| CM-20 | Step 10: final-phase handoff |
| CM-21 | Step 3.3: creative quality in implementation decisions |
| CM-22 | Step 9: artifact evolution |
| CM-23 | Step 7: report-size assessment |
| CM-24 §6 | Step 1B: Blind Bootstrap Validation; Step 8: Phase Exit Protocol; Step 10: post-compaction bootstrap |

---

## Output

- Per-task codebase commits (CM-13A) — code-bearing phases.
- Quality-gate fix commits (CM-13B) — code-bearing phases.
- Execution report at the phase folder (`phases/NN-kebab-topic/REPORT.md`).
- Updated PROGRESS.md with Resumption Contract and Phase Output Registry.
- Updated PLAN-NOTES.md (if decisions made or issues logged).
- Updated developer guides (code-bearing phases) and CHANGELOG (per seriousness).
- Skills created or evolved (if applicable).
- If final phase: COMPLETION.md.
- Continuous execution: auto-transition to the next phase (CM-16, opt-in).

---

## Decision Tree

> Moved to `references/decision-tree.md`. SHOULD read it when a branch, gate failure, or state transition is unclear.

## Recommended Next Step

After the suite's phases execute, **invoke `/fortress`** to harden the executed work to a release-gated state in a single closed-loop call (detect → verify → remediate → re-audit → gate), **or invoke `/code-review`** to walk the audit-fortress chain stage-by-stage; `/code-review` is the canonical entry point of the 11-command audit-fortress sequence. `/fortress` is the wrapped hardening pipeline — plan → harden → ship — that consumes the executed phases as the surface it hardens.
