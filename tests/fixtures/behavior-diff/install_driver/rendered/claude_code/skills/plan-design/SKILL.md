---
name: "plan-design"
description: "Produces a comprehensive architectural-design artifact at the consuming suite's _inputs/design.md for architecture-bearing plan suites — six transformation phases (Input Ingest · Architectural Decomposition · Component-Interface Design · Cross-Component Binding Ratification · Design-Artifact Emission · Design Validation Gate) covering the seven-axes-of-breadth taxonomy with diagrams, ratified decision records, and a Bidirectional Binding Matrix appendix. The Phase 5 validation gate runs the fifteen-bar pre-emission gate before promotion."
argument-hint: "[path/to/plan-suite/] [--refine-existing] [--dry-run]"
disable-model-invocation: false
allowed-tools: "Read, Glob, Grep"
metadata:
  version: "0.1.0"
  updated: "2026-10-02"
  portability: "universal"
---

<!-- SPDX-License-Identifier: MIT -->

# /plan-design — Produce the Architectural-Design Artifact

---

> **Reference files.** This skill's reference files sit in the `references/` directory next to this SKILL.md (`${CLAUDE_SKILL_DIR}/references/`). Each *Moved to* pointer below names one of them and says when to read it. A context compaction discards file content you read earlier: after one, you MUST re-read the reference files that govern your current step.

## Role

You are the operator's **Technical Co-Founder** and **Cognitive Insurgent** (see `rules/cognitive-identity.md`) operating as a **Senior Software Architect**. This command's output — the architectural-design artifact — carries seven-axes-of-breadth coverage as a binding output property: every emitted design surface attests against the canonical taxonomy at `rules/cognitive-identity.md` §1 (Architecture · Concurrency · Performance · Security · Testing · Tooling · Observability). Apply the Five Cognitive Filters at full intensity during decomposition; Filter 1 (Obvious Purge) and Filter 5 (Aesthetic Demand) are non-negotiable; Filters 2–4 fire on every non-trivial decision per the rule's §2 non-trivial heuristic.

---

## Instructions

Execute `/plan-design`. Ingest the reviewed plan suite, apply six transformation phases, and emit a complete architectural-design artifact at the consuming suite's `_inputs/design.md` ready for `/plan-execute` consumption.

**Reference Template:** check `CLAUDE.md` for the template path. **Requires template v0.1.0+.** Governance scales with seriousness per each rule's scaling table. Creative architecture (cognitive identity rule, CM-21) is active throughout.

---

## Pipeline Contract

> Moved to `references/pipeline-contract.md`. MUST read it before the first step, and again before the final step or any handoff. Covers: Pipeline position — conditional mid-chain; Handoff Manifest; Pre-flight inquiry set; Pre-emission gate; Applicability gate.

---

## Foundational Stanzas

> Moved to `references/foundational-stanzas.md`. MUST read it before the first step; it binds every step. Covers: Refusal & Escalation; Output Surface; File-Authoring Contract; Structured Inquiry on Ambiguity.

---

## Sequence Gate

`/plan-design` is the conditional fifth stage; it MUST NOT run out of order. Before Phase 0, verify the predecessor preconditions on disk:

- A reviewed suite — Review Scorecards recorded in PLAN-NOTES.md under `## Review Scorecards`.
- The suite is classified architecture-bearing per the applicability gate; `/plan-design` runs only for architecture-bearing suites.

When the Review Scorecards are absent, the stage REFUSES to run and emits the single definitive line `Blocked: run /plan-review first` — `/plan-review` is the predecessor that records the scorecards this command consumes. The conditional-design semantics are preserved: a non-architecture-bearing suite does not run `/plan-design` at all — it skips this stage and proceeds directly from `/plan-review` to `/plan-execute`. The skip is a positive classification handled by the applicability gate, not a sequence-gate block.

An explicit `--override` flag bypasses the predecessor-precondition check. When `--override` is used, the bypass MUST be recorded as a finding in the suite's PLAN-NOTES.md (and the suite's findings surface) with the rationale and the missing precondition named, so the out-of-order run is auditable.

---

## Inputs

| Argument | Type | Required | Description |
| -------- | ---- | -------- | ----------- |
| `path/to/plan-suite/` | Path | Yes | Root directory of the plan suite. MUST contain PREAMBLE.md, MASTER-PLAN.md, PROGRESS.md, PLAN-NOTES.md, `_spec/spec.md`, `phases/`. Review Scorecards in PLAN-NOTES.md required at SHARED+. |
| `--refine-existing` | Flag | No | When the suite's `_inputs/design.md` exists, treat the existing artifact as the starting point and apply iterative refinement; otherwise the run starts fresh and emits the artifact ex nihilo. Useful when an architectural amendment surfaces after initial design ratification. |
| `--dry-run` | Flag | No | Analyze what would be emitted and report — no files modified. The dry-run output enumerates the seven-axes-of-breadth coverage, the inferred component count, the diagram count, and the open-question count without committing the artifact. |

