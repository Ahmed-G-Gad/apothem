---
name: "canonical-layout-reporting-tiers"
description: "Path-filtered companion rule carrying the operational depth of `rules/canonical-layout.md` — the two-tier reporting body (per-sub-phase + phase rollup), the numeric-prefix discipline, the orphan-output recovery surface, the reciprocal producer / consumer cross-reference body, the surface-imposition table, and the M11 ↔ M12 correspondence table; demand-loaded on plan-suite / phase / migration touches."
pathFilter: "**/.apothem/plans/**, **/.plans/**, **/phases/**, **/REPORT.md, **/PHASE.md, **/MASTER-PLAN.md, **/PROGRESS.md, **/migrations/**"
alwaysApply: false
paths:
  - "**/.apothem/plans/**"
  - "**/.plans/**"
  - "**/phases/**"
  - "**/REPORT.md"
  - "**/PHASE.md"
  - "**/MASTER-PLAN.md"
  - "**/PROGRESS.md"
  - "**/migrations/**"
---

<!-- SPDX-License-Identifier: MIT -->

# Rule: Canonical Layout — Reporting Tiers & Operational Body (Companion Sub-Rule)

## Purpose

Carry the operational depth of the canonical-layout discipline declared at the parent `rules/canonical-layout.md` rule. Path-filtered: loads on any per-suite plan artifact, per-phase artifact, per-sub-phase report, migration script, or progress / master-plan singleton. The parent owns the M12 standing directive and the per-section summaries; this companion owns each section's full body — §1 two-tier reporting, §2 canonical layout, §2.1 numeric-prefix discipline, §2.2 `_outputs/`, §2.3 anti-inflation, §2.4 maintenance suites, §3 orphan prevention, §4 reciprocal cross-references, §5 surface imposition, §6 M11 ↔ M12 correspondence, §7 three-tier scalability (D7).

## Obligations

### 1. Two-Tier Reporting — Per-Sub-Phase + Phase Rollup

#### 1.1 Per-Sub-Phase Report (Working Tier)

Every sub-phase produces a report at the sub-phase folder's canonical filename (`REPORT.md` is the plan-suite convention; the host's discovered convention overrides per M1). This is the **working tier** — fine-grained, as-it-happens, capturing the sub-phase's substantive work.

Canonical sections:

- **Summary** — one-paragraph statement of what the sub-phase produced.
- **Tasks executed** — enumeration of tasks completed, mapped to the sub-phase's `PHASE.md` task list.
- **Outputs emitted** — every artifact produced, with path, line count or size, and a one-line description.
- **Verification results** — every per-sub-phase verification item with its outcome.
- **Disclosure ledger** — the sub-phase's amendments, extensions, refinements, deferrals, defaults, and inquiry outcomes per `rules/disclosure-ledger.md`.
- **Pre-emission gate attestation** — the fifteen-bar attestation per `rules/pre-emission-gate.md`.
- **Bindings (§0.j five-direction)** — reciprocal cross-references per `rules/bidirectional-binding.md`.

#### 1.2 Phase-Level Rollup Report (Reviewing Tier)

Every phase produces a rollup report aggregating across its sub-phases — the **reviewing tier**: derivative, condensed, cross-cutting.

**The rollup is NOT a concatenation of sub-phase report links.** A document that lists the sub-phase reports as bullets and stops is non-conformant. The rollup carries five required behaviors:

1. **Summarizes each sub-phase's outputs in a uniform template.** Each sub-phase gets the same shape — same headings, same fields, same reading order. Heterogeneous sub-phase summaries (one verbose, another a stub, a third in a different format) violate the uniform-template requirement.
2. **Aggregates metrics across sub-phases.** Counts (artifacts emitted, lines authored, tests passed, verifications cleared), durations (sub-phase elapsed time, sprint velocity per `rules/agile-sprints.md` §1.7), trajectories (defect rate, churn, finding density) are aggregated and presented at the phase level.
3. **Surfaces phase-level patterns invisible at any single sub-phase.** Patterns that emerge only across sub-phases — recurring failure modes, convergent decisions, drift between sub-phases — are surfaced explicitly. The phase-level pattern surface is the rollup's **unique** value over per-sub-phase concatenation.
4. **Carries a phase-level self-check.** The rollup runs the pre-emission gate at the **phase level**, not just the per-sub-phase level. The phase's own bindings, the phase's own definitiveness, the phase's own production-readiness are inspected as a whole.
5. **Advances the phase's outward declarations on behalf of the whole phase.** The rollup commits the phase's outputs to the phase's downstream consumers — the next phase's inputs, the parent suite's progress tracker, the host's index registries.

