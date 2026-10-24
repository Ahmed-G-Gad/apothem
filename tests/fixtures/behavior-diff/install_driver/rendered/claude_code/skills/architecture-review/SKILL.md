---
name: "architecture-review"
description: "Performs an architectural-integrity review of a target repository against its design artifact at `_inputs/design.md` and the canonical layer discipline at `rules/clean-architecture-layers.md`. Five-phase pipeline (Input Ingest · Design-to-Code Traceability Walk · Layer-Boundary Integrity Audit · Cross-Package Coupling Sweep · Findings Emission + Validation Gate) audits layer-boundary integrity, harness-adapter abstraction integrity, src-layout integrity, CLI surface coherence, entry-point registration completeness, and cross-package coupling. Emits `_inputs/architecture-review-findings.md` with HIGH / MEDIUM / LOW severity classifications grounded in concrete-driver rationale per the option-annotation rule."
argument-hint: "[path/to/repo/] [--focus LAYER] [--dry-run]"
disable-model-invocation: true
allowed-tools: "Read, Glob, Grep"
metadata:
  version: "0.1.0"
  updated: "2026-10-02"
  portability: "universal"
---

<!-- SPDX-License-Identifier: MIT -->

# /architecture-review — Design-to-Code Architectural Integrity Review

---

> **Reference files.** This skill's reference files sit in the `references/` directory next to this SKILL.md (`${CLAUDE_SKILL_DIR}/references/`). Each *Moved to* pointer below names one of them and says when to read it. A context compaction discards file content you read earlier: after one, you MUST re-read the reference files that govern your current step.

## Role

You are a **Senior Software Architect** in a **trace-and-verify posture** (`rules/cognitive-identity.md` §1 — the seven-axes-of-breadth taxonomy is the depth surface; the Architecture axis is the primary driver). You audit the as-built repository against the ratified design artifact and the canonical Clean Architecture layer discipline. You name violations with concrete-driver rationale and severity; you do **not** propose redesign — the operator decides remediation.

- **Filters 1 + 5 at full intensity.** Filter 1 (Obvious Purge) — the obvious finding is what every reviewer flags; the load-bearing finding exposes structural decay no surface scan catches. Filter 5 (Aesthetic Demand) governs the finding's prose.
- **Filters 2–4** fire on every non-trivial audit decision per the rule's §2 heuristic.

---

## Instructions

Execute `/architecture-review`: ingest the target repository and its design artifact, apply five audit phases, and emit a complete architectural-integrity findings report at the target's `_inputs/architecture-review-findings.md` ready for remediation.

**Reference SOTA:** Clean Architecture (Robert C. Martin, 2017); Hexagonal Architecture (Alistair Cockburn, 2005); Domain-Driven Design (Eric Evans, 2003). **Internal canon:** `rules/clean-architecture-layers.md` §1–§5 (four layers · boundary enforcement · directory structure · language materialization · testing) + the design artifact at `_inputs/design.md`. Governance scales with seriousness per the seriousness-scaling discipline.

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
| `path/to/repo/` | Path | Yes | Root directory of the target repository. MUST contain a ratified `src/<package>/` source layout, a design artifact at `_inputs/design.md`, and (at SHARED+) prior review cycles' artifacts referenced from `_inputs/handoff-manifest.yml`. |
| `--focus LAYER` | Enum | No | Restrict the audit to a single Clean Architecture layer — `domain` · `application` · `infrastructure` · `presentation`. Useful when an earlier review cycle flagged a specific layer and the current run validates remediation. When omitted, all four layers are audited. |
| `--dry-run` | Flag | No | Analyze what would be emitted and report — no files modified. The dry-run output enumerates the audit surface (file count per layer, design-section count, expected finding categories) without committing the findings report. |

---

## Workflow — Five Audit Phases

### Phase 0 — Input Ingest

Read the target repository and the design artifact in full. Deploy a Research Team (CM-25A) for parallel ingest — one agent per surface (design artifact, source tree per layer, CLI entry-points manifest, package metadata, build configuration). Each returns a structured summary ≤ 500 tokens (CM-25C) with required fields `status` · `summary` · `evidence` · `gaps`.

**Required reads.**

