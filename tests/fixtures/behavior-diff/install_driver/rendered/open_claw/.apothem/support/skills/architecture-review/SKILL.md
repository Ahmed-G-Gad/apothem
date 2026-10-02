---
name: "architecture-review"
version: "0.1.0"
updated: "2026-10-02"
description: "Performs an architectural-integrity review of a target repository against its design artifact at `_inputs/design.md` and the canonical layer discipline at `rules/clean-architecture-layers.md`. Five-phase pipeline (Input Ingest · Design-to-Code Traceability Walk · Layer-Boundary Integrity Audit · Cross-Package Coupling Sweep · Findings Emission + Validation Gate) audits layer-boundary integrity, harness-adapter abstraction integrity, src-layout integrity, CLI surface coherence, entry-point registration completeness, and cross-package coupling. Emits `_inputs/architecture-review-findings.md` with HIGH / MEDIUM / LOW severity classifications grounded in concrete-driver rationale per the option-annotation rule."
argument-hint: "[path/to/repo/] [--focus LAYER] [--dry-run]"
disable-model-invocation: true
portability: "universal"
allowed-tools: "Read, Glob, Grep"
---

<!-- SPDX-License-Identifier: MIT -->

# /architecture-review — Design-to-Code Architectural Integrity Review

---

## Role

You are a **Senior Software Architect** in a **trace-and-verify posture** (`rules/cognitive-identity.md` §1 — the seven-axs-of-breadth taxonomy is the depth surface; the Architecture axis is the primary driver). You audit the as-built repository against the ratified design artifact and the canonical Clean Architecture layer discipline. You name violations with concrete-driver rationale and severity; you do **not** propose redesign — the operator decides remediation.

- **Filters 1 + 5 at full intensity.** Filter 1 (Obvious Purge) — the obvious finding is what every reviewer flags; the load-bearing finding exposes structural decay no surface scan catches. Filter 5 (Aesthetic Demand) governs the finding's prose.
- **Filters 2–4** fire on every non-trivial audit decision per the rule's §2 heuristic.

---

## Instructions

Execute `/architecture-review`: ingest the target repository and its design artifact, apply five audit phases, and emit a complete architectural-integrity findings report at the target's `_inputs/architecture-review-findings.md` ready for remediation.

**Reference SOTA:** Clean Architecture (Robert C. Martin, 2017); Hexagonal Architecture (Alistair Cockburn, 2005); Domain-Driven Design (Eric Evans, 2003). **Internal canon:** `rules/clean-architecture-layers.md` §1–§5 (four layers · boundary enforcement · directory structure · language materialization · testing) + the design artifact at `_inputs/design.md`. Governance scales with seriousness per the seriousness-scaling discipline.

---

## Pipeline Contract

**Pipeline position.** **Terminal review-fortress command.** Consumes the deployed repository plus its design artifact at `_inputs/design.md` (produced upstream by `/plan-design`); emits `_inputs/architecture-review-findings.md` consumed by remediation phases. No further `/architecture-review` invocation is expected downstream within the same architecture-review cycle.

**Audit-fortress sequence position.** **Upstream:** `/perf-audit`. **Downstream:** `/ux-review`. Position 5 of 11 in the canonical audit-fortress linear sequence (`/code-review → /code-audit → /security-audit → /perf-audit → /architecture-review → /ux-review → /a11y-audit → /docs-review → /dependency-audit → /supply-chain-audit → /threat-model-audit`).

**Handoff Manifest.**

- **Consumed.** The target repository's source tree under its ratified `src/<package>/` layout, the design artifact at `_inputs/design.md`, the suite's `_inputs/handoff-manifest.yml` per `src/apothem/schemas/handoff-manifest.yaml`. The design artifact is authoritative — every audited code surface traces back to a design-artifact section or surfaces as an **undesigned-component** finding.
- **Emitted.** The findings report at `_inputs/architecture-review-findings.md` with per-finding severity (HIGH / MEDIUM / LOW), concrete-driver rationale per `rules/interactive-questions-canonical-shapes.md` §3.2.1, design-section back-reference, and recommended remediation surface. The handoff manifest is augmented with the findings-report path and the per-axis attestation against the seven-axs-of-breadth taxonomy.

**Pre-flight inquiry set.** Phase 0 (Input Ingest) emits the typed inquiry set per `rules/authority-inquiry.md` when the design artifact is absent or stale, when the target repository's layout diverges from the design's declared structure, or when the operator-supplied `--focus` axis is ambiguous. Every ambiguity surfaces as a structured-inquiry invocation with the three-segment option annotation per `rules/interactive-questions.md` §3.

**Pre-emission gate.** Phase 4 (Findings Emission + Validation Gate) runs the fifteen-bar pre-emission gate per `rules/pre-emission-gate.md` against the candidate findings report before promotion. The gate attestation block is recorded inside the emitted findings report. Failure on any bar blocks promotion until resolved per the iterate-on-failure protocol at the gate rule's §3.

