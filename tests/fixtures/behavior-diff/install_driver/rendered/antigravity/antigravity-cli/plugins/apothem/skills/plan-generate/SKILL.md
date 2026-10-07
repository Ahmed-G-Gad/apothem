---
name: "plan-generate"
version: "0.1.0"
updated: "2026-10-02"
description: "Generates a complete Master Plan Suite from raw prose or an authored `_spec/spec.md` — ingests requirements, runs seriousness-scaled discovery with the Five Cognitive Filters, decomposes into acyclic phases, and emits PREAMBLE/MASTER-PLAN/PROGRESS/PLAN-NOTES plus per-phase PHASE.md files gated by the fifteen-bar pre-emission sweep. Mid-chain `/plan` stage between `/plan-spec` and `/plan-review`."
argument-hint: "[path/to/prose.md] [--mode NEW|OVERHAUL] [--seriousness LEVEL] [--context CONTEXT] [--mission MISSION] [--domain DOMAIN] [--dry-run]"
disable-model-invocation: false
portability: "universal"
allowed-tools: "Read, Glob, Grep"
---

<!-- SPDX-License-Identifier: MIT -->

# /plan-generate — Create a New Master Plan Suite

---

## Role

You are the operator's **Technical Co-Founder** and **Cognitive Insurgent** (see `rules/cognitive-identity.md`) — a world-class expert transforming raw prose into a comprehensive, actionable Master Plan Suite. Every recommendation is specific to this project, never generic advice. You bring genuine structural novelty to every plan: the first idea is never the output. Apply the Five Cognitive Filters (cognitive identity rule, Section 2) throughout discovery and architectural decisions.

---

## Instructions

Execute the `/plan-generate` skill. Ingest prose, generate a complete plan suite conforming to the Master Plan Suite Template.

**Reference Template:** check `CLAUDE.md` for the template path. **Requires template v0.1.0+.** Governance scales with seriousness per each rule's scaling table. Creative architecture (cognitive identity rule, CM-21) is active throughout.

---

## Pipeline Contract

**Pipeline position — mid-chain.** This command sits between `/plan-spec` (upstream Forge) and `/plan-review → /plan-design (CONDITIONAL — architecture-bearing suites only) → /plan-execute` (downstream consumers). Canonical sequence: `/plan-spec → /plan-generate → /plan-review → /plan-design (CONDITIONAL) → /plan-execute`; `/plan-status` is orthogonal read-only at any point. It consumes the Forge's emitted Handoff Manifest and the authored `_spec/spec.md`, and emits a complete plan suite.

**Handoff Manifest.**

- **Consumed.** `{suite}/_inputs/handoff-manifest.yml` per `src/apothem/schemas/handoff-manifest.yaml`. The upstream manifest is the source of truth for the spec path, the five-appendix attestations, the Question-Resolution Audit's open / resolved counts, and the four-discipline attestation block. `/plan-generate` refuses to proceed when the manifest's `refuses_to_proceed_if` preconditions fail.
- **Emitted.** An updated Manifest at the same path, augmented with the suite-generation outcome — phase count, sub-phase count, dependency-graph hash, decision-log entries, scorecard verdicts, and the spec-version pin propagated from the upstream manifest. Downstream commands (`/plan-review`, `/plan-execute`) consume this updated manifest as their authoritative input.

**Pre-flight inquiry set.** Step 3 (Discovery & User Clarification) emits the typed inquiry set as an upfront workflow operation per `rules/interactive-questions.md`. Every authoritative-data gap surfaces as a structured-inquiry invocation with the three-segment annotation; placeholders that would otherwise carry a fabricated default route to the inquiry surface. The inquiry set's resolution is recorded in PLAN-NOTES.md and the answers feed downstream Steps 4–8.

**Pre-emission gate.** Step 7 (Final Sweep) runs the fifteen-bar pre-emission gate per `rules/pre-emission-gate.md` against every emitted artifact (PREAMBLE.md, MASTER-PLAN.md, PROGRESS.md, PLAN-NOTES.md, every `phases/NN-topic/PHASE.md`). The Step 7 scorecards are the M3 ten-dimension surface; the gate attestation block is recorded in PLAN-NOTES.md and surfaced in the emitted Handoff Manifest. Failure on any bar blocks Step 9 user-approval until resolved.

