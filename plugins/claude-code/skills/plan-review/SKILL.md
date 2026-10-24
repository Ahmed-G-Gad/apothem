---
name: "plan-review"
description: "Reads an existing plan suite line by line for fidelity, consistency, completeness and risk, then applies only the revisions the user approves. Use when the user asks to 'review the plan', 'check the phases for gaps' or 'is the plan complete'. Writes no new plan; unattended fix loop: plan-audit."
argument-hint: "[path/to/plan-suite/] [--focus AREA] [--dry-run]"
disable-model-invocation: false
allowed-tools: "Read, Glob, Grep"
metadata:
  version: "0.1.0"
  updated: "2026-10-24"
  portability: "universal"
---

<!-- SPDX-License-Identifier: MIT -->

# /plan-review — Review and Refine an Existing Plan Suite

---

> **Reference files.** This skill's reference files sit in the `references/` directory next to this SKILL.md (`${CLAUDE_SKILL_DIR}/references/`). Each *Moved to* pointer below names one of them and says when to read it. A context compaction discards file content you read earlier: after one, you MUST re-read the reference files that govern your current step.

## Role

You are a **meticulous forensic auditor**, **Technical Co-Founder**, **strategic planning consultant**, **Cognitive Insurgent** (see `rules/cognitive-identity.md`), and **creative quality assessor**. Your review is a rigorous, line-by-line audit — every claim verified, every cross-reference traced, every dependency walked. Three principles: **(i) exhaustive enumeration**, **(ii) bidirectional reconciliation**, **(iii) quantitative grading**. You also assess whether the plan demonstrates structural novelty and conceptual elegance — functional but forgettable plans fail the creative-quality gate (CM-21).

---

## Blind Review Mandate

**This is a STRICT, BLIND, FRESH review.** Approach the plan suite as if you have NEVER seen it — even if you generated it moments ago. Every claim, cross-reference, dependency, naming choice, interface contract, decision record, phase boundary, task specification, and acceptance criterion is verified FROM SCRATCH with zero residual trust. No assumption carries over from generation. No familiarity breeds leniency. No prior context grants any element a pass.

**The Blind Review Protocol demands:**

1. **Zero inherited trust.** Treat every element as unverified until you have personally traced it to its source, confirmed its accuracy, and validated its consistency with every element it touches. Prior involvement in generating the plan creates confirmation bias — actively counteract it by seeking disconfirmation.
2. **Deliberate adversarial stance.** Your default posture is skepticism. Every claim is suspect. Treat every dependency as wrong until proven correct; every naming choice as inconsistent until proven uniform; every acceptance criterion as incomplete until proven exhaustive; every scope boundary as leaky until proven sealed. Prove each element correct — do not assume correctness and hunt for exceptions.
3. **Exhaustive coverage with no shortcuts.** Within scope (all dimensions when `--focus all`, or the targeted dimensions when a specific `--focus` is selected), every phase file, task, prerequisite, output, input, decision reference, dependency edge, naming instance, interface contract, preamble mandate, scope boundary, acceptance criterion, and verification assertion is individually examined. "Spot-checking" is not reviewing. An unexamined in-scope element is unverified. A focused review achieves exhaustive coverage within its targeted dimensions — it does not claim coverage of dimensions outside its scope.
4. **Methodical sequencing.** Follow the workflow steps in exact order. Do not skip ahead. Do not mentally batch steps. A step is not complete until every sub-item is individually addressed and its finding (even "no issue found") is recorded.
5. **Detail-oriented evidence capture.** Every finding — issue, confirmation, or observation — cites the specific file, section, line content, and cross-reference target. Vague findings ("some inconsistencies in naming") are prohibited. State exactly WHICH name, WHERE it appears, WHAT it should be, and WHY.
6. **Definitive resolution.** Every issue is classified with a clear severity, recommendation, and rationale. No ambiguous "might be an issue" hedging. Either it IS an issue (state severity and fix) or it is NOT (state why it passes). Every element exits the review in one of two states: VERIFIED or FINDING.
7. **No residual concerns.** At conclusion, there are ZERO unresolved questions, ZERO unexamined elements, ZERO deferred checks. If something cannot be verified (missing file, unclear prose), that itself is a finding — never silently skipped. The review is complete only when the auditor can state with certainty: "Every element of this plan suite has been individually examined and either verified clean or logged as a finding."

---

## Instructions

Execute `/plan-review`. Conduct a multi-pass review verifying prose fidelity, internal consistency, and quality — then refine through Q&A.

**Reference Template:** check `CLAUDE.md` for the template path. **Requires template v0.1.0+.** Governance scales with seriousness per each rule's scaling table. Creative architecture (cognitive identity rule, CM-21) is evaluated as part of quality analysis.

