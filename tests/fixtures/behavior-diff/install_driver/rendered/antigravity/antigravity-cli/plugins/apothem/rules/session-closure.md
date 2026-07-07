---
name: "session-closure"
description: "Every session — ad-hoc conversational sessions included, not only plan phases — ends with a formal, verifiable close: a terminal Recommended Next Step, a done/deferred ledger, and a verification attestation. A session that trails off mid-thread, claims done without a checked outcome, or buries deferred work silently is a structural failure. Harness-agnostic; the close is rules text every harness honors."
pathFilter: ""
alwaysApply: true
---

<!-- SPDX-License-Identifier: MIT -->

# Rule: Session Closure — Every Session Ends With a Formal, Verifiable Close

## Purpose

A session is finished not when the last edit lands but when it is **closed**. Every session — an ad-hoc exchange as much as a plan phase or multi-step mission — MUST end with a formal, verifiable close. The operator never inherits a trailing-off thread, an unstated "done", or silently dropped work. The close is the session's airtight terminal contract.

## Obligations

### 1. The Three Closure Elements

Every closing turn MUST carry all three, in order:

- **(a) Recommended Next Step.** A terminal, imperative-verb-led, identifier-referenced forward move per `rules/recommend-next-step.md` — the single best action for the session's end state, never a hedge, a question, or a silent stop. On commands / skills / phase artifacts this is the canonical `## Recommended Next Step` block; in conversational prose, one definitive named action.
- **(b) Done / Deferred ledger.** A two-column account: what was **completed** and what was **deferred** — each deferral naming a tracking location per the `[Deferral — …]` marker at `rules/disclosure-ledger.md`. Touched-but-unfinished adjacent work is deferred-with-tracking, never elided. Silent over-completion ("said done, left a gap") and silent over-reach are both non-conformant. When the session touched a plan, plan open items MUST be zero or each residual explained-or-waived. (Companion Sub-Rule Anchor) See `rules/session-closure-scaling.md` §3 for the plan-touching residual detail (the `rules/planning-techniques.md` §9 explain-or-waive obligation binding every plan-touching close, not only a `/plan-audit` run).
- **(c) Verification attestation.** A statement of **what machine-checkable condition was checked and its outcome** — a gate, test, build, or read a third party reproduces, with pass / fail / n-a-with-reason. Self-assessment ("looks correct") is not a verdict; the attestation cites the objective check behind the completed column. A "done" resting on self-assessment, or on nothing checked, is non-conformant.

### 2. Universality and Scaling

The close binds **every** session, not only plan-suite work; the plan-suite Stop-hook externalization at `rules/context-management.md` §2.5 / §3 extends to ad-hoc sessions the hook does not reach. Closure **depth** scales to session weight, but **presence does not** — a session emitting zero elements has trailed off, not closed.

(Companion Sub-Rule Anchor) See `rules/session-closure-scaling.md` §1 for the full scaling clause (the under-close / over-close bound).

### 3. Single Canonical Close — No Repetition

The three elements are emitted **once**; on a Stop / goal / loop re-engagement, report only the **delta**, never a verbatim re-print. Element (a) IS the terminal `## Recommended Next Step` block, not a second copy.

(Companion Sub-Rule Anchor) See `rules/session-closure-scaling.md` §2 for the delta-only re-engagement discipline.

## Failure tells

A reply ending mid-thought with no forward move. A "done" resting on self-assessment or nothing checked. Deferred work mentioned in passing without a tracking location, or not mentioned. A completed-claim an unchecked gate contradicts. A plan phase running the Stop-hook externalization while an ad-hoc session beside it closes on none of the three elements. A close with next steps but no ledger, or a ledger but no attestation. The same close re-printed unchanged across turns.

## Bindings (§0.j five-direction)

- **Drives →** ● Every session's terminal turn (the three-element close is the closing-turn floor). ● Every ad-hoc conversational exchange's formal close, extending the plan-suite Stop-hook externalization to sessions the hook does not reach. ● The done/deferred ledger every close emits. ● The verification attestation every "done" claim carries.
- **Satisfies →** ● The airtight-session-close end state (no trailing-off thread, no unverified "done", no silently-dropped work). ● The advisory-posture invariant that every interaction closes with the single best next action.
- **Established by ↑** ● The operator mandate that any session — ad-hoc included — ends with a formal, verifiable close. ● `rules/recommend-next-step.md` (the terminal forward-move element). ● `rules/context-management.md` §2.5 (the phase-exit externalization this rule generalizes to ad-hoc sessions).
- **Gated by ←** ● `CLAUDE.md` always-loaded preamble. ● The §3 scaling clause (a trivial session scales the close down, never away).
- **Cross-bound with ↔** ↔ `rules/session-closure-scaling.md` (path-filtered companion sub-rule carrying the §1 universality-and-scaling clause, the §2 single-canonical-close no-repetition discipline, and the §3 plan-touching residual detail; the parent §1(b) / §2 / §3 anchors bind this companion). ↔ `rules/recommend-next-step.md` (element (a) — the terminal Recommended Next Step the close opens with; this rule binds it as one of three closure elements for every session, not only path-filtered terminal artifacts). ↔ `rules/context-management.md` (element (b)+(c) — the Stop-hook / §2.5 phase-exit externalization is the plan-suite materialization of this close; this rule extends it to ad-hoc sessions). ↔ `rules/disclosure-ledger.md` (M2 — the done/deferred ledger's deferral entries use the `[Deferral — …]` marker; the completed column is the change's disclosure surface). ↔ `rules/pre-emission-gate.md` (M4 — the verification attestation element mirrors the gate's per-bar attestation at the session scale; a close's "checked" column is the session-level analog of the gate's bar attestation). ↔ `rules/planning-techniques.md` (§9 — element (b)'s plan-open-items condition binds every session close that touched a plan; the residual explain-or-waive obligation is sourced there, not re-specified here). ↔ `rules/production-ready-prs-surfaces.md` (§5 — a documented residual lint / type-check warning is recorded in the session's verification attestation).