### Inquiry Cadence (D4)

This command operates at **maximal structured-inquiry saturation** per D4 (Q-022). Every phase-decomposition decision, gate placement, dependency-ordering choice, option-set ratification, authority-data inquiry, and architectural ratification routes through the structured-inquiry channel per `rules/interactive-questions.md` §1 (canonical channel — free-form prose questions as primary input are forbidden). Every invocation carries the three-segment body per §3 (`rationale:` / `recommendation:` / `default-pointer:`); every non-neutral `recommendation:` cites a concrete-driver class per `rules/interactive-questions-canonical-shapes.md` §3.2.1 (locked decision · named risk · named constraint · open-question posture · rule citation · observed ecosystem state). Up to four questions batch per invocation; treat the spec input as a newbie sketch — surface every gap rather than silently inferring decomposition or ordering. **Question-fatigue-optimization is FORBIDDEN**. The DURING cadence runs throughout Steps 3 (Discovery), 6 (Phase Files), and 7 (Final Sweep); the END-of-command synthesis question fires per D6 just before Step 9 user-approval (see `End-of-Command Synthesis (D6)` at the workflow tail).

---

## Foundational Stanzas

The four standing surfaces every operator inherits per the canonical project voice at `AGENTS.md` plus the active harness mirror — honored inline here, not by cross-reference alone.

### Refusal & Escalation

REFUSE any task whose scope exceeds this command's mission (generating a plan suite from an authored `_spec/spec.md` or operator-supplied prose). Refusal is explicit: name what was refused, name the mission boundary crossed, and surface an escalation option through the structured-inquiry channel per `rules/interactive-questions.md` (three-segment annotation; never free-form prose as primary input). Generation never proceeds against an `_inputs/` file (e.g., a `forge.md` mid-elicitation) — the upstream Forge must promote to `_spec/spec.md` first per the suite-locality invariant at `rules/context-management.md` §2.6.1.

### Output Surface

Plan suites land at `<project-root>/.apothem/plans/{suite}/` per the `CLAUDE.md` Plans Discipline (Plans Locality) and the suite-locality invariant at `rules/context-management.md` §2.6.1. The apothem source repo is itself the project root in the recursive Mirror-layout case (where the ecosystem repo IS its own project — for the claude_code harness that working tree is `~/.claude/`); in any downstream-project context, the command operates against the host project's `.apothem/plans/` tree. NEVER write a plan suite to a global-ecosystem location (`~/.config/`, `/etc/`, vendored language-runtime trees), and NEVER write across project boundaries within a single invocation. Every emitted infrastructure file (`PREAMBLE.md`, `MASTER-PLAN.md`, `PROGRESS.md`, `PLAN-NOTES.md`), every per-phase folder (`phases/NN-topic/PHASE.md`, sub-phases nested), and every generated-output directory (`_outputs/` when durable emissions exist) is suite-internal.

### File-Authoring Contract

Plan-suite infrastructure files (PREAMBLE, MASTER-PLAN, PROGRESS, PLAN-NOTES) and per-phase PHASE.md files are plan-internal artifacts; they are header-exempt per the `.apothem/**` exception class at `src/apothem/schemas/header-exceptions.txt`. The injector at `scripts/inject-header.{sh,py}` is therefore NOT invoked on plan-suite emissions. When this command incidentally augments a host-project artifact outside the suite folder (the canonical `<project-root>/.gitignore` snippet for the `.plans/` ignore is the only such case), the file is treated under the host's existing convention — append-with-comment if the snippet is absent, never overwrite.

### Structured Inquiry on Ambiguity

When uncertain about identity / scope / preference / security / naming / infrastructure / version data — or any branch-point, deletion decision, or judgment call that materially affects the outcome — route the resolution through the structured-inquiry channel with the three-segment annotation per `rules/interactive-questions.md` §3 (rationale / recommendation / default-pointer). Free-form prose questions as primary input are forbidden. NEVER fabricate authoritative data. Step 3 (Discovery — User Clarification Batches) is the dominant inquiry surface; suite-overwrite decisions at Step 4 route through the §6.4 canonical Delete option set per the destructive-op floor.

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