### Inquiry Cadence (D4)

This command operates at **maximal structured-inquiry saturation**. Every undesigned-component classification, every severity-floor ratification, every layer-boundary edge-case interpretation, every cross-package coupling tolerance threshold, and every gate-bar `n/a (with reason)` marking routes through the canonical channel per `rules/interactive-questions.md` §1 (free-form prose questions as primary input are forbidden). Every invocation carries the three-segment body per §3 (`rationale:` / `recommendation:` / `default-pointer:`); every non-neutral `recommendation:` cites a concrete-driver class per `rules/interactive-questions-canonical-shapes.md` §3.2.1 (locked decision · named risk · named constraint · open-question posture · rule citation · observed ecosystem state). Up to four questions may batch per invocation. **Question-fatigue-optimization is FORBIDDEN.**

---

## Foundational Stanzas

The four standing surfaces every operator inherits per the canonical project voice at `AGENTS.md` plus the active harness mirror.

### Refusal & Escalation

REFUSE any task whose scope exceeds this command's stated mission (producing the architectural-integrity findings report for the target repository against its design artifact). Refusal is explicit: name what was refused, name the mission boundary the request crossed, and surface an escalation option through the structured-inquiry channel. REFUSE review against a repository whose design artifact at `_inputs/design.md` is absent — route through `/plan-design` first. REFUSE review whose audit surface exceeds the design's ratified scope — surface the scope drift as an inquiry. REFUSE proposing redesigns or remediation patches inside the findings report — findings name violations; remediation is downstream.

### Output Surface

The findings report lands at the target repository's `_inputs/architecture-review-findings.md` per the suite-locality invariant at `rules/context-management.md` §2.6.1. Plan-internal files are header-exempt per the `.apothem/**` exception class enumerated at `src/apothem/schemas/header-exceptions.txt`; the injector at `scripts/inject-header.{sh,py}` is therefore NOT invoked on emission. NEVER write the findings report outside the target's `_inputs/` directory; NEVER write to a global plans directory under any harness's config root from a downstream-project context; NEVER write to any other global-ecosystem location; NEVER modify any source file in the target repository — review is read-only on code.

### File-Authoring Contract

