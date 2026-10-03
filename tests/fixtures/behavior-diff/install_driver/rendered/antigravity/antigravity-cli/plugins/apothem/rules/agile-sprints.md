---
trigger: always_on
description: "Non-trivial multi-step work in host projects runs as disciplined Agile sprints — Sprint Goal + Backlog + Definition of Ready + Definition of Done + Sprint Review + Retrospective + Velocity tracking. The trivial-vs-non-trivial threshold is the ratifiable choice (line-count + scope hybrid). Empirical process control — transparency, inspection, adaptation — applies throughout."
---

<!-- SPDX-License-Identifier: MIT -->

# Rule: Agile Process — Sprints, DoR / DoD, Empirical Process Control

## What this rule enforces

Binds **M11 — Agile Process — Sprints, DoR / DoD, Empirical Process Control**. Non-trivial multi-step work in a host project MUST be structured as disciplined Agile sprints carrying the seven canonical elements (Sprint Goal, Backlog, DoR, DoD, Review, Retrospective, Velocity) under empirical process control — transparency, inspection, adaptation.

## Pre-conditions

Applies whenever the agent undertakes non-trivial multi-step work, per the trivial-vs-non-trivial threshold ratified once at the trivial-vs-non-trivial threshold (and any project-scope override per §3). Trivial work is exempt; the threshold MUST NOT be silently picked per task.

## Required behavior

### 1. Seven Canonical Elements

Every non-trivial multi-step work surface MUST emit all seven: Sprint Goal (outcome-shaped, testable), Sprint Backlog (INVEST-shaped, prioritized), Definition of Ready (sprint-entry gate), Definition of Done (sprint-exit gate), Sprint Review (approved / rejected / carry-forward per item), Sprint Retrospective (continue / stop / start), Velocity Tracking (signal, never target).

(Companion Sub-Rule Anchor) See `rules/agile-sprints-elements.md` §1 for per-element bodies.

### 2. Three Pillars of Empirical Process Control

Transparency, inspection, adaptation operate throughout every sprint.

(Companion Sub-Rule Anchor) See `rules/agile-sprints-elements.md` §2 for pillar detail.

### 3. Trivial-Threshold Anchor

The trivial-vs-non-trivial threshold is ratified once at the trivial-vs-non-trivial threshold; a project-scope override per §8.1 honors M1 host-discovery and cites its ratifying source. Host silence at the boundary routes through `rules/authority-inquiry.md` with the §8.1 default as the **Recommended** option per `rules/option-annotation.md`.

### 4. Surface Imposition

The apparatus binds `CLAUDE.md`, multi-step skills / commands / agents, output-styles (preserved), and multi-phase plans (each phase IS a sprint per the M11 ↔ M12 correspondence at `rules/canonical-layout.md`).

(Companion Sub-Rule Anchor) See `rules/agile-sprints-elements.md` §3 for the surface table.

### 5. Failure Recovery

A missing Sprint Goal, an INVEST-failing item, a DoD-failing item, a skipped retrospective, and velocity-as-target gaming each carry a specific recovery path; none MAY collapse silently into a passing sprint.

(Companion Sub-Rule Anchor) See `rules/agile-sprints-elements.md` §4 for the recovery table.

## Disclosure surface

Every sprint apparatus emission is recorded in the disclosure ledger per `rules/disclosure-ledger.md` with `[Sprint — opened …]` at planning, `[Sprint — increment …]` at each Review item (approved / rejected / carry-forward outcome plus DoD pass / fail lists), `[Sprint — retrospective …]` at close (continue / stop / start plus velocity), and `[Sprint — adaptation …]` when DoR / DoD checklists are amended.

## Failure tells

A bulk multi-day diff with no sprint structure or retrospective. A Sprint Goal phrased as activity rather than outcome. Backlog items without estimates or acceptance criteria. DoD with `n/a` on every criterion. Rubber-stamp Reviews. Vague retrospective actions. Velocity collected but never inspected. Non-trivial work emitting no apparatus (silent threshold-pick). Trivial scope emitting full apparatus (over-calibration). Project-scope threshold override without ratifying-source citation.

## Bindings (§0.j five-direction)

- **Drives →** ● Every non-trivial multi-step work surface in every host project (the seven canonical sprint elements are the work-shape floor). ● Every `skills/*/SKILL.md` multi-step procedure (Sprint Planning → Execution → Review → Retrospective). ● Every multi-phase plan's per-phase apparatus (the M11 ↔ phase-apparatus correspondence). ● The empirical process control's three pillars (transparency, inspection, adaptation) at every sprint cadence. ● The pre-emission gate's per-increment DoD inspection per `rules/pre-emission-gate.md`.
- **Satisfies →** ● the fifteen-mandate registry row **M11 — Agile Sprints**. ● the Pre-Emission Gate row 11 (M11 agile-sprints check). ● the trivial-vs-non-trivial threshold (this rule operationalizes the §8.1 ratification at sprint planning).
- **Established by ↑** ● the fifteen-mandate registry (ratifies M11). ● the trivial-vs-non-trivial threshold (the trivial-threshold ratification). ● the Pre-Emission Gate row 11. ● The Scrum Guide's empirical process control framework (transparency / inspection / adaptation — the canonical Agile foundation; this rule's §2 Three Pillars subsection is the host-project projection of that framework).
- **Gated by ←** ● The §8.1 trivial-threshold (trivial work is exempt from the sprint apparatus). ● `CLAUDE.md` always-loaded preamble. ● `rules/expertise-posture.md` calibration ladder (depth-to-task calibration governs whether sprint apparatus is the right scale; over-calibration on trivial work is non-conformant per §6's failure tells).
- **Cross-bound with ↔** ↔ `rules/agile-sprints-elements.md` (path-filtered companion sub-rule carrying §1 per-element bodies, §2 Three Pillars detail, §3 Surface Imposition table, §4 Failure Recovery table). ↔ `rules/canonical-layout.md` (M12 — phase / sub-phase reporting; the M11 ↔ M12 correspondence is mutual). ↔ `rules/pre-emission-gate.md` (M4 — bar 11 enforces sprint-apparatus instantiation). ↔ `rules/expertise-posture.md` (M6 — calibration ladder cross-references the trivial-threshold). ↔ `rules/production-ready-prs.md` (M15 — DoD's `production-ready` criterion). ↔ `rules/disclosure-ledger.md` (M2 — sprint emissions recorded). ↔ `rules/definitiveness.md` (M8 — Sprint Goal definitiveness floor). ↔ `rules/agnostic-posture.md` (the sprint apparatus is opt-in under the host-agnostic posture, not a default-on obligation). ↔ `rules/canonical-layout-reporting-tiers.md` (M11 — the §6 M11 ↔ M12 correspondence table is the mutual-reinforcement surface; sprint apparatus and layout / reporting surface bind both ways). ↔ `rules/expertise-posture-elements.md` (↔ reciprocal of the peer's Cross-bound citation). ↔ `rules/pre-emission-gate-bars.md` (this rule is among the M-rules named in the gate's "Failure → action" column; the bar-level catalog cross-binds each).