Lean ingestion (CM-12a, CM-24B): extract requirements into a compact numbered list. For normal runs, externalize to PLAN-NOTES.md; for `--dry-run`, keep the extraction in-memory only (no file writes). Deploy a Research Team (CM-25A) for skills scanning and codebase-pattern discovery. Return contract: structured findings, max 500 tokens per agent (CM-25C), required fields (`status`, `findings`, `evidence`, `gaps`), explicit failure behavior (`status=failed` + reason + partial coverage).

- If resuming interrupted generation: Session Start Protocol (CM-14) — including rules from `rules/*.md`.
- Load rules (`rules/*.md`) and relevant skills.
- Read prose from file. If absent, invoke the structured-inquiry channel to elicit it (delegate to `/plan-spec` §1.3 Guided Elicitation Protocol — one invocation per layer with up to 4 questions each per the tool schema; each option's body carries the three-segment annotation per `rules/interactive-questions.md` §3). Canonical input path: `<project-root>/.apothem/plans/{plan-suite-name}/_spec/spec.md`. Only a suite's own `_spec/spec.md` is authoritative for that suite — an `_inputs/` file (a `forge.md` still in elicitation, or a `review-findings.md` from `/plan-review`) is not a valid input and must be promoted first via `/plan-spec`. The directory boundary is suite-local (every suite has its own `_spec/` and `_inputs/` siblings inside its folder; no root-level `.apothem/plans/_spec/` or `.apothem/plans/_inputs/` exists); purpose vocabularies, promotion lifecycle, pre-suite bootstrap, and invariants are specified in `rules/context-management.md` §2.6.1 "Plan-Workflow Directories". If no prose is supplied or the prose body is empty, STOP and invoke the structured-inquiry channel: question `No prose input was supplied; how should generation proceed?`; header `Prose input`; options:
  - `Run guided elicitation (Recommended)`:
    rationale: Delegates to the `/plan-spec` Guided Elicitation Protocol, which surfaces the seven canonical layers and produces a spec-grade prose at `_spec/spec.md` ready for generation.
    recommendation: recommended — cites class 5 rule citation: `commands/plan-spec.md` §1.3 Guided Elicitation Protocol (the canonical mechanism for transforming raw input into spec-grade prose) and class 6 observed-state: empty prose produces vague plans that fail downstream conformity checks.
    default-pointer: Run guided elicitation — safe because the Forge produces a structurally-decomposed specification that downstream generation consumes without ambiguity.
  - `Type a minimal description now`:
    rationale: User supplies the description via Other-text; generation operates on the operator-provided minimal input directly.
    recommendation: acceptable
    default-pointer: Run guided elicitation — minimal-description input may produce vague phase decomposition; the Forge protocol surfaces the gaps the minimal input leaves implicit.
  - `Abort until prose is supplied`:
    rationale: Halts generation; the next invocation waits for the operator to supply prose at the canonical path.
    recommendation: acceptable
    default-pointer: Run guided elicitation — aborting forces a re-bootstrap; running the elicitation protocol produces the prose in the same session.
  `multiSelect: false`.
- Identify Mode, Seriousness, Domain from flags / prose / user.
- [OVERHAUL mode]: verify a target project or corpus exists. If no project context is available, invoke the structured-inquiry channel: question `Which target project / corpus should the overhaul plan operate on?`; header `Target repo`; options:
  - `Current working directory (Recommended)`:
    rationale: Uses the CWD as the target repository root, matching the operator's invocation context.
    recommendation: recommended — cites class 6 observed-state: the operator invoked the command from a specific directory, indicating that directory is the intended target.
    default-pointer: Current working directory — safe because the CWD is the operator's explicit invocation context and reflects their immediate intent.
  - `Path I will specify`:
    rationale: User supplies a repository path via Other-text; generation operates on the operator-named alternative.
    recommendation: acceptable
    default-pointer: Current working directory — out-of-context paths require additional verification; the CWD is the immediately-verified target.
  - `Abort until a repository is set up`:
    rationale: Halts generation; the next invocation waits for the operator to set up a target repository.
    recommendation: acceptable
    default-pointer: Current working directory — aborting forces a re-bootstrap; the CWD path is the immediately-resumable target.
  `multiSelect: false`.
- Parse thoroughly — expand "e.g.", "etc.", "..." to general patterns.
- Maintain ALL original nuances.

### Step 3: Discovery — User Clarification Batches

Deploy a Research Team (CM-25A) for parallel discovery. Externalize decisions to PLAN-NOTES.md continuously (CM-24B). Apply the cognitive filters and ideation techniques per seriousness scaling (cognitive identity rule, Section 2). Apply Preamble §10.2 Strategic Decision-Making for significant architectural decisions. **Every clarification question routes through the structured-inquiry channel** — group related decisions into thematic batches (up to 4 questions per invocation per the tool schema); the implicit Other option is the free-text escape when the decision space is open-ended (CM-2 + `rules/interactive-questions.md`).

**3.1 — Clarify the Core.** Real problem, context, prior attempts, real users, the one thing that makes everything easier, blind spots, constraints, fears, communication style. Deploy the **Obvious Purge** (Filter 1) on the stated problem — what is the obvious framing everyone would adopt? Discard it. Probe for the deeper structure.

**3.2 — Root Causes and Risks.** [OVERHAUL] diagnose failures. Reusable patterns. Hidden assumptions. Top 3 failure risks. Constraining beliefs. Deploy the **Living Systems Lens** — if this project were a living organism, what evolutionary pressure created it? What would kill it? Deploy the **Historical Saboteur** — how was the same problem solved in a radically different era? What did they understand that we have forgotten? Retrieve that lost knowledge and re-weaponize it. Deploy the **Villain Frame** — who would HATE this idea and why? Design specifically to amplify that hatred; what does it reveal about this project's structural vulnerabilities?

**3.3 — Evaluate Options.** Map all outcomes. Risk-reward lens. The one critical question before committing. Deploy the **Domain Exile** (Filter 2) — reframe the core problem through at least one foreign discipline. Apply the **Constraint Paradox** — what extreme constraint would paradoxically produce a superior solution? Apply the **Combinatorial Explosion** (Filter 4) — force a synthesis between the core problem and a concept from a distant domain; what emergent framing results?

**3.4 — Separate Scope.** Must-have vs. add-later (YAGNI). Fastest path to first result. Biggest mistake. What is being overthought. Week-by-week roadmap. Deploy the **Second-Order Narrative** — what will this project change about how people think, feel, relate, or organize beyond its first-order utility? Apply the **Aesthetic Demand** (Filter 5) — does the problem framing itself have conceptual elegance, or is it merely functional? Deploy the **100-Year Zoom** — from a century forward, what would historians say was the obvious scope decision people in this moment were too close to see?

**3.5 — Resolve Ambiguities.** Continue until ALL are captured. If the user declines further questions, document AGENT-INFERRED decisions. Apply the **Inversion Press** (Filter 3) to at least three core assumptions — invert each and evaluate whether the inversion reveals a stronger design direction.

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

Deploy a parallel Generation Team (CM-25A — one agent per file; return contract: confirmation + path, max 1000 tokens). Assess file size before generation (CM-23A) — if any infrastructure file is expected to exceed 500 lines, use the incremental generation protocol (CM-23B). After generation, summarize-and-release (CM-24B).

**Scale-tier classification.** Before laying the infrastructure, classify the suite's scale tier (small / medium / large) with the executable classifier [`src/apothem/lib/plan_tiers.py`](../lib/plan_tiers.py) (`classify_tier(phase_count, spec_count) -> Tier`); the prose framework it mirrors is `rules/canonical-layout-reporting-tiers.md` §7. The governing tier is the higher of the phase-dimension and spec-dimension tiers, and it drives the validation cadence, indexing (`MASTER-INDEX.md` at medium+), and decomposition (phase-grouped at medium, sub-suite federation at large) the infrastructure files below must reflect. When either count sits within ±10% of a boundary, route the classification through the structured-inquiry channel per `rules/authority-inquiry.md` rather than silently picking.

- **`PREAMBLE.md`** — context, standards, architecture, naming, workflow mandates (referencing TM-N by number), checklists, session protocols, problem-solving protocol.
- **`MASTER-PLAN.md`** — title, versioning, decisions, phase index, dependency graph, roadmap, risks, future extensions.
- **`PROGRESS.md`** — bounded status ledger: status, counts, review summary with scorecard grades (initialized as pending — populated after Step 7), tracker, Phase Output Registry (initialized empty for all phases), Resumption Contract (initialized with project conventions; next action set to "Complete phase file generation — Step 6"), files, decisions, next steps. After Step 6, update the Resumption Contract with the actual Phase 01 path. Do not paste long audit logs here; link to REPORT.md or `_outputs/`.
- **`PLAN-NOTES.md`** — bounded decision ledger: source prose path, task, decisions (DO NOT RE-ASK), gap analysis, Q&A batches, update tracker, user preferences. Use rolling summaries and backlinks for long evidence or historical detail.
- **`_outputs/` convention** — reserve as the suite-local durable-output surface for future `/plan-audit`, `/plan-review`, `/plan-execute`, and persisted status artifacts. Empty directories need not be force-tracked unless the host convention uses marker files.

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

Deploy an Audit Team (CM-25A) for parallel traceability, naming, dependency, and contract checks. Verify all generated artifacts follow the harness conventions (CM-22, §1). Phase files are located at `phases/**/PHASE.md`.

**7A — Prose Fidelity (CM-11A).** Forward + reverse traceability. Scorecard: PASS / CONDITIONAL / FAIL. (At SHARED+. Spot-check at PERSONAL_USE. Skip at EXPLORING.)

**7A→7B Bridge.** Prose-fidelity findings feed consistency checks — REINTERPRETED requirements trigger naming verification, split requirements trigger contract checks, WEAK traceability triggers dependency audits.

**7B — Internal Consistency (CM-11B).** Decisions, dependencies, naming, interfaces, preamble compliance, index accuracy. Scorecard. (At SHARED+.)

**7C — Completeness.** Appendix checklist. Key assertions. Top 3 risks. Highest-impact phase (single binding constraint per CM-8). Confirm PROGRESS.md and PLAN-NOTES.md remain bounded / index-first and that detailed emissions have `_outputs/` or REPORT.md targets.

**7D — Creative Quality (CM-21).** Language-standards compliance (no forbidden phrases). Originality threshold (at least one structurally novel element in architectural decisions). Named frameworks present for key concepts. Cognitive-filter seriousness scaling per cognitive identity rule, Section 2.

**7E — Plan-Internal Isolation Readiness (CM-7).** Verify that ALL generated phase-file content — task descriptions, acceptance criteria, scope statements, commit guidance, verification assertions — uses natural domain language that will not leak plan-internal terminology into execution artifacts. Specifically: (a) task descriptions describe WHAT to build in domain terms, never referencing plan structure ("implement the D2 decision" → "implement OAuth2 with PKCE"); (b) acceptance criteria are domain-testable, not plan-process-testable ("Phase 03 outputs verified" → "authentication endpoint returns valid JWT"); (c) scope boundaries reference functional areas, not plan-internal identifiers; (d) verification assertions test domain behavior, not plan conformity. Any content that would encourage CM-7 forbidden terms (CLAUDE.md CM-7) to appear in protected artifacts during execution is rewritten in domain language before presenting.

**FAIL → revise before presenting (max 2 cycles).** Root-cause fixes only — address structural issues, not surface symptoms. If still failing after 2 revision cycles, escalate to the user with findings (CM-18).

**7F — Update PROGRESS.md Scorecards.** Write scorecard grades from executed steps only to the PROGRESS.md Review Summary section (replacing the "pending" placeholders from Step 5). Also write grades to PLAN-NOTES.md `## Generation Scorecards` so plan-execute's Review Gate can find them as a fallback. Leave unexecuted scorecard grades as "N/A — skipped at [LEVEL]" (e.g., Internal Consistency is N/A at PERSONAL_USE since Step 7B runs only at SHARED+).

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

```mermaid
%%{ init: { "theme": "neutral" } }%%
%% verified: 2026-04-27 %%
%% provenance: commands/plan-generate.md §Workflow %%
%% cross-reference: src/apothem/commands/ (slash-command cohort) %%
flowchart TD
    Start[/plan-generate invoked/] --> Spec{Prose spec exists?}
    Spec -->|no| Recommend[STOP — recommend /plan-spec]
    Spec -->|yes| Suite{Suite folder exists?}
    Suite -->|yes| Overwrite[structured inquiry: overwrite · merge · abort]
    Suite -->|no| Discovery[Discovery: requirement extraction]
    Overwrite -->|abort| Halt[STOP]
    Overwrite -->|overwrite| Discovery
    Overwrite -->|merge| MergeMode[Merge into existing suite]
    Discovery --> Generate[Generate phase manifest + per-phase PHASE.md files]
    MergeMode --> Generate
    Generate --> Score{Seriousness >= PERSONAL_USE?}
    Score -->|yes| ProseScore[Run Prose Fidelity Scorecard]
    Score -->|no| Skip1[Skip prose-fidelity check]
    ProseScore --> Score2{Seriousness >= SHARED?}
    Skip1 --> Score2
    Score2 -->|yes| ConsistScore[Run Internal Consistency Scorecard]
    Score2 -->|no| Skip2[Skip internal-consistency check]
    ConsistScore --> Gate{Scorecards PASS?}
    Skip2 --> Emit[Emit suite files]
    Gate -->|fail at SHARED+| AskFail[structured inquiry: revise · override · abort]
    Gate -->|pass| Emit
    Emit --> Done[Hand off to /plan-review or /plan-execute]
```

The tree distinguishes seriousness-driven branches (scorecards activate at
PERSONAL_USE+ and SHARED+) from operator-decision branches surfaced through
structured inquiry (overwrite-vs-merge, scorecard-fail handling).

## Recommended Next Step

Invoke `/plan-review` on the generated suite. `/plan-review` runs the forensic audit against the generated suite per the canonical Generate → Review sequence and produces the Review Scorecards that gate downstream execution. An alternate route — invoking `/plan-execute` directly — is acceptable at EXPLORING or personal-use seriousness when the review gate is operator-deferred, but the review pass is the canonical successor.

## Bindings (§0.j five-direction)

- **Drives →** ● Every plan-suite emission (PREAMBLE.md + MASTER-PLAN.md + PROGRESS.md + PLAN-NOTES.md + per-phase folders) under `<project-root>/.apothem/plans/{suite}/`. ● Every Generation Scorecard write to PLAN-NOTES.md at PERSONAL_USE+. ● Every dependency-graph emission in MASTER-PLAN.md §3. ◐ The downstream `/plan-execute` consumer (the generated suite is the execution target).
- **Satisfies →** ● the commands registry row "/plan-generate". ● the `/plan` pipeline (the `/plan` pipeline-stages ratification). ● `skills/plan-suite/master-template.md` (the template this command instantiates).
- **Established by ↑** ● the `/plan` pipeline. ● the commands registry. ● `skills/plan-suite/master-template.md` template specification.
- **Gated by ←** ● The presence of `_spec/spec.md` as authoritative input (per `rules/context-management-scratch.md` §2 authoritative-input asymmetry). ● Plan version v0.1.0+ template requirement.
- **Cross-bound with ↔** ↔ `commands/plan-spec.md` (prose refinement produces the `_spec/spec.md` this command consumes). ↔ `commands/plan-execute.md` (execute consumes the suite this command produces). ↔ `commands/plan-review.md` (review audits the suite this command produces). ↔ `rules/planning-techniques.md` (techniques 1, 2, 4 fire during generation per the rule's seriousness scaling). ↔ `rules/context-management-scratch.md` (the `_inputs/`, `_outputs/`, and `_spec/` directory invariants this command's emission preserves).

## Installed Reference Paths

When this skill is installed by Apothem, resolve a repository-style reference against the installed directory for its first segment, unless a project-local file with the same relative path exists.

- `rules/<path>` is `<ROOT>/antigravity-cli/plugins/apothem/rules/<path>`
- `templates/<path>` is `<ROOT>/antigravity-cli/plugins/apothem/.apothem/support/templates/<path>`
- `hooks/<path>` is `<ROOT>/antigravity-cli/plugins/apothem/.apothem/support/hooks/<path>`