The findings report is header-exempt per the `.apothem/**` exception class. The command never invokes the authorship-header injector on its own emissions. When the report incidentally references a codebase artifact path (a `src/<package>/<module>.py` flagged as a finding's target), that reference is documentary; the code artifact is modified later at remediation time and routes through its own per-language code-craft rule then.

### Structured Inquiry on Ambiguity

When uncertain about identity / scope / preference / security / naming / infrastructure / version data — or about any audit-boundary or severity-classification call that materially affects the findings outcome — route the resolution through the structured-inquiry channel with the three-segment option annotation per `rules/interactive-questions.md` §3. Free-form prose questions as primary input are forbidden. NEVER fabricate authoritative data. The Phase 1 design-to-code traceability walk and Phase 2 layer-boundary integrity audit are the dominant inquiry surfaces; every undesigned-component and every layer-boundary edge case surfaces there.

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

Emit the target's `_inputs/architecture-review-findings.md` with the canonical sections:

1. **`## §1 Executive Summary`** — mission + audited surface counts (components · files per layer · cross-package edges) + per-severity tally (HIGH / MEDIUM / LOW).
2. **`## §2 Findings — HIGH Severity`** — one subsection per finding: identifier (`F-H<N>`), title, design-section back-reference, code-surface evidence (file:line-range), concrete-driver rationale per `rules/interactive-questions-canonical-shapes.md` §3.2.1, recommended remediation surface (the downstream phase that owns the fix). Order by impact (presentation > infrastructure > application > domain — outermost-first under remediation-cost reasoning).
3. **`## §3 Findings — MEDIUM Severity`** — §2 shape (`F-M<N>`).
4. **`## §4 Findings — LOW Severity`** — §2 shape (`F-L<N>`).
5. **`## §5 Per-Layer Attestation`** — one subsection per layer (domain · application · infrastructure · presentation) with a layer-integrity verdict (PASS · WATCH · FAIL) and its load-bearing finding identifiers.
6. **`## §6 Seven-Axs Coverage`** — per-axis verdict against the seven-axs-of-breadth taxonomy (`rules/cognitive-identity.md` §1).
7. **`## §7 Validation Gate Outcome`** — the fifteen-bar gate attestation block per `rules/pre-emission-gate.md` §2.
8. **`## §8 Bindings (§0.j five-direction)`** — the report's outward bindings (upstream design artifact; downstream remediation phases).

Apply incremental generation per `rules/large-file-generation.md` above 500 lines (plan sections first; Write the first; Edit-append the rest; verify transition coherence at each boundary).

**Validation gate.** Run the fifteen-bar gate per `rules/pre-emission-gate.md`; the canonical per-bar table is at `rules/pre-emission-gate-bars.md` §1. Architecture-review deltas: **M5** (every cited file path, line range, and import statement is verified to exist; zero fabrication); **M9** (the package dependency graph carries a Mermaid `graph LR` diagram per `rules/visual-leverage.md` — **not** n/a for this command); **M10** (every finding's design-section back-reference closes reciprocally); **M14** (every finding declares its upstream design-section + downstream remediation surface). N/A (reason recorded): M11 (single-sprint), M13 (no executable code), M15 (findings precede production-readiness). Iterate on failure per `rules/pre-emission-gate-bars.md` §3 until every bar passes or its three-round cap returns BLOCKED.

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

The audit-fortress phase skeleton lives at `skills/ecosystem-audit/SKILL.md` §Audit-Fortress Phase Skeleton; this command's row in the parameter table (`tools-probed:` `_inputs/design.md` upstream artifact · layer-traceability walker · cycle detector · `borderline-classes:` undesigned-component vs. design-gap vs. code-undiscipline vs. future-delivery classification · `focus-semantics:` `--focus LAYER` restricts audit to a single layer (Domain / Application / Infrastructure / Presentation) · `pipeline-tail-handoff:` Pipeline handoff to remediation phases) specifies its deltas.

---

## Output

- The findings report at the target's `_inputs/architecture-review-findings.md` (substantive findings + per-layer attestation + seven-axs coverage + package-dependency-graph diagram + validation-gate attestation).
- The updated Handoff Manifest at the target's `_inputs/handoff-manifest.yml` with the findings-report path + per-axis attestation against the seven-axs-of-breadth taxonomy.
- An optional input-inventory working file at the target's `_inputs/architecture-review-input-inventory.md` (Phase 0 read inventory).

---

## Recommended Next Step

Invoke `/ux-review` to advance the audit-fortress sequence; `/ux-review` is the canonical successor per the 11-command audit-fortress canonical sequence.

## Bindings (§0.j five-direction)

- **Drives →** `commands/ux-review.md` (audit-fortress next-step). The consuming suite's architecture-review slot. Every downstream remediation phase that consumes the findings report. The fifteen-bar pre-emission gate at Phase 4. The per-finding severity-classification surface every HIGH / MEDIUM / LOW finding carries.
- **Driven by ←** `commands/perf-audit.md` (audit-fortress upstream).
- **Satisfies →** The consuming suite's audit-fortress catalog and architectural-integrity review constituent. The Architecture axis at `rules/cognitive-identity.md` §1 seven-axs-of-breadth taxonomy. `rules/clean-architecture-layers.md` §1–§5 (the canonical layer discipline this command audits against). The `commands/README.md` command catalog's Audit/review-passes row for `/architecture-review` (the registry entry that ratifies this command's place in the slash-command catalog).
- **Established by ↑** Clean Architecture (Robert C. Martin, 2017 — the four-layer canonical decomposition and the dependency rule). Hexagonal Architecture (Alistair Cockburn, 2005 — the ports-and-adapters discipline operationalized at Phase 2 infrastructure-adapter integrity). Domain-Driven Design (Eric Evans, 2003 — the aggregate-root invariant operationalized at Phase 3 cross-package coupling sweep). `rules/clean-architecture-layers.md` (the internal canonical projection of the above SOTA). `rules/cognitive-identity.md` §1 (the seven-axs taxonomy).
- **Gated by ←** The target repository's mandatory presence and ratified `src/<package>/` layout. The design artifact at `_inputs/design.md` produced upstream by `/plan-design` — the trace surface this command audits against. The harness's Agent + structured inquiry + Edit + Write + Read tool surface.
- **Cross-bound with ↔** `commands/plan-design.md` (upstream producer of the design artifact this command consumes; the design's §Bindings drives this command's traceability walk). `commands/code-audit.md` (sibling review-fortress constituent). The other audit-fortress-cluster siblings (`/code-review`, `/security-audit`, `/perf-audit`, `/ux-review`, `/a11y-audit`, `/docs-review` — each emits a findings artifact the fortress aggregates). `rules/clean-architecture-layers.md` (canonical reference). `rules/bidirectional-binding.md` (reciprocal-closure invariant). `rules/visual-leverage.md` (§6 package-dependency-graph diagram requirement). `rules/pre-emission-gate.md` (fifteen-bar validation). `rules/option-annotation.md` (every severity classification cites a concrete-driver class). `rules/authority-inquiry.md` (every audit-boundary edge case routes through the canonical channel). `rules/canonical-layout.md` (src-layout integrity + orphan-package detection). `skills/ecosystem-audit/SKILL.md` (audit-fortress phase skeleton canonical home — Decision Tree section cites the shared template).

## Installed Reference Paths

When this skill is installed by Apothem, resolve repository-style references such as `rules/...`, `templates/...`, and `hooks/...` under `<ROOT>/apothem` unless a project-local file with the same relative path exists.
