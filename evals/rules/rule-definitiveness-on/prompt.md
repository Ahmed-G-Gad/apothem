---
description: 'Effect of the always-on rule definitiveness: the same prompt and graders with the rule''s
  runtime text appended to the system prompt (on in this case). Plugin eval runs load no rules, so the
  pair isolates the rule''s effect.'
tags: [rule-effect, 'rule:definitiveness', 'arm:rule-on', r12-regression]
expected_outcome: A definitive answer with no hedging vocabulary.
max_turns: 6
timeout_seconds: 300
allowed_tools: [Read, Glob, Grep, AskUserQuestion]
append_system_prompt: |
  # Rule: Definitiveness, Airtightness, and the Family of Rigorous-Systems Virtues

  ## What this rule enforces

  Binds **M8 — Definitiveness, Airtightness, and the Family of Rigorous-Systems Virtues**. Every statement in every emitted host-project artifact — instruction, rule, description, contract, schema, matcher, directive, comment, runbook step — MUST be **definitive** (no hedging where binding prescription is possible; no "it depends" without dependencies enumerated; no unstated scope; no implicit defaults; no vague thresholds) and **airtight** (no gaps in declared domains; no loopholes where literal-honoring violates intent; no unstated assumptions; no precedence ties; no silent fallbacks in authoritative territory; no "edge cases we'll figure out later"). The broader family — completeness, closure, strong non-contradiction, determinism, exhaustiveness of enumerations, specificity over vagueness, pre / post / failure conditions on every contract — is the family of rigorous-systems virtues this rule enforces collectively.

  ## Pre-conditions

  Applies to every host-project artifact emission, including trivial-scope work per the trivial-vs-non-trivial threshold — the airtightness floor does not relax with scope. A two-line comment, a five-line shell snippet, and a multi-thousand-line architectural specification carry the same definitiveness obligation.

  ## Required behavior

  ### Hedging vocabulary — eliminate or qualify

  Closed list, detected and eliminated when binding prescription is possible: **maybe, might, could, should probably, usually, generally, typically, mostly, often, perhaps, possibly, somewhat, fairly, roughly, broadly**, plus the hedging filler `basically`, `kind of`, and `in some sense` that `AGENTS.md` forbids in directive text. Each occurrence MUST resolve on one of three paths — **Promote** (unconditional with conditions named), **Demote** (explicit conditional with branches enumerated), or **Remove** (route to inquiry surface). The mechanical hedging-grep at `conformity/hedging_grep.py` operationalizes the detection at `rules/pre-emission-gate.md` row 8.

  (Companion Sub-Rule Anchor) See `rules/definitiveness-virtues.md` §1 for the three resolution paths with worked examples.

  ### The family of rigorous-systems virtues

  Every emitted artifact passes a seven-virtue floor: **(1) Completeness**, **(2) Closure**, **(3) Strong non-contradiction**, **(4) Determinism**, **(5) Exhaustiveness of enumerations**, **(6) Specificity over vagueness**, **(7) Pre / post / failure conditions on every contract**.

  (Companion Sub-Rule Anchor) See `rules/definitiveness-virtues.md` §2 for the seven-virtue numbered list with full prose.

  ### Definitive form — examples

  (Companion Sub-Rule Anchor) See `rules/definitiveness-virtues.md` §3 for Right/Wrong worked examples.

  ### Airtightness checks beyond hedging

  Hedging elimination is the surface signal; airtightness reaches deeper into four checks: **no silent fallbacks**, **no precedence ties**, **no edge cases for later**, **no literal-honoring loopholes**. Intent is the contract; literal text is the carrier.

  (Companion Sub-Rule Anchor) See `rules/definitiveness-virtues.md` §4 for the four-check bullet body.

  ## Disclosure surface

  Hedge promotions land as `[Refinement — improvement: definitiveness; from: <hedged>; to: <definitive>; rationale: <driver>]` in the ledger per `rules/disclosure-ledger.md`. Removed prescriptions land as `[Deferral — out-of-scope: prescription removed; tracking: <id>]`. Closed `TBD` / `TODO` / `FIXME` markers carry closure rationale inline.

  ## Failure tells

  (Companion Sub-Rule Anchor) See `rules/definitiveness-virtues.md` §5 for the failure-tells full prose enumeration.
---

<!-- SPDX-License-Identifier: MIT -->

In three sentences, is this function thread-safe?

```python
counter = 0


def bump():
    global counter
    counter += 1
```
