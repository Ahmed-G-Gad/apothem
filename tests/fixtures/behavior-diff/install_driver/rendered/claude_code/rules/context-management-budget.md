---
name: "context-management-budget"
description: "Path-filtered companion rule carrying the §7 Context Budget Discipline (budget awareness, demand loading, pressure signals) and §7.4 Per-Task Effort Calibration (CM-12d) declared at the parent `context-management.md` rule's §7 anchor; demand-loaded on commands / PROGRESS / plan-suite artifact touches."
pathFilter: "**/commands/**/*.md, **/PROGRESS.md, **/.apothem/plans/**, **/.plans/**"
alwaysApply: false
paths:
  - "**/commands/**/*.md"
  - "**/PROGRESS.md"
  - "**/.apothem/plans/**"
  - "**/.plans/**"
---

<!-- SPDX-License-Identifier: MIT -->

# Rule: Context Budget Discipline (Companion Sub-Rule)

## Purpose

Carry the operational depth of context budget discipline the parent rule `rules/context-management.md` §7 anchors. Demand-loads on commands (the surfaces CM-12d effort calibration guides), `PROGRESS.md` (which records per-phase effort calibrations), or any per-suite plan artifact under `.apothem/plans/**` (where phase-scoped budget decisions land). The parent owns the context-health signals, externalization invariant, compaction-trigger summary, blind-execution invariant, and §7 one-line budget summary; this companion owns the §7.1 / §7.2 / §7.3 / §7.4 operational bodies.

## Obligations

### 7. Context Budget Discipline

**7.1 — Budget Awareness:** always-on rules + CLAUDE.md + system prompt consume a fixed baseline; track what is loaded and avoid redundant reads.

**7.2 — Demand Loading:** load only what the phase requires; release after extraction; never hold two >200-line files concurrently when sequential processing suffices; prefer Resumption Contract snapshots over re-reading full sources.

**7.3 — Pressure Signals:** mandatory externalization + compaction per §3 triggers; key thresholds — >3 large reads in sequence, >500 lines of generated output, or any recall-degradation signal.

**7.4 — Per-Task Effort Calibration (CM-12d):** Effort is a finite resource calibrated per-task to the work's decision-density. Per the agnostic posture (`rules/agnostic-posture.md`), no shipped command pre-sets an effort tier — effort resolves only from the operator's explicit in-conversation choice. CM-12d supplies the *recommended* calibration the operator may apply, expressed on the harness's own effort scale: high-decision-density work warrants the upper tier (prose elicitation, architectural decomposition, forensic audit, and closed-loop remediation — `/plan-spec`, `/plan-generate`, `/plan-review`, `/plan-audit`); mechanical implementation (`/plan-execute`) the middle tier; read-only reporting (`/plan-status`) the lowest. The operator may also author a per-phase calibration in the target `phases/NN-topic/PHASE.md` frontmatter `effort:` field — single-phase-scoped, never persisting across the granular-pause boundary — recorded in the PROGRESS.md Resumption Contract (`**Effort override (this phase):** <value>`). CM-12d ties D1's always-on rule-body sizing to per-task effort calibration: both are token-optimization mechanisms on different surfaces (rule-body sizing vs. command-invocation sizing).

**7.5 — Tool-Call Budget Calibration:** Tool-call *volume* is a finite resource calibrated to the work's decision-density, distinct from §7.4's effort tier (which governs how hard the assistant thinks, not how many calls it issues). The recommended calibration scales the count of read / search / fetch invocations to the shape of the question rather than spending a uniform budget on every task:

- **Single-fact lookup** (a value at a known path, one symbol, one config key) — one targeted call. The `Grep`-then-`Read`-the-cited-range discipline at `rules/large-file-reading.md` §2 is the floor; a known target never triggers a broad sweep.
- **Moderate, bounded research** (a handful of related facts, one subsystem's shape) — a few calls, released after each extraction per §7.2 demand loading.
- **Deep or unknown-shape research** (a question whose surface is not yet mapped, a cross-cutting trace) — many calls, but past a high threshold the work routes to the dedicated research surface (`/research` or `/deep-research`) rather than accreting an unbounded in-conversation sweep that bloats the active context per §7.3.

Over-budget tool use is itself a pressure signal: a sweep that crosses the §7.3 thresholds (>3 large reads in sequence, recall degradation) without converging on the answer indicates the question was deeper-shape than its initial call budget assumed — escalate to the research surface, do not keep sweeping. Cost-awareness extends across agent waves: when work is offloaded to parallel agents, the spawn-overhead and per-task amortization criteria at `rules/agent-orchestration-patterns.md` §2.1.1 bound the dispatch the same way this clause bounds direct tool calls — a thread whose per-task work is a single read does not earn a spawned agent. Like §7.4, this calibration is *recommended*, not enforced: no shipped command pre-sets a tool-call ceiling, and the operator's explicit direction overrides it.

## Enforcement

Path-filtered (the four glob patterns in this rule's `pathFilter` field — `**/commands/**/*.md`, `**/PROGRESS.md`, `**/.apothem/plans/**`, `**/.plans/**`), always-on at every seriousness level when in scope. Demand-loaded companion to `rules/context-management.md` §7: the parent owns the context-health signals (§1), externalization-invariant summary (§2), compaction-trigger summary (§3), blind-execution invariant (§6), §7 one-line budget summary, and §2.6 scratch-convention anchor (delegated to the sibling `context-management-scratch.md`); this companion owns the §7 operational bodies.
