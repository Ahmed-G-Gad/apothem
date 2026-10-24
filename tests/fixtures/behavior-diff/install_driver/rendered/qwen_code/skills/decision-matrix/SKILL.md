---
name: "decision-matrix"
version: "0.1.0"
updated: "2026-10-24"
description: "Choose between two or more options with a weighted, evidence-cited matrix. Matched when the user asks to 'compare these options', 'help me choose between', 'weigh the trade-offs', or 'which one should we pick'. Eliminates dealbreakers first, tests whether the winner flips under weight changes, names a runner-up and a first step. Never invents weights."
archetype: "research-template"
userInvocable: true
argument-hint: "[decision question]"
disable-model-invocation: false
allowedTools:
  - "Read"
  - "Glob"
  - "Grep"
  - "WebSearch"
---

<!-- SPDX-License-Identifier: MIT -->

## Purpose

Turn a choice between named options into a reasoned, checkable recommendation. The skill makes the criteria, the weights, and the evidence behind every score visible, so the user can disagree with a specific number rather than with a verdict. A result that flips under a small weight change is reported as a close call, not as a winner.

## Detection Signal

The user asks to `compare these options`, `help me choose between`, `weigh the trade-offs`, or `which one should we pick`, or hands over two or more candidates (libraries, designs, vendors, plans, approaches) and wants a decision.

**Falsifiable counter-signal.** A factual lookup with one answer, a request to implement an option already chosen, or a question about a single candidate with no alternative is NOT a match.

## Non-Goals

- **Not a decider by fiat.** Weights express the user's priorities. When they are unknown the skill asks; it never fills them in and presents the result as settled.
- **Not an implementer.** It ends at a recommendation and a first step; carrying out the option is a separate task.
- **Not a research pipeline.** It gathers only the evidence needed to justify a score. Open-ended multi-source research belongs to `skills/multi-source-research/SKILL.md`.

## Workflow

Six steps, in order. Scoring never starts before step 3 completes.

1. **Frame the decision.** State the question in one sentence and list the options (at least two). Name any option the user did not list but the evidence makes obvious, and ask whether to include it. Include "do nothing" when staying put is a real choice.
2. **Fix criteria and weights.** List 3 to 7 criteria, each phrased so a higher score is better (for example 'low operating cost', not 'cost'). Assign integer weights summing to 100. Weights the user supplied are used as given; if they do not sum to 100, show the rescaled figures and confirm them. When any weight is unknown, ask through the structured-inquiry channel and attach a recommended default set with the reason for each figure; the default takes effect only when the user accepts it. Record separately which weights came from the user and which from an accepted default.
3. **Apply dealbreakers.** Ask for hard constraints (budget ceiling, required license, platform support, deadline). Test every option against each one, citing evidence, before any scoring. An option that fails is eliminated regardless of how it would score, and the elimination is listed with its reason. If one option survives, it is the answer: skip steps 4 and 5, mark `scores` and `sensitivity` as not applicable (sole survivor) and `runner-up` as none, and still give step 6. If none survive, stop and ask which dealbreaker to relax.
4. **Score the survivors.** Score each option on each criterion from 0 to 10 using the anchors in `references/scoring-and-sensitivity.md`. Every cell carries a one-line justification and an evidence pointer: a file and line, a URL, a measured figure, or a quoted user statement. Evidence that cannot be found leaves the cell marked `unknown` with a low and a high bound; a score is never guessed to fill the grid. Compute each total as the sum of weight times score, divided by 100; a cell marked `unknown` enters the base total at the midpoint of its bounds and the total is flagged provisional.
5. **Test sensitivity.** Perturb each weight by plus 20 percent and by minus 20 percent of its own value, rescale the other weights proportionally so the sum stays 100, and recompute the totals. Also recompute with every `unknown` cell at its low bound and at its high bound. Record each case where the winner changes. The result is a close call when any case flips the winner or when the top two totals differ by less than 0.5. Procedure and table shape are in `references/scoring-and-sensitivity.md`.
6. **Conclude.** Emit the record below. For a close call, present the top two options as tied on the evidence and say what would separate them, not a single pick.

## Return Contract

One record per decision, all fields populated:

| Field | Content |
|-------|---------|
| `question` | The decision in one sentence |
| `options` | Options considered, with those eliminated by a dealbreaker and the reason |
| `weights` | Criteria with integer weights, each marked user-supplied or accepted-default |
| `scores` | The option-by-criterion grid with justification and evidence per cell |
| `sensitivity` | Each perturbation that flips the winner, or `none flipped` |
| `recommendation` | The chosen option, or the tied pair when the result is a close call |
| `runner-up` | The strongest alternative and the criterion where it leads most, or `none` |
| `would change if` | The specific evidence or weight shift that changes the answer |
| `first step` | The cheapest reversible action that moves toward the recommendation |

A record with any field unpopulated is non-conformant.

## Foundational Stanzas

### Refusal & Escalation

Decline to pick a winner from invented weights, to score a cell without evidence, or to run an option's implementation under this skill. Name the boundary crossed and offer the way forward through the structured-inquiry channel per `rules/interactive-questions.md`: supply the weights, supply the evidence, or accept a flagged default. When the user rejects every default and supplies nothing, report the grid as unweighted and say so in the recommendation field.

### Output Surface

The record prints to STDOUT as a markdown table plus short prose. Nothing is written to disk unless the user asks for the record to be saved, in which case it goes to the path the user names or the host's documented decision-record location per `rules/host-discovery.md`.

### File-Authoring Contract

A saved record is a new file and routes through `scripts/inject-header.py`; exempt classes are listed in `src/apothem/schemas/header-exceptions.txt`. A record printed to STDOUT is header-exempt.

### Structured Inquiry on Ambiguity

Unknown weights, an unclear dealbreaker, an option list that may be incomplete, and a score the evidence cannot settle are all questions, not assumptions. Ask through the structured-inquiry channel per `rules/interactive-questions.md` with a rationale, a recommendation, and a default pointer for each option, and discover host facts per `rules/host-discovery.md` before asking about them.

## Recommended Next Step

**Take the first step the record names** — it is chosen to be cheap and reversible; if the `would change if` evidence turns up during it, rerun the matrix with the new figure.

## Bindings (§0.j five-direction)

- **Drives →** ● Every decision record emitted with the nine fields of the Return Contract. ● The first-step recommendation handed to the user.
- **Satisfies →** ● `CLAUDE.md` Ambiguity Handling (unknown weights are asked about, never invented). ● `CLAUDE.md` Source Layout row for the skills/ class.
- **Established by ↑** ● `skills/README.md` (this skill's index entry). ● `CLAUDE.md` Source Layout (folder-with-`SKILL.md` convention).
- **Gated by ←** ● The harness's Read / Glob / Grep / WebSearch surface for gathering evidence. ● User-confirmed options, dealbreakers, and weights before scoring starts.
- **Cross-bound with ↔** ↔ `rules/interactive-questions.md` (the channel for weight and dealbreaker questions). ↔ `rules/host-discovery.md` (host facts are discovered, never assumed). ↔ `skills/multi-source-research/SKILL.md` (deeper evidence gathering when a score needs it).