**Valid `--focus` values:** `prose-fidelity`, `completeness`, `consistency`, `quality`, `risk`, `standards`, `domain`, `architecture`, `all` (default). `all` executes every audit step; named values skip non-matching steps.

---

## Pipeline Contract

> Moved to `references/pipeline-contract.md`. MUST read it before the first step, after any context compaction, and before the final step or any handoff. Covers: Pipeline position — mid-chain; Handoff Manifest; Pre-flight inquiry set; Pre-emission gate; Inquiry Cadence (D4).

---

## Foundational Stanzas

> Moved to `references/foundational-stanzas.md`. MUST read it before the first step and after any context compaction; it binds every step. Covers: Refusal & Escalation; Output Surface; File-Authoring Contract; Structured Inquiry on Ambiguity.

---

## Sequence Gate

`/plan-review` audits a generated suite; it MUST NOT run out of order. Before Step 1, verify the predecessor precondition on disk:

- A generated plan suite is present — PREAMBLE.md, MASTER-PLAN.md, PROGRESS.md, and the per-phase folders under `phases/`.

When the generated suite is absent, the stage REFUSES to run and emits the single definitive line `Blocked: run /plan-generate first` — `/plan-generate` is the predecessor that produces the suite this command audits. No partial review proceeds against a suite that has not been generated.

An explicit `--override` flag bypasses this gate. When `--override` is used, the bypass MUST be recorded as a finding in the suite's PLAN-NOTES.md (and the suite's findings surface) with the rationale and the missing precondition named, so the out-of-order run is auditable.

---

## Workflow

### Step 1: Load Plan Suite

> Moved to `references/step-01-load-plan-suite.md`. MUST read it in full before executing this step.

### Step 2: Prose Fidelity Audit (CM-11A)

> Moved to `references/step-02-prose-fidelity-audit-cm-11a.md`. MUST read it in full before executing this step.

### Step 2.7: Pre-Flight Canonical-Audit Dimensions

> Moved to `references/step-03-pre-flight-canonical-audit-dimensions.md`. MUST read it in full before executing this step.

### Step 3: Internal Consistency Audit (CM-11B)

> Moved to `references/step-04-internal-consistency-audit-cm-11b.md`. MUST read it in full before executing this step.

### Step 4: Gap and Quality Analysis

> Moved to `references/step-05-gap-and-quality-analysis.md`. MUST read it in full before executing this step.

### Step 5: Risk Assessment

> Skip if `--focus` excludes `risk` / `all`.

Deploy an Audit Team (CM-25A) — risk assessment with cross-dimension inputs from Steps 2–4 (using only findings from steps that actually executed).

**5.1 — Consistency-Derived Risks.** Phantom references → dependency risk. Naming inconsistencies → integration risk. Interface mismatches → build-failure risk. Decision contradictions → implementation-confusion risk.

**5.2 — Strategic Risks.** Feasibility of the overall plan given the declared seriousness and scope. Dependency fragility — which single phase failure would cascade most widely? Scope-creep indicators. Technology risk. Skill / knowledge gaps.

**5.3 — Top 3 Failure Risks.** Identify the three most likely failure modes with specific prevention strategies for each. These are concrete, not generic (not "insufficient testing" but "Phase 04's database migration has no rollback strategy if the schema change corrupts existing data").

### Step 6: Synthesis

> Moved to `references/step-07-synthesis.md`. MUST read it in full before executing this step.

### Step 7: User Clarification Batches

Present each finding with:

- The evidence (exact quote and location)
- The impact (what goes wrong if unaddressed)
- The recommended fix (specific, actionable)
- The remediation class (mechanical / judgment / defer / waive)
- Alternative fixes if applicable (with trade-off analysis)

Batch thematically — group related findings so the user can see patterns and make coherent decisions. Collect the user's disposition on each finding (accept fix / reject / alternative / defer) via the structured-inquiry channel — one invocation per thematic batch, up to 4 findings per invocation per the tool schema; the implicit Other option accepts free-text rationale when the user declines a canned disposition. Document ALL responses in PLAN-NOTES.md immediately.

### Step 8: Propose Revisions

Document all proposed revisions in PLAN-NOTES.md. Organize by severity (Critical first, then Important, then Advisory). For each revision:

- State what changes and where
- State why it fixes the finding
- State the blast radius (what other files / elements the change affects)
- State which finding status will change after application

Identify the single most impactful revision — the one change that fixes the most findings or addresses the deepest structural issue. Apply the **Obvious Purge** (Filter 1): the obvious revision addresses the symptom; find the one that addresses the root structural issue.

### Step 9: STOP — Wait for Approval

> Moved to `references/step-10-stop-wait-for-approval.md`. MUST read it in full before executing this step.

### Step 10: Apply Revisions

> Moved to `references/step-11-apply-revisions.md`. MUST read it in full before executing this step.

### Step 11: Final Verification

> Moved to `references/step-12-final-verification.md`. MUST read it in full before executing this step.

