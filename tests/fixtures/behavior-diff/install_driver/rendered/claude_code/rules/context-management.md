---
name: "context-management"
description: "Systematic context management under the blind-execution invariant — every turn must be executable by a fresh session with zero prior history, so all state lives in durable files and active context is acceleration, not storage. Covers context-rot monitoring, proactive externalization, compaction discipline, opt-in continuous single-session execution, and context-budget calibration. Implements CM-12 / CM-14 / CM-18 / CM-19 / CM-24."
pathFilter: ""
alwaysApply: true
---

<!-- SPDX-License-Identifier: MIT -->

# Rule: Context Management and Conversation-Independent Execution

## Purpose

Manage context systematically: mitigate context rot, preserve state across compaction and session boundaries, favor continuous single-session execution when the phase graph can advance, and guarantee every plan phase is executable in a fresh session with zero prior history. **Invariant: if every turn were the first turn of a new session, no information would be lost and no action would be incorrect.**

## Obligations

### 1. Context Health Monitoring

Continuously monitor five signals: **token pressure** (latency, truncation, compression warnings), **recall degradation** (re-reading to recover earlier decisions), **repetition** (re-asking, re-discovering), **drift** (naming / convention inconsistencies, contradictions), **staleness** (outdated file-state references).

### 2. Proactive Externalization Protocol (Companion Sub-Rule Anchor)

Externalize critical state to durable files before it can decay; conversation history is never the sole record. (Companion Sub-Rule Anchor) See rules/context-management-protocol.md §1 for externalize-on-decide, on-accumulate, before-compact, on-complexity, and on-phase-exit sub-clauses.

**2.6 — Scratch File Conventions and Plan-Workflow Directories (Companion Sub-Rule Anchor):** The plan-workflow directory convention — file-naming inside `<project-root>/.apothem/plans/{suite}/_inputs/`, the `_spec/` authored-spec surface, the `_outputs/` durable emission surface, the closed-purpose vocabularies, the forge→spec promotion lifecycle, the suite-locality invariant, and the directional-promotion rule — lives at the path-filtered companion rule [`rules/context-management-scratch.md`](./context-management-scratch.md), demand-loaded when the assistant edits any per-suite plan artifact under `<project-root>/.apothem/plans/**` (or the legacy `.plans/**`), `_inputs/**`, `_outputs/**`, or `_spec/**`.

### 3. Compaction Discipline (CM-19) (Companion Sub-Rule Anchor)

Compaction is the primary defense against context rot — trigger proactively per the cataloged boundaries; post-compaction restoration runs the Blind Bootstrap Sequence. A dispatch-routed `PostToolUse` hook makes the size-based triggers mechanical: it measures the context size from the session transcript and surfaces a save-state advisory at half the window and again at three quarters (advisory-only, never blocks, fail-open). (Companion Sub-Rule Anchor) See rules/context-management-protocol.md §2 for the full trigger catalog and the proactive-advisory hook.

### 4. Long Conversation Resilience (Companion Sub-Rule Anchor)

Long conversations apply periodic snapshots, progressive summarization, convention anchoring, regression detection, and concurrent-modification awareness. (Companion Sub-Rule Anchor) See rules/context-management-protocol.md §3.

### 4A. Continuous Single-Session Execution (CM-16) (Companion Sub-Rule Anchor)

Full-suite plan execution halts at each phase boundary by default; continuous advancement is opt-in per `agnostic-posture.md` (the operator sets the profile `enforcement.continuous_execution` flag, passes `--no-pause`, or requests it). Once opted in, the boundary sequence is: complete the phase, externalize the Phase Exit Protocol, compact, run the Blind Bootstrap Sequence, advance to the next unblocked phase. Execution still halts on explicit single-phase invocations, BLOCKED phases, final-suite completion, or unreconciled context-rot / regression signals after one externalize→compact→bootstrap recovery cycle. (Companion Sub-Rule Anchor) See rules/context-management-protocol.md §3.6.

### 5. Graceful Degradation (Companion Sub-Rule Anchor)

Under critical context pressure, externalize-then-complete-then-record-then-compact; silent quality degradation, unmarked partials, and undocumented state loss are forbidden. (Companion Sub-Rule Anchor) See rules/context-management-protocol.md §4.

### 6. Blind Execution Protocol — Invariant (Companion Sub-Rule Anchor)

Every phase must be executable by a fresh session with zero conversation history. **The Invariant:** all state lives in durable files; active context is ephemeral acceleration, not storage. (Companion Sub-Rule Anchor) See rules/context-management-protocol.md §5 for the Blind Bootstrap Sequence, Output Validation Gate, Convention Recovery, and State File Validation procedures.

### 7. Context Budget Discipline (Companion Sub-Rule Anchor)

Budget awareness, demand loading, pressure-signal thresholds (>3 large reads, >500 lines emitted, recall-degradation), and per-task effort calibration (CM-12d — operator-invoked per the agnostic posture, with the D3 stratified taxonomy supplying the recommended tier; per-phase calibration at `phases/NN-topic/PHASE.md`; single-phase scope; PROGRESS.md Resumption Contract recording). (Companion Sub-Rule Anchor) See rules/context-management-budget.md §7 for §7.1 / §7.2 / §7.3 / §7.4 operational bodies.

### 8. Error Classification (CM-18) (Companion Sub-Rule Anchor)

Six error classes (Parse / Resolution / Validation / Generation / External / State) structure recovery; escalate to user after 3 cumulative failures across any class. (Companion Sub-Rule Anchor) See rules/context-management-protocol.md §6 for the trigger / recovery-strategy table.

## Seriousness Scaling

| Level | Context Management Behavior |
| ----- | --------------------------- |
| EXPLORING | Basic externalize-on-decide; compact between phases (§3 detailed triggers from PERSONAL_USE+); Blind Bootstrap at session start; budget awareness (§7.1); no periodic snapshots |
| PERSONAL_USE | Full externalization (§2); compact per §3; budget discipline (§7); periodic snapshots every 20 tool calls; Blind Bootstrap + Phase Exit Protocol active |
| SHARED | Add long-conversation resilience (§4); Resumption-Contract convention anchoring; regression detection; graceful degradation (§5); full Blind Execution Protocol (§6) including Output Validation Gate; budget discipline enforced |
| PUBLIC_LAUNCH | Aggressive compaction; snapshots every 15 tool calls; externalization failures block continuation; Output Validation Gate failures block execution (no override); budget discipline strictly enforced |

## Anti-Patterns

- **DON'T** rely on active context as sole record — **BECAUSE** it will be compressed or lost.
- **DON'T** defer or batch externalization — **BECAUSE** "later" may be after compaction or session end.
- **DON'T** ignore recall-degradation signals — **BECAUSE** continuing compounds the error.
- **DON'T** hold more than 5 active threads without externalization — **BECAUSE** overflow is structural.
- **DON'T** skip Phase Exit Protocol — **BECAUSE** it breaks the Blind Execution Invariant.
- **DON'T** re-read full sources when Resumption Contract snapshots suffice — **BECAUSE** it inflates context.
- **DON'T** redispatch a full-suite execution merely because a phase boundary was reached — **BECAUSE** continuous mode already externalizes, compacts, bootstraps, and proceeds.

## Enforcement

Always-on at every seriousness level, scaling per the table. Implements CM-12 / CM-14 / CM-18 / CM-19 / CM-24. CM-14 session-start (Blind Bootstrap) and session-end (Phase Exit) are owned here; session-end memory evaluation delegates to CM-26 and artifact evolution delegates to CM-22, coordinated by the Stop hook.
