---
description: 'Effect of the always-on rule session-closure: the same prompt and graders with the rule''s
  runtime text appended to the system prompt (on in this case). Plugin eval runs load no rules, so the
  pair isolates the rule''s effect.'
tags: [rule-effect, 'rule:session-closure', 'arm:rule-on', rule-scoping-regression]
expected_outcome: The closing reply carries a Recommended Next Step, a done/deferred account, and what
  was checked.
max_turns: 6
timeout_seconds: 300
allowed_tools: [Read, Glob, Grep, AskUserQuestion]
append_system_prompt: |
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
---

<!-- SPDX-License-Identifier: MIT -->

Rename the variable tmp to total in this function and tell me when you are done:

```python
def add(a, b):
    tmp = a + b
    return tmp
```
