---
name: "code-audit"
description: "Cross-file forensic code audit operating at the repository-corpus scope rather than the per-file craft scope — six adversarial phases (Input Ingest · Cross-File Dependency Walk · Type-Hint + Coverage Audit · Dead-Code + Duplicate Detection · Architectural-Integrity Audit · Findings Emission + Validation Gate) interrogate cross-file consistency, hidden coupling, layer-boundary violations, type-hint accuracy under `mypy --strict`, test-coverage gaps against critical paths, dead code via `vulture`, duplicate code via `pylint --disable=all --enable=duplicate-code`, and architectural integrity at the implementation layer. Findings carry severity (HIGH / MEDIUM / LOW) with concrete-driver rationale and land at the consuming suite's `_inputs/code-audit-findings.md` ready for review-fortress consumption. Distinct from `/code-review` (per-file craft) — `/code-audit` is the cross-file forensic surface."
argument-hint: "[path/to/repo/] [--focus AREA] [--dry-run]"
disable-model-invocation: true
allowed-tools: "Read, Glob, Grep"
metadata:
  version: "0.1.0"
  updated: "2026-10-02"
  portability: "universal"
---

<!-- SPDX-License-Identifier: MIT -->

# /code-audit — Cross-File Forensic Code Audit

---

> **Reference files.** This skill's reference files sit in the `references/` directory next to this SKILL.md (`${CLAUDE_SKILL_DIR}/references/`). Each *Moved to* pointer below names one of them and says when to read it. A context compaction discards file content you read earlier: after one, you MUST re-read the reference files that govern your current step.

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

> Moved to `references/pipeline-contract.md`. MUST read it before the first step, and again before the final step or any handoff. Covers: Pipeline position; Audit-fortress sequence position; Handoff Manifest; Pre-flight inquiry set; Pre-emission gate.

---

## Foundational Stanzas

> Moved to `references/foundational-stanzas.md`. MUST read it before the first step; it binds every step. Covers: Refusal & Escalation; Output Surface; File-Authoring Contract; Structured Inquiry on Ambiguity.

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

> Moved to `references/step-06-findings-emission-validation-gate.md`. MUST read it in full before executing this step.

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

> Moved to `references/decision-tree.md`. SHOULD read it when a branch, gate failure, or state transition is unclear.

---

## Output

- The findings artifact at the consuming suite's `_inputs/code-audit-findings.md` (per-severity finding sections + per-phase tool-output attestations + open-question inventory + validation-gate attestation).
- The updated Handoff Manifest at the suite's `_inputs/handoff-manifest.yml` with the findings-artifact path + per-severity finding counts + per-phase tool-output attestations + Phase 5 gate-attestation block.
- An optional dependency-graph working file at the suite's `_inputs/code-audit-dependency-graph.md` (Phase 1 corpus-wide dependency enumeration + Phase 2 / Phase 3 tool-output snippets).
- An optional input-inventory working file at the suite's `_inputs/code-audit-input-inventory.md` (Phase 0 read inventory).

---

## Recommended Next Step

Invoke `/security-audit` to advance the audit-fortress sequence; `/security-audit` is the canonical successor per the 11-command audit-fortress canonical sequence.