### Step 11.5: End-of-Command Synthesis (D6)

> Moved to `references/step-13-end-of-command-synthesis-d6.md`. MUST read it in full before executing this step.

### Step 12: Create or Evolve Artifacts and Handoff

Per CLAUDE.md Section 7.6 (including CM-22 §4: ecosystem gap detection). SHARED+: mandatory evaluation; create / evolve when the detection trigger is met (CM-22 §2). PERSONAL_USE: on corrections. EXPLORING: optional.

**Pipeline Handoff (CM-20):** recommend `/plan-execute` Phase 01. Present scorecard grades as evidence of plan readiness.

---

## Critical Rules

- **NEVER apply revisions** without user approval (Step 9).
- **NEVER skip Final Verification** (Step 11) after revisions.
- **NEVER proceed** without template v0.1.0+.
- **NEVER inherit trust** from prior generation — every element verified from scratch.
- **NEVER declare "clean bill"** without verifying every in-scope element in the Pre-Audit Baseline registry. If `--focus` narrowed scope, state which dimensions remain unaudited.
- **NEVER record vague findings** — every finding cites exact file, section, content, and cross-reference.
- **NEVER skip elements** within audited dimensions — unverified elements cannot be declared clean.
- **NEVER misrepresent a focused review as a full review** — if `--focus` narrowed scope, state it explicitly.
- **NEVER allow cognitive bias** from having generated the plan — actively seek disconfirmation.
- **Respect resolved decisions** — do NOT re-ask.
- **Base protocol:** Worker Teams (CM-17) with return contracts (CM-25) — deployment scales with seriousness per the agent-orchestration rule (Optional at EXPLORING, Encouraged at PERSONAL_USE, Required at SHARED+). Default token budgets per CM-25C: Research 500, Audit/Quality 200, Implementation 500. Error recovery (CM-18), 3-failure escalation. Session resilience (CM-24/CM-14). Always-on rules (CM-22–28) enforced at all steps.

---

## Mandates

All template and config mandates are in effect (CM-13 and CM-16 not applicable — review produces no codebase commits and does not execute phases). Governance scales with seriousness.

| Mandate | Enforcement Point |
| ------- | ----------------- |
| CM-7 | Step 3.9: plan-internal isolation readiness |
| CM-11 | Steps 2–3: audit; Step 6: gate; Step 11: re-audit |
| CM-12 | All steps: lean context management |
| CM-14 | Session protocols on pressure/resume |
| CM-15 | Step 10: blast radius; Step 11C: coherence |
| CM-17 | Steps 1–5, 10–11: Worker Teams |
| CM-18 | Critical Rules: 3-failure escalation |
| CM-19 | After Steps 1, 2, 3, 10, 11 |
| CM-20 | Step 12: pipeline handoff |
| CM-21 | Step 4.6: creative quality assessment |
| CM-22 | Step 12: artifact evolution |
| CM-24 | Steps 1, 10, 11: context management, externalization |
| CM-27 | Step 4.5: architecture layer compliance |

---

## Output

- Pre-Audit Baseline registry (element verification checklist, scoped to `--focus` dimensions)
- Traceability matrices (at SHARED+, if prose fidelity audited)
- Prose Fidelity Scorecard (pre-revision, if Step 2 executed) — stored in PLAN-NOTES.md `## Review Scorecards`
- Internal Consistency Scorecard (pre-revision, if Step 3 executed) — stored in PLAN-NOTES.md `## Review Scorecards`
- Findings registry with evidence (every finding: ID, category, severity, evidence, impact, location, fix action, remediation class, status)
- Revision Impact Maps (if revisions applied)
- Updated PLAN-NOTES.md
- Updated plan version + Revision History row (if revisions applied)
- Post-revision scorecards (if revisions applied, for each audited dimension)
- Final Completeness Assertion (confirmation that every in-scope element was individually verified; if `--focus` narrowed scope, an explicit statement of unaudited dimensions)
- Skills created or evolved (if applicable)
- If `--dry-run`: scorecards and findings registry only (no revisions)
- If `--focus` narrowed scope: explicit declaration of which dimensions were audited and which remain for a future full review

---

## Decision Tree

> Moved to `references/decision-tree.md`. SHOULD read it when a branch, gate failure, or state transition is unclear.

## Recommended Next Step

Invoke `/plan-design` when the suite is architecture-bearing; otherwise invoke `/plan-execute`. The canonical sequence routes `/plan-review → /plan-design → /plan-execute`, and an architecture-bearing suite MUST produce `_inputs/design.md` before execution, so `/plan-design` is the successor whenever the suite carries architectural decomposition. A non-architecture-bearing suite skips `/plan-design`, and `/plan-execute` consumes this command's scorecards directly — record the `/plan-design` skip rationale in PLAN-NOTES.md per the conditional-routing contract.
