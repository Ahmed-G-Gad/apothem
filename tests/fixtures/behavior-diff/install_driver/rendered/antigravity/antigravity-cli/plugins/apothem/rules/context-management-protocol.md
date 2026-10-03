---
trigger: glob
description: "Path-filtered companion rule carrying the detailed externalization sub-clauses, compaction-trigger catalog, long-conversation resilience procedures, graceful-degradation priorities, blind-execution protocol full body, and error-classification table declared at the parent `context-management.md` rule's §2/§3/§4/§5/§6/§8 anchors; demand-loaded on plan-workflow entry."
globs: "**/.apothem/plans/**, **/.plans/**, **/PROGRESS.md, **/PLAN-NOTES.md, **/PHASE.md, **/MASTER-PLAN.md, **/REPORT.md, **/PREAMBLE.md"
---

<!-- SPDX-License-Identifier: MIT -->

# Rule: Context Management Protocol (Companion Sub-Rule)

## Purpose

Carry the operational depth for the parent rule's externalization, compaction, long-conversation resilience, graceful-degradation, blind-execution, and error-classification surfaces. Demand-loads on any plan-suite artifact (PROGRESS.md, PLAN-NOTES.md, PHASE.md, MASTER-PLAN.md, REPORT.md, PREAMBLE.md, or anything under `<project-root>/.apothem/plans/**`). The parent owns the context-health signals, externalization invariant, compaction-trigger summary, blind-execution invariant, and context-budget summary; this companion owns the full operational specifications below.

## Obligations

### 1. Proactive Externalization Protocol — Detailed Sub-Clauses

Externalize critical state to durable files before it can decay:

**1.1 — Externalize-On-Decide:** Every significant decision, resolution, or discovery must be written to a durable file (PLAN-NOTES.md, PROGRESS.md, memory files, or scratch files) within the same turn it is made. Conversation history is never the sole record.

**1.2 — Externalize-On-Accumulate:** When more than 3 related facts accumulate in conversation without being written to a file, externalize immediately.