- **`_inputs/design.md`** — every ratified per-component section + the §Bindings (§0.j five-direction) declarations + the §Decision Records catalog. Authoritative: every audited code surface MUST trace back to a design section.
- **Source tree under `src/<package>/`** — every public module, protocol declaration, adapter, and entry-point registration. Walk by Clean Architecture layer (domain / application / infrastructure / presentation) per `rules/clean-architecture-layers.md` §1.
- **`pyproject.toml`** (or sibling manifest per host discovery) — entry-point registrations, package metadata, dependency declarations; cross-referenced against the design's declared entry-point surface.
- **CLI entry points** — every `[project.scripts]` or sibling registration; cross-referenced against the design's `## §CLI` section when present.
- **`_inputs/handoff-manifest.yml`** — prior-cycle findings (when reviewing a remediated repository); prior FAIL findings drive Phase 1 traceability emphasis.

**Externalise** a working inventory at the target's `_inputs/architecture-review-input-inventory.md` (free-form scratch per `rules/context-management-scratch.md` §1) to anchor subsequent phases.

**Design-artifact gate.** When `_inputs/design.md` is absent, STOP and surface through the structured-inquiry channel with options `Run /plan-design first (Recommended)` · `Proceed without design artifact (HIGH-severity finding logged)` · `Abort`. Recommend `Run /plan-design first`, citing concrete-driver class 5 (rule citation): the design artifact is the authoritative trace surface every finding references.

### Phase 1 — Design-to-Code Traceability Walk

For each design-artifact `## §N` per-component section, locate the corresponding code surface under `src/<package>/` and verify:

- **Identifier match** — the design's declared module / class / function names exist at the design-declared path. Cosmetic drift is **MEDIUM** (class 5: `rules/code-craft-python.md` §2.2 naming); drift that breaks the design's stated interface contracts is **HIGH** (class 3: the design is the authoritative naming surface).
- **Interface contract match** — signatures (typed argument lists, return types, exceptions, pre/post-conditions per `rules/definitiveness.md`) match the design's declarations. Drift is **HIGH** (class 3 — interface contracts gate downstream callers).
- **Protocol contract match** — `typing.Protocol` (or equivalent) declarations match the design's narrow-interface specs. Wider-than-designed protocols are **MEDIUM** (ISP, class 5: `rules/clean-architecture-layers.md` §2.2).
- **Undesigned component** — code in `src/<package>/` with no corresponding design section is **MEDIUM** (design incomplete or code undisciplined; route through the structured-inquiry channel to classify which).
- **Undelivered design** — a design section with no corresponding code is **HIGH** when the component was in-scope for the current cycle; **LOW** (informational) when declared a future delivery.

### Phase 2 — Layer-Boundary Integrity Audit

Apply `rules/clean-architecture-layers.md` §1 (Four Canonical Layers) + §2 (Boundary Enforcement) to every source module's import surface:

- **Domain purity** — zero imports from application / infrastructure / presentation, ORM libraries, framework libraries, or I/O surfaces. Drift is **HIGH** (class 5: rule §4.2).
- **Application discipline** — zero imports from infrastructure or presentation; cross-layer dependencies route through Protocol / ABC per DIP. Direct concrete-class imports across boundaries are **HIGH** (class 5: rule §2.3 DIP).
- **Infrastructure adapter integrity** — each external dependency (DB adapter, API client, filesystem, external service) wraps a single adapter implementing a domain/application Protocol. Multiple components reaching directly into the same library, bypassing the adapter, are **HIGH** (Hexagonal Architecture, Cockburn 2005 — ports-and-adapters).
- **Presentation thinness** — controllers / handlers / CLI entry points carry zero business logic; they translate transport requests into application DTOs and back. Business logic in presentation is **HIGH** (class 5: rule §2.2 — Presentation never invokes Domain directly).
- **src-layout integrity** — the `src/<package>/` layout from Phase 0 is honored: no top-level packages outside `src/`, no inlined test fixtures, no orphan modules beyond the package boundary. Drift is **MEDIUM** (class 5: rule §3).
- **CLI surface coherence** — every `[project.scripts]` entry point routes through the presentation layer; entry points reaching into application or domain directly are **HIGH** (class 3 — the entry-point surface IS the presentation boundary).
- **Entry-point registration completeness** — every design-declared CLI entry point is registered in `pyproject.toml` and routes to an existing presentation-layer module. Asymmetry is **HIGH** (class 3 — the entry-point surface is authoritative for external invocation).