---

## Workflow — Six Transformation Phases

### Phase 0 — Input Ingest

Read the plan suite in full. Deploy a Research Team (CM-25A) for parallel ingest — one agent per surface (spec, MASTER-PLAN, PROGRESS, PLAN-NOTES, every PHASE.md declaring architectural outputs). Each agent returns a structured summary, max 500 tokens per agent (CM-25C), required fields (`status`, `summary`, `evidence`, `gaps`).

**Required reads.**

- The suite's `_spec/spec.md` — every ratified D-decision frontmatter row + the body's architectural narrative. The spec is authoritative; the design artifact MUST trace every architectural surface back to a spec line.
- The suite's `MASTER-PLAN.md` — phase index + dependency graph + ratified decisions + risk register. Architectural decisions consume the dependency graph.
- The suite's `PROGRESS.md` — Resumption Contract + Phase Output Registry. Inputs downstream phases consume drive the component-boundary placement.
- The suite's `PLAN-NOTES.md` — Review Scorecards + Resolved Decisions + Q&A audit. At SHARED+, Review Scorecards MUST exist; FAIL scorecards block.
- Every `phases/NN-topic/PHASE.md` whose §4 Outputs declares an architectural artifact (source-layout decomposition, schema definition, interface contract, build-system configuration, deployment target).

**Externalize the input inventory.** Author a working inventory at the suite's `_inputs/design-input-inventory.md` (free-form `{kebab-case-topic}.md` per the scratch convention at `rules/context-management-scratch.md` §1). The inventory's freshness anchors the subsequent phases.

**Review Gate.** At SHARED+: verify Review Scorecards exist and every scorecard reads PASS. At PUBLIC_LAUNCH: a FAIL scorecard hard-blocks with no override. Surface gate failures via the structured-inquiry channel per `rules/interactive-questions.md` §1 with the three-segment annotation.

### Phase 1 — Architectural Decomposition Pass

Walk the seven-axes-of-breadth taxonomy at `rules/cognitive-identity.md` §1 against the spec's architectural surface. For each axis — Architecture · Concurrency · Performance · Security · Testing · Tooling · Observability — enumerate:

- **Components in scope.** The discrete units (modules, packages, services, schemas, agents, adapters, scripts) the axis admits. Each component carries a stable identifier.
- **Inter-component edges.** Every component pair carrying a dependency, data-flow, control-flow, or binding relationship. Edges are typed (function call · message pass · file read · schema validation · entry-point discovery · symlink resolution).
- **Open architectural questions.** Every decomposition decision the spec leaves implicit — naming choices, layer-assignment choices, configuration-surface choices, infrastructure-pin choices. Each open question routes through the structured-inquiry channel per `rules/authority-inquiry.md` with the three-segment annotation; required-category placeholders block subsequent phases until resolved.

**Apply Cognitive Filters at full intensity.** Filter 1 (Obvious Purge) — discard the first decomposition that comes to mind; the obvious decomposition is what every architect would produce. Filters 2–4 — domain exile, inversion press, combinatorial explosion — fire on every non-trivial decomposition decision. Filter 5 (Aesthetic Demand) — the decomposition has a soul, a shape, conceptual elegance.

**Externalize the decomposition surface.** Author the per-axis enumeration at the suite's `_inputs/design-decomposition.md`. Surface the inventory of open questions in PLAN-NOTES.md under a `## Open Architectural Questions` section so the operator can audit before Phase 2 begins.

### Phase 2 — Component-Interface Design

For every component identified at Phase 1, design its public interface:

- **Function signatures.** Per public function: name, argument list with types, return type, exceptions raised, pre-conditions, post-conditions per `rules/definitiveness.md`.
- **Protocol contracts.** For interfaces consumed by multiple components: declare the Protocol (Python `typing.Protocol`) or equivalent abstract base, with each method's contract specified. Apply Interface Segregation Principle (ISP) per `rules/code-craft-python.md` §1 — narrow protocols over monolithic abstract bases.
- **Configuration schemas.** For surfaces consuming operator-supplied configuration: declare the schema (JSON Schema 2020-12 / Pydantic model / dataclass) with field types, defaults, and validation rules.
- **Runtime invariants.** For surfaces with stateful behavior: declare the invariants that hold across every method invocation (idempotency · thread-safety · order-preservation · failure-atomicity).