The rollup's filename convention follows the host's discovery; the established plan-suite convention is `phases/NN-topic/REPORT.md` (the parent phase's `REPORT.md` at the parent folder), with sub-phases at `phases/NN-topic/NNL-subtopic/REPORT.md`. Single-sub-phase phases collapse the tier — the per-sub-phase report IS the rollup.

### 2. Canonical Layout — Predictable Locations with Provenance

Generated outputs sit at **predictable, canonical locations** with provenance and reciprocal cross-references. The exact form of "canonical" — directory naming, filename conventions, structural-marker prefixes, per-directory index conventions — is **delegated to the host's discovered conventions** per `rules/host-discovery.md`. Where the host is silent on layout, the choice surfaces as an inquiry per `rules/authority-inquiry.md` with apothem's recommendation per `rules/option-annotation.md`.

**No artifact is laid as a flat file at an ad-hoc location.** Every emitted output has:

- A **canonical directory** the host has ratified for outputs of its kind (e.g., test files under the host's tests directory; documentation pages under the host's docs directory; CI workflows under `.github/workflows/`; migration scripts under the host's migrations directory).
- A **filename matching the host's sibling convention** (kebab-case / snake_case / PascalCase / etc. — whatever the siblings use).
- A **provenance record** — either embedded in the artifact (frontmatter, header comment, docstring) or recorded in the producer's report. Every emitted artifact answers "where did this come from?" by inspection.
- An **index entry** in the enclosing directory's index where the host maintains one (`__init__.py`, `index.md`, TOC, sidebar, package manifest).

Cross-phase artifacts — synthesizing across phases — sit at the host's designated cross-phase deliverable location (whatever the host's convention is), indexed in the enclosing directory's index, with reciprocal back-references from every phase that contributed.

### 2.1 Numeric-Prefix Discipline — Ordering Sequences Only

Numeric prefixes on filesystem paths (`00-`, `01-`, `02-`, `NN-`) **convey ordering**. The discipline scopes them to artifacts whose **sequence is intrinsic to the contract**:

- **Phase-ordering folders** under `phases/` (`phases/00-discovery/`, `phases/01-foo/`, `phases/02-bar/`) — the prefix carries the ordering the phase apparatus depends on. The `NN-` prefix is mandatory on every phase folder.
- **Sub-phase folders** under a parent phase (`phases/02-foo/02A-subtopic/`, `02B-subtopic/`) — the prefix-plus-letter carries the sub-phase ordering. Mandatory.
- **Migration scripts** where the host orders by numeric prefix (`migrations/0042_user_schema.sql`) — honor the host's ratified scheme.
- **Any other artifact class where the host has ratified ordinal-prefix naming** as a convention — discovered per `rules/host-discovery.md` and honored.

**Numeric prefixes are forbidden on artifacts that have no sibling sequence** — root-level singletons, lone configuration files, top-of-suite infrastructure files. Adding a prefix to a file that has no `01-` / `02-` siblings is **meaningless decoration that mis-signals an ordering relationship that does not exist**, and is a structural failure on the same axis as the orphan-output failure at §3.

**Suite-root infrastructure files** at every plan-suite root (`<project-root>/.apothem/plans/{suite}/`) — the suite preamble, the master index, the progress tracker, the plan-notes ledger, the completion attestation, every other root-level singleton — carry **no numeric prefix**. They are siblings of one another, not items in an ordered sequence; the prefix would falsely imply an ordering the contract does not require. The same discipline extends to **any new root-level singleton class** the ecosystem admits in the future: the prefix appears only where ordering is intrinsic, never as decoration.

**Failure tells.** A `00-FOO.md` at any root level where there is no `01-FOO.md` sibling is a finding. A renamed file gaining the prefix when its prior sibling-set never carried one is a finding. A new artifact class whose first instance is `00-X.md` ratifies a prefix the second instance (`01-X.md`?) would have to honor — preferable: drop the prefix on the first instance unless ordering is genuinely intrinsic.

### 2.2 Plan-Suite `_outputs/` Emission Surface

Every plan suite may carry a suite-local `_outputs/` sibling beside `_inputs/`, `_spec/`, and `phases/`. `_outputs/` is the canonical home for durable generated emissions that are useful after the session but too detailed for PROGRESS.md or PLAN-NOTES.md: audit reports, report mirrors, rollups, metrics, exports, and bounded operator-facing summaries.

Placement discipline:

- `/plan-audit` writes bounded audit reports to `<suite>/_outputs/audit-report-<YYYY-MM-DD>.md`.
- `/plan-execute` writes phase implementation reports at `phases/NN-topic/REPORT.md` and may mirror operator-facing summaries at `<suite>/_outputs/<phase-slug>/REPORT.md`.
- `/plan-review` keeps scorecards and concise findings state in PLAN-NOTES.md, but durable large review reports or revision-impact detail maps move to `_outputs/` with backlinks.
- `/plan-status` remains read-only; if another orchestrator persists its prose output, that file belongs under `_outputs/report-<YYYY-MM-DD>.md` unless the host has a more specific documentation surface.

Every `_outputs/` artifact must carry producer attribution and a consumer/index reference: the producer report's `Outputs emitted` section, PROGRESS.md Phase Output Registry, a local README/index if the suite maintains one, or the Handoff Manifest. `_outputs/` artifacts are evidence, not authoritative requirements; requirement traceability still resolves to the suite specification, MASTER-PLAN.md, PHASE.md, or operator-ratified decisions.

### 2.3 Anti-Inflation Reporting Discipline

PROGRESS.md and PLAN-NOTES.md are bounded state ledgers, not storage for every detail. They use index-first summaries and backlink to reports:

- PROGRESS.md records current status, counters, blocker summaries, Phase Output Registry rows, Resumption Contract, next action, and critical file manifests. It does not accumulate long chronological narratives or paste full verification logs.
- PLAN-NOTES.md records durable decisions, scorecard summaries, open questions, waivers, and rationale. It uses rolling summaries when a section grows beyond the current decision horizon.
- REPORT.md and `_outputs/` hold detailed task logs, verification transcripts, audit reports, metrics, and long evidence tables.

When a workflow produces detailed evidence, the same change-set writes the detail to REPORT.md or `_outputs/`, then writes a concise PROGRESS.md / PLAN-NOTES.md backlink. The backlink is the state surface; the report is the evidence surface.

### 2.4 `*-maintenance` Suite Pattern

Deferred, incomplete, or out-of-scope work that would inflate the active suite routes to a sibling maintenance suite named `<suite>-maintenance`. Maintenance routing is for work that the originating suite should not execute now, not for hiding open findings required by the current gate.

Each maintenance item carries:

- Source suite path and source artifact anchor.
- Finding or task ID.
- Rationale for maintenance routing.
- Expected downstream command or phase.
- Current status and owner, if known.

The originating suite records only a concise maintenance backlink in PLAN-NOTES.md or PROGRESS.md. The maintenance suite carries the expanded backlog and its own `_spec/`, `_inputs/`, `_outputs/`, and `phases/` surfaces when it becomes executable.

### 3. Orphan Output Prevention

An **orphan output** is a generated artifact that satisfies any of:

- **No consumer.** Nothing in the host's reference graph reads, imports, executes, links to, or references the artifact.
- **No index entry.** The artifact is not listed in its enclosing directory's index where the host maintains one.
- **No producer attribution.** The artifact carries no provenance — no frontmatter `provenance:` field, no header comment naming the producer, no record in the producer's report.

Orphan outputs are **structural failures**. The `orphan-output-grep` mechanical matcher at `conformity/orphan_output_grep.py` scans every emitted artifact's enclosing directory for index-entry presence and the producer's report for attribution presence. Orphan findings are HIGH-severity at the pre-emission gate per `rules/pre-emission-gate.md` row 12.

**Orphan recovery.** When an orphan is detected:

- **Add the consumer.** If the artifact is genuinely needed but no consumer exists, surface the gap as a finding for the user's decision (the artifact's existence is justifiable but its consumer is missing).
- **Add the index entry.** Update the enclosing directory's index in the same change-set. The index update is part of the artifact's emission, not a follow-up.
- **Add the producer attribution.** Update the producer's report to record the artifact's emission. Update the artifact's frontmatter / header to cite the producer.
- **Retire the artifact.** When investigation reveals the artifact has no genuine consumer, it is retired in the same change-set rather than left as an orphan. Retirement routes through the destructive-op confirmation surface at `rules/interactive-questions.md` §6.4 (the canonical Delete option set).

