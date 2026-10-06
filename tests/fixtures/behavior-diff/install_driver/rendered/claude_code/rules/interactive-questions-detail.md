---
name: "interactive-questions-detail"
description: "Path-filtered companion to interactive-questions.md carrying the authoring-discipline procedure and the anti-pattern catalog; demand-loaded on path match when a surface authors structured-inquiry invocations."
pathFilter: "**/commands/**/*.md, **/rules/**/*.md, **/skills/**/*.md, **/agents/**/*.md, **/hooks/**/*.md"
alwaysApply: false
paths:
  - "**/commands/**/*.md"
  - "**/rules/**/*.md"
  - "**/skills/**/*.md"
  - "**/agents/**/*.md"
  - "**/hooks/**/*.md"
---

<!-- SPDX-License-Identifier: MIT -->

# Rule: Interactive-Questions Authoring Detail & Anti-Patterns (Companion Sub-Rule)

## Purpose

Carry the demand-load detail for the always-on parent `rules/interactive-questions.md`: the authoring-discipline procedure and the anti-pattern catalog. Loads on path match when a surface authors structured-inquiry invocations, so the detail pays its context cost only where questions are written.

## Authoring Discipline

Author every invocation in five ordered steps:

1. **Write the question first.** One sentence ending in `?`, naming the decision — not the implementation. The question fixes the decision space before any option is drafted.
2. **Derive options from the decision space.** Each option is a distinct, reachable outcome of the question. Two-to-four options (the choice-overload bound); the implicit `Other` covers the long tail. Labels are 1–5 words.
3. **Annotate each option** with the three-segment body per `rules/interactive-questions.md` §3: `rationale:` (observable consequence) · `recommendation:` (taxonomy value) · `default-pointer:` (named default OR `no-default: user decision required`).
4. **Cite a concrete driver** on every non-neutral `recommendation:` value (`recommended` / `discouraged` / `destructive-no-default`) — one of the six driver classes; never a vague-rationale phrase. Downgrade to `acceptable` when no driver supports the claim.
5. **Review before emission** for the four invariants: driver presence (§4), destructive-op no-default floor (§6), label↔body `(Recommended)` consistency (§3 bidirectional bind), and the two-to-four cardinality bound.

## Anti-Patterns

- **DON'T** issue a raw "Please confirm…" / "Which of…" / imperative-plus-`?` as primary input — **BECAUSE** it bypasses the schema and the annotation that biases-check the choice.
- **DON'T** batch destructive files into one invocation — **BECAUSE** per-file confirmation is the floor; one irreversible decision per invocation.
- **DON'T** mark a non-neutral recommendation without a concrete-driver why-clause — **BECAUSE** an un-driven nudge biases the operator invisibly.
- **DON'T** name a default on a destructive question — **BECAUSE** it makes the irreversible action the easy path; destructive ops are universally `no-default`.
- **DON'T** put `(Recommended)` on more than one option in a single-select question, or on a non-`recommended` body — **BECAUSE** the label↔body bind is bidirectional and a stray postfix corrupts the signal.
- **DON'T** fall back to prose silently when structured inquiry is available — **BECAUSE** the degradation MUST be logged with the conversation marker and a ledger row.

## Bindings (§0.j five-direction)

- **Drives →** The authoring review every structured-inquiry invocation passes before emission; the anti-pattern checks the parent §8 sweep matchers operationalize.
- **Satisfies →** The demand-load detail tier for the parent `interactive-questions.md` authoring discipline and anti-pattern catalog.
- **Established by ↑** `rules/interactive-questions.md` (the always-on parent this companion carries detail for, per the parent / companion-sub-rule pattern).
- **Gated by ←** The `pathFilter` glob (demand-loads only when a question-authoring surface is touched).
- **Cross-bound with ↔** `rules/interactive-questions.md` (parent — §9 Authoring Discipline and the Anti-Patterns catalog were moved here under the companion-sub-rule pattern); `rules/interactive-questions-canonical-shapes.md` and `rules/interactive-questions-sweep-matchers.md` (sibling companions carrying the schema worked-examples and the H1–H7 matcher catalog). ↔ `rules/option-annotation-form.md` (choice-overload bound, authoring discipline).
