---
trigger: glob
description: "Path-filtered companion rule carrying the canonical sprint-element bodies (Sprint Goal, Backlog INVEST, DoR, DoD, Review, Retrospective, Velocity), the Three Pillars detail, the Surface Imposition table, and the Failure Recovery table; demand-loaded when the parent `agile-sprints.md` rule's anchors surface."
globs: "**/.apothem/plans/**, **/.plans/**, **/phases/**, **/PHASE.md, **/MASTER-PLAN.md, **/PROGRESS.md, **/REPORT.md"
---

<!-- SPDX-License-Identifier: MIT -->

# Rule: Agile Sprints — Canonical Elements (Companion Sub-Rule)

## Purpose

Specify the canonical sprint-element bodies for the M11 — Agile Process discipline declared at the parent rule's `rules/agile-sprints.md`. This companion is path-filtered: it loads when the assistant edits any of the multi-phase plan or phase-report surfaces where the sprint apparatus is operationalized, keeping the parent's always-on payload lean while preserving full element fidelity at the demand-load surface. The parent rule remains the canonical home for the M11 standing directive, the seven-element summary, the trivial-vs-non-trivial threshold anchor, and the disclosure surface; this companion carries the per-element bodies (§1.1–§1.7), the Three Pillars detail (§2), the Surface Imposition table (§3), and the Failure Recovery table (§4).

## Obligations

### 1. The Canonical Sprint Apparatus — Per-Element Bodies

Every non-trivial multi-step work surface emits the seven canonical elements detailed below.

#### 1.1 Sprint Goal

A **single sentence** stating the sprint's outcome, definitive per `rules/definitiveness.md` (no hedging vocabulary, no `TBD` / `TODO`, pre / post / failure conditions stated where applicable). The goal MUST be **outcome-shaped**, not activity-shaped — "users can authenticate with OAuth" is a goal; "implement OAuth" is an activity. The goal MUST be testable: at sprint close it is either achieved or not, with evidence.

#### 1.2 Sprint Backlog

A **committed, ordered list of work-items** that together achieve the Sprint Goal. Every backlog item is **INVEST-shaped**:

- **Independent.** Each item delivers value alone; cross-item dependencies are explicit and minimized.
- **Negotiable.** The item's scope can be refined at sprint planning without re-deriving the goal.
- **Valuable.** The item advances the Sprint Goal in a way the user can recognize.
- **Estimable.** The item carries a story-point estimate (or a host-discovered alternative — t-shirt size, hours, story points) that fits within the sprint's velocity.
- **Small.** The item fits within the sprint window; items larger than the sprint window are split during planning.
- **Testable.** The item carries acceptance criteria the Definition of Done verifies.

The backlog is **prioritized** — items are ordered by value, dependency, or risk, with the ordering rationale recorded.

#### 1.3 Definition of Ready (DoR)

The DoR is a checklist applied at **sprint entry** to every backlog item. An item that fails the DoR MUST NOT be committed to the sprint; it is returned to the upstream backlog for refinement. The canonical DoR:

- Item description states the change in natural domain language.
- Acceptance criteria are stated and testable.
- Item carries an estimate (story points, hours, or host-discovered unit).
- Item's prerequisites (other items, upstream gates, host-side decisions) are satisfied or explicitly deferred.
- Item's INVEST shape is verified.
- Item's affected scope (files, modules, services, public surfaces) is identified.

The host may extend the DoR with project-specific gates (e.g., security review for items touching auth surfaces, performance benchmark for items touching hot paths) per M1 host-discovery.

#### 1.4 Definition of Done (DoD)

The DoD is a checklist applied at **sprint exit** to every committed backlog item. An item that fails the DoD MUST NOT count toward the sprint's velocity. The canonical DoD:

- Artifact emitted (code / docs / configuration / data) at the canonical layout per `rules/canonical-layout.md`.
- Verification passed (tests, lint, format, type-check, security scan — every gate the host ratifies per M13 code-craft and M15 production-ready).
- Pre-emission gate attestation recorded per `rules/pre-emission-gate.md` (every fifteen-bar check passed or marked `n/a` with reason).
- Bindings updated per `rules/bidirectional-binding.md` (reciprocal back-pointers added in the same change-set).
- Acceptance criteria met (from §1.3 DoR).
- Disclosure ledger updated per `rules/disclosure-ledger.md` (amendments, extensions, refinements, deferrals disclosed).
- Production-ready discipline satisfied per `rules/production-ready-prs.md` (tests + docs + CHANGELOG entry + conformant commit + CI green in the same change-set).

