<!-- SPDX-License-Identifier: MIT -->

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
