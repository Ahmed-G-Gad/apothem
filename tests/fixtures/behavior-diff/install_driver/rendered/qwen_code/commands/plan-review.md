---
description: "Forensic, blind, line-by-line audit of an existing plan suite — prose fidelity, internal consistency, completeness, quality, risk, standards, domain, and architecture — then refine through interactive Q&A. Mid-chain `/plan` stage; emits Review Scorecards that gate downstream execution at SHARED+ and a zero-open-finding terminal verdict."
---

# /plan-review — Review and Refine an Existing Plan Suite

---

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

**Pipeline position — mid-chain.** This command sits between `/plan-generate` (upstream producer) and `/plan-design (CONDITIONAL — architecture-bearing suites only) → /plan-execute` (downstream consumer; for non-architecture-bearing suites, `/plan-execute` consumes directly). Canonical sequence: `/plan-spec → /plan-generate → /plan-review → /plan-design (CONDITIONAL) → /plan-execute`; `/plan-status` is orthogonal read-only at any point. It consumes the generated suite plus its emitted Handoff Manifest, applies forensic audit and refinement, and emits an updated Manifest carrying the review verdict.

**Handoff Manifest.**

- **Consumed.** `{suite}/_inputs/handoff-manifest.yml` per `src/apothem/schemas/handoff-manifest.yaml`. The upstream manifest carries the suite-generation outcome (phase counts, dependency-graph hash, scorecard verdicts, spec-version pin) and the four-discipline attestation block from `/plan-spec`. `/plan-review` refuses to proceed when the upstream manifest's `refuses_to_proceed_if` preconditions fail.
- **Emitted.** The same manifest path, augmented with the review outcome — Review Scorecards verdicts (Prose Fidelity, Internal Consistency, Completeness, Quality, Risk, Standards, Domain, Architecture, Creative Quality), per-finding severity counts, the Review Scope (which dimensions were audited; relevant when `--focus` is narrower than `all`), and the unaudited-dimensions list. Downstream `/plan-execute` reads the Review Scorecards to gate execution at SHARED+ seriousness.

**Pre-flight inquiry set.** Step 7 (User Clarification Batches) emits the inquiry set as part of audit-finding disposition — every finding above the disposition threshold surfaces via the structured-inquiry channel per `rules/interactive-questions.md`. The pre-flight surface is canonicalized here so review-time inquiries surface before the audit fires (Step 1 Discovery), not only after it completes; the upfront surface inventories authoritative-data gaps the audit would otherwise stall on. The post-audit batches in Step 7 retain their per-finding disposition role.

**Pre-emission gate.** Step 8 (Final Review Report Emission) runs the fifteen-bar pre-emission gate per `rules/pre-emission-gate.md` against the emitted review report, the updated PLAN-NOTES.md scorecards, and the augmented Manifest. The gate attestation block is recorded in the review report and surfaced in the Manifest. Failure on any bar blocks the report's promotion until resolved.

### Inquiry Cadence (D4)

This command operates at **maximal structured-inquiry saturation** per D4 (Q-022). Every finding triage, severity ratification, blind-re-audit decision, disposition choice (accept · revise · reject · defer), revision-impact map, and authority-data inquiry routes through the structured-inquiry channel per `rules/interactive-questions.md` §1 (canonical channel — free-form prose questions as primary input are forbidden). Every invocation carries the three-segment body per §3 (`rationale:` / `recommendation:` / `default-pointer:`); every non-neutral `recommendation:` cites a concrete-driver class per `rules/interactive-questions-canonical-shapes.md` §3.2.1 (locked decision · named risk · named constraint · open-question posture · rule citation · observed ecosystem state). Up to four questions batch per invocation. Treat the generated suite as a newbie sketch under the Blind Review Mandate — surface every gap rather than inheriting trust from prior generation. **Question-fatigue-optimization is FORBIDDEN**. The DURING cadence runs throughout Steps 4 (Gap Analysis), 5 (Risk Assessment), 7 (User Clarification Batches), 8 (Propose Revisions), and 9 (Wait for Approval); the END-of-command synthesis question fires per D6 just before Step 12 review-report finalization (see `End-of-Command Synthesis (D6)` at the workflow tail).

---

## Foundational Stanzas

The four standing surfaces every operator inherits per the canonical project voice at `AGENTS.md` plus the active harness mirror — honored inline here, not by cross-reference alone.

### Refusal & Escalation

REFUSE any task whose scope exceeds this command's mission (forensic audit and refinement of an existing plan suite — prose fidelity / internal consistency / quality / risk / standards / domain / architecture). Refusal is explicit: name what was refused, name the mission boundary crossed, and surface an escalation option through the structured-inquiry channel per `rules/interactive-questions.md` (three-segment annotation; never free-form prose as primary input). The Blind Review Mandate forbids inherited trust from prior generation; any pressure to soften a finding because the operator generated the plan themselves is itself a refusable scope-overreach.

### Output Surface

Review outputs are plan-suite-internal: scorecards write to `<project-root>/.apothem/plans/{suite}/PLAN-NOTES.md` `## Review Scorecards`, the Review Summary writes to `<project-root>/.apothem/plans/{suite}/PROGRESS.md`, the augmented Manifest writes to `<project-root>/.apothem/plans/{suite}/_inputs/handoff-manifest.yml`, concise per-finding revision-impact maps land in PLAN-NOTES.md, and durable large review reports or evidence tables land in `<project-root>/.apothem/plans/{suite}/_outputs/` per the suite-locality invariant at `rules/context-management.md` §2.6.1 (which governs `_inputs/`, `_outputs/`, and `_spec/` siblings). Findings disposition surfaces via structured-inquiry invocations whose answers are externalized to PLAN-NOTES.md inline. NEVER write review artifacts outside the suite folder, NEVER write to a global plans directory under any harness config root from a downstream-project context, and NEVER write to any other global-ecosystem location.

### File-Authoring Contract

