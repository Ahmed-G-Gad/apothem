<!-- SPDX-License-Identifier: MIT -->

# Scoring anchors and sensitivity procedure

Detail for steps 4 and 5 of the decision-matrix workflow. Read it when scoring.

## Score anchors (0 to 10)

Score against what the option delivers on the criterion, not against the other options. Use the anchors so two reviewers land within one point.

| Score | Meaning |
|-------|---------|
| 0 | Does not meet the criterion at all |
| 2 | Meets it only with a workaround the user would reject |
| 4 | Partly meets it; a visible gap remains |
| 6 | Meets it adequately; no standout |
| 8 | Meets it well; a minor limitation at most |
| 10 | Fully meets it with margin; no practical improvement available |

Odd scores are allowed between anchors. A score of 0 on a criterion the user marked essential should have been caught as a dealbreaker; move it to step 3.

## Evidence pointers

Acceptable, strongest first: a measured figure the user or a tool produced; a line in the repository or in documentation (cite path and line, or URL); a statement the user made in this conversation (quote it); a stated vendor claim (mark it as a claim). Judgment with no pointer is allowed only on the cell's justification line and is flagged `judgment` so the reader sees it is unsupported.

## Unknown cells

When evidence cannot be found, do not choose a middle value. Record `unknown (low-high)`, for example `unknown (3-8)`, and carry both bounds into the sensitivity step. Say which single lookup would resolve the cell and what it costs.

## Totals

The total for an option is the sum over criteria of weight times score, divided by 100, giving a value from 0 to 10. Report it to one decimal place. A cell marked `unknown` enters the base total at the midpoint of its bounds, and any total that uses one is flagged provisional.

## Sensitivity procedure

1. For each criterion in turn, raise its weight by 20 percent of its value (a weight of 30 becomes 36), then lower it by 20 percent (30 becomes 24).
2. Spread the difference across the other weights in proportion to their current values so the sum stays 100. Keep two decimal places during the computation.
3. Recompute every total and note the winner.
4. Repeat with each `unknown` cell set to its low bound, then to its high bound, with the original weights.
5. List every case where the winner differs from the base winner.

Report the result in this shape:

| Case | Winner | Flips? |
|------|--------|--------|
| Base weights | Option A | no |
| Cost weight +20% | Option A | no |
| Cost weight -20% | Option B | yes |
| Cell B/maintenance low bound | Option A | no |

Classification:

- No case flips and the base margin is 0.5 or more: report a clear recommendation.
- Any case flips, or the base margin is under 0.5: report a close call. Name the criteria whose weight changes the outcome, because those are the questions to put back to the user.

## Choosing the first step

Pick the action with the smallest commitment that produces the evidence most likely to change the answer: a time-boxed spike on the leading option, a single quote request, a one-day trial on the cell marked `unknown`. Prefer a step that can be undone in under a day. State what is undone and how.
