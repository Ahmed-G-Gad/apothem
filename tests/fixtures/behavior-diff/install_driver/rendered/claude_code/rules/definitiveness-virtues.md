---
name: "definitiveness-virtues"
description: "Path-filtered companion to `rules/definitiveness.md` carrying the operational depth of M8 — Definitiveness, Airtightness, and the Family of Rigorous-Systems Virtues. Demand-loaded when the assistant edits authoring surfaces (Markdown, rules, skills, agents, commands, docs) where prescriptive prose lands: the three hedge-resolution paths with worked examples, the seven-virtue floor, the definitive-form Right/Wrong examples, the airtightness checks, and the failure tells."
pathFilter: "**/*.md, **/CLAUDE.md, **/rules/**, **/skills/**, **/agents/**, **/commands/**, **/docs/**"
alwaysApply: false
paths:
  - "**/*.md"
  - "**/CLAUDE.md"
  - "**/rules/**"
  - "**/skills/**"
  - "**/agents/**"
  - "**/commands/**"
  - "**/docs/**"
---

<!-- SPDX-License-Identifier: MIT -->

# Rule: Definitiveness — Virtues, Resolution Paths, and Failure Tells (Companion Sub-Rule)

## Purpose

Carry the operational depth of **M8 — Definitiveness, Airtightness, and the Family of Rigorous-Systems Virtues** — the three hedge-resolution paths with worked examples, the seven-virtue numbered list with full prose, the definitive-form Right/Wrong examples, the airtightness-checks-beyond-hedging bullet body, and the failure-tells full prose. This companion is path-filtered: it loads when the assistant edits authoring surfaces (Markdown, rules, skills, agents, commands, docs) where prescriptive prose lands, keeping the parent's always-on payload lean while preserving full fidelity at the demand-load surface. The parent rule remains the canonical home for the always-on directive, the closed hedging-vocabulary list (load-bearing for the mechanical matcher), and the one-line summary of the seven virtues.

## Obligations

### 1. Hedging-Vocabulary Resolution — The Three Paths

The closed hedging-vocabulary list lives in the parent rule (load-bearing for the `conformity/hedging_grep.py` matcher). Each occurrence in prescriptive prose MUST resolve on exactly one of three paths:

1. **Promote** to an unconditional form with the conditions named — "the build typically completes in 5 minutes" → "the build completes in 5 minutes when the cache is warm; up to 12 minutes on a cold start (criterion: `~/.cache/<host>` size below the threshold)".
2. **Demote** to an explicit conditional with the branches enumerated — "users should probably commit small changes" → "when the change touches a single revertable unit, commit; when it touches multiple, split the commit per `rules/production-ready-prs.md`."
3. **Remove** when the hedge concedes the prescription does not apply ("this is generally recommended" with no host-specific evidence) — drop the prescription; the option set is underdetermined and routes through the inquiry surface per `rules/authority-inquiry.md`.

The mechanical hedging-grep at `conformity/hedging_grep.py` operationalizes detection at the pre-emission gate per `rules/pre-emission-gate.md` row 8.

### 2. The Family of Rigorous-Systems Virtues — Seven-Virtue Floor

Every emitted artifact passes the seven-virtue floor:

1. **Completeness.** Every declared domain is fully covered. A partial enumeration that lists three of five cases names the omission as `(remaining cases: …)` rather than eliding it.
2. **Closure.** Every `TBD` / `TODO` / `FIXME` / `XXX` / `we'll handle later` is closed in place or surfaced as an inquiry per `rules/authority-inquiry.md`. Open markers in emitted artifacts are non-conformant.
3. **Strong non-contradiction.** No two clauses in the same artifact (or its declared neighbors) contradict each other. The pre-emission gate's M3 dimension 2 (consistency · coherence · integration · validity) at `rules/ten-dimension-check.md` enforces the cross-artifact case.
4. **Determinism.** Same inputs produce the same outputs. Non-deterministic behavior is declared with the source of non-determinism named (random seed, timing-dependent ordering, external-state read).
5. **Exhaustiveness of enumerations.** Every closed enumeration declares the closure with `{a, b, c}` set notation or an explicit "the four classes are X / Y / Z / W". Open enumerations declare the open-set nature with `{a, b, c, …}` and the discovery surface that admits new members.
6. **Specificity over vagueness.** Numbers carry units; thresholds carry comparison operators; durations carry bounds. "Five minutes" is conformant; "around five minutes" is hedging unless the bound is named.
7. **Pre / post / failure conditions on every contract.** Every function, schema, runbook step, CI job, and migration script declares its pre-conditions (what must hold before invocation), post-conditions (what holds after a successful return), and failure modes (what holds after a failure return — exception type, observable state, recovery path).

### 3. Definitive Form — Right / Wrong Examples