Plan-suite review artifacts (PLAN-NOTES.md scorecard updates, PROGRESS.md Review Summary updates, the per-phase REPORT.md when revisions touch one, the augmented Manifest) are plan-internal and header-exempt per the `.apothem/**` exception class at `src/apothem/schemas/header-exceptions.txt`. The injector at `scripts/inject-header.{sh,py}` is therefore NOT invoked on review emissions. The contract applies to any orchestrator that materializes this command's findings into a non-plan artifact (a separate audit report at the host's documentation surface, for example) — that orchestrator routes the new file through the injector per the canonical authorship-header policy.

### Structured Inquiry on Ambiguity

When uncertain about identity / scope / preference / security / naming / infrastructure / version data — or any branch-point, deletion decision, or judgment call that materially affects the outcome — route the resolution through the structured-inquiry channel with the three-segment annotation per `rules/interactive-questions.md` §3 (rationale / recommendation / default-pointer). Free-form prose questions as primary input are forbidden. NEVER fabricate authoritative data. Step 7 (User Clarification Batches) is the dominant inquiry surface — every finding above the disposition threshold surfaces through one batched invocation per thematic group; per-revision approval at Step 9 routes through the canonical channel. REINTERPRETED prose-fidelity findings always require operator confirmation.

---

## Sequence Gate

`/plan-review` audits a generated suite; it MUST NOT run out of order. Before Step 1, verify the predecessor precondition on disk:

- A generated plan suite is present — PREAMBLE.md, MASTER-PLAN.md, PROGRESS.md, and the per-phase folders under `phases/`.

When the generated suite is absent, the stage REFUSES to run and emits the single definitive line `Blocked: run /plan-generate first` — `/plan-generate` is the predecessor that produces the suite this command audits. No partial review proceeds against a suite that has not been generated.

An explicit `--override` flag bypasses this gate. When `--override` is used, the bypass MUST be recorded as a finding in the suite's PLAN-NOTES.md (and the suite's findings surface) with the rationale and the missing precondition named, so the out-of-order run is auditable.

---

## Workflow

### Step 1: Load Plan Suite

Deploy a Research Team (CM-25A) for parallel file extraction (structured summaries, not raw content — CM-25C return contract: max 500 tokens per agent; required fields: `status`, `summary`, `evidence`; on failure: `status=failed` with explicit reason and scope covered). If resuming: Session Start Protocol (CM-14) — including rules from `rules/*.md`.

Verify all mandatory files exist (including the `phases/` directory with phase folders). If missing → STOP, recommend `/plan-generate`. Load rules (`rules/*.md`) and relevant skills. If PROGRESS.md carries a Resumption Contract, use its convention anchors and critical-files manifest for efficient loading. Read ALL files — every phase file (`phases/**/PHASE.md`, recursing into sub-phase folders), every infrastructure file, every report (`phases/**/REPORT.md`). Locate the original prose (ask the user if not found; if unavailable, proceed consistency-only — skip Step 2).

**Pre-Audit Baseline.** Externalize declared counts, dependencies, decisions, artifacts (CM-24B). Build a complete registry of every element that must be verified (scoped to `--focus` dimensions when not `all`):

- Total phase count and file list
- Total task count per phase
- Total decision count and decision IDs
- All dependency edges (Phase X depends on Phase Y)
- All named outputs and their declared consumers
- All named inputs and their declared sources
- All naming conventions declared in the preamble
- All interface contracts between phases
- All verification assertions

This registry is the verification checklist. Every in-scope item is individually checked off during the applicable audit steps. Any in-scope item not checked off by Step 6 is an automatic finding.

### Step 2: Prose Fidelity Audit (CM-11A)