### 4. Reciprocal Producer / Consumer Cross-References

Every emitted output carries reciprocal cross-references on both ends of every producer / consumer edge:

- **Producer side.** The phase's report (per-sub-phase or rollup) lists the artifact in its `Outputs emitted` section with the artifact's path, the consumer(s) that depend on it, and the binding direction (`Drives → <consumer>`).
- **Consumer side.** Every artifact that consumes the output references it explicitly. For code, this is an import / require / link. For documentation, this is a Markdown link or include. For configuration, this is a path reference. The consumer's reference IS the reciprocal back-pointer per `rules/bidirectional-binding.md`.

When an output's consumer changes (added, removed, renamed), the producer's report is updated in the same change-set. Stale producer reports (claiming a consumer that no longer exists, omitting a new consumer) are findings.

### 5. Surface Imposition — Where the Layout Discipline Lands

| Surface | Layout obligation |
|---|---|
| `CLAUDE.md` | Carries the standing directive that non-trivial multi-step work lays outputs under the canonical layout with two-tier reporting (M12 row in §8 fifteen-mandate registry). |
| `skills/*/SKILL.md` | Procedures spanning sub-phases specify the sub-phase partitioning and the expected reports; per-sub-phase report shape is declared in the procedure. |
| `agents/*.md` | Agents with multi-artifact remits return a work-root path with the canonical layout populated. The return format includes the per-sub-phase reports and the rollup. |
| `commands/*.md` | Commands declare their place in the host's pipeline conventions. Each command's outputs section names the canonical layout the command honors. |
| Multi-phase plans at `<project-root>/.apothem/plans/*/` | Each phase folder follows `phases/NN-topic/{REPORT.md, NNL-subtopic/}` shape. Sub-phase folders follow `phases/NN-topic/NNL-subtopic/{PHASE.md, REPORT.md, …}` shape. Cross-phase synthesis sits at the suite-root level (`MASTER-PLAN.md`, `PREAMBLE.md`, `PROGRESS.md`, `PLAN-NOTES.md`); durable generated emissions sit under `_outputs/`. |
| Hook scripts at `conformity/` | The `orphan-output-grep` and the `non-canonical-location-grep` matchers operationalize §3 and §2 respectively at the pre-emission gate. |

