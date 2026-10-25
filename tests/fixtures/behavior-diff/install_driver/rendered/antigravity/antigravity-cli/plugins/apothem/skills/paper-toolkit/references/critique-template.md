<!-- SPDX-License-Identifier: MIT -->

# Draft critique template

Detail for `critique` mode. It applies to any draft that makes a claim and offers support: a paper, a proposal, a report, a design note, a thesis chapter. It reads the draft, says what works, says what a careful outside reader would ask, and ranks the changes. It does not rewrite the draft.

## Label

Open the output with this line: `Model-assisted reading of <draft>; not peer review.` The output never appears in a list of reviews or reviewers (`rules/authoritative-referencing-provenance.md` §6). It gives no accept or reject verdict and no score. A scored referee review, a venue profile, or a recommendation on a scale is `commands/research-review.md`, which takes a suite's paper and, with its `--paper` mode, a paper outside any suite.

## Before judging

Read the whole draft first. List what the input lacks: appendices, supplementary material, data, code, figures that did not render. Anything in that list goes to the final section as something that was not judged.

## 1. What is strong

Two to four items. Each names a place in the draft and says specifically why it works: a claim stated with its limits, a comparison that includes the strongest alternative, a table that lets the reader check the number. "Well written" with no place and no reason is not an item. If nothing is strong enough to list, write `none identified` and go on.

## 2. Five questions a reviewer would ask

Five slots, filled with questions specific to this draft.

| Slot | Empirical draft | Non-empirical draft |
|------|-----------------|---------------------|
| 1. Claim and support | Does the evidence shown reach the claim as it is worded? | Does the argument or example set support the stated conclusion? |
| 2. Alternatives | What other explanation fits the result, and is the comparison or control that would rule it out present? | What other options or readings were considered, and why were they set aside? |
| 3. Position | Who is the closest prior work, and is the difference from it stated and tested? | What exists already, and what does this add beyond it? |
| 4. Checkability | Can a reader repeat or check this from what is written: data, settings, code, variation? | Can a reader confirm the key facts and figures from what is cited? |
| 5. Reach | Where does the result stop holding, and does the draft say where? | Under what conditions does the recommendation fail, and does the draft say so? |

Each question is written as the reviewer would put it, then followed by three short lines:

- **Triggered by:** the place in the draft and its wording.
- **What an answer takes:** a sentence, a number, a control, an added citation, or a new experiment.
- **Weight:** `substantive` (a reader would doubt the claim without an answer) or `minor` (a reader would be satisfied by a clarification).

Do not invent a weakness to make a slot `substantive`. When the draft is sound on a slot, write the best remaining question and tag it `minor`. When all five come out minor, say at the top of the section that the draft holds up on these questions.

## 3. The three changes that matter most

Ranked by how much each would change a reader's belief in, or ability to use, the draft. Each change has:

- **Where:** section, paragraph, or table.
- **Change:** one or two sentences saying what to do, as an instruction, not a rewrite.
- **Why it ranks here:** the question or strength it relates to.
- **Effort:** small (wording), medium (new analysis or section), large (new data or experiment).

Fewer than three is allowed when fewer matter; say that and stop. Do not pad the list to reach three.

## 4. What was not judged

State the limits of the reading: material the input lacked, claims in a field the reading cannot assess, references not checked (route to `agents/citation-auditor.md`), numbers not recomputed. The section is never empty; if nothing applies, write that the draft was read in full and no references or numbers were checked.

## Conduct

- Quote the draft's own words to anchor each point, with a section or paragraph position that was seen.
- Keep praise and doubt in separate sections; do not soften a doubt with a compliment attached to it.
- Do not raise a point about presentation (grammar, layout) unless it hides a claim from the reader.