A generated rule that says "users should probably commit in small chunks" is non-conformant; the rule says "every commit covers one logical change (criterion: a single revertable unit; an indicator: `git revert <sha>` produces a coherent rollback)" or it does not say it. A generated test description that says "this test should usually pass within 5 seconds" is non-conformant; the description says "this test asserts completion within 5 seconds; if the assertion exceeds, the test fails — hard timeout, not a soft expectation". A generated configuration that says "the cache size is generally 100 MB" is non-conformant; the configuration declares `cache_size_mb: 100` and the comment names the condition under which the value changes.

### 4. Airtightness Checks Beyond Hedging

Hedging-vocabulary elimination is the surface signal; airtightness reaches deeper:

- **No silent fallbacks.** A configuration default carries a comment naming the conditions under which it changes. A library's silent retry-on-error declares its retry budget, back-off, and failure surface.
- **No precedence ties.** When two rules apply to the same surface, the precedence MUST be stated explicitly. The §6 inline-vs-rule-delegated mandate split at `CLAUDE.md` is the canonical pattern — the registry table names which mandate is inline and which is rule-delegated, with no ambiguity.
- **No edge cases for later.** Edge-case handling is part of the contract, not a follow-up. A genuinely out-of-scope edge case carries an explicit `[Deferral — out-of-scope: <description>; tracking: <where>]` ledger entry per `rules/disclosure-ledger.md`.
- **No literal-honoring loopholes.** When the literal text of a directive admits a reading that violates its intent, rewrite the directive to close the loophole. The intent is the contract; the literal text is the carrier.

### 5. Failure Tells — Full Prose

"It might be worth considering" / "this should usually work" / "you may want to" / "it's generally recommended" / "this is broadly compatible" — all in prescriptive contexts where definitiveness is possible. Open-ended exception clauses ("exceptions may apply"). Unstated assumptions surfacing as runtime errors. A rule body that uses "should" where "must" applies and the conditions are knowable. A function with no docstring declaring pre / post / failure. A test description that asserts probabilistic behavior without the probability named. A `TBD` left in a shipped artifact. A configuration default that lacks a comment naming the condition under which the default changes. A precedence tie where two rules apply to the same surface without a stated ordering. A literal-honoring loophole where the directive's intent is violated by an admissible reading of its text. **Simulated tools or fabricated output presented as real** — mock command output, an invented tool result, a hand-written transcript, or a fabricated tool interface offered as if it were a genuine invocation. The airtightness floor admits no fabricated evidence: run the real tool and report its actual output, or, when the tool is unavailable, surface the gap as an inquiry per `rules/authority-inquiry.md` and name what went unchecked — never stand in a plausible-looking invention for the result that was not produced.

## Enforcement

Path-filtered (the seven glob patterns in this rule's `pathFilter` field — `**/*.md`, `**/CLAUDE.md`, `**/rules/**`, `**/skills/**`, `**/agents/**`, `**/commands/**`, `**/docs/**`), always-on at every seriousness level when in scope. Demand-loaded companion to `rules/definitiveness.md`. The parent rule carries the always-on directive, the closed hedging-vocabulary list, and the one-line summary of the seven virtues; this companion carries the operational depth — three hedge-resolution paths with worked examples, the seven-virtue numbered list with prose, the definitive-form Right/Wrong examples, the airtightness-checks-beyond-hedging bullet body, and the failure-tells full prose.

## Bindings (§0.j five-direction)

- **Drives →** Every prescriptive-prose authoring surface under the path-filter (Markdown, CLAUDE.md, rules, skills, agents, commands, docs). The three-path hedge-resolution surface every hedging-grep finding routes through. The seven-virtue floor every emitted artifact passes at the pre-emission gate.
- **Satisfies →** the fifteen-mandate registry row **M8 — Definitiveness, Airtightness** (operational-depth tier; always-on directive lives at the parent rule). `rules/definitiveness.md` parent-rule anchor (the parent's pointer to this companion's full specifications).
- **Established by ↑** `rules/definitiveness.md` (parent-rule anchor — the parent's §"Required behavior" subsections cite this companion for full operational depth). the fifteen-mandate registry (ratifies M8). the Pre-Emission Gate row 8 (M8 mechanical bar).
- **Gated by ←** The path-filter (the seven glob patterns) — this rule demand-loads only on authoring-surface touches. `rules/definitiveness.md` always-on baseline (parent rule must be live for this companion's pointers to surface coherently).
- **Cross-bound with ↔** `rules/definitiveness.md` (parent rule; the always-on directive and closed hedging-vocabulary list live there). `rules/operational-mandates.md` §CM-10 Brutal Honesty (M8 ↔ CM-10 cross-mapping; the inward-axis analog). `rules/disclosure-ledger.md` (M2 — every hedge promotion / removal is recorded in the ledger). `rules/ten-dimension-check.md` (M3 — dimension 2 consistency / coherence + dimension 6 structurality enforce airtightness across artifacts; this rule enforces it within the artifact). `rules/pre-emission-gate.md` (M4 — bar 8 of the gate operationalizes the hedging-vocabulary scan and the pre / post / failure-condition presence check). `rules/authority-inquiry.md` (M5 — removed-prescription cases route to the inquiry surface).