### 6. The M11 ↔ M12 Correspondence

The sprint apparatus per `rules/agile-sprints.md` and the layout / reporting discipline here are **mutually-reinforcing**. The correspondence:

| Sprint apparatus element (M11) | Layout / reporting surface (M12) |
|---|---|
| Sprint Goal | The phase / sub-phase folder's `PHASE.md` Goal section |
| Sprint Backlog | The phase / sub-phase folder's Tasks section |
| Definition of Ready | Pre-conditions checklist in the per-sub-phase report's preamble |
| Definition of Done | Verification section in the per-sub-phase report |
| Sprint Review | The rollup report's per-sub-phase summaries with approve / reject / carry-forward outcomes |
| Sprint Retrospective | The rollup report's pattern-surfacing section + retrospective subsection |
| Velocity tracking | Aggregated metrics in the rollup report (artifacts emitted, items completed per sub-phase) |

The mapping is the operational form of the M11 Agile-process discipline materialized at the M12 layout / reporting surface. A non-trivial multi-step work session that satisfies M11 without populating the corresponding M12 surface is non-conformant; a session that satisfies M12 without the M11 apparatus is equally non-conformant.

### 7. Three-Tier Scalability Framework (D7)

The two-tier reporting discipline at §1 governs intra-phase / intra-suite reporting; this section governs inter-suite scalability — how the layout, validation cadence, indexing, and decomposition heuristics shift as a plan suite grows from a few dozen phases to thousands.