**1.3 — Externalize-Before-Compact:** Before any `/compact` (the harness's built-in context-compression command — invoked manually by the user or fired automatically by a CM-19 trigger) or any other context compression:

- Write all unexternalized state to appropriate files.
- Update PROGRESS.md Resumption Contract with current task state.
- Update PLAN-NOTES.md with any pending decisions.
- Verify no critical state exists only in active context.

**1.4 — Externalize-On-Complexity:** When a conversation involves more than 5 distinct topics, files, or decision threads, create a scratch summary file. Delete when its purpose is complete.

**1.5 — Externalize-On-Phase-Exit:** At the end of every phase, write structured state to PROGRESS.md:

- **Phase Output Registry:** For every declared output, verify existence on disk and record verified status and actual path.
- **Resumption Contract:** Structured fields — phase/task status, next action (precise imperative), active decisions, convention anchors, critical files manifest for next phase, watch items, blockers.
- **Convention Anchors:** Key naming, formatting, and architectural conventions — a full snapshot so the next session adopts them without re-deriving.
- **Critical Files Manifest:** Ordered list of exact file paths the next session must read.

### 2. Compaction Discipline — Detailed Trigger Catalog

Compaction is the primary defense against context rot. Trigger proactively (scope per the parent rule's Seriousness Scaling table — EXPLORING applies phase-boundary triggers only; PERSONAL_USE+ applies all detailed triggers):

- **After every phase completion** (mandatory — execute Phase Exit Protocol first).
- **Between phases** during continuous execution (mandatory at PERSONAL_USE+).
- **Between sub-phases** within a parent phase (mandatory at PERSONAL_USE+ — lighter externalization: update Resumption Contract task pointer only, skip full Phase Exit Protocol).
- **After heavy reads** (3+ files exceeding 150 lines each in sequence, or cumulative read volume exceeding 500 lines without externalization).
- **After substantial output** (generating 500+ lines of content) — `OBSERVED-2026-04-26` against the audit's emission-volume sample (1,106-line and 706-line phase REPORTs both exceeded the threshold and triggered incremental-append per CM-23); register row at `scripts/dev/per-claim-register.md`. Falsifier: a sample emission below 500 lines that consistently fails to trigger context pressure invalidates the threshold.
- **After error recovery** (failed attempts consume context without producing value).
- **After ~18 tool calls** (tool results accumulate faster than their value persists) — `RATIONALE-2026-04-26`: tool-result accumulation rate observed across the audit's sub-phase emissions (~22 tool calls per sub-phase before compaction-after-large-output triggered; "~18" sits at the lower-quartile of that distribution as a defensive margin); register row at `scripts/dev/per-claim-register.md`. Falsifier: a controlled measurement showing post-18-call results retain reusable value with negligible accumulation cost invalidates the trigger.
- **After multi-agent results** (any wave of 3+ agents — post-wave compaction is the norm, not exceptional, since 3+ matches the deployment threshold in `rules/agent-orchestration.md` §2.1; OR cumulative agent results exceeding 2000 tokens across waves without compaction). Post-wave compaction may be deferred only when the immediate next action requires the raw agent results in active context (rare — synthesize first, then compact).
- **When recall degrades** (unable to reference earlier content without re-reading).

**Post-compaction restoration** — execute Blind Bootstrap Sequence (§4.2 below).

**Mechanical operationalization (proactive-compaction advisory).** The two
size-based triggers above — the "~18 tool calls" trigger and the "500-line
emission" / heavy-read band — are no longer agent-discipline only: a
dispatch-routed `PostToolUse` hook (`hooks/proactive_compaction_tracker.py`,
wired all-tools via the empty matcher) maintains lightweight per-session
counters keyed off the hook stdin `session_id` and surfaces a concise
proactive-compaction advisory once a threshold crosses, then resets the
counters (anti-spam back-off), at most twice per session. This makes the
existing CM-19 triggers *mechanical* rather than introducing a competing policy:
the advisory asks for the same externalization this section already mandates
and suggests compaction to the operator, and the hook itself never blocks (a `PostToolUse` hook fires after the tool ran). The
two thresholds default to the catalog values (18 tool calls; ~20 KB cumulative
output ≈ the 500-line emission band) and are each overridable by an environment
variable — `APOTHEM_PROACTIVE_COMPACTION_TOOL_THRESHOLD` and
`APOTHEM_PROACTIVE_COMPACTION_OUTPUT_THRESHOLD`; a non-positive or unparseable
override falls back to the default so a typo can never silently disable the
tracker; `APOTHEM_PROACTIVE_COMPACTION_ENABLED=0` disables it explicitly.
The hook is advisory-on but low-noise (silent below threshold), fast (a single
small counter-file read + write), and fail-open (any error emits nothing).
Per-session state lives in a per-user `0700` state directory, never in the
repository tree. The hook complements `PreCompact`/`PostCompact` (which fire
only once compaction is already underway; where a harness discards their
output, the recovery context arrives with the post-compaction SessionStart event
instead) by advising
*before* context fills.

### 3. Long Conversation Resilience

For conversations exceeding ~50 tool calls or ~30 minutes (`RATIONALE-2026-04-26`: observed conversation-degradation onset across the audit's session sample averaged 47 tool calls before periodic-snapshot pressure surfaced; "~50" is the rounded upper bound of that distribution; register row at `scripts/dev/per-claim-register.md`; falsifier: a controlled session that holds zero degradation past 50 calls / 30 minutes invalidates the threshold):

**3.1 — Periodic State Snapshots:** Every 15–20 tool calls, verify: actions aligned with original request, conventions not drifted, cross-references accurate. When a periodic snapshot coincides with a compaction trigger, execute the snapshot first, then proceed with pre-compaction externalization and compaction.

**3.2 — Progressive Summarization:** Replace detailed recollections with pointers to externalized files. Summarize completed work into compact status lines. Release processed content after verification and externalization.

**3.3 — Convention Anchoring:** Establish conventions at session start and write them to PROGRESS.md Resumption Contract (not just held in conversation). Periodically re-read (every 20–25 tool calls) to prevent drift.

**3.4 — Regression Detection:** Before significant outputs, verify consistency with earlier outputs in naming, formatting, and style. Correct immediately if drift detected.

**3.5 — Concurrent Modification Awareness:** When subagents write to shared files (PROGRESS.md, PLAN-NOTES.md, memory files), sequence these writes — never dispatch parallel agents that modify the same file. If a file was modified externally since last read, re-read before editing.

**3.6 — Continuous Single-Session Execution:** Full-suite `/plan-execute` invocations advance phase-to-phase inside the same execution session by default. Boundary sequence: finish verification → write the Phase Exit Protocol → commit codebase changes → compact → run the Blind Bootstrap Sequence → start the next unblocked phase. Granular pause modes remain explicit opt-ins through the persisted `Execution mode` line.

Stop conditions are limited and concrete: explicit single-phase invocation; final phase complete; current phase BLOCKED; no unblocked next phase in the dependency graph; or a §1 context-health signal that persists after one recovery cycle. The recovery cycle is mandatory before stopping — externalize all observations and decisions, compact or start a fresh session, re-read the Resumption Contract and target phase, rerun the relevant output/input validation, then continue if the contradiction or degradation is gone. Silent quality degradation is forbidden.

### 4. Graceful Degradation

When context pressure becomes critical despite all mitigation:

- **Priority 1:** Externalize ALL remaining unwritten state to durable files.
- **Priority 2:** Complete the current atomic task (do not leave partial state).
- **Priority 3:** Write Resumption Contract with exact pickup point, remaining work, and critical context.
- **Priority 4:** Trigger compaction or session end protocol.
- **Never:** Silently degrade quality. Never produce partial outputs without marking them partial. Never lose state without documenting what was lost.

### 5. Blind Execution Protocol

The foundational inter-session protocol. Every phase must be executable by a fresh session with zero conversation history.

**5.1 — The Invariant:** All state must exist in durable files; active context is ephemeral acceleration, not storage. Loss of active context at any point must cause zero information loss.

**5.2 — Blind Bootstrap Sequence:** Deterministic file-read order for cold-start or post-compaction recovery. Memory files (MEMORY.md + referenced topic files) are always read first, regardless of plan-suite presence.

**Plan-suite sessions:**

0. **Memory files** (MEMORY.md + referenced topic files) — already read as preamble above.
1. **PROGRESS.md Resumption Contract** → phase/task status, next action, convention anchors, active decisions, critical files manifest, watch items, blockers, **execution mode** (the persisted `**Execution mode (this session):**` line — closed taxonomy `{continuous, granular, granular-phase-only, granular-sub-phase-only}`; consumed by `/plan-execute` Step 1A to adopt the persisted mode on resume, and by Step 10A to drive the per-boundary amendment-loop pause cadence).
2. **PLAN-NOTES.md § Resolved Decisions** → what's been decided (never re-ask). Skip if Active Decisions snapshot in Resumption Contract is sufficient.
3. **Target phase file** (`phases/NN-topic/PHASE.md`) → what needs to be done (scope, tasks, inputs, outputs, verification).
4. **PREAMBLE.md** → project conventions, standards, architecture. Skip if convention anchors in Resumption Contract are sufficient.
5. **Prior phase report** (if exists) → what just happened, deviations, watch items.
6. **Rules** (always-on) → behavioral directives.

**Ad-hoc sessions (no plan suite):**

1. **Memory files** (MEMORY.md + referenced topic files) — already read as preamble above.
2. **Active files** referenced in the user's request or prior conversation.
3. **Rules** (always-on) — auto-loaded by the runtime; need not be explicitly re-read.

**5.3 — Output Validation Gate:** Before executing any phase, verify every declared Input from the phase file exists in the Phase Output Registry as verified. Missing inputs = STOP. Inform user which prerequisite outputs are absent.

**5.4 — Convention Recovery:** If convention anchors exist in Resumption Contract, adopt them immediately. If absent (first session or incomplete contract), derive from preamble and externalize to Resumption Contract immediately.

**5.5 — State File Validation:** When reading PROGRESS.md during Blind Bootstrap, validate structural integrity: Resumption Contract fields present and non-empty, Phase Tracker rows parseable, Phase Output Registry columns intact. If malformed (truncated, garbled, missing required sections): (a) attempt reconstruction from the last known-good state — phase reports, git log, and on-disk file existence; (b) log the corruption in PLAN-NOTES.md Recovery Log; (c) notify the user of the reconstruction and any unrecoverable fields.

### 6. Error Classification (CM-18)

Six error classes for structured recovery. Escalate to user after 3 cumulative failures across any class.

| Class | Trigger | Recovery Strategy |
| ----- | ------- | ----------------- |
| **Parse** | Malformed input, invalid YAML/JSON, syntax failures | Re-read source, validate format, retry with corrected input |
| **Resolution** | Missing files, broken cross-references, unresolvable paths | Search for moved/renamed artifacts, check Phase Output Registry, ask user if unresolvable |
| **Validation** | Constraint violations, scorecard failures, spec mismatches | Identify violated constraint, fix root cause, re-validate — never suppress |
| **Generation** | Output doesn't meet specification, incomplete generation | Re-derive from specification (clean-room), verify against all declared outputs |
| **External** | Tool failures, API errors, permission denied, timeout | Retry once with adjusted parameters, then attempt alternative approach, then escalate |
| **State** | Stale context, contradictions between artifacts, convention drift | Re-read authoritative source, externalize corrected state, trigger compaction if context-induced |

## Enforcement

Path-filtered (the eight glob patterns in this rule's `pathFilter` field — `**/.apothem/plans/**`, `**/.plans/**`, `**/PROGRESS.md`, `**/PLAN-NOTES.md`, `**/PHASE.md`, `**/MASTER-PLAN.md`, `**/REPORT.md`, `**/PREAMBLE.md`), always-on at every seriousness level when in scope. Demand-loaded companion to `rules/context-management.md` §2 / §3 / §4 / §4A / §5 / §6 / §8: the parent owns the context-health signals (§1), externalization-invariant summary (§2), compaction summary (§3), blind-execution invariant (§6), context-budget summary (§7), and §2.6 scratch-convention anchor (delegated to `context-management-scratch.md`); this companion owns the operational depth.

## Bindings (§0.j five-direction)

- **Drives →** ● Every phase-exit externalization sequence (§1.5 Externalize-On-Phase-Exit operationalizes the parent's §2.5 anchor). ● Every compaction trigger evaluation (§2's nine triggers operationalize the parent's §3 summary). ● Every continuous full-suite phase transition (§3.6 operationalizes the parent's §4A anchor). ● Every Blind Bootstrap sequence (§5.2 plan-suite + ad-hoc orderings operationalize the parent's §6 invariant). ● Every error-recovery routing decision (§6's six-class table operationalizes the parent's §8 anchor).
- **Satisfies →** ● CM-12 / CM-14 / CM-18 / CM-19 / CM-24 (rule-delegated mandates; this companion is the path-filtered procedural depth). ● the rules registry row "Context Management Protocol". ● `rules/context-management.md` §2 / §3 / §4 / §5 / §6 / §8 anchors (the parent rule's pointers to this companion's full specifications).
- **Established by ↑** ● `rules/context-management.md` §2 / §3 / §4 / §5 / §6 / §8 (parent-rule anchors). ● CM-12 + CM-14 + CM-18 + CM-19 + CM-24 inline definitions. ● the hooks pipeline PreCompact / PostCompact / Stop / SessionStart events.
- **Gated by ←** ● The path-filter (the eight glob patterns) — this rule demand-loads only on plan-workflow artifact touches. ● `rules/context-management.md` always-on baseline (parent rule's §2 / §3 / §4 / §5 / §6 / §8 anchors must be live for the companion to demand-load coherently).
- **Cross-bound with ↔** ↔ `rules/context-management.md` (parent rule; §2 / §3 / §4 / §4A / §5 / §6 / §8 anchors bind this companion). ↔ `rules/context-management-scratch.md` (sibling companion carrying the §2.6 plan-workflow scratch convention; both companions demand-load on overlapping plan-suite paths). ↔ `rules/context-management-budget.md` (sibling companion carrying the §7 Context Budget Discipline operational bodies — §7.1 budget awareness, §7.2 demand loading, §7.3 pressure signals, §7.4 per-task effort calibration / CM-12d). ↔ `rules/auto-memory.md` (CM-26 owns the session-end memory evaluation that §1.5 phase-exit externalization delegates). ↔ `rules/persistent-conventions-vigilance.md` (CM-22 owns the artifact-evolution evaluation that §1.5 delegates). ↔ `hooks/messages/precompact.md` + `hooks/messages/postcompact.md` + `hooks/messages/stop.md` (the hook contexts the protocol's enforcement points emit).
