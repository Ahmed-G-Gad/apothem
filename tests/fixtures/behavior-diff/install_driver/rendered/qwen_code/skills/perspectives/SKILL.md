---
name: "perspectives"
version: "0.1.0"
updated: "2026-10-25"
description: "Answers a contested question by arguing it from several separate viewpoints, then reconciling them, when the user asks to 'argue both sides', 'what would a skeptic say' or 'we are split on'. Weighted choices go to decision-matrix, claim checks to fact-checker, builds and reviews to workflow."
archetype: "research-template"
userInvocable: true
argument-hint: "[contested question] [--isolated]"
disable-model-invocation: false
allowedTools:
  - "Read"
  - "Glob"
  - "Grep"
  - "WebSearch"
  - "Agent"
---

<!-- SPDX-License-Identifier: MIT -->

## Purpose

Answer a question that informed people disagree on by running several viewpoints on it separately, each arguing from evidence, and then reconciling them. One voice tends to give one fluent answer and hide its weakest step. Separate viewpoints show whether the answer turns on a fact, a priority, or a definition. The output is a recommendation with a stated confidence and the strongest dissent still in view, not a consensus.

## Detection Signal

The user asks to `argue both sides`, `what would a skeptic say`, or `we are split on`, or poses a judgment question whose dispute is about facts, priorities, or framing rather than about a scored list of options: whether a rewrite is worth it, whether a policy will backfire, whether a design is sound.

**Falsifiable counter-signal.** A question that one lookup settles, or a request to write up a conclusion the user already holds, is NOT a match.

## Non-Goals

- **Not a vote.** Viewpoints are never counted. Weight comes from evidence that was opened and checked.
- **Not a scoring tool.** Named options with agreed criteria go to `skills/decision-matrix/SKILL.md`.
- **Not claim verification.** A claim to confirm or refute goes to `agents/fact-checker.md`. A viewpoint marks the claims it could not check; it does not verify them.
- **Not a build or review mission.** Multi-agent construction or audit goes to `skills/workflow/SKILL.md`.
- **Not professional advice.** Personal medical, legal, or investment advice is out of scope; the skill can lay out the positions and the evidence in general terms.

## Workflow

Seven steps, in order. Reconciliation (step 6) starts only after every viewpoint is complete.

1. **Frame.** State the question in one sentence, worded so that no side is presupposed, and say what would settle it. If one lookup settles it, give that answer and stop: an uncontested question is a valid result. If the question bundles several, split it and ask which comes first. Note any leaning the user showed; it is kept out of the viewpoint briefs.
2. **Choose viewpoints.** Pick 3 to 5 (default 4) from `references/viewpoint-roster.md`, fitted to the question. Each has a stance, a stake, and an evidence remit. Include one for and one against the proposition, include at least one positioned against the user's leaning, and give no two viewpoints the same stake. Add the domain expert when the question has a technical or empirical core and the pragmatist when cost, time, or reversibility matter. Record the roster before any viewpoint runs. Use viewpoints the user named, and add the missing opposing one.
3. **Choose the run mode.** Isolated: each viewpoint is its own subagent. It needs a harness that offers subagents and subagent dispatch switched on, by the user's request (`--isolated`, 'run them separately') or the profile's dispatch flag, per `rules/agnostic-posture.md` §1. Sequential is the default: all viewpoints are written in this context, one after another. State the mode in the record. Sequential runs have weaker independence, because each later block is written by a context that already holds the earlier ones.
4. **Run the viewpoints.** Every brief carries the neutral question, the role's stance, stake, and evidence remit, the same shared context for all (files, constraints, figures the user gave), and the return template from the roster reference. A brief never carries another viewpoint's output or the user's leaning. In isolated mode, launch all subagents in one message per `rules/agent-orchestration.md`. In sequential mode, do each viewpoint's lookups inside its own block, write the block to completion before starting the next, never refer back to an earlier block, never edit one after a later block exists, and write the viewpoint furthest from the user's leaning first.
5. **Check the returns.** A viewpoint that cites another one's output is contaminated: rerun it or report it as contaminated. A viewpoint with no evidence behind its claims, or one that only restates the question, is reported as thin, never dropped silently. Claims resting on recalled figures stay marked unchecked. A viewpoint that rests a claim on a proof, a reported number, or a novelty statement states it as `rules/authoritative-referencing-assurance.md` §1 to §4 require (assumptions and weakest step, the run behind the number, the closest prior work), or marks it unchecked.
6. **Reconcile.** Write four parts in this order.
   - **Agreement.** Points two or more viewpoints share. For each, say whether they rest on separate evidence or on the same source or assumption. Agreement between viewpoints run on one model is coverage, not independent confirmation.
   - **Disagreements.** Keep only real ones; fold apart those that dissolve once a term is defined. Classify each as fact, priority, definition, or forecast, and name the evidence that would settle it and what getting it costs. When one or two reads or searches would settle a fact, get them before recommending and report what they showed.
   - **Recommendation.** One position, not an average and not a split of the difference unless the evidence supports the middle. Give the confidence, the assumptions it rests on, and the conditions that would reverse it. A disagreement about priorities goes to the user through structured inquiry with a recommended default; the skill does not pick the user's priorities.
   - **Strongest dissent.** The best argument against the recommendation, in the dissenting viewpoint's own words, not softened.
