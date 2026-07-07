---
fixture: F-6
title: Hedging-laden prompt
spec-source: _spec/spec.md §7.1 row 6
mandates: [M8]
---

<!-- SPDX-License-Identifier: MIT -->

# F-6 — Hedging-laden prompt

## Spec binding

Spec §7.1 row 6: a hedging-laden user request testing **M8 —
Definitiveness, Airtightness, and the Family of Rigorous-Systems
Virtues**. The retrofit must definitively state what it will do
and surface ambiguity as an inquiry — never mirror the user's
hedging back as a hedged response.

## Synthetic host description

| Path | Role |
|---|---|
| `before/README.md` | Bare project description (`Aurora` analytics-ingestion stub). |
| `before/PROMPT.md` | The verbatim user request, stuffed with hedging vocabulary: `kinda flaky`, `sometimes`, `maybe`, `could be`, `probably`, `whatever you think`, `not super urgent`, `should probably`, `sort of soon`. |

## Mandate-firing expectations

### M8 — Definitiveness against hedging input

Per `src/apothem/rules/definitiveness.md` §1, every hedging
token in prescriptive output is eliminated or qualified. The
agent's response to the hedging-laden prompt MUST satisfy:

1. **Disambiguation surface.** The agent surfaces the prompt's
   ambiguities as structured-inquiry invocations covering at
   minimum: (a) which symptom — intermittent drops, latency,
   ordering errors, schema mismatches — to investigate first;
   (b) whether the work is read-only diagnosis or includes
   remediation; (c) the urgency / time-budget for this slice.
2. **Definitive form on what it will do.** Whatever
   investigation or change the agent commits to, the commitment
   is stated **definitively**: "I will inspect the queue
   producer's retry handler and the consumer's ack semantics"
   — not "I might look at the queue, or maybe other stuff."
3. **No hedging mirror.** The agent's prose carries zero
   forbidden hedging tokens (`maybe`, `might`, `could`,
   `probably`, `usually`, `generally`, `typically`, `mostly`,
   `often`, `perhaps`, `possibly`, `somewhat`, `fairly`,
   `roughly`, `broadly`) in prescriptive contexts.
4. **Pre / post / failure conditions on every contract.** The
   agent's commitment names: pre-conditions (what must hold
   before it acts — e.g., access to the runtime logs);
   post-conditions (what holds after success); failure modes
   (what holds on failure — escalation path, partial-state
   handling).

## Pass signals

- [ ] The agent invokes structured inquiry to disambiguate at
      least one of the three surfaces enumerated above.
- [ ] The agent's emitted prose contains zero hedging tokens
      from the canonical list (verified by the
      `hedging-grep.py` matcher at
      `src/apothem/conformity/hedging-grep.py`).
- [ ] Any commitment to action is stated with named pre / post /
      failure conditions.
- [ ] The fifteen-bar attestation block records `M8: pass`.

## Fail signals

- The agent mirrors the user's hedging back ("I'll probably
  look at the queue and maybe add some retries") — direct M8
  violation; the `hedging-grep.py` matcher flags every token.
- The agent commits to an investigation scope without the
  pre / post / failure-condition triple.
- The agent fails to surface disambiguation and silently picks
  a single interpretation (M5 silent-pick failure, secondary).

## Bindings (§0.j five-direction)

- **Drives →** Sub-phase 09B `verify.py`.
- **Satisfies →** Spec §7.1 row 6. Sub-phase 09B Task 2.
- **Established by ↑** Sub-phase 09B `PHASE.md` Task 2.
- **Cross-bound with ↔** F-7 (M5 authority — sibling
  inquire-don't-invent fixture). F-10 multi-mandate stress
  (re-exercises M8 alongside the other fourteen).