> Skip if `--focus` excludes `prose-fidelity` / `completeness` / `all`. Skip at EXPLORING seriousness. **Focus-seriousness conflict check:** after resolving `--focus` dimensions, if the current seriousness level would skip ALL focused dimensions (e.g., `--focus prose-fidelity` at EXPLORING), invoke the structured-inquiry channel: question `At the current seriousness level, the focused dimensions are skipped by default; how should the review proceed?`; header `Scope conflict`; options:
>   - `Raise seriousness (Recommended)`:
>     rationale: Temporarily escalates the seriousness tier for this review so the focused dimensions run; the original tier restores after the review completes.
>     recommendation: recommended — cites class 5 rule citation: the seriousness-scaling discipline (Seriousness-Scaled Governance — escalating to satisfy a focused-dimension audit preserves the audit's evidence requirement) and class 6 observed-state: the operator explicitly named the focused dimensions, indicating they want those dimensions audited.
>     default-pointer: Raise seriousness — safe because the escalation is scoped to this review only and produces the audit evidence the operator requested.
>   - `Broaden focus`:
>     rationale: Expands `--focus` to include dimensions available at the current tier; the originally-named dimensions are dropped from the audited set.
>     recommendation: acceptable
>     default-pointer: Raise seriousness — broadening focus drops the operator's named dimensions from coverage; raising seriousness preserves coverage of the named dimensions.
>   - `Abort`:
>     rationale: Halts the review; the next invocation can resume with adjusted parameters.
>     recommendation: acceptable
>     default-pointer: Raise seriousness — aborting forces a re-bootstrap; raising seriousness completes the review in the same session.
>   `multiSelect: false`. At PERSONAL_USE: spot-check mode — select 5 representative requirements spanning different functional areas, trace forward only (Step 2.1), produce a scorecard on the sample. At SHARED+: full exhaustive audit as specified below.

Deploy an Audit Team (CM-25A) — parallel per-phase traceability. Each agent returns traceability findings with evidence citations (CM-25C).

**2.1 — Forward (Prose→Plan).** Extract EVERY requirement from the original prose — not a sample, not the obvious ones, ALL of them. Assign sequential IDs (R1, R2, R3...). Trace each to a specific phase and specific task. Classify each mapping:

- **STRONG:** the requirement is fully and faithfully represented in a specific task with matching acceptance criteria.
- **WEAK:** partially represented — some aspect is covered but nuance, scope, or specificity is lost.
- **ABSENT:** no corresponding task anywhere in the plan. A Critical finding.
- **REINTERPRETED:** present but materially altered in meaning. Quote both the original prose and the plan's rendering side by side. Requires user confirmation.

**2.2 — Reverse (Plan→Prose).** For EVERY task in EVERY phase, trace back to the prose requirement it implements. Classify:

- **JUSTIFIED:** the task directly implements a prose requirement.
- **UNJUSTIFIED:** the task has no prose basis — it may be a valid domain-standard addition, but it must be flagged and justified. (At PUBLIC_LAUNCH: mandatory for all tasks with full reverse traceability and justification. At SHARED: reverse traceability executed — flag unjustified tasks, accept valid domain-standard additions with brief rationale.)

**2.3 — Nuance Preservation.** Examine specifically:

- Subtle intentions — does the plan capture what the user *meant*, not just what they *said*?
- Thresholds and quantities — are specific numbers preserved verbatim?
- Examples — are user-provided examples expanded into patterns, not flattened?
- Negatives — are "do NOT" and exclusion requirements captured as explicit OUT-of-scope items?
- Hedging and uncertainty — where the user expressed uncertainty, does the plan reflect that as a decision point instead of silently resolving it?

**2.4 — Scope Drift.** Identify every plan item with no prose basis. For each: either justify it as a necessary technical implementation detail or flag it as scope drift. Identify every reinterpretation — quote both the original prose and the plan's rendering side by side.

**2.5 — Emphasis Alignment.** Is plan emphasis proportional to prose emphasis? If the user spent 40% of their prose on feature X, does the plan allocate proportional attention? Disproportionate emphasis (inflated or deflated) is a finding.

**2.6 — Scorecard.** Grade per CM-11A scoring criteria:

- **PASS:** ≥90% STRONG, 0 ABSENT.
- **CONDITIONAL:** ≥75% STRONG, ≤2 ABSENT.
- **FAIL:** below CONDITIONAL thresholds.

Record the full traceability matrix and scorecard.

### Step 2.7: Pre-Flight Canonical-Audit Dimensions

> Mandatory pre-flight sweep firing before the Step 3 forensic audit. These 9 dimensions are not optional; they apply at every seriousness ≥ PERSONAL_USE and on every `--focus` value (including `all`). Each dimension specifies (i) detection logic, (ii) finding classification (severity floor + category), (iii) routing to the receiving scorecard. Findings emitted here are appended to the Step 6.1 Findings Registry and re-checked at Step 11 Final Verification.
>
> Deploy an Audit Team (CM-25A) — one agent per dimension where parallel coverage is feasible (a–i are non-overlapping by detection target). Each agent returns pass/fail + per-finding evidence (CM-25C; max 200 tokens per agent; required fields: `dimension`, `findings[]` with `evidence`, `severity`, `category`).

**2.7.a — Foundational Naming-Drift Detection.**

- **Detection logic.** Sweep every host artifact (source files, configs, docs, plan-suite files) for naming-token drift against the ratified per-language conventions: kebab-case (filenames, folders, slugs), snake_case (Python identifiers, env vars where ratified), PascalCase (Python classes, TypeScript types, Rust types), camelCase (TypeScript identifiers, Go exported), UPPER_SNAKE_CASE (constants). For each token, compare the observed form against the ratified convention for its scope; flag every mixed-convention occurrence (e.g., `UserService` alongside `user_service` for the same entity; `kebab-case-file.py` in a snake_case-Python corpus).
- **Classification.** **MEDIUM** severity floor; category **Internal Consistency**. Promote to **HIGH** when the drift crosses a public-API surface (exported identifier, CLI flag, config key).
- **Routing.** Findings route to the **Internal Consistency Scorecard** (Step 3.10) alongside Step 3.3 Naming Coherence outcomes; pre-flight findings are pre-seeded so Step 3.3 inherits them without re-discovery.

**2.7.b — State-Freshness Sweep.**

- **Detection logic.** Sweep `PROGRESS.md` / `PLAN-NOTES.md` / every `phases/**/PHASE.md` / every `phases/**/REPORT.md` for stale references: (i) references to removed APIs or renamed identifiers (cross-check against the current source tree), (ii) dead URLs (links to repositories, vendor docs, RFCs that 404 or redirect), (iii) files cited at paths that no longer exist (moved or removed), (iv) decision references (D-N) pointing at decisions no longer in the Resolved Decisions table.
- **Classification.** **MEDIUM** severity floor; category **Internal Consistency**. Promote to **HIGH** when the stale reference is load-bearing for downstream `/plan-execute` (a critical-files-manifest entry, a Resumption Contract pointer).
- **Routing.** Findings route to the **Internal Consistency Scorecard** (Step 3.10); cross-fed into Step 3.6 Progress/State Consistency for synthesis.

**2.7.c — Scope-Evolution / Directive-Codification Propagation Audit.**

- **Detection logic.** Enumerate every operator-ratified directive (every decision in the suite's decision registry, every locked-decision-class citation per `rules/interactive-questions-canonical-shapes.md` §3.2.1). For each directive, verify it propagates to its declared target phase(s) and sub-phase(s) tasks — the directive's mandate is materially reflected in task descriptions, acceptance criteria, or scope boundaries of the target phases. A directive ratified but absent from its target phase is a silent omission.
- **Classification.** **HIGH** severity floor; category **Prose Fidelity** (the directive IS the prose contract per the suite's spec-relative anchoring). Promote to **Critical** when the omission affects an irreversible decision class (per `rules/operational-mandates.md` §CM-9).
- **Routing.** Findings route to the **Prose Fidelity Scorecard** (Step 2.6) — pre-flight findings raise the Step 2.6 grade ceiling (a directive omission caps Prose Fidelity at CONDITIONAL until resolved).

**2.7.d — Tooling-Reconsideration Audit.**

- **Detection logic.** Inspect the host's ratified toolchain — formatter (e.g., `ruff format` / `black` / `prettier`), linter (e.g., `ruff check` / `eslint` / `clippy`), type-checker (e.g., `mypy` / `pyright` / `tsc`), test framework (e.g., `pytest` / `vitest` / `cargo test`), docs generator (e.g., Fumadocs / Docusaurus / `mdBook`), CI provider (e.g., GitHub Actions / GitLab CI / CircleCI). For each, compare the host's ratified version (per `pyproject.toml` / `package.json` / `Cargo.toml` and sibling configs) against the tool's current SOTA release (vendor latest stable). Flag stale ratifications (e.g., `mypy` pinned at a version superseded by a newer release with material correctness improvements; `black` where the host's idiom drifted toward `ruff format`).
- **Classification.** **LOW** to **MEDIUM** advisory; category **Tooling-axis Quality** (per `rules/cognitive-identity.md` §1 seven-axes taxonomy — Tooling axis). Promote to **HIGH** only when the staleness blocks a CI-green gate (e.g., a deprecated tool version produces breaking changes against newer Python).
- **Routing.** Findings route to the **Quality Scorecard** (Step 4 — specifically the Standards sub-check 4.3 and the Tooling-axis surface).

**2.7.e — Harness-Cohort Audit.**

- **Detection logic.** At every phase or sub-phase that touches multi-harness work (any phase whose scope names ≥ 2 harness adapters, or whose outputs land under `src/apothem/harnesses/*`), verify the 17-harness adapter cohort is honored: `antigravity`, `claude_code`, `codebuddy`, `codex`, `cursor`, `gemini_cli`, `github_copilot`, `hermes`, `kimi_code`, `kiro`, `open_claw`, `opencode`, `qwen_code`, `trae`, `windsurf`, `zed`, `glm`. Any missing harness in a multi-harness-touching phase is a silent cohort drop.
- **Classification.** **HIGH** severity floor; category **Completeness**. Promote to **Critical** when the missing harness is operator-installed in the active project (verified via the host's harness registry).
- **Routing.** Findings route to the **Completeness Scorecard** (Step 4.1).

**2.7.f — i18n-Cohort Audit.**

- **Detection logic.** At every phase or sub-phase that touches i18n work (any phase whose scope names ≥ 2 locales, or whose outputs land under `docs/i18n/`, `locales/`, or sibling i18n surfaces), verify the 12-locale Modern dev cohort is honored: EN, ZH-CN, ES, PT-BR, FR, DE, JA, KO, RU, ID, AR, HI. Any missing locale in an i18n-touching phase is a silent cohort drop.
- **Classification.** **HIGH** severity floor; category **Completeness**. Promote to **Critical** when the missing locale is mandated by a published rollout commitment.
- **Routing.** Findings route to the **Completeness Scorecard** (Step 4.1).

**2.7.g — Widget-Class Audit.**

- **Detection logic.** At every phase or sub-phase that touches README widgets (any phase whose scope names README header / badge / activity-widget surfaces, or whose outputs land at the host's README), verify the 4 widget classes are honored: (i) Star History, (ii) contrib.rocks contributors graph, (iii) Repobeats activity pulse, (iv) Sponsors / Discord / Showcase badges. Any missing class in a widget-touching phase is a silent omission.
- **Classification.** **MEDIUM** severity floor; category **Completeness**. Promote to **HIGH** when the omission lands on a release-tier README that ships to a public registry.
- **Routing.** Findings route to the **Completeness Scorecard** (Step 4.1).

**2.7.h — Adoption-Maximization Audit.**

- **Detection logic.** At the adoption-surfaces phase, verify the 4 N2 adoption surfaces are honored: (i) Comparison page, (ii) Showcase / Users page, (iii) Discord / Slack community page, (iv) Blog / RSS feed surface. Any missing surface in that cohort is a silent omission.
- **Classification.** **MEDIUM** severity floor; category **Completeness**. Promote to **HIGH** when the omission affects a launch-blocker surface declared in the suite's release-readiness checklist.
- **Routing.** Findings route to the **Completeness Scorecard** (Step 4.1).

**2.7.i — Standard-Conformance Audit.**

- **Detection logic.** Pre-flight check: every adapter, config, framework, or tool the plan uses MUST adhere to its vendor-documented LATEST convention, with a **commit-SHA-pinned citation** and a **per-harness STANDARD CONVENTION PIN** where the artifact is a harness adapter. For each adapter / config / framework / tool reference, verify: (i) the citation names the vendor's canonical convention document with a commit-SHA-pinned URL (not a branch-pointed URL), (ii) the per-harness pin block carries the harness's ratified convention version, (iii) the cited version matches the vendor's current LATEST (no stale conformance). Unpinned-or-stale conformance is a silent fabrication risk per `rules/authority-inquiry.md` (M5 authority half).
- **Classification.** **HIGH** severity floor; category **Authority (M5)**. Promote to **Critical** when the unpinned reference governs a security-relevant adapter surface (auth, secrets, network egress).
- **Routing.** Findings route to the **Standards Scorecard** (Step 4.3) AND the **Risk Assessment** (Step 5.2 Strategic Risks — unpinned conformance is a long-tail supply-chain risk).

**Pre-flight emission contract.** Each dimension above emits at minimum a per-dimension verdict line (`2.7.{letter}: PASS | CONDITIONAL | FAIL — <count> findings`) recorded inline in PLAN-NOTES.md `## Pre-Flight Canonical-Audit`. Findings cross-link to the receiving scorecard per the Routing field above. The pre-flight verdicts feed Step 3 (Internal Consistency), Step 4 (Quality/Completeness/Standards), and Step 5 (Risk) without re-discovery.

### Step 3: Internal Consistency Audit (CM-11B)

> Skip if `--focus` excludes `consistency` / `all`. Skip at EXPLORING seriousness. At PERSONAL_USE: dependency chain only — run sub-check 3.2 (Dependency Chain Integrity) and 3.9 (Plan-Internal Isolation Readiness); skip 3.1, 3.3–3.8. Produce a scorecard on the audited dimensions. At SHARED: all dimensions (3.1–3.9). At PUBLIC_LAUNCH: all dimensions with pairwise cross-validation — for each pair of phase files, verify mutual consistency of shared references, inputs/outputs, and naming.

Deploy an Audit Team (CM-25A) — parallel per-dimension. Every check examines EVERY instance, not a sample. Each agent returns pass/fail + evidence (CM-25C).

**3.1 — Decision Consistency.** Extract every decision reference (D1, D2, ...) from every file. Verify: (a) each decision ID exists in `PLAN-NOTES.md` or `MASTER-PLAN.md` Resolved Decisions table, (b) every phase file referencing a decision uses it consistently with the recorded resolution, (c) no two decisions contradict each other, (d) no phase file implements logic that contradicts a recorded decision.

**3.2 — Dependency Chain Integrity.** For every dependency edge in the dependency graph: (a) verify the prerequisite phase actually produces the declared output, (b) verify the dependent phase actually lists the required input, (c) verify there are no circular dependencies, (d) verify all declared outputs have at least one consumer (orphan outputs are a finding), (e) verify all declared inputs have a producing source (phantom inputs are a Critical finding).

**3.3 — Naming Coherence.** Extract every proper noun, variable name, file path, module name, class name, function name, and technical term used across ALL files. For each term: verify it is spelled identically everywhere it appears. A single inconsistency (e.g., `UserService` in one file vs. `userService` in another) is a finding. Verify all naming follows the conventions declared in the preamble.

**3.4 — Interface/Contract Consistency.** For every input/output pair across phase boundaries: verify the output's specification (type, format, content) matches the input's expectation. If Phase 3 outputs `config.yaml` and Phase 4 consumes `config.json`, that is a Critical finding.

**3.5 — Preamble-Phase Alignment.** For every mandate, standard, convention, and instruction in `PREAMBLE.md`: verify every phase file complies. If the preamble mandates conventional commits and a phase file says "commit with descriptive messages", that is a finding.

**3.6 — Progress/State Consistency.** Verify `PROGRESS.md` accurately reflects the current state — phase counts match actual phase files, dependency references match the graph, statuses are internally consistent.

**3.7 — Master Plan Index Integrity.** Verify the `MASTER-PLAN.md` Phase Index: (a) every listed phase folder actually exists in `phases/`, (b) every existing phase folder is listed, (c) scope descriptions match the phase files' Scope sections, (d) dependency declarations match the dependency graph, (e) parallelization opportunities are correctly identified (no parallel phases that actually carry sequential dependencies).

**3.8 — Cross-Phase Semantic Continuity.** Read the plan as a narrative from Phase 01 through Phase NN. Verify the logical flow: does Phase N's output set up Phase N+1 correctly? Are there semantic gaps where a phase assumes context or artifacts no prior phase produces? Is the overall arc coherent?

**3.9 — Plan-Internal Isolation Readiness (CM-7).** Verify that phase-file task descriptions, acceptance criteria, and scope descriptions are written in natural domain language that will NOT leak plan-internal terminology into execution artifacts. Specifically: (a) task descriptions describe WHAT to build, not plan structure ("implement the D2 decision" → "implement OAuth2 with PKCE"); (b) acceptance criteria are domain-testable, not plan-process-testable ("Phase 03 outputs verified" → "authentication endpoint returns valid JWT"); (c) commit guidance uses domain language, not phase/decision references; (d) scope boundaries reference functional areas, not plan-internal identifiers. Any content that would encourage CM-7 forbidden terms (CLAUDE.md CM-7) to appear in protected artifacts during execution is a finding.

**3.10 — Scorecard.** Grade per CM-11B scoring criteria:

- **PASS:** 0 findings across all audited dimensions (3.1–3.9).
- **CONDITIONAL:** 0 Critical findings and ≤3 Important findings.
- **FAIL:** any Critical finding, or >3 Important findings.

Record the full consistency audit results and scorecard.

### Step 4: Gap and Quality Analysis

> Skip if `--focus` excludes `quality` / `standards` / `domain` / `architecture` / `completeness` / `all`.

Deploy an Audit Team (CM-25A) — parallel per-dimension analysis. Prose-anchored: every gap classified as prose-relative or domain-standard-relative.

**4.1 — Completeness.** Are there functional areas implied by the project scope that no phase addresses? Edge cases that should be handled but are not mentioned? Integration points assumed but not explicitly tasked? Deployment, monitoring, or operational concerns that are missing?

**4.2 — Quality (TM-13 thresholds and success metrics).** For every phase: (a) does it have a clear, measurable success metric? (b) are acceptance criteria specific and testable? (c) do task counts stay within the ≤10 task, ≤5 file, ≤2000 token thresholds? (d) are mixed concerns properly separated? Any phase exceeding thresholds without a sub-phase split is a finding.

**4.3 — Standards.** Does the plan specify all necessary technical standards — linting, formatting, type checking, testing framework, code-coverage targets, security scanning, documentation format? Are these consistent with the preamble's mandates?

**4.4 — Domain Bundles.** Based on the declared domain, are domain-specific requirements addressed? (Web app: accessibility, CORS, CSP, rate limiting, auth. ML: reproducibility, data versioning, experiment tracking. API: versioning, pagination, error codes, rate limiting.)

**4.5 — Architecture (roadmap, milestones, layer compliance).** Is the week-by-week roadmap realistic? Are milestones clear and measurable? Is the dependency graph optimized for parallelization? Is Phase 1 delivering the fastest path to a first tangible result? **Layer boundary verification (CM-27):** if the project warrants clean architecture (3+ modules, SHARED+ seriousness, or the preamble declares layer structure), verify: (a) phases producing domain logic do not introduce infrastructure imports, (b) the dependency direction between planned modules respects the inward-only rule (Domain ← Application ← Infrastructure/Presentation), (c) testing strategy aligns with layer boundaries (domain = pure unit, application = mocked interfaces, infrastructure = integration), (d) no phase task bundles cross-cutting concerns that should be separated across layers.

**4.6 — Creative Quality (CM-21).** A mandatory quality gate, not a decorative assessment.

- **Language-standards compliance:** scan EVERY file for forbidden phrases (cognitive identity rule, Section 4). Any occurrence is a finding. Scan for required qualities (specificity, surprise, internal logic, generativity, tension) in substantive sections — architectural decisions, scope descriptions, strategic analysis.
- **Originality assessment:** does the plan contain at least one structurally novel element per substantive architectural decision? Are key concepts given named frameworks? Does the overall design demonstrate conceptual elegance or merely functional adequacy?
- **Filter 1 (Obvious Purge) compliance:** is there evidence that obvious / default solutions were identified and rejected in favor of non-obvious alternatives? If every architectural choice is the "standard" approach, this gate fails.
- **Filter 2 (Domain Exile) compliance:** is there evidence the problem was reframed through at least one foreign discipline?
- **Filter 3 (Inversion Press) compliance:** does at least one inverted assumption survive into the plan's design decisions?
- **Filter 4 (Combinatorial Explosion) compliance:** is there at least one cross-domain synthesis in the plan's architectural decisions?
- **Filter 5 (Aesthetic Demand):** would this plan make a staff engineer stop and think *"I have never approached it that way"*? Apply this as a final quality bar.
- **Seriousness scaling:** per cognitive identity rule, Section 2.

### Step 5: Risk Assessment

> Skip if `--focus` excludes `risk` / `all`.

Deploy an Audit Team (CM-25A) — risk assessment with cross-dimension inputs from Steps 2–4 (using only findings from steps that actually executed).

**5.1 — Consistency-Derived Risks.** Phantom references → dependency risk. Naming inconsistencies → integration risk. Interface mismatches → build-failure risk. Decision contradictions → implementation-confusion risk.

**5.2 — Strategic Risks.** Feasibility of the overall plan given the declared seriousness and scope. Dependency fragility — which single phase failure would cascade most widely? Scope-creep indicators. Technology risk. Skill / knowledge gaps.

**5.3 — Top 3 Failure Risks.** Identify the three most likely failure modes with specific prevention strategies for each. These are concrete, not generic (not "insufficient testing" but "Phase 04's database migration has no rollback strategy if the schema change corrupts existing data").

### Step 6: Synthesis

**6.1 — Findings Registry.** Compile EVERY finding from all executed steps into a single registry. If `--focus` narrowed scope, note which dimensions were audited and which were excluded. Each finding includes:

- **ID:** sequential (F1, F2, ...)
- **Category:** Prose Fidelity / Consistency / Quality / Risk / Creative
- **Severity:** Critical (blocks execution, structural failure) / Important (degrades quality, creates risk) / Advisory (improvement opportunity, minor inconsistency)
- **Evidence:** exact quote, file location, cross-reference target
- **Impact:** what goes wrong if this finding is not addressed
- **Location:** specific file(s) and section(s) affected
- **Fix Action:** specific proposed remediation, not a vague "review" or "address"
- **Remediation Class:** mechanical / judgment / defer / waive
- **Status:** open / resolved / operator-waived / deferred-to-maintenance

**6.2 — Gate Determination.** Gate only on audited dimensions. If Step 3 ran: Internal Consistency ≥ CONDITIONAL required. If Step 2 ran: Prose Fidelity ≥ CONDITIONAL required. If either executed scorecard is FAIL: at PUBLIC_LAUNCH → execution is hard-blocked, no override; at SHARED → execution is blocked until addressed, but Product Owner override is permitted (log rationale in PLAN-NOTES.md); at PERSONAL_USE → advisory only, warn the user but do not block. If `--focus` excluded a dimension, that dimension's gate is deferred — neither passed nor failed, and must be audited in a subsequent full review before execution at SHARED+.

**6.2.1 — Strict Zero-Open-Finding Terminal Gate.** Independent of per-scorecard CONDITIONAL tolerance, the terminal handoff verdict to `/plan-execute` is PASS only when the post-remediation Findings Registry has zero `open` findings. Every finding is `resolved`, `operator-waived` with logged rationale in PLAN-NOTES.md, or `deferred-to-maintenance` with an explicit out-of-scope rationale and source anchor. A CONDITIONAL scorecard that still carries open findings is not passing; it loops through remediation or exits BLOCKED. Write the terminal verdict and open-finding count to the Handoff Manifest and PROGRESS.md Review Summary.

**6.3 — Summary.** Present findings grouped by category and severity. State the single biggest structural issue in the plan — the one finding that, if fixed, would improve the plan more than any other.

**6.4 — Clean Bill.** If ZERO findings across all executed steps: (a) in normal runs, write scorecard grades (all PASS) to PLAN-NOTES.md `## Review Scorecards` and PROGRESS.md Review Summary, then skip Steps 7–10, proceed directly to Step 11C (skipping 11A/11B since no revisions were applied), then continue to Step 12; (b) in `--dry-run`, do not write files and report the would-write targets only, then proceed directly to Step 6.6 and STOP. A clean bill requires that EVERY in-scope element in the Pre-Audit Baseline registry (Step 1) has been individually verified and marked clean. If any in-scope element was not examined, the review is incomplete — not clean. If `--focus` narrowed scope, the clean bill applies only to audited dimensions — state explicitly which dimensions were not audited and include a `Review Scope:` field listing audited/unaudited dimensions.

**6.5 — User Rejects All Revisions.** If findings exist but the user rejects all proposed revisions → skip Steps 10–11A/11B, proceed to Step 11C with pre-revision scores as final, then continue to Step 12. Log the user's rationale in PLAN-NOTES.md.

**6.6 — Dry-Run Exit.** If `--dry-run`: present scorecards, findings registry, risk assessment, and gate determination. **Do NOT write any files, create or evolve artifacts, or proceed to Q&A or revisions. STOP.**

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

**STOP. Never apply changes without user approval.** Present:

- Total number of proposed revisions
- Breakdown by severity
- The single most impactful revision highlighted
- Clear instruction that no changes will be made until the user approves

Invoke the structured-inquiry channel: question `Which proposed revisions should apply to the plan suite?`; header `Revisions`; options:
  - `Approve all (Recommended)`:
    rationale: Applies every proposed revision in Step 10; the revision-impact map and post-revision verification cover the entire revision set as one cohesive cohort.
    recommendation: recommended — cites class 5 rule citation: `commands/plan-review.md` Step 8 (Propose Revisions — every revision is documented with severity, rationale, and blast radius, satisfying the prerequisite for cohesive application) and class 6 observed-state: Step 6's Findings Registry surfaces every finding with evidence, indicating the proposed revision set is the operator-reviewable cohesive cohort.
    default-pointer: Approve all — safe because Step 11 Final Verification re-scores every audited dimension, catching any regression introduced by the revisions.
  - `Approve a subset`:
    rationale: User specifies which revisions to apply and which to reject via Other-text or follow-up; only approved revisions apply in Step 10, rejected revisions are logged with rationale in PLAN-NOTES.md, and Step 11 re-runs on the partial revision set.
    recommendation: acceptable
    default-pointer: Approve all — partial approval requires the operator to map per-revision dispositions, while the cohesive revision set is the operator-reviewable cohort.
  - `Reject all revisions`:
    rationale: Proceeds to the Step 6.5 path; the existing plan suite is preserved at its current state with the operator's rationale logged in PLAN-NOTES.md.
    recommendation: discouraged — cites class 5 rule citation: `rules/operational-mandates.md` CM-1 (Critical Evaluation — push back when suboptimal) and class 6 observed-state: Step 6 surfaced findings with severity classifications, indicating substantive defects exist that rejection leaves unresolved.
    default-pointer: Approve all — rejecting all revisions leaves the surfaced findings unresolved, propagating risk into downstream execution; approval addresses the findings cohesively.
  `multiSelect: false`.

### Step 10: Apply Revisions

Deploy an Implementation Team (CM-25A) for parallel non-overlapping revisions — each agent handles revisions in non-overlapping files (CM-25E).

**10.1** Pre-revision impact analysis → Revision Impact Map. For each revision, trace every file and element it affects. Identify revision pairs whose targets overlap or whose changes interact. If revisions have overlapping file targets, partition into conflict-free groups — execute each group as a parallel wave (non-overlapping files within each wave; waves execute sequentially). When several revisions target the same file(s), apply sequentially in severity order (Critical first) without deploying an Implementation Team.

**10.2** Apply with cross-reference tracking. Classify each applied revision as STRUCTURAL (adds/removes phases, changes the dependency graph, or alters architectural decisions) or REFINEMENT (modifies task scope, updates acceptance criteria, or fixes inconsistencies within existing phases). Bump the plan's semver: STRUCTURAL → MAJOR (vN.0.0), REFINEMENT → MINOR (vN.M.0), pure-typo or formatting fix → PATCH (vN.M.P). Append each applied revision to the Revision History table as `vX.Y.Z | YYYY-MM-DD | classification | summary`.

**10.3** Post-revision checklist: every proposed revision applied; every blast-radius impact checked; no new inconsistencies introduced by the revisions themselves. If a revision introduces a new inconsistency, that is a Critical finding requiring immediate re-revision before proceeding.

**10.4** If a STRUCTURAL revision (phases added/removed, dependency graph changed): update the PROGRESS.md phase tracker, counts, and dependency references to reflect the new plan structure.

**10.5** Findings status update: after each applied revision, update the Findings Registry row from `open` to `resolved` only when Step 11 re-checks the finding's exact evidence locus. Operator-waived and deferred-to-maintenance statuses require a rationale, source anchor, and downstream routing entry; they never silently count as resolved.

### Step 11: Final Verification

Deploy an Audit Team (CM-25A) for parallel re-scoring. This step re-applies the same rigorous, blind, exhaustive methodology from Steps 2–3 — not a cursory re-check. Re-check only dimensions that were audited (i.e., steps that executed per `--focus` scope).

**11A — Prose Fidelity Recheck.** If Step 2 executed: re-score the full traceability matrix on the revised plan. The post-revision score MUST be ≥ the pre-revision score. If post < pre (a revision degraded prose fidelity): identify the offending revision(s), revert them, re-score, and escalate to the user if still regressing.

**11B — Internal Consistency Recheck.** If Step 3 executed: re-score ALL consistency dimensions on the revised plan. The post-revision score MUST be ≥ the pre-revision score. If post < pre: same revert-and-escalate procedure. Pay particular attention to consistency dimensions the revisions touched — a revision that touches one consistency dimension also touches every dimension that cross-references it, and a fix in one dimension can introduce a new inconsistency in any of the cross-referencing dimensions.

**11B.1 — Update Stored Scorecards.** Write post-revision scorecard grades to PLAN-NOTES.md `## Review Scorecards` (overwriting pre-revision grades). Update PROGRESS.md Review Summary with post-revision grades so downstream commands (plan-execute, plan-status) read current scores. If `--focus` narrowed scope, include a `Review Scope:` field listing audited and unaudited dimensions — plan-execute uses this to detect partial coverage at SHARED+.

**11C — Collective Coherence.** Final coherence verification:

- Appendix checklist: verify all mandatory files exist and are properly cross-referenced.
- Verification assertions: run the key assertions from the Master Plan.
- Verify the Revision History row was appended with the correct classification (STRUCTURAL/REFINEMENT/PATCH per Step 10.2) and the plan version bumped accordingly.
- If revisions were applied: compare pre-revision and post-revision scorecards side by side (confirm post ≥ pre for each audited dimension).
- If no revisions (clean-bill path): confirm scorecards from executed audit steps meet gate thresholds and present as final scores.
- Findings Registry: verify zero `open` findings remain. If any finding remains open, return to Step 8 or exit BLOCKED; do not hand off to `/plan-execute`.
- **Final Completeness Assertion:** revisit the Pre-Audit Baseline registry from Step 1. Confirm every in-scope element has been individually verified. If any in-scope element remains unverified, the review is incomplete — examine it now. If `--focus` narrowed scope, state explicitly which dimensions were audited and which remain unaudited.

### Step 11.5: End-of-Command Synthesis (D6)

Just before review-report finalization at Step 12 handoff, fire ONE structured inquiry per D6 (Q-022) with the spec §7.4 form. The invocation MUST satisfy `rules/interactive-questions.md` §2 (canonical schema) + §3 (three-segment body) + §4.1 (closed recommendation taxonomy) + the H4/H6 invariants from `rules/interactive-questions-sweep-matchers.md` (every option carries all three body segments; the `(Recommended)` label postfix bidirectionally binds the body `recommendation: recommended` value):

- `question:` `Review complete. Are there any deferred findings or improvements to surface before finalization?`
- `header:` `End synthesis`
- `multiSelect:` `false`
- Option `All clear (Recommended)`:
  - `rationale:` No deferred findings; review report is finalized and the augmented Handoff Manifest emits.
  - `recommendation:` recommended — cites class 6 observed-state: Step 11 Final Verification confirmed post-revision PASS scorecards across every audited dimension.
  - `default-pointer:` no-default: user decision required (review's final-finding ratification surface).
- Option `Surface findings`:
  - `rationale:` Operator surfaces additional findings before finalization; agent extends the Findings Registry and re-runs partial verification on the new findings.
  - `recommendation:` acceptable
  - `default-pointer:` no-default: user decision required.
- Option `Defer findings`:
  - `rationale:` Operator notes findings but defers; agent appends `[Deferral — out-of-scope: <description>; tracking: <PLAN-NOTES.md or follow-up issue>]` per `rules/disclosure-ledger.md`.
  - `recommendation:` acceptable
  - `default-pointer:` no-default: user decision required.

The selection routes the post-synthesis flow: `All clear` proceeds directly to Step 12 handoff and Manifest emission only when the Findings Registry has zero open findings; `Surface findings` extends the Findings Registry, re-runs the affected dimension's audit (Steps 2/3/4 as applicable), and re-runs Step 11 Final Verification on the augmented finding set; `Defer findings` appends the deferral marker to the disclosure ledger and proceeds to Step 12 only when the finding is explicitly out of scope for the source suite and routed via the augmented Manifest's `deferrals` field per `rules/disclosure-ledger.md`.

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
- **Base protocol:** Agent Teams (CM-25) with return contracts — deployment scales with seriousness per the agent-orchestration rule (Optional at EXPLORING, Encouraged at PERSONAL_USE, Required at SHARED+). Default token budgets per CM-25C: Research 500, Audit/Quality 200, Implementation 500. Error recovery (CM-18), 3-failure escalation. Session resilience (CM-24/CM-14). Always-on rules (CM-22–28) enforced at all steps.

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
| CM-17 | Steps 1–5, 10–11: Agent Teams |
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

```mermaid
%%{ init: { "theme": "neutral" } }%%
%% verified: 2026-04-27 %%
%% provenance: commands/plan-review.md §Workflow %%
%% cross-reference: src/apothem/commands/ (slash-command cohort) %%
flowchart TD
    Start[/plan-review invoked/] --> Suite{Suite files present?}
    Suite -->|no| Recommend[STOP — recommend /plan-generate]
    Suite -->|yes| Focus{--focus argument?}
    Focus -->|yes| Narrow[Audit scoped dimensions only]
    Focus -->|no| Full[Audit all dimensions]
    Narrow --> Baseline[Pre-Audit Baseline registry]
    Full --> Baseline
    Baseline --> ProseAudit{Prose fidelity audited?}
    ProseAudit -->|yes| ProseScore[Prose Fidelity Scorecard]
    ProseAudit -->|no| Skip1[Skip prose-fidelity dimension]
    ProseScore --> ConsistAudit{Internal consistency audited?}
    Skip1 --> ConsistAudit
    ConsistAudit -->|yes| ConsistScore[Internal Consistency Scorecard]
    ConsistAudit -->|no| Skip2[Skip internal-consistency dimension]
    ConsistScore --> Findings[Compile findings registry · severity-count verification]
    Skip2 --> Findings
    Findings --> DryRun{--dry-run?}
    DryRun -->|yes| EmitOnly[Emit scorecards + findings · halt]
    DryRun -->|no| AnyFindings{Findings present?}
    AnyFindings -->|no| Done[Emit clean-bill report]
    AnyFindings -->|yes| AskRevise[structured inquiry: revise · accept-as-is · abort]
    AskRevise -->|revise| Apply[Apply revisions · update plan version]
    AskRevise -->|accept| Done2[Emit findings without revision]
    AskRevise -->|abort| Halt[STOP]
    Apply --> Rescore[Re-run scorecards on revised plan]
    Rescore --> Gate{Post-revision PASS?}
    Gate -->|yes| Done3[Emit revision-impact map · halt]
    Gate -->|no| AskFail[structured inquiry: re-revise · accept · abort]
```

The tree distinguishes scope-narrowing forks (`--focus` reduces dimensional
coverage), audit-mode branches (each dimension activates its own scorecard),
and revision-loop forks where operator decision drives whether findings flow
into applied revisions or stand as advisory output.

## Recommended Next Step

Invoke `/plan-design` when the suite is architecture-bearing; otherwise invoke `/plan-execute`. The canonical sequence routes `/plan-review → /plan-design → /plan-execute`, and an architecture-bearing suite MUST produce `_inputs/design.md` before execution, so `/plan-design` is the successor whenever the suite carries architectural decomposition. A non-architecture-bearing suite skips `/plan-design`, and `/plan-execute` consumes this command's scorecards directly — record the `/plan-design` skip rationale in PLAN-NOTES.md per the conditional-routing contract.

## Bindings (§0.j five-direction)

- **Drives →** ● Every Review Scorecards emission to PLAN-NOTES.md `## Review Scorecards`. ● Every revision-loop application across the plan suite. ● Every PASS/FAIL verdict gating downstream `/plan-execute` runs at SHARED+ per the Review Gate at Step 2 of plan-execute. ◐ The nine planning techniques' application across the audit dimensions (techniques 1, 2, 4 mandatory at SHARED+).
- **Satisfies →** ● the commands registry row "/plan-review". ● CM-11A Prose Fidelity + CM-11B Internal Consistency + CM-11C Gates.
- **Established by ↑** ● the `/plan` pipeline. ● the commands registry. ● CM-11 (Plan Integrity).
- **Gated by ←** ● The presence of a generated plan suite (PREAMBLE.md + MASTER-PLAN.md + PROGRESS.md + PLAN-NOTES.md + phases/). ● The presence of `_spec/spec.md` for prose-fidelity audits.
- **Cross-bound with ↔** ↔ `commands/plan-generate.md` (review audits the suite generate produces). ↔ `commands/plan-audit.md` (audit wraps review findings into a closed remediation loop). ↔ `commands/plan-execute.md` (execute's Step 2 Review Gate consumes this command's scorecards). ↔ `rules/planning-techniques.md` (the nine techniques operationalize here per the rule's seriousness scaling). ↔ `rules/clean-room-generation.md` (review revisions follow the §3 Re-Writing Protocol).