#### 7.1 Tier Table

| Tier | Phase count | Spec count | Validation cadence | Indexing | Decomposition |
|---|---|---|---|---|---|
| `small` | <50 | <100 | Full-suite each pass — `/plan-review` audits every phase, every spec section, every constraint per cycle | In-line refs (PLAN-NOTES.md narrative trace tables) | Monolithic — single suite at `<project-root>/.apothem/plans/{suite}/` |
| `medium` | 50–500 | 100–1000 | Incremental + sampled-rollup — per-phase validation continues, plus phase-group rollups (5–20 phases each) sampled per cycle | Suite-root `MASTER-INDEX.md` per `src/apothem/templates/master-index-template.md` | Phase-grouped — `phases/NN-group/NNL-phase/` two-level shape, groups of 5–20 phases |
| `large` | ≥500 | ≥1000 | Index-driven + on-demand drilldown — `MASTER-INDEX.md` is queried first, sub-suite REPORTs read on demand | `MASTER-INDEX.md` per sub-suite + suite-of-suites parent index | Sub-suite federation — multiple plan suites with parent-child relationship; each child suite is small or medium |

#### 7.2 Drift-Prevention Mechanisms

| Mechanism | Tier applicability | Description |
|---|---|---|
| Trace matrix | All tiers | Every spec requirement maps to one or more phases; every phase maps to one or more spec requirements. Bidirectional. At small tier, narrative trace tables inside the plan suite's notes file substitute for the formal trace-matrix file; at medium+ tier, `src/apothem/templates/trace-matrix-template.md` is materialized at the suite root. |
| Stable IDs | medium+ | Cross-references use stable IDs (`R-NNNN` for requirements; `P-NN` for phases) so renames do not break refs. |
| `MASTER-INDEX.md` | medium+ | Suite-root index of every phase + every spec section + every constraint + every named decision per `src/apothem/templates/master-index-template.md`. |
| Sub-suite federation | large | Plan decomposes into multiple plan suites with parent-child relationship; each child suite is small or medium; the parent index aggregates. |
| Per-phase verification | All tiers | Every phase emits a per-phase REPORT.md per §1.1. |
| Phase-rollup verification | medium+ | Every group of 5–20 phases emits a rollup REPORT per §1.2. |
| Suite-rollup verification | large | Every child suite emits a final rollup; federation aggregates child-suite rollups at the parent. |

#### 7.3 Borderline-Tier Inquiry

When a plan suite's phase count sits within ±10% of a tier boundary (45–55 phases for the small/medium boundary; 450–550 phases for the medium/large boundary), the agent MUST surface a tier-classification choice through the structured-inquiry channel per `rules/authority-inquiry.md` (preference category) rather than silent-pick. Question shape: `Plan suite phase count is within ±10% of a tier boundary; which scalability tier should govern this suite?`; header `Tier`; options `Small / Medium / Large` each with three-segment body citing the boundary thresholds and any host-discoverable prior-suite tier conventions per `rules/host-discovery.md`; `default-pointer:` `no-default: user decision required` (long-lived ratification per the §7.2 stable-ID convention; silent default would commit the suite to a tier without the operator's awareness of boundary proximity).

#### 7.4 Small-Tier Worked Example

The `sample-overhaul` plan suite at `<project-root>/.apothem/plans/sample-overhaul/` is a worked small-tier example: 24 PHASE.md files (well under the 50-phase boundary) governed by full-suite validation per cycle, in-line cross-references inside `PLAN-NOTES.md`, and a monolithic single-suite layout at the suite root. No `MASTER-INDEX.md` is materialized; no formal trace-matrix file is produced; the narrative trace tables inside `PLAN-NOTES.md` carry the all-tier trace-matrix obligation at the small-tier alternative form.

#### 7.5 Tier Transition

When a small-tier suite grows past the 50-phase boundary (or a medium-tier suite past 500), the transition is a deliberate operator decision routed through `/plan-review` plus a tier-classification structured inquiry. The transition emits the medium-tier (or large-tier) infrastructure in the same change-set: `MASTER-INDEX.md` materialized, stable IDs assigned to existing phases / requirements, trace-matrix file produced per `src/apothem/templates/trace-matrix-template.md`, sub-suite federation laid out (large only). Silent transitions are non-conformant — a 51-phase suite with no `MASTER-INDEX.md` is a structural failure on the same axis as a missing per-phase REPORT.md.