The host may extend the DoD with project-specific gates (e.g., CODEOWNERS approval, security sign-off, performance regression gate) per M1 host-discovery.

#### 1.5 Sprint Review

At sprint close, **every committed backlog item is inspected** against the Definition of Done. The inspector is the **user-as-Product-Owner** by default; where the user has authorized batched review per the continuous-execution discipline at CM-16, the agent simulates the inspection and emits a Sprint Review record the user audits asynchronously.

Each item's inspection outcome is one of three:

- **Approved.** Item meets the DoD. Counts toward the sprint's velocity.
- **Rejected.** Item fails the DoD. Item is returned to the backlog for the next sprint. The rejection reason is recorded against the specific DoD criterion that failed.
- **Carry-forward.** Item is partially complete and the remaining scope is fungible across the sprint boundary. The carried portion enters the next sprint's backlog as a fresh item with refined scope.

The Sprint Review surfaces emergent concerns — items the agent encountered during execution that surface gaps in the host's process (per M6 Expertise Incorporation). Emergent concerns are recorded as findings for the user's decision.

#### 1.6 Sprint Retrospective

After the Sprint Review, a **Sprint Retrospective** identifies **process-adjustment actions for the next sprint**. The retrospective surfaces three classes of observation:

- **Continue.** Process elements that worked and the next sprint should preserve.
- **Stop.** Process elements that produced friction or waste; the next sprint should eliminate them.
- **Start.** Process elements absent from this sprint that the next should adopt.

Retrospective actions are **specific** and **actionable**, not vague (`"do better next time"` is non-conformant; `"add a test-coverage gate to the DoD"` is conformant). Actions enter the next sprint's backlog as process work-items or amend the DoR / DoD checklists in place.

#### 1.7 Velocity Tracking

Velocity is the **count of approved backlog items** (or the sum of their story points / equivalents) per sprint. Velocity feeds **empirical process control**:

- **Transparency.** Velocity is recorded sprint-over-sprint; the trajectory is visible.
- **Inspection.** Velocity changes (rising, falling, oscillating) are inspected for their drivers (scope drift, technical debt, external dependencies, learning curve).
- **Adaptation.** The next sprint's backlog is sized against the rolling velocity; over-commitment is flagged at sprint planning.

Velocity is **not** a performance metric — it is an empirical signal feeding sprint-sizing decisions. Velocity MUST NOT be treated as a target: doing so produces gaming behavior and corrupts the signal.

### 2. Empirical Process Control — The Three Pillars

Throughout the sprint, three pillars operate:

- **Transparency.** Every increment is visible to the user. The Sprint Backlog, work-in-progress items, completed items, and emergent concerns are surfaced at the user's review cadence (real-time at SHARED+, batched at PUBLIC_LAUNCH per CM-16, on-demand at lower seriousness tiers).
- **Inspection.** Every increment is inspected against the Definition of Done at the moment of completion, not deferred to sprint close. The pre-emission gate per `rules/pre-emission-gate.md` operationalizes per-increment inspection.
- **Adaptation.** Every retrospective adapts the next sprint based on what was learned. Adaptations are recorded as process work-items in the next sprint's backlog.

### 3. Surface Imposition — Where Sprints Land

| Surface | Sprint obligation |
|---|---|
| `CLAUDE.md` | Carries the standing directive that non-trivial multi-step work runs as Agile sprints with the canonical apparatus (M11 row in §8 fifteen-mandate registry). |
| `skills/*/SKILL.md` with multi-step procedures | Procedure body is structured as Sprint Planning → Execution → Review → Retrospective. |
| `commands/*.md` with multi-step output | Working trace emits sprint structure (Sprint Goal, backlog of steps, DoD verification per step, retrospective at command exit). |
| `agents/*.md` whose remit is multi-step | Return format organizes work as sprints with DoD attestation. |
| `output-styles/*.md` | Preserve sprint metadata (Sprint Goal, backlog references, retrospective notes) rather than flattening them. |
| Multi-phase plans at `<project-root>/.apothem/plans/*/` | Each top-level phase IS a sprint; the phase apparatus (Goal, Inputs, Outputs, Verification, Report) maps to (Sprint Goal, DoR, DoD, Sprint Review, Retrospective). The mapping is explicit per the M11 ↔ phase-apparatus correspondence at `rules/canonical-layout.md`. |

