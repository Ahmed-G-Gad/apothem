---
trigger: glob
description: "Every rendered option set carries the (Recommended) marker in its answer header, every terminal surface closes with a named next step, and every command, skill, output-style, and statusline surface holds a deterministic output shape — identical inputs produce identically-shaped output. The determinism harness proves the contract mechanically; the marker and next-step semantics are owned by their dedicated rules and this rule consolidates them under the determinism contract."
globs: "**/commands/**/*.md, **/skills/**/SKILL.md, **/rules/**/*.md, **/output-styles/**/*.md, **/statuslines/**/*.md"
---

<!-- SPDX-License-Identifier: MIT -->

# Rule: Determinism & Advisory Next-Step

## What this rule enforces

The agent renders option sets and terminal surfaces with a strictly-expected output structure. Three invariants bind as **one** determinism contract:

1. **Marker.** Every rendered option set carries the recommended option's `(Recommended)` marker in its answer header.
2. **Next step.** Every terminal surface (command, skill, phase) closes with a definitive named next step.
3. **Shape.** Identical inputs produce identically-shaped output; any non-determinism is declared and its source named.

The harness `conformity/determinism_grep.py` is the executable proof. This rule **consolidates** the marker and next-step semantics owned by `rules/option-annotation.md` and `rules/recommend-next-step.md`; it does not duplicate them — it binds them into the composite contract and adds the output-shape-stability guarantee none of them carries alone.

## Pre-conditions

Applies whenever a command, skill, output-style, statusline, or option-rendering surface is authored or modified.

## 1. The `(Recommended)`-in-header invariant

Every rendered option set MUST carry the recommended option's marker in the answer header: the literal `(Recommended)` postfix at the end of the label, one leading space, bound bidirectionally to the option body's `recommended` value. The canonical placement, separator, case, and bidirectional bind are specified at `rules/interactive-questions-canonical-shapes.md` §2.1; the prose-and-document form uses the inline `**Recommended**` marker per `rules/option-annotation.md`. This rule binds that specification into the determinism contract — it does not restate it.

**Label-only, multi-recommended.** The marker lives SOLELY in the option label. It MUST NOT appear in the accompanying narrative — neither the `rationale:` nor the `recommendation:` body segment carries the postfix string; the body carries verifiable concrete-driver evidence instead. The marker MAY appear on more than one option when the question is `multiSelect: true` (each independently-recommended option carries its own postfix); a `multiSelect: false` question carries the marker on at most one option. A marker string surfacing inside a body/narrative segment is a `narrative-marker-leak` finding at `conformity/option_annotation_grep.py`.

**Concrete-driver requirement.** Every recommended marker MUST carry a rationale grounded in a named concrete-driver class per `rules/option-annotation.md` (locked decision, named risk, named constraint, open-question posture, rule citation, or observed state). A markerless option set where one option dominates, or a recommended marker with no concrete driver, is a defect.

**Call-time enforcement.** Marker well-formedness is checked not only on committed surfaces but on the LIVE `AskUserQuestion` tool payload at call time by the runtime PreToolUse validator (`hooks/askuserquestion_validator.py`), advisory by default and blocking under the strict opt-in. The runtime check guarantees well-formedness (canonical case, placement, at-most-one-per-single-select, never on a destructive option); it cannot force a recommendation to exist — the native payload has no separate recommended field, so a missing marker surfaces only as a heuristic nudge. See `rules/interactive-questions-canonical-shapes.md` §2.1.1.

## 2. The determinant-next-step convention

Every terminal surface MUST close with a `## Recommended Next Step` (or multi-action `## Next Steps`) block naming a definitive, imperative-verb-led action referenced by identifier — never a hedge, never a question, never a silent end-of-document. The canonical block shape and per-surface-class materialization (command, skill, phase) are specified at `rules/recommend-next-step.md`. The matcher `conformity/recommend_next_step_grep.py` enforces presence across command and skill surfaces.

## 3. The deterministic-output contract

Identical inputs MUST produce identically-shaped output. The output-shape-stability contract binds every authored markdown surface — commands, skills, output-styles, statuslines — over its structural signature; the terminal-next-step floor (§2, §4) additionally binds command / skill / phase interaction surfaces, but not output-style and statusline *definition* surfaces (which are not terminal interaction surfaces). The structural signature held stable across runs spans seven dimensions:

1. SPDX authorship-header presence;
2. the frontmatter key set (where the surface carries frontmatter);
3. the ordered H2 heading sequence;
4. the recommended-marker count (`**Recommended**` and `(Recommended)` postfix);
5. the fenced-code language multiset;
6. the bindings-section presence;
7. the terminal next-step form (singular, multi, or absent).

Any non-determinism MUST be declared with its source named — e.g., a surface embedding a generation date marks the date as the non-deterministic element. Undeclared non-determinism — a signature that drifts between identical reads — is a defect. The harness `conformity/determinism_grep.py` computes the signature across repeated reads and asserts byte-stability; a structurally-incomplete surface fails the minimal output-shape floor (header, headings, terminal next-step).

## 4. The advisory-posture invariant

Every interaction MUST close with the single best next action for its current end state. A terminal surface emits exactly one recommended next action calibrated to where the surface ends; a surface ending without a recommended action is a defect. This is the advisory posture: the agent surfaces findings and a forward move, never a silent stop.

## Mechanical enforcement

- `conformity/determinism_grep.py` — composite output-shape signature stability plus the minimal-shape floor, across command and skill surfaces.
- `conformity/option_annotation_grep.py` — the `(Recommended)` marker placement and bidirectional bind on rendered option sets.
- `conformity/recommend_next_step_grep.py` — the terminal next-step block presence across command and skill surfaces.

Findings surface at the pre-emission gate per `rules/pre-emission-gate.md`.

## Disclosure surface

- `[Determinism — signature-drift: <surface>; runs: <N>]` when a surface's structural signature is non-deterministic.
- `[Determinism — incomplete-shape: <surface>; missing: <header | headings | next-step>]` when a surface fails the output-shape floor.

## Failure tells

An option set rendering no `(Recommended)` marker where one option dominates. A recommended marker with no concrete-driver rationale. A command or skill surface ending mid-section with no next-step block. A surface whose structural signature drifts between identical reads with no declared non-determinism source. A terminal surface that stops silently rather than naming the single best next action.

## Bindings (§0.j five-direction)

- **Drives →** every command and skill surface's output shape · the `(Recommended)` marker on every rendered option set · the terminal next-step block on every terminal surface · the mechanical harness `conformity/determinism_grep.py`.
- **Driven by ←** the option-annotation and recommend-next-step conventions this rule consolidates · the pre-emission gate that consumes the harness verdict.
- **Gated by ←** The frontmatter `pathFilter` (commands, skills, rules, output-styles, statuslines): the rule loads when an output-shaping surface is authored or modified. `conformity/determinism_grep.py` (the mechanical harness that checks the expected-output structure under `gate --all`).
- **Satisfies →** the strictly-expected-output-structure end state · the advisory posture (findings plus a forward move, never a silent stop).
- **Established by ↑** `rules/option-annotation.md` · `rules/recommend-next-step.md` · `rules/definitiveness.md` (the determinism virtue).
- **Cross-bound with ↔** `rules/option-annotation.md` · `rules/recommend-next-step.md` · `rules/interactive-questions-canonical-shapes.md` · `rules/definitiveness.md` · `rules/pre-emission-gate.md`. ↔ `rules/agent-capability-discipline-matrix.md` (↔ reciprocal of the peer's Cross-bound citation).
