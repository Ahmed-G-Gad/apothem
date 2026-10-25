<!-- SPDX-License-Identifier: MIT -->

# Paper comparison guide

Detail for `compare` mode. The aim is to say which results can sit side by side, which cannot, and which paper to cite for which claim.

## Scope

Two to five papers. Each gets a short note first (see the reading-note reference), with its basis. A paper with basis `abstract only` can be compared on what its abstract states and nowhere else; every axis the abstract does not cover is `undetermined` for that paper.

## Comparability axes

Check each axis for every pair of papers that report on the same claim. The question in the middle column is answered from the text read.

| Axis | Question | A mismatch that changes the meaning of a number |
|------|----------|-----------------------------------------------|
| Quantity | Is the measured quantity defined the same way? | One counts per item, the other per document; one reports an error rate, the other its complement |
| Task and data | Same task formulation, same dataset version, same split, same filtering, same population? | A cleaned test set against the original; a different sampling frame |
| Metric and scoring | Same metric, same implementation, same thresholds, same averaging? | Macro against micro averaging; a stricter match rule |
| Protocol | Same budget (compute, time, tries), same repeats, tuning allowed on the test data in one and not the other? | One result is the best of many runs, the other a single run |
| System versions and settings | Same version of the thing tested and of each baseline, tuned to the same degree? | A baseline run with defaults against a tuned method |
| Scale and period | Same size of model, sample, or system; same time window for observational data? | Data from different years of a changing process |
| Reporting | Single run or repeated, with what interval or test? | A gap smaller than the run-to-run spread |

When the text read does not settle an axis, the answer is `not stated in what was read`. That is not the same as "same", and the verdict below treats it that way.

## Verdicts

Give one per pair per claim.

- **Comparable.** Every axis matches or is stated to match.
- **Comparable with a caveat.** One or more axes differ in a way that should not change the ranking; name the axis and why.
- **Not directly comparable.** An axis differs in a way that can change the number's meaning. Name the axis, quote the two settings, and say what would align them: a re-run under one protocol, a conversion the papers themselves supply, or restriction to a shared subset. Do not produce an adjusted number. A conversion is used only when one of the papers or a cited source provides it, and then it is cited.
- **Undetermined.** At least one axis is `not stated in what was read` and the rest match. Say which axis, and which part of which paper would settle it.

## Side-by-side table

One row per paper, one column per item.

| Paper (key) | Basis | Question or task | Data | Metric | Protocol | Headline result as printed | Variation reported |
|-------------|-------|------------------|------|--------|----------|----------------------------|--------------------|

Below the table, list where results agree, where they differ, and for each difference the axis that most plausibly explains it, or `unexplained`.

## Cite-for table

| Claim to support | Cite | Why this paper | Also usable | Do not cite it for |
|------------------|------|----------------|-------------|--------------------|

Rules for choosing the paper in the second column:

1. Prefer the paper that produced the result over one that restates it.
2. Prefer the version whose text was actually read. If the read version is a preprint and a published version exists, say so and leave the swap to the user.
3. Prefer the paper whose setting is closest to the claim as the user will state it, and name the setting gap when none is close.
4. When two papers disagree on the claim, the row names both, states the disagreement, and gives the axis that likely explains it. Never pick silently.
5. A claim no paper in the set supports gets a row reading `no paper in this set`, not a stretched citation.

## When the question is a choice

If the user wants to know which paper's method to adopt, that is a decision under weights and constraints, not a comparison of evidence. Hand it to `skills/decision-matrix/SKILL.md` with the comparison table as its evidence.