### 4. Failure Recovery — When Sprint Discipline Lapses

- **Missing Sprint Goal.** Pause execution. Surface the gap as a finding. Author the goal before resuming execution.
- **Backlog item fails INVEST at planning.** Return the item to the upstream backlog for refinement. Do not commit the item to the sprint with a placeholder estimate or unstated acceptance criteria.
- **Item fails DoD at review.** Reject or carry-forward per §1.5. Do not silently lower the DoD bar to admit the item.
- **Retrospective skipped under time pressure.** The retrospective is **mandatory** at SHARED+; skipping it forfeits empirical process control's adaptation pillar. The skip is itself a finding the next sprint's retrospective surfaces.
- **Velocity treated as target.** Velocity is the **signal**, not the **target**. When velocity gaming surfaces (item splitting to inflate count, scope shrinking to claim completion), the retrospective surfaces the corruption and the DoD adapts to close the loophole.

## Enforcement

Path-filtered (the seven glob patterns in this rule's `pathFilter` field — `**/.apothem/plans/**`, `**/.plans/**`, `**/phases/**`, `**/PHASE.md`, `**/MASTER-PLAN.md`, `**/PROGRESS.md`, `**/REPORT.md`), always-on at every seriousness level when in scope. Demand-loaded companion to `rules/agile-sprints.md`. The parent rule carries the M11 standing directive, the seven-element summary, the trivial-vs-non-trivial threshold anchor, the disclosure surface, and the failure-tells; this companion carries the per-element bodies (§1.1–§1.7), the Three Pillars detail (§2), the Surface Imposition table (§3), and the Failure Recovery table (§4).

## Bindings (§0.j five-direction)

- **Drives →** ● The per-element population at every multi-phase plan's `phases/NN-topic/PHASE.md` and parent `MASTER-PLAN.md`. ● Every Sprint Review record's three-outcome classification (approved / rejected / carry-forward) per §1.5. ● Every retrospective's continue / stop / start surface per §1.6. ● The DoR / DoD checklists at every sprint-entry / sprint-exit boundary.
- **Satisfies →** ● the fifteen-mandate registry row **M11 — Agile Sprints** (the demand-load surface for the per-element bodies). ● `rules/agile-sprints.md` parent anchor (the parent rule's pointer to this companion's full element catalog).
- **Established by ↑** ● `rules/agile-sprints.md` (parent-rule anchor). ● the fifteen-mandate registry (ratifies M11). ● The Scrum Guide's empirical process control framework (transparency / inspection / adaptation — the canonical Agile foundation; this rule's §2 Three Pillars subsection is the host-project projection of that framework).
- **Gated by ←** ● The path-filter (the seven glob patterns) — this rule demand-loads only on multi-phase plan / phase-report artifact touches. ● `rules/agile-sprints.md` always-on baseline (parent rule must be live for the companion's anchors to surface). ● The §8.1 trivial-vs-non-trivial threshold (trivial work is exempt from the sprint apparatus).
- **Cross-bound with ↔** ↔ `rules/agile-sprints.md` (parent rule; anchors bind this companion). ↔ `rules/canonical-layout.md` (M12 — phase / sub-phase reporting is the layout-tier surface for sprint outputs; the M11 ↔ M12 correspondence is mutual). ↔ `rules/pre-emission-gate.md` (M4 — bar 11 of the gate enforces sprint-apparatus instantiation; §2 Inspection pillar operationalizes per-increment gate inspection). ↔ `rules/production-ready-prs.md` (M15 — DoD's `production-ready` criterion). ↔ `rules/disclosure-ledger.md` (M2 — sprint apparatus emissions are recorded in the ledger). ↔ `rules/definitiveness.md` (M8 — Sprint Goal must satisfy the definitiveness floor per §1.1).