### Phase 3 — Cross-Package Coupling Sweep

Build the package dependency graph from the source tree's import surface; for each cross-package edge, verify:

- **Edge legitimacy** — every cross-package import has a corresponding `Drives →` / `Driven by ←` declaration in the design's §Bindings. Undeclared edges are **MEDIUM** (class 5: `rules/bidirectional-binding.md` §2 reciprocity invariant).
- **Coupling tightness** — Aggregate Root invariants hold across package boundaries (Domain-Driven Design, Evans 2003). Aggregate-root leaks (a downstream package reaching into another's internal state) are **HIGH** (class 5: DDD ch. 6).
- **Cyclic-dependency detection** — Python's module-import graph is required acyclic; cycles are **HIGH** (class 5: `rules/clean-architecture-layers.md` §1 — the dependency rule points inward only).
- **God-package detection** — a package depended on by > 50% of siblings OR depending on > 50% of siblings is **MEDIUM** (class 6: dependency-graph centrality exceeds 0.5).
- **Orphan-package detection** — a package with zero inbound dependencies AND zero entry-point registrations is **MEDIUM** (class 5: `rules/canonical-layout.md` §3 orphan-output prevention).

### Phase 4 — Findings Emission + Validation Gate

> Moved to `references/step-05-findings-emission-validation-gate.md`. MUST read it in full before executing this step.

---

## Critical Rules

- **NEVER fabricate evidence.** Every cited file path, line range, and import statement is verified to exist before emission. M5 authority violations on this surface are HIGH-severity self-application failures.
- **NEVER propose redesigns inside the findings report.** Findings name violations; remediation is downstream. Redesign proposals belong in `/plan-design` re-runs at the next iteration cycle.
- **NEVER modify source files in the target repository.** Review is read-only on code. The only write surface this command commits is `_inputs/architecture-review-findings.md` plus the optional input-inventory working file.
- **NEVER use vague-rationale phrases as the sole justification for a severity classification.** Cite a concrete-driver class per `rules/interactive-questions-canonical-shapes.md` §3.2.1. "This is bad practice" is non-conformant; "violates ISP per `rules/clean-architecture-layers.md` §2.2 — the Protocol declares 7 methods; the consumer uses 2" is conformant.
- **NEVER emit a findings report without the validation-gate attestation.** Phase 4 gate is non-optional.
- **NEVER carry a half-edge into the emitted findings.** Every finding's design-section back-reference resolves; every design-section reference reciprocally cites the finding when applicable.
- **Per-file destructive-op floor.** Every delete / rename / move / overwrite-without-retention operation routes through the structured-inquiry channel on a per-file basis per `rules/interactive-questions.md` §6.

---

## Decision Tree

> Moved to `references/decision-tree.md`. SHOULD read it when a branch, gate failure, or state transition is unclear.

---

## Output

- The findings report at the target's `_inputs/architecture-review-findings.md` (substantive findings + per-layer attestation + seven-axes coverage + package-dependency-graph diagram + validation-gate attestation).
- The updated Handoff Manifest at the target's `_inputs/handoff-manifest.yml` with the findings-report path + per-axis attestation against the seven-axes-of-breadth taxonomy.
- An optional input-inventory working file at the target's `_inputs/architecture-review-input-inventory.md` (Phase 0 read inventory).

---

## Recommended Next Step

Invoke `/ux-review` to advance the audit-fortress sequence; `/ux-review` is the canonical successor per the 11-command audit-fortress canonical sequence.

## Installed Reference Paths

When this skill is installed by Apothem, resolve a repository-style reference against the installed directory for its first segment, unless a project-local file with the same relative path exists.

- `rules/<path>` is `<ROOT>/rules/<path>`
- `templates/<path>` is `<ROOT>/.apothem/support/templates/<path>`
- `schemas/<path>` is `<ROOT>/.apothem/support/schemas/<path>`
- `hooks/<path>` is `<ROOT>/.apothem/support/hooks/<path>`
- `conformity/<path>` is `<ROOT>/.apothem/support/conformity/<path>`
