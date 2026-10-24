---
name: "agile-sprints"
description: "Non-trivial multi-step work in host projects runs as disciplined Agile sprints — Sprint Goal + Backlog + Definition of Ready + Definition of Done + Sprint Review + Retrospective + Velocity tracking. The trivial-vs-non-trivial threshold is the ratifiable choice (line-count + scope hybrid). Empirical process control — transparency, inspection, adaptation — applies throughout."
pathFilter: "**/.apothem/plans/**, **/.plans/**, **/phases/**, **/PHASE.md, **/MASTER-PLAN.md, **/PROGRESS.md, **/REPORT.md"
alwaysApply: false
paths:
  - "**/.apothem/plans/**"
  - "**/.plans/**"
  - "**/phases/**"
  - "**/PHASE.md"
  - "**/MASTER-PLAN.md"
  - "**/PROGRESS.md"
  - "**/REPORT.md"
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