## Enforcement

Path-filtered (the eight glob patterns in this rule's `pathFilter` field — `**/.apothem/plans/**`, `**/.plans/**`, `**/phases/**`, `**/REPORT.md`, `**/PHASE.md`, `**/MASTER-PLAN.md`, `**/PROGRESS.md`, `**/migrations/**`), always-on at every seriousness level when in scope. Demand-loaded companion to `rules/canonical-layout.md`: the parent owns the M12 standing directive and per-section summaries; this companion owns the operational bodies for §1 two-tier reporting, §2 / §2.1 layout and numeric-prefix discipline, §2.2 `_outputs/`, §2.3 anti-inflation, §2.4 maintenance suites, §3 orphan-output recovery, §4 reciprocal cross-references, §5 surface imposition, §6 M11 ↔ M12 correspondence, and §7 three-tier scalability (D7).

## Bindings (§0.j five-direction)

- **Drives →** ● Every sub-phase `REPORT.md` body across every plan suite (§1.1 canonical-sections list). ● Every phase rollup `REPORT.md`'s five required behaviors (§1.2 — uniform template, aggregate metrics, surface patterns, phase-level self-check, advance outward declarations). ● Every phase folder's `NN-` prefix and every sub-phase folder's `NNL-` suffix (§2 numeric-prefix discipline). ● Every `_outputs/` durable emission and anti-inflation backlink (§2.2-§2.3). ● Every `*-maintenance` suite routing (§2.4). ● Every orphan-recovery action (§3 — add consumer / add index entry / add producer attribution / retire). ● Every producer-side / consumer-side reciprocal cross-reference closure (§4). ◐ The `orphan-output-grep` mechanical matcher at `conformity/orphan_output_grep.py`.
- **Satisfies →** ● the fifteen-mandate registry row **M12 — Phase Reporting & Canonical Layout** (operational depth tier; standing-directive tier is the parent rule). ● `rules/canonical-layout.md` per-section anchors (each anchor's `(Companion Sub-Rule Anchor)` pointer line resolves to a section here).
- **Established by ↑** ● `rules/canonical-layout.md` (parent rule; this companion carries the operational depth the parent's anchors point to). ● the fifteen-mandate registry (ratifies M12). ● the Pre-Emission Gate row 12.
- **Gated by ←** ● The path-filter (the eight glob patterns) — this rule demand-loads only on plan-suite / phase / migration artifact touches. ● `rules/canonical-layout.md` always-on baseline (parent rule must be live for the per-section anchors to surface and resolve here). ● The trivial-vs-non-trivial threshold (trivial-scope work bypasses the two-tier requirement; this rule's body never engages).
- **Cross-bound with ↔** ↔ `rules/canonical-layout.md` (parent rule; per-section anchors bind this companion). ↔ `rules/agile-sprints.md` (M11 — the §6 M11 ↔ M12 correspondence table is the mutual-reinforcement surface; sprint apparatus and layout / reporting surface bind both ways). ↔ `rules/bidirectional-binding.md` (M10 — §4 reciprocal producer / consumer cross-references operationalize M10 reciprocity at the artifact layer). ↔ `rules/host-discovery.md` (M1 — §1.1 / §1.2 / §2 honor host-discovered conventions for filenames and prefix schemes). ↔ `rules/pre-emission-gate.md` (M4 — bar 12 enforces this rule's two-tier + canonical-layout + orphan-prevention invariants). ↔ `rules/disclosure-ledger.md` (M2 — output / report / orphan-resolution emissions are recorded in the parent's ledger). ↔ `rules/interactive-questions.md` (§6.4 destructive-op canonical option set governs §3's orphan-retirement path; §7.3 borderline-tier inquiry routes through the canonical channel). ↔ `src/apothem/templates/master-index-template.md` (medium+ tier suite-root index per §7.2). ↔ `src/apothem/templates/trace-matrix-template.md` (all-tier trace-matrix surface per §7.2; small tier substitutes a narrative trace table in the plan suite's notes file).
