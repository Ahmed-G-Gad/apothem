---
trigger: glob
description: "Caps every always-on rule body at 500 substantive tokens and the whole always-on set at a byte ceiling (four core rules plus the rule index); over-budget bodies decompose into path-filtered companion sub-rules per the established demand-load pattern; mechanical matcher and PreToolUse hook enforce the budget at write time."
globs: "src/apothem/rules/*.md, **/rules/*.md"
---

<!-- SPDX-License-Identifier: MIT -->

# Rule: Token-Budget Discipline for Always-On Rules

## Purpose

Always-on rules load every session; body length multiplies every turn's cost. This rule caps each always-on body so the tier stays small and load-bearing — detail moves to the demand-load surface, where it costs only when relevant.

## Obligations

### 1. Ceiling and Warn Band

- **MAX_SUBSTANTIVE_TOKENS = 500.** Hard ceiling per always-on body. An always-on body over 500 MUST NOT ship.
- **WARN_BAND_THRESHOLD = 450.** Bodies at 450–500 pass but emit an advisory; the author SHOULD plan a companion before the ceiling triggers.

### 2. Substantive-Token Counter

A substantive token is a whitespace-separated token in the body after excluding three regions:

1. YAML frontmatter (between the head `---` delimiters).
2. The trailing `## Bindings (§0.j five-direction)` section through end of file.
3. Every line containing `(Companion Sub-Rule Anchor)`.

None of the three is a standing directive — frontmatter classifies, bindings point, pointer lines name surfaces — so none counts.

### 3. Always-On Classification

A rule is always-on **iff** frontmatter declares `alwaysApply: true` AND `pathFilter:` is empty. Path-filtered rules (`alwaysApply: false` OR non-empty `pathFilter`) demand-load on glob match and are exempt — their cost is paid only when the filter activates.

### 4. Decomposition Pattern (Companion Sub-Rule Anchor)

When an always-on body would exceed the ceiling, decompose along a natural path-filtered seam:

- Author a sibling at `rules/<parent-name>-<aspect>.md` with `alwaysApply: false` and a `pathFilter:` matching the demand-load triggers.
- Move detail (catalogs, sub-cases, exhaustive enumerations, executable specs, worked examples) to the companion.
- Trim the parent to load-bearing anchors plus the `(Companion Sub-Rule Anchor)` pointer naming the companion path.
- Cite the companion under the parent's `Cross-bound with ↔`.

Precedents: `rules/context-management.md` ↔ `rules/context-management-scratch.md`; `rules/interactive-questions.md` ↔ `rules/interactive-questions-sweep-matchers.md`.

### 5. Reading Discipline

Mid-session, read only the needed segment: `Read` with `offset` / `limit`; `Grep` to locate first; `Glob` for traversal. NEVER full-read when a segment suffices.

### 6. Mechanical Enforcement

`conformity/always_on_budget_grep.py` measures every `rules/*.md`; PreToolUse Write/Edit hooks fire it on rule edits; the pre-emission gate FAILs on any always-on body over the ceiling. Pointed at the shipped rules directory, it also enforces the aggregate ceiling of §7.

### 7. Aggregate Ceiling

The always-on set is exactly four rules — `agnostic-posture`, `authority-inquiry`, `session-closure`, `context-management` — plus `rules/apothem-rule-index.md`. The ceilings count the source text after the frontmatter, `## Bindings` section included, which is what the `opencode` and `antigravity` adapters load. The `claude_code` adapter writes each rule without that section, so it loads less than the ceilings allow:

- **MAX_ALWAYS_ON_LOADED_BYTES = 40,250.** Ceiling on the loaded bytes of the whole set, about 11.5K tokens at bytes/3.5.
- **MAX_INDEX_LOADED_BYTES = 5,250.** Ceiling on the index file alone.
- A rule MUST NOT join the always-on set unless the same change-set edits the core list in the unit test and, if the bytes require it, both ceilings. That edit is the review gate on what loads in every session.
- Every other rule carries `alwaysApply: false` and a non-empty `pathFilter`, and the index names it, so it stays reachable when no path matches.

## Seriousness Scaling

| Level | Enforcement |
|-------|-------------|
| EXPLORING | Advisory; warn-band notes only |
| PERSONAL_USE | Hard ceiling enforced on rule edits; existing over-budget rules surface as findings |
| SHARED | Hard ceiling enforced; over-budget edits blocked until decomposed |
| PUBLIC_LAUNCH | Full enforcement; matcher exit-non-zero blocks emission per the pre-emission gate |

## Anti-Patterns

- **DON'T** add a paragraph to an always-on body for an edge case — **BECAUSE** the edge case belongs in a path-filtered companion that loads only when on the touch surface.
- **DON'T** raise the ceiling to fit content — **BECAUSE** the ceiling is the discipline; raising it inverts the gradient.
- **DON'T** count pointer lines toward the budget — **BECAUSE** the pointer is the demand-load handle, not a directive.
- **DON'T** promote a rule to always-on to make sure it is seen — **BECAUSE** the index names it and a path match loads it; promotion spends the aggregate ceiling every session.

## Enforcement

Path-filtered — demand-loaded when a `rules/*.md` file is edited — at every seriousness level, scaling per the table above. Implements the D1 token-budget ratification. Canonical specification for always-on rule body sizing and the aggregate ceiling.

## Bindings (§0.j five-direction)

- **Drives →** Every always-on `rules/*.md` body's pre-emission size check; the aggregate byte ceiling on the always-on set; the mechanical matcher at `conformity/always_on_budget_grep.py`; the PreToolUse Write/Edit hook entries that fire the matcher on rule-file edits; every decomposition that splits an over-budget always-on rule into a path-filtered companion.
- **Satisfies →** the rules registry row "Token Budget Discipline"; the "Always-on rule body budget" sub-mandate; the validation gate sub-mandate "PreToolUse hook fires on rule edits; gate FAILs if any always-on body > 500 tokens substantive".
- **Established by ↑** The operator decision to optimize tokens aggressively with explicit budget enforcement; the demand-load companion-sub-rule pattern at `rules/context-management.md` ↔ `rules/context-management-scratch.md` (validated precedent).
- **Gated by ←** The `pathFilter` rule-file globs (demand-loaded when a `rules/*.md` file is edited); the PreToolUse Write/Edit hook entries that wire the matcher.
- **Cross-bound with ↔** `rules/context-management.md` §7 Context Budget Discipline (the budget framework this rule tightens for the always-on tier); `rules/large-file-generation.md` (sibling write-side budget protocol; this rule extends to read-side / always-on-tier sizing); `rules/persistent-conventions-vigilance.md` §4 Ecosystem Gap Detection (the demand-load companion-sub-rule pattern is itself a gap-closure); `rules/performance-discipline.md` §1 per-class budgets (the budget methodology); `conformity/always_on_budget_grep.py` (the mechanical matcher); `rules/token-efficiency-rewrite.md` (sizing pair — this rule caps; that rule rewrites to fit the cap); `rules/large-file-reading.md` (read-side analogue of the always-on body-size ceiling; both rules optimize the same gradient on different surfaces). ↔ `rules/context-management-budget.md` (D1 always-on rule body sizing — the rule-body lever; this companion governs the command-invocation lever; both close CM-12d's two-surface token-optimization mandate). ↔ `rules/token-efficiency-rewrite-protocol.md` (the always-on body sizing cap this rewrite fits content into). ↔ `rules/apothem-rule-index.md` (the one always-on file the aggregate ceiling names; the index keeps every path-scoped rule reachable).
