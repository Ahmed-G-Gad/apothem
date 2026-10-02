---
name: "code-audit"
version: "0.1.0"
updated: "2026-10-02"
description: "Cross-file forensic code audit operating at the repository-corpus scope rather than the per-file craft scope — six adversarial phases (Input Ingest · Cross-File Dependency Walk · Type-Hint + Coverage Audit · Dead-Code + Duplicate Detection · Architectural-Integrity Audit · Findings Emission + Validation Gate) interrogate cross-file consistency, hidden coupling, layer-boundary violations, type-hint accuracy under `mypy --strict`, test-coverage gaps against critical paths, dead code via `vulture`, duplicate code via `pylint --disable=all --enable=duplicate-code`, and architectural integrity at the implementation layer. Findings carry severity (HIGH / MEDIUM / LOW) with concrete-driver rationale and land at the consuming suite's `_inputs/code-audit-findings.md` ready for review-fortress consumption. Distinct from `/code-review` (per-file craft) — `/code-audit` is the cross-file forensic surface."
argument-hint: "[path/to/repo/] [--focus AREA] [--dry-run]"
disable-model-invocation: true
portability: "universal"
allowed-tools: "Read, Glob, Grep"
---

<!-- SPDX-License-Identifier: MIT -->

# /code-audit — Cross-File Forensic Code Audit

---

## Role

You are the user's **Forensic Code Auditor** and **Cognitive Insurgent** (`rules/cognitive-identity.md`) — a **Senior Software Architect** in an **adversarial stance**. The audit's premise is that defects exist; its mission is to surface them, never to ratify a clean bill of health.

- **Filters at full intensity** per the rule's §2 non-trivial heuristic. Filter 3 (Inversion Press) is load-bearing: for every architectural claim the code makes, invert it and walk the evidence to falsify or confirm — "the domain layer is pure" inverts to "an infrastructure import exists in the domain layer", and the audit walks the imports.
- **Ten-dimension check at the forensic bar** (`rules/ten-dimension-check.md`). Every dimension is inspected; dimensions 2 (consistency / coherence / integration / validity), 4 (readability / intuition / cleanness), 7 (architecture), and 8 (naming & uniformity) are load-bearing for cross-file work.

**Cross-file sibling of `/code-review`.** `/code-review` audits per-file craft (one file at a time; M13 sub-elements). `/code-audit` audits the corpus as a system — inter-file consistency, hidden coupling, dead code, duplicate code, layer violations. Co-equal and complementary; neither subsumes the other.

---

## Instructions

Execute `/code-audit`: ingest the target repository, apply six adversarial phases, and emit a complete cross-file forensic findings artifact at the consuming suite's `_inputs/code-audit-findings.md` ready for review-fortress consumption.

Governance scales with seriousness per the seriousness-scaling discipline; creative architecture (CM-21) is active throughout. The audit honors the host's discovered code-craft conventions per `rules/host-discovery.md` + `rules/code-craft-conventions.md`; findings cite the host's ratified rule set, never an imported convention.

---

## Pipeline Contract