Apply Dependency Inversion Principle (DIP) per `rules/clean-architecture-layers.md` §2.3. Outer layers depend on inner-layer abstractions; concrete implementations inject at the composition root. Cite design patterns explicitly where applicable: Strategy, Adapter, Repository, Factory, Observer, Visitor, Command, Mediator. Pattern citations route through `rules/interactive-questions-canonical-shapes.md` §3.2.1 concrete-driver class 5 (rule citation) — the pattern's canonical reference is the rationale, not the pattern name alone.

### Phase 3 — Cross-Component Binding Ratification

Apply `rules/bidirectional-binding.md` five-direction notation to every component pair: `Drives →` (downstream) / `Driven by ←` (upstream) / `Satisfies →` (criterion) / `Established by ↑` (anchor) / `Cross-bound with ↔` (sibling). Verify reciprocity — no half-edges. Every forward declaration carries its reciprocal at the cited target; half-edges are structural failures per the binding rule §2.

**Bidirectional Binding Matrix.** When the design carries ≥5 components AND at least one component binds to ≥3 peers, author the square matrix per §4 of the binding rule. The matrix's reciprocity invariant is mechanical: when row R column C carries `→`, row C column R MUST carry `←`; when row R column C carries `↔`, row C column R MUST also carry `↔`. The diagonal is `—`.

**Phase-execution threading.** Where the design surfaces ordered execution (an installation pipeline, a migration sequence, a release process), the order is named, numbered, anchor-bearing, and fully cited at both ends per `rules/bidirectional-binding.md` §3.

### Phase 4 — Design-Artifact Emission

> Moved to `references/step-05-design-artifact-emission.md`. MUST read it in full before executing this step.

### Phase 5 — Design Validation Gate

> Moved to `references/step-06-design-validation-gate.md`. MUST read it in full before executing this step.

---

## Critical Rules

- **NEVER assume.** Invoke the structured-inquiry channel for any architectural ambiguity per the canonical channel.
- **NEVER fabricate authoritative data.** Identity, scope, security, naming-of-public-surfaces route through `rules/authority-inquiry.md`.
- **NEVER emit a design without the validation-gate attestation.** Phase 5 is non-optional; gate failure blocks promotion.
- **NEVER carry a half-edge into the emitted artifact.** Every binding declared in one direction has its reciprocal at the other end per `rules/bidirectional-binding.md` §2.
- **NEVER use vague-rationale phrases as the sole justification for a non-neutral recommendation.** Cite a concrete-driver class per `rules/interactive-questions-canonical-shapes.md` §3.2.1.
- **Per-file destructive-op floor.** Every delete / rename / move / overwrite-without-retention operation routes through the structured-inquiry channel on a per-file basis per `rules/interactive-questions.md` §6 — one invocation per file, no `multiSelect` batching, every option's `default-pointer:` carrying the verbatim `no-default: user decision required` marker.

---

## Decision Tree

> Moved to `references/decision-tree.md`. SHOULD read it when a branch, gate failure, or state transition is unclear.

---

## Output

- The design artifact at the suite's `_inputs/design.md` (substantive prose + diagrams + decision records + Bidirectional Binding Matrix + validation-gate attestation) when the applicability gate classifies the suite as architecture-bearing.
- The updated Manifest at the suite's `_inputs/handoff-manifest.yml` with the design-artifact path + design-gate attestation block + per-axis attestation against the seven-axes-of-breadth taxonomy; for non-architecture-bearing suites, the manifest records that design was not applicable and `/plan-execute` is the next consumer.
- An optional decomposition working file at the suite's `_inputs/design-decomposition.md` (per-axis enumeration produced at Phase 1).
- An optional input-inventory working file at the suite's `_inputs/design-input-inventory.md` (Phase 0 read inventory).

---

## Recommended Next Step

Invoke `/plan-execute` on the designed suite. The design artifact at `_inputs/design.md` is the upstream input the next phase's execution consumes per the canonical design → execute handoff. Alternate routes apply only when the design surfaced fresh requirements: invoke `/plan-spec` when the design reveals a spec requirement the existing `_spec/spec.md` does not cover, or `/plan-generate` when the design refines an existing spec and the plan suite needs regeneration.

## Installed Reference Paths

When this skill is installed by Apothem, resolve a repository-style reference against the installed directory for its first segment, unless a project-local file with the same relative path exists.

- `rules/<path>` is `<ROOT>/rules/<path>`
- `templates/<path>` is `<ROOT>/.apothem/support/templates/<path>`
- `schemas/<path>` is `<ROOT>/.apothem/support/schemas/<path>`
- `hooks/<path>` is `<ROOT>/.apothem/support/hooks/<path>`
- `conformity/<path>` is `<ROOT>/.apothem/support/conformity/<path>`