7. **Close.** Emit the record. Name the cheapest test that would settle the largest open disagreement. If the run was sequential, the confidence is not high, and the stakes are high, offer an isolated rerun.

## Confidence scale

A closed three-tier scale, set by how independent and checkable the evidence is, never by how many viewpoints agree.

| Tier | Meaning |
|------|---------|
| high | The decisive points rest on evidence that was opened and checked by two or more independent routes, or on a measurement anyone can repeat, and no factual disagreement is open. |
| medium | The decisive points rest on one checked source, or on a sound argument with one unchecked premise; what remains open is priority or forecast. |
| low | A decisive point rests on recalled or reasoned claims, or a factual disagreement is unsettled. |

## Return Contract

One record per question, all fields populated:

| Field | Content |
|-------|---------|
| `question` | The neutral one-sentence form, and what would settle it |
| `mode` | `isolated` or `sequential`, and the independence limit that follows |
| `viewpoints` | Per viewpoint: role, stake, position, confidence, and its strongest claim with its evidence label |
| `agreement` | Shared points, each marked separate evidence or shared assumption |
| `disagreements` | Each with kind, the evidence that would settle it, the cost, and anything fetched during reconciliation |
| `recommendation` | The position, its confidence tier, its assumptions |
| `strongest dissent` | The best case against the recommendation, unsoftened |
| `would change if` | The specific finding or priority that reverses it |
| `first step` | The cheapest test or reversible action |

A record without a dissent, or with a confidence tier raised by headcount, is non-conformant.

## Foundational Stanzas

### Refusal & Escalation

REFUSE to present viewpoints that disagree as a consensus or a vote, to let a viewpoint see another's output while the record says isolated, to write a claim as established when nobody opened its source, and to pick the user's priorities for them. Name the boundary crossed and offer the way forward through the structured-inquiry channel per `rules/interactive-questions.md`: supply the priority, supply the evidence, or accept the result as provisional.

### Output Surface

The record prints to STDOUT as a short table plus prose. Each viewpoint appears as its position and strongest claim; the full text of a viewpoint is shown or saved only when the user asks, so the main thread stays short. A saved record goes to the path the user names or to the host's documented decision-record location per `rules/host-discovery.md`.

### File-Authoring Contract

A saved record is a new file and goes through `scripts/inject-header.py`; exempt classes are listed in `src/apothem/schemas/header-exceptions.txt`. A record printed to STDOUT needs no header.

### Structured Inquiry on Ambiguity

A question that bundles several, a term at the centre of the dispute that the parties define differently, a priority the answer hinges on (speed against safety, cost against quality), and a leaning the user has not stated are all asked, not assumed. Ask through the structured-inquiry channel per `rules/interactive-questions.md`, with a rationale, a recommendation, and a default pointer for each option.

## Recommended Next Step

**Run the cheapest test the record names for its largest open disagreement**, then redo the reconciliation, not the viewpoints, with the new fact; if the disagreement is about priorities, answer the priority question the record raised.

## Bindings (§0.j five-direction)

- **Drives →** ● Every contested-question record emitted with the nine fields of the Return Contract. ● The cheapest-test recommendation handed to the user.
- **Satisfies →** ● `CLAUDE.md` Ambiguity Handling (priorities are asked about, never invented). ● `CLAUDE.md` Operating Loop & Synthesis Posture (independent viewpoints reconciled in one pass with the main thread kept lean).
- **Established by ↑** ● `skills/README.md` (this skill's index entry). ● `rules/multi-agent-workflow.md` (independent critique as an opt-in capability).
- **Gated by ←** ● The harness's Read / Glob / Grep / WebSearch surface for evidence, and its subagent surface for isolated mode. ● `rules/agnostic-posture.md` §1 (subagent dispatch is default-off).
- **Cross-bound with ↔** ↔ `rules/agent-orchestration.md` (isolated launch and return contracts). ↔ `rules/agnostic-posture.md` (dispatch is opt-in). ↔ `rules/interactive-questions.md` (the channel for priority and scope questions). ↔ `rules/host-discovery.md` (where a saved record lives). ↔ `rules/authoritative-referencing-provenance.md` (the evidence labels viewpoints use). ↔ `rules/authoritative-referencing-assurance.md` (the proof, number, and novelty checks a viewpoint's claims meet, which otherwise load only when a research file is open). ↔ `skills/decision-matrix/SKILL.md` (scored choice between known options). ↔ `agents/fact-checker.md` (verification of a single claim). ↔ `skills/workflow/SKILL.md` (multi-agent build or review).