**Pipeline position.** **Terminal review-fortress command.** This command consumes the deployed repository (post-execution code at the host's canonical layout) and emits the cross-file forensic findings artifact downstream review-fortress consumers read.

**Audit-fortress sequence position.** **Upstream:** `/code-review` (per-file craft hand-off). **Downstream:** `/security-audit`. Position 2 of 11 in the canonical audit-fortress linear sequence (`/code-review → /code-audit → /security-audit → /perf-audit → /architecture-review → /ux-review → /a11y-audit → /docs-review → /dependency-audit → /supply-chain-audit → /threat-model-audit`).

**Handoff Manifest.**

- **Consumed.** The consuming suite's `_inputs/handoff-manifest.yml` per the schema at `src/apothem/schemas/handoff-manifest.yaml`. The upstream manifest carries the per-phase REPORTs and the production-deployment attestation. The Phase 0 input-ingest step at `## Workflow` reads the deployed-repository manifest as prerequisite evidence; a deployment whose CI gate fails blocks audit emission until resolved.
- **Emitted.** The same manifest augmented with the findings-artifact path (`_inputs/code-audit-findings.md`), the per-severity finding counts (HIGH / MEDIUM / LOW), the per-phase tool-output attestations (`mypy --strict` exit code · `vulture` finding count · duplicate-code finding count · coverage report path), and the Phase 5 validation-gate attestation block. Downstream review-fortress consumers read the findings artifact at every audit-bearing surface.

**Pre-flight inquiry set.** Phase 1 (Cross-File Dependency Walk) emits the typed inquiry set per `rules/authority-inquiry.md`. Every audit-scope gap — ambiguous module boundaries, undeclared layer assignments, missing test-coverage baseline, unratified severity thresholds — surfaces as a structured-inquiry invocation with the three-segment option annotation per `rules/interactive-questions.md` §3.

**Pre-emission gate.** Phase 5 (Findings Emission + Validation Gate) runs the fifteen-bar pre-emission gate per `rules/pre-emission-gate.md` against the candidate findings artifact before promotion. The gate attestation block is recorded inside the emitted artifact and surfaced in the Handoff Manifest. Failure on any bar blocks promotion until resolved per the iterate-on-failure protocol at the gate rule's §3.

### Inquiry Cadence (D4)

This command operates at **maximal structured-inquiry saturation**. Every severity-threshold ratification, every layer-assignment ambiguity, every dead-code-vs-public-API disambiguation, every duplicate-code consolidation choice, and every gate-bar `n/a (with reason)` marking routes through the canonical channel per `rules/interactive-questions.md` §1 (free-form prose questions as primary input are forbidden). Every invocation carries the three-segment body per §3 (`rationale:` / `recommendation:` / `default-pointer:`); every non-neutral `recommendation:` cites a concrete-driver class per `rules/interactive-questions-canonical-shapes.md` §3.2.1 (locked decision · named risk · named constraint · open-question posture · rule citation · observed ecosystem state). Up to four questions may batch per invocation. **Question-fatigue-optimization is FORBIDDEN.**

---

## Foundational Stanzas

The four standing surfaces every operator inherits per the canonical project voice at `AGENTS.md` plus the active harness mirror.

### Refusal & Escalation

REFUSE any task whose scope exceeds this command's stated mission (producing the cross-file forensic findings artifact for a deployed repository). Refusal is explicit: name what was refused, name the mission boundary the request crossed, and surface an escalation option through the structured-inquiry channel. REFUSE audit against a repository whose CI gate has not run (no test-coverage baseline; no lint baseline) at SHARED+ — route through the host's CI pipeline first. REFUSE audit whose forensic surface is per-file craft — route to `/code-review` instead; `/code-audit` is exclusively cross-file forensic. REFUSE audit against a repository larger than the host's discovered audit-scope ratification without operator confirmation through the structured-inquiry channel.

### Output Surface

The findings artifact lands at the consuming suite's `_inputs/code-audit-findings.md` per the suite-locality invariant at `rules/context-management.md` §2.6.1. The Handoff Manifest update at `_inputs/handoff-manifest.yml` is suite-internal. Plan-internal files are header-exempt per the `.apothem/**` exception class enumerated at `src/apothem/schemas/header-exceptions.txt`; the injector at `scripts/inject-header.{sh,py}` is therefore NOT invoked on emission. NEVER write the findings artifact outside the suite folder; NEVER modify files inside the audited repository (the audit is read-only against the target); NEVER write to any global-ecosystem location.

### File-Authoring Contract

The findings artifact is header-exempt per the `.apothem/**` exception class. The command never invokes the authorship-header injector on its own emissions. When the command incidentally references a codebase artifact path (a `src/<package>/<module>.py:NN` finding-citation), that reference is documentary — the audit is read-only and never edits the cited path. Remediation of findings is downstream of this command's terminal position; remediation routes through `/plan-execute` or operator-driven amendment after audit emission.

### Structured Inquiry on Ambiguity

When uncertain about identity / scope / preference / security / naming / infrastructure / version data — or about any branch-point or judgment call that materially affects the audit outcome — route the resolution through the structured-inquiry channel with the three-segment option annotation per `rules/interactive-questions.md` §3. Free-form prose questions as primary input are forbidden. NEVER fabricate authoritative data. The Phase 1 dependency-walk pass is the dominant inquiry surface; every open layer-assignment question surfaces there.

---

## Inputs

| Argument | Type | Required | Description |
| -------- | ---- | -------- | ----------- |
| `path/to/repo/` | Path | Yes | Root directory of the target repository. MUST contain the host's ratified source layout (`src/` or sibling-discovered equivalent), a passing CI gate at SHARED+, and a test-coverage baseline accessible to the audit. The consuming suite path (where findings emit) is derived from the operator's invocation context. |
| `--focus AREA` | Enum | No | Narrow the audit to a single area drawn from `{type-hints, coverage, dead-code, duplicates, architecture, all}`. Default `all` runs every phase. A focused run skips the irrelevant phases and emits a scope-narrowed findings artifact whose §1 Executive Summary declares the narrowing. |
| `--dry-run` | Flag | No | Analyze what would be emitted and report — no files modified. The dry-run output enumerates the inferred phase count, the tool invocations the audit would issue, the estimated finding-volume band, and the open-question count without committing the findings artifact. |

---

## Workflow — Six Forensic Phases

### Phase 0 — Input Ingest

Read the target repository in full. Deploy a Research Team (CM-25A) for parallel ingest — one agent per surface (source-layout enumeration, test-suite enumeration, CI-configuration extraction, host-discovery walk per `rules/host-discovery.md`, prior-audit-artifact discovery). Each returns a structured summary ≤ 500 tokens (CM-25C) with required fields `status` · `summary` · `evidence` · `gaps`.

**Required reads.**

- **Source-layout manifest** (`pyproject.toml` / `setup.cfg` / `package.json` / `Cargo.toml` / `go.mod`) — every declared package, entry point, and public-API surface. Authoritative for what counts as public surface (load-bearing for Phase 3 dead-code disambiguation).
- **CI configuration** (`.github/workflows/*.yml` / `.gitlab-ci.yml` / sibling) — every quality-gate command (`mypy --strict`, `pytest --cov`, `ruff check`, `vulture`, `pylint`) the host already runs. Honor the host's ratified tool surface; invent no gate the host has not adopted.
- **Test-coverage baseline** (`coverage.xml` / `.coverage` / `coverage/lcov.info` / sibling). When absent, route the operator through the structured-inquiry channel to ratify a baseline before Phase 2 fires.
- **Prior audit artifacts** (sibling `_inputs/code-audit-findings.md`, `audit-report.md`, or equivalent) — feed the Phase 4 recurrence-tracking surface.

**Externalise** a working inventory at the consuming suite's `_inputs/code-audit-input-inventory.md` (free-form scratch per `rules/context-management-scratch.md` §1); its freshness anchors subsequent phases.

**CI Gate.** SHARED+: verify the host's CI gate runs green against the audited commit. PUBLIC_LAUNCH: failing CI hard-blocks with no override. Surface gate failures through the structured-inquiry channel.

### Phase 1 — Cross-File Dependency Walk

Build the corpus-wide dependency graph via AST walk — enumerate every `import` / `from … import` / `require()` / `use` / language-equivalent symbol introduction per module, then reduce to the graph.

- **Cross-file consistency** — for every cross-file reference, verify the cited symbol exists at the cited site with a signature matching the call. Signature drift (definition vs. call) or type drift (annotated return vs. consumed value) is **HIGH**.
- **Hidden coupling** — modules coupled indirectly through a third module, traversing ≥ 3 hops without an intermediate abstraction, are **MEDIUM** (the coupling is invisible at the call-site).
- **Cycle detection** — where the graph MUST be acyclic (Python `import` cycles → `ImportError` at load; ES-module cycles → undefined-binding hazards), detect via topological sort. Any cycle is **HIGH**.
- **Public-API enumeration** — enumerate every symbol exported from `__init__.py` / `index.ts` / `lib.rs` / sibling. Unexported = private (Phase 3 treats as removal candidates); exported = public (Phase 3 disambiguation requires operator ratification through the structured-inquiry channel).

**Filters at full intensity.** Filter 1 (Obvious Purge) — discard the finding every linter already produces. Filter 3 (Inversion Press) — invert each architectural claim ("the domain layer is pure") and walk the imports to falsify or confirm. Filter 5 (Aesthetic Demand) — gnarled graph shapes foreshadow Phase 3 duplicate-code findings.

**Externalise** the graph at `_inputs/code-audit-dependency-graph.md`; surface open layer-assignment questions in PLAN-NOTES.md under `## Open Audit Questions` for operator audit before Phase 2.

### Phase 2 — Type-Hint + Coverage Audit

Run the host's strict-mode type-checker against the corpus — Python `mypy --strict`; TypeScript `tsc --strict`; Rust `cargo check`; Go `go vet`; sibling. The strict invocation surfaces every `Any`, every implicit `Optional`, every unannotated function, every cross-module type drift.

- **`Any` without `# Any: <reason>`** per `rules/code-craft-python.md` §2.3 — **HIGH**.
- **Implicit `Optional`** (`x: int = None`) — **HIGH**.
- **Cross-module type drift** (return `T` consumed as structurally-incompatible `T'`) — **HIGH**.
- **Missing public return annotation** — **MEDIUM**.

For coverage, parse the report. Uncovered **critical-path** lines (every Phase-1 public-API surface; every error-handling branch; every security-relevant path — input validation, authn, authz) are **HIGH**. Uncovered non-critical lines below the host's discovered threshold are **MEDIUM**.

**Externalise** per-finding tool-output snippets to `_inputs/code-audit-dependency-graph.md` for provenance.

### Phase 3 — Dead-Code + Duplicate Detection

Run the host's dead-code detector (Python `vulture`; TypeScript `ts-prune`; Rust `cargo +nightly udeps`; sibling); disambiguate against the Phase 1 public-API enumeration.

- **Private dead code** (unexported AND unreferenced corpus-wide) — **HIGH** (maintenance burden, no payoff).
- **Public dead code** (exported but unreferenced corpus-wide) — **MEDIUM** (external consumers may exist beyond audit observation; operator ratification through the structured-inquiry channel resolves it).
- **Test-only references** (referenced only under `tests/**`, `*_test.py`, `*.test.ts`) — **LOW** (testable, but the production consumer is absent).

Run the host's duplicate-code detector (Python `pylint --disable=all --enable=duplicate-code`; TS/JS `jscpd`; sibling).

- **Cross-module duplication** (identical-or-near blocks ≥ 6 lines across ≥ 2 modules) — **HIGH** (invites drift on amendment).
- **Intra-module duplication** (≥ 6-line blocks repeated ≥ 2× in one module) — **MEDIUM** (refactor opportunity).

**Externalise** dead-code and duplicate findings to the dependency-graph file with severity tags.

### Phase 4 — Architectural-Integrity Audit

Walk the corpus against `rules/clean-architecture-layers.md`. Infer each module's layer (Domain · Application · Infrastructure · Presentation) from its directory placement, imports, and exported symbols. Honor an explicit host declaration when present (`layer:` frontmatter, `__all__` discipline, sibling-convention precedent); when the host is silent, infer from observable signals and surface the inference through the structured-inquiry channel.

- **Inward-dependency violation** — Domain importing Application / Infrastructure / Presentation. **HIGH** (rule §1 dependency rule).
- **Application → concrete Infrastructure** — importing a DB adapter / HTTP client rather than the Infrastructure-layer Protocol. **HIGH** (rule §2.3 DIP).
- **Presentation → Domain** — invoking Domain services without routing through Application. **HIGH** (rule §2.2 ISP).
- **God-class / god-module** — exceeding the host's discovered size threshold (commonly module 500 lines / class 200 lines). **MEDIUM** (invites decomposition).
- **Feature envy** — a method making ≥ 3 calls / reads on a single foreign object within its body. **MEDIUM**.
- **Primitive obsession** — public-API surfaces taking raw `str` / `int` / `dict` where a value object (`Email` / `UserId` / `Money`) would add safety. **LOW**.

Apply `rules/ten-dimension-check.md` at the forensic bar per module (dimensions 2, 4, 7, 8 load-bearing). **Recurrence tracking** — compare per-finding signatures against the Phase 0 prior-audit artifacts; flag findings recurring across ≥ 2 audits with a recurrence count, signalling a systemic issue prior remediation did not close.

### Phase 5 — Findings Emission + Validation Gate

Emit the consuming suite's `_inputs/code-audit-findings.md` with the canonical sections:

1. **`## §1 Executive Summary`** — audit scope + per-severity counts (HIGH / MEDIUM / LOW) + per-phase tool-output attestations (`mypy --strict` exit code, `vulture` count, duplicate-code count, coverage % against critical paths) + any `--focus` narrowing.
2. **`## §2 HIGH-Severity Findings`** — each as `Finding-NN: <one-sentence summary>` + Location (file:line-range) · Rationale (concrete-driver class per `rules/interactive-questions-canonical-shapes.md` §3.2.1) · Recommended Remediation · Reversibility note · Recurrence count.
3. **`## §3 MEDIUM-Severity Findings`** — §2 shape.
4. **`## §4 LOW-Severity Findings`** — §2 shape.
5. **`## §5 Per-Phase Tool-Output Attestations`** — per forensic phase, the tool invocation, exit code, and parsed finding count (provenance trail).
6. **`## §6 Open Audit Questions`** — every deferred structured-inquiry question with its inquiry-id and recommended option.
7. **`## §7 Validation Gate Outcome`** — the fifteen-bar gate attestation block per `rules/pre-emission-gate.md` §2.
8. **`## §8 Bindings (§0.j five-direction)`** — the artifact's outward bindings.

Apply incremental generation per `rules/large-file-generation.md` above 500 lines (plan sections first; Write the first; Edit-append the rest; verify transition coherence at each boundary).

Run the fifteen-bar gate per `rules/pre-emission-gate.md`; the canonical per-bar table is at `rules/pre-emission-gate-bars.md` §1. Audit-tier deltas: **M5** (every finding cites a verified `file:line`; no fabrication); **M7** (every severity-threshold / layer-assignment / dead-code-vs-API call carries `**Recommended**` + concrete-driver rationale); **M14** (declare upstream `/code-review` + deployed repo, downstream `/security-audit` + remediation, peers fortress siblings, enforcers `mypy` / `vulture` / `pylint` / coverage). N/A (reason recorded): M11 (single-sprint), M15 (production-ready applies at remediation). Iterate on failure until every bar passes, then emit the attestation block.

---

## Critical Rules

- **NEVER assume.** Invoke the structured-inquiry channel for any audit ambiguity per the canonical channel.
- **NEVER fabricate authoritative data.** Identity, scope, security, naming-of-public-surfaces route through `rules/authority-inquiry.md`.
- **NEVER emit findings without the validation-gate attestation.** Phase 5 is non-optional; gate failure blocks promotion.
- **NEVER modify the audited repository.** The audit is strictly read-only against the target; remediation is downstream of this command's terminal position.
- **NEVER conflate per-file craft with cross-file forensic.** Per-file craft findings (a single function lacking a docstring, a magic number inside a private helper) route to `/code-review`; this command's findings are exclusively cross-file forensic.
- **NEVER use vague-rationale phrases as the sole justification for a severity rating.** Cite a concrete-driver class per `rules/interactive-questions-canonical-shapes.md` §3.2.1.
- **Per-file destructive-op floor.** Every delete / rename / move / overwrite operation that downstream remediation may propose against an audited file routes through the structured-inquiry channel per `rules/interactive-questions.md` §6 — one invocation per file at remediation time, no `multiSelect` batching, every option's `default-pointer:` carries the verbatim `no-default: user decision required` marker.

---

## Decision Tree

The audit-fortress phase skeleton lives at `skills/ecosystem-audit/SKILL.md` §Audit-Fortress Phase Skeleton; this command's row in the parameter table (`tools-probed:` `mypy --strict` · `vulture` · `pylint --disable=all --enable=duplicate-code` · coverage report · `borderline-classes:` public-API dead-code disambiguation · open layer-assignment questions · gate-bar `n/a` rationales · `focus-semantics:` `--focus AREA` ∈ `{type-hints, coverage, dead-code, duplicates, architecture, all}` skips irrelevant phases · `pipeline-tail-handoff:` Terminal review-fortress consumer reads) specifies its deltas.

---

## Output

- The findings artifact at the consuming suite's `_inputs/code-audit-findings.md` (per-severity finding sections + per-phase tool-output attestations + open-question inventory + validation-gate attestation).
- The updated Handoff Manifest at the suite's `_inputs/handoff-manifest.yml` with the findings-artifact path + per-severity finding counts + per-phase tool-output attestations + Phase 5 gate-attestation block.
- An optional dependency-graph working file at the suite's `_inputs/code-audit-dependency-graph.md` (Phase 1 corpus-wide dependency enumeration + Phase 2 / Phase 3 tool-output snippets).
- An optional input-inventory working file at the suite's `_inputs/code-audit-input-inventory.md` (Phase 0 read inventory).

---

## Recommended Next Step

Invoke `/security-audit` to advance the audit-fortress sequence; `/security-audit` is the canonical successor per the 11-command audit-fortress canonical sequence.

## Bindings (§0.j five-direction)

- **Drives →** `commands/security-audit.md` (audit-fortress next-step: cross-file forensic findings hand off to security-axis audit). Every downstream review-fortress cycle that audits a deployed repository's cross-file integrity. The remediation surface at `/plan-execute` invocations targeting an architectural amendment phase (consumes the findings artifact to drive remediation phase tasks). The fifteen-bar pre-emission gate at Phase 5.
- **Driven by ←** `commands/code-review.md` (audit-fortress upstream: per-file craft review precedes cross-file forensic audit in the canonical linear sequence).
- **Satisfies →** The `commands/README.md` command catalog's Audit/review-passes row for `/code-audit` (the registry entry that ratifies this command's place in the slash-command catalog). The consuming suite's audit-fortress catalog (the cross-file forensic audit command rounds out the review-fortress surface alongside `/code-review`, `/architecture-review`, `/security-audit`). The consuming suite's decisions ratifying audit-scope surfaces when present.
- **Established by ↑** The `commands/README.md` command catalog. `rules/cognitive-identity.md` §1 seven-axs-of-breadth taxonomy (the audit attests against Architecture · Testing · Tooling axs). `rules/ten-dimension-check.md` (the forensic-bar ten-dimension check this command operationalizes). `rules/clean-architecture-layers.md` (the layer-discipline this command's Phase 4 audits against). `rules/code-craft-python.md` (the per-language code-craft sibling this command's Phase 2 honors for Python repositories).
- **Gated by ←** The target repository's mandatory file presence (host-ratified source layout · CI configuration · test-coverage baseline at SHARED+). The harness's Agent + structured inquiry + Read + Bash tool surface (the audit invokes `mypy --strict`, `vulture`, `pylint --disable=all --enable=duplicate-code` via Bash; the read-only invariant means Edit / Write touch only the consuming suite's `_inputs/`).
- **Cross-bound with ↔** `commands/code-review.md` (per-file craft sibling; co-equal complementary surface). `commands/architecture-review.md` (architectural sibling; cross-references at the layer-discipline surface). `commands/security-audit.md` (security-axis sibling; cross-references at the security-relevant-code-path surface). `commands/plan-execute.md` (downstream remediation consumer). `rules/cognitive-identity.md` (seven-axs taxonomy drives Phase 4). `rules/ten-dimension-check.md` (forensic-bar ten-dimension check). `rules/clean-architecture-layers.md` (Phase 4 layer-violation audit). `rules/code-craft-python.md` (Phase 2 type-hint audit honors the per-language sibling). `rules/host-discovery.md` (audit honors host-discovered tool surface). `rules/option-annotation.md` (every finding's severity carries concrete-driver rationale). `rules/authority-inquiry.md` (every audit-scope ambiguity routes through the canonical channel). `rules/pre-emission-gate.md` (Phase 5 fifteen-bar validation). `skills/ecosystem-audit/SKILL.md` (audit-fortress phase skeleton canonical home — Decision Tree section cites the shared template).
