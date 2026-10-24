---
name: "recommend-next-step"
description: "Every command, skill, and phase artifact closes with a Recommended Next Step block — canonical heading, named action, optional rationale — so terminal output never leaves the operator without a definitive forward move. Hedged or absent next-step blocks are structural failures; the mechanical matcher operationalises the check at the pre-emission gate."
pathFilter: "**/commands/**/*.md, **/skills/**/SKILL.md, **/phases/**/PHASE.md"
alwaysApply: false
paths:
  - "**/commands/**/*.md"
  - "**/skills/**/SKILL.md"
  - "**/phases/**/PHASE.md"
---

<!-- SPDX-License-Identifier: MIT -->

# Rule: Recommended Next Step — Definitive Forward Move on Every Terminal Surface

## What this rule enforces

Every command file, skill entry-point, and phase artifact MUST close its terminal section with a **Recommended Next Step** block naming a definitive forward move the operator can take next — not a hedged suggestion, not a list of possibilities without a recommendation, not a silent end-of-document. Terminal sections that omit the block or carry it in a non-conformant shape are structural failures.

## Pre-conditions

Applies to every artifact under the path-filter — `commands/**/*.md`, `skills/**/SKILL.md`, `phases/**/PHASE.md`. The block lives at the artifact's **tail** (the final section before any closing `## Bindings`, appendix, or metadata footer). Trivial-scope edits that do not modify the terminal section are exempt from re-authoring the block but inherit the existing block's conformance.

## Required behaviour

### 1. Canonical Heading

The block opens with one of two ratified headings:

- `## Recommended Next Step` — **preferred**; single-action terminal surfaces (one canonical forward move).
- `## Next Steps` — acceptable when the surface genuinely admits a small ordered set of forward moves (two or three; **never more than four** — beyond four routes through the option-annotation surface per `rules/option-annotation.md`).

Heading-level drift (`###` / `####`), alternate phrasings (`## What's Next`, `## Follow-Up`, `## Suggested Actions`), and missing headings are non-conformant.

### 2. Named Action

The block body MUST name a **definitive action** that is:

- **Imperative-verb-led.** "Run `apothem verify`", "Author the suite specification", "Invoke `/plan-execute` to advance the next phase". Never a hedged participle ("you might consider running …") nor a question ("should you run X?").
- **Referenced by identifier.** Commands cite their slash-name (`/plan-spec`); scripts cite their path (`scripts/dev/audit.py`); files cite their canonical location.
- **Definitive per `rules/definitiveness.md`.** Hedging vocabulary (maybe, might, could, should probably, usually, typically) is forbidden in the action statement. The block is a binding next-move declaration, not a probabilistic forecast.

### 3. Optional Rationale Clause

The block MAY carry a one-sentence rationale clause naming why this action is the canonical next step. The rationale cites a concrete driver per `rules/option-annotation.md` §2 — observed state of the artifact set, a rule citation, a named prerequisite gate. A rationale clause without a concrete driver is non-conformant; omit the rationale rather than fill it with platitude.

### 4. Multi-Action Form (`## Next Steps`)

When the surface admits multiple forward moves, the block uses an ordered list and marks exactly one entry as **Recommended** per `rules/option-annotation.md`:

```markdown
## Next Steps

1. **Run `apothem verify`** — **Recommended**. Confirms the install reached the canonical end state before further changes land.
2. Inspect `apothem doctor` output — when verify fails, doctor surfaces the failing precondition.
3. Re-run the install with `--force` — only when the verify failure traces to a partial install.
```

A multi-action block without a Recommended marker falls back to the option-annotation rule's zero-recommended fallback (the rationale section names the underdetermined dimensions and routes the choice via inquiry per `rules/authority-inquiry.md`).

### 5. Terminal Placement

The block MUST be the **last substantive section** of the artifact. It precedes only:

- `## Bindings (§0.j five-direction)` (when present per `rules/bidirectional-binding.md`);
- closing metadata / appendix / disclosure footers.

It MUST NOT precede further substantive sections. A `## Recommended Next Step` followed by `## Implementation Details` is a placement violation — the block has been displaced from its terminal role.

### 6. Per-Surface Materialisation

| Surface | Block role |
|---|---|
| `commands/**/*.md` | Names the next command to invoke, the next file to read, or the next operator decision after the command completes. Ties the command into the pipeline shape declared by `rules/canonical-layout.md` M12. |
| `skills/**/SKILL.md` | Names the canonical follow-up after the skill's procedure completes — the verification step, the index-update step, or the next skill in the chain. |
| `phases/**/PHASE.md` | Names the next phase per the suite's progress tracker (`PROGRESS.md` Resumption Contract). Phase rollup REPORTs follow the same discipline at their tail. |

## Mechanical enforcement

The matcher `conformity/recommend_next_step_grep.py` operationalises the check. For every artifact under the path-filter it verifies:

- presence of `## Recommended Next Step` or `## Next Steps`;
- heading placement at the artifact's terminal section per §5;
- absence of hedging vocabulary inside the block body per `rules/definitiveness.md`;
- multi-action form carries exactly one `**Recommended**` marker per §4.

Findings surface at the pre-emission gate per `rules/pre-emission-gate.md` — HIGH-severity on a missing block, MEDIUM-severity on shape drift.

## Disclosure surface

Block emission is recorded in the disclosure ledger per `rules/disclosure-ledger.md`:

- `[Next-Step — emitted: <artifact-path>; heading: <Recommended Next Step | Next Steps>; action: <imperative-summary>]` for new blocks.
- `[Next-Step — refreshed: <artifact-path>; reason: <pipeline-shape-change | action-target-renamed | downstream-surface-retired>]` for updates.

## Failure tells

An artifact ending mid-section with no block. A block headed `## Conclusion` / `## Wrap-Up` / `## What's Next` (heading drift). A block body opening with "You might want to …" / "Consider …" / "It's usually a good idea to …" (hedging — M8 violation). A `## Next Steps` list of seven items with no Recommended marker (cardinality drift; route through `rules/option-annotation.md` instead). A block placed mid-artifact with substantive sections following it (placement violation). A `## Recommended Next Step` whose action names no identifier — "run the next thing" (action under-specified). A rationale clause that says "this is generally the safer path" with no concrete driver (vague-rationale forbid list per `rules/option-annotation.md`).

## Recommended Next Step

**Run `python src/apothem/conformity/recommend_next_step_grep.py .`** to confirm every command and skill terminal Recommended-Next-Step block satisfies the mechanical matcher before the artifact lands at its emission gate.
