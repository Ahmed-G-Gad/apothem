---
name: "session-closure-scaling"
description: "Path-filtered companion sub-rule to session-closure.md — carries the universality-and-scaling clause (the close binds every session; depth scales to session weight), the single-canonical-close no-repetition discipline (emit once, report only the delta on re-engagement), and the plan-touching residual detail (plan open items zeroed or explained-or-waived on every plan-touching close). Demand-loaded on plan-suite / context-management / recommend-next-step touches."
pathFilter: "**/.apothem/plans/**, **/context-management*.md, **/recommend-next-step.md, **/session-closure.md"
alwaysApply: false
paths:
  - "**/.apothem/plans/**"
  - "**/context-management*.md"
  - "**/recommend-next-step.md"
  - "**/session-closure.md"
---

<!-- SPDX-License-Identifier: MIT -->

# Rule: Session Closure — Scaling & Single-Canonical-Close (Companion Sub-Rule)

## Purpose

Carry the operational depth of the session-closure discipline the parent rule `rules/session-closure.md` anchors. Path-filtered: loads when the assistant works a plan suite, the context-management externalization surface, the recommend-next-step artifact, or the parent rule itself. The parent retains the always-on directive core (the three closure elements — Recommended Next Step, done/deferred ledger, verification attestation); this companion carries the universality-and-scaling clause (§1), the single-canonical-close no-repetition discipline (§2), and the plan-touching residual detail (§3).

## Obligations

### 1. Universality and Scaling

The close binds **every** session, not only plan-suite work. The phase-exit and Stop-hook externalization at `rules/context-management.md` §2.5 / §3 is the plan-suite materialization; the parent rule extends it to ad-hoc sessions the hook does not reach. Closure **depth** scales to session weight — a trivial exchange emits one line per element, a multi-step mission a full ledger and multi-gate attestation. Depth flexes; **presence does not**. A session emitting zero elements has not closed — it has trailed off.

The scaling clause is what keeps the discipline proportionate: it forbids both the under-close (a heavyweight mission trailing off with no ledger) and the over-close (a one-line exchange dragged through a multi-gate attestation apparatus). The depth dial is set by the session's weight, never picked to minimize effort.

### 2. Single Canonical Close — No Repetition

The three elements are emitted **once**, as one close — never duplicated in the turn, never re-printed unchanged across turns; on a Stop / goal / loop re-engagement, report only the **delta**. Element (a) IS the terminal `## Recommended Next Step` block, not a second copy; the Stop-hook externalization is file-side, not re-narrated.

A re-engagement that re-prints the prior close verbatim is a repetition failure: the operator reads the same three elements twice and cannot tell what changed. The delta-only rule preserves signal — each successive close reports only what moved since the last one, so the closing surface stays a live ledger rather than a growing transcript.

### 3. Plan-Touching Residual Detail (Parent §1(b) Detail)

When the session touched a plan, the done/deferred ledger's completed-and-deferred account carries a further condition: plan open items MUST be zero or each residual explained-or-waived per `rules/planning-techniques.md` §9. This condition binds **every** plan-touching close, not only a `/plan-audit` run — a session that edits a plan phase, ticks off a task, or leaves a plan artifact mid-transition owes the same zero-open-or-explained accounting as the audit command, discharged inline in the close rather than deferred to a later audit. A plan-touching session that closes with residual open items neither zeroed nor explained-or-waived is non-conformant, exactly as it would be under `/plan-audit`; the explain-or-waive obligation is sourced from `rules/planning-techniques.md` §9 and applied here at the session-close scale.

## Enforcement

Path-filtered (the four glob patterns in this rule's `pathFilter` field — `**/.apothem/plans/**`, `**/context-management*.md`, `**/recommend-next-step.md`, `**/session-closure.md`), demand-loaded companion to `rules/session-closure.md`. The parent carries the always-on directive core (the three closure elements); this companion carries the universality-and-scaling clause (§1), the single-canonical-close no-repetition discipline (§2), and the plan-touching residual detail (§3). Together the parent and companion constitute the canonical specification for the session-closure discipline.

## Bindings (§0.j five-direction)

- **Drives →** Every session's depth-calibrated close (the scaling dial set by session weight). Every re-engagement's delta-only report (no verbatim re-print of a prior close). The plan-suite phase-exit externalization's extension to ad-hoc sessions. Every plan-touching close's zero-open-or-explained-or-waived accounting (the §3 residual condition applied inline at the session-close scale).
- **Satisfies →** `rules/session-closure.md` §1(b) + §2 + §3 anchors (the parent rule's pointers to this companion's plan-touching residual detail, universality-and-scaling clause, and no-repetition discipline). The airtight-session-close end state at the correct depth for the session's weight.
- **Established by ↑** `rules/session-closure.md` (parent-rule anchor). `rules/context-management.md` §2.5 (the phase-exit externalization this companion's §1 generalizes to ad-hoc sessions). `rules/planning-techniques.md` §9 (the plan-open-items explain-or-waive obligation this companion's §3 applies at the session-close scale).
- **Gated by ←** The path-filter (the four glob patterns) — this rule demand-loads only on plan-suite / context-management / recommend-next-step / parent-rule touches. `rules/session-closure.md` always-on baseline (parent rule must be live for the anchors to surface).
- **Cross-bound with ↔** `rules/session-closure.md` (parent rule; §1(b) / §2 / §3 anchors bind this companion — the sole self-reciprocal edge; the parent cites this companion back under its own `↔` line). `rules/planning-techniques.md` (§9 — the plan-open-items explain-or-waive obligation the §3 plan-touching residual detail applies at the session-close scale; the parent binds it under its own `↔` line as the source of element (b)'s plan-touching condition). The context-management materialization (↑ above) and the recommend-next-step forward-move element (→ above) are directional, not self-reciprocal, so they sit in those buckets rather than here.
