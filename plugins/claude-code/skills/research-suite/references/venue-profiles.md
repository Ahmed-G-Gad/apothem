<!-- SPDX-License-Identifier: MIT -->

# Venue Profiles and Recommendation Scales

Reference surface for the [`research-suite`](../SKILL.md) skill, read by
`/research-review --paper` when a review has no venue profile of its own to
apply. It holds six generic venue profiles, the rule that turns axis verdicts
into an overall verdict, and the tables that map that verdict onto a
recommendation scale. Loads selectively, beside `SKILL.md`.

## What a profile is

A profile is a starting stance for one *shape* of venue. Apothem authored the
six below; none of them quotes, summarises, or approximates the published
criteria of any conference, journal, society, or publisher.

- A review MUST NOT write "the venue requires" on the strength of a profile.
- When the operator names a venue, the review applies the nearest shape and
  prints one line in the report header: `generic <profile-id> profile; the
  venue's own reviewer guidelines were not applied`.
- When the operator supplies the venue's reviewer guidelines or checklist as a
  file or pasted text, that text governs. The review reads it from the
  supplied text, never from recall, and uses a profile only to fill what the
  text leaves open.
- The operator ratifies the profile through the structured-inquiry channel;
  where no one can answer, the review states the chosen profile as an
  assumption in the report header.

## The six profiles

Weights rank the seven review axes for each shape and sum to 100 per row. A
weight of 0 marks the axis not applicable; the report names the reason.

| Profile id | Novelty | Rigor | Reproducibility | Clarity | Ethics | Statistical review | Reporting |
| ---------- | ------- | ----- | --------------- | ------- | ------ | ------------------ | --------- |
| `empirical-conference` | 20 | 20 | 15 | 10 | 5 | 20 | 10 |
| `systems-conference` | 15 | 25 | 20 | 10 | 5 | 15 | 10 |
| `theory-venue` | 25 | 40 | 5 | 20 | 5 | 0 | 5 |
| `field-journal` | 10 | 25 | 15 | 10 | 5 | 20 | 15 |
| `human-subjects-journal` | 5 | 20 | 10 | 5 | 20 | 20 | 20 |
| `workshop-short` | 25 | 20 | 10 | 25 | 5 | 10 | 5 |

### `empirical-conference`

- **Fits.** A selective conference that accepts chiefly empirical method
  papers.
- **Bar.** The contribution is new over the closest work, matters to the
  field, and the headline claim survives a comparison run at equal budget.
- **Checklist.** The abstract's headline claim matches the evidence in the
  results. The strongest current baseline is in the comparison. Replication and
  significance meet `empirical-comparison-rigor.md`. A limitations section
  exists. Compute, data, and code availability are stated.
- **Severity notes.** A headline gain inside run-to-run variation is HIGH. A
  missing limitations section is MEDIUM.

### `systems-conference`

- **Fits.** Systems, networking, database, and tooling papers whose claim is a
  measured improvement of a built artifact.
- **Bar.** The design is sound, the workload is realistic, and the measurement
  method supports the numbers.
- **Checklist.** The workload and datasets are described and representative.
  Baselines are the deployed or best-known systems, configured as their own
  documentation recommends. Hardware, software versions, and configuration are
  listed. Tail behaviour and variance appear beside means. Overheads and
  failure cases are reported. The artifact is available, or the reason it is
  not is stated.
- **Severity notes.** A speed-up measured on a workload the new system was
  tuned for, against a baseline that was not, is HIGH.

### `theory-venue`

- **Fits.** Papers whose main results are theorems.
- **Bar.** The statements are correct and non-trivial, the proofs are
  complete, and the result is placed against the known bounds.
- **Checklist.** Each theorem states its assumptions exactly. Each proof is
  complete, or the gap is named. A matching lower bound or the reason for its
  absence is given. The gap to known results is quantified. Sanity limits and
  special cases are checked. Numerical experiments are labelled as
  illustration, not evidence.
- **Severity notes.** A gap in the proof of the main theorem is HIGH. Unclear
  notation is MEDIUM. The statistical-review axis stays at weight 0 unless the
  paper reports experiments.

### `field-journal`

- **Fits.** A journal in an empirical field, where soundness outranks novelty.
- **Bar.** The conclusions follow from the data and methods, the methods are
  reported well enough to repeat, and the claims are scoped to the evidence.
- **Checklist.** The design fits the question. Pre-specified and exploratory
  analyses are labelled. Effect sizes carry intervals. Multiplicity is handled.
  Alternative explanations and limitations are discussed. Data and code
  availability are stated. The field's reporting checklist is completed where
  one exists.
- **Severity notes.** A conclusion that reaches past the sample or the design
  is HIGH.

### `human-subjects-journal`

- **Fits.** Health, clinical, behavioural, and other human-participant
  research.
- **Bar.** Participants are protected, the design and reporting meet the
  field's reporting guideline, and the conclusions stay in proportion to the
  evidence.
- **Checklist.** Ethics approval and consent are stated. Protocol registration
  is stated where the field expects it. The reporting-guideline checklist is
  named and completed. Participant flow carries numbers. Missing data and
  harms are reported. Funding and competing interests are declared. The limits
  of the sample are stated.
- **Severity notes.** An absent approval statement, an undeclared competing
  interest, and an outcome that differs from the registered one are HIGH.

### `workshop-short`

- **Fits.** Early or narrow results offered for discussion.
- **Bar.** The idea is clear and worth discussing, the evidence shown is sound
  as far as it goes, and the claims stop where the evidence stops.
- **Checklist.** Each claim is scoped to what the paper shows. Preliminary
  evidence is labelled preliminary. The next step is stated.
- **Severity notes.** An incomplete evaluation (few baselines, no ablation) is
  MEDIUM or LOW when the claims are scoped to match. An unsupported or wrong
  claim is HIGH at every venue shape.

### Papers outside the six shapes

Surveys, position papers, and benchmark or dataset papers take the nearest
profile with an adjustment the report states.

- **Survey.** Use `field-journal`; read *rigor* as the search protocol and the
  coverage, and *novelty* as the insight the synthesis adds.
- **Benchmark or dataset.** Use `empirical-conference`; the reviewer raises the
  reproducibility weight by 10 and takes it from novelty, and checks data
  documentation, licensing, and the ethics of collection.
- **Position paper.** Use `workshop-short`; read *rigor* as the soundness of
  the argument.

## From axis verdicts to the overall verdict

The procedure is Apothem's own convention and applies to every profile.

1. Score each applicable axis: `strong` 3, `adequate` 2, `weak` 1, `failing` 0.
2. Take the weighted mean over the applicable axes, leaving out weight-0 axes.
3. Read the mean as a starting band: 2.5 or higher is an `accept` candidate,
   2.0 up to 2.5 is `minor-revision`, 1.2 up to 2.0 is `major-revision`, and
   below 1.2 is `reject`.
4. Apply the gates, which override the band. An unresolved HIGH finding caps
   the verdict at `major-revision`. An improvement claimed without significance
   over its comparators caps it at `major-revision`. A `failing` verdict on any
   axis with weight 20 or more caps it at `major-revision`. A refuted headline
   claim sets `reject`.
5. Print the weights used, the mean, and each gate that fired, so the operator
   can re-derive the verdict.

When a supplied guidelines file gives its own weights or decision rules, those
replace steps 1 to 3; the gates in step 4 still apply.

## Recommendation scales

The review reaches the four-way verdict first and maps it second. The report
prints both together, with one sentence on why the verdict sits where it does
inside its band; a number never appears without the verdict beside it.

| Verdict | Meaning |
| ------- | ------- |
| `accept` | Clears the bar convincingly and significantly; no unresolved HIGH finding. |
| `minor-revision` | Sound; clears the bar once the MEDIUM and LOW findings are fixed; the fixes need no new experiments. |
| `major-revision` | A HIGH finding is open or the core evidence is incomplete; the contribution stands once new evidence is added. |
| `reject` | The core claim is refuted or unsupported, or the contribution sits below the bar and no revision within the paper's design repairs that. |

| Scale shape | `reject` | `major-revision` | `minor-revision` | `accept` |
| ----------- | -------- | ---------------- | ---------------- | -------- |
| Three labels: reject, borderline, accept | reject | borderline | accept, conditions listed | accept |
| Four labels: reject, major, minor, accept | reject | major | minor | accept |
| 1 to 5, 5 = strong accept, 3 = borderline | 1; 2 when the work is sound but below the bar | 2; 3 only when overall confidence is 3 or lower | 4 | 4; 5 when no MEDIUM finding is open and two or more axes are `strong` |
| 1 to 6, 6 = strong accept, no neutral point | 1; 2 when the work is sound but below the bar | 3 | 4 | 5; 6 when no MEDIUM finding is open and two or more axes are `strong` |
| 1 to 10, 10 = best | 1 to 2 when unsound; 3 when sound but below the bar | 4 when the core claim needs new evidence; 5 when it needs added analysis only | 6 with three or more MEDIUM findings open; 7 otherwise | 8; 9 when no MEDIUM finding is open and two or more axes are `strong`; 10 only when every axis is `strong` at confidence 4 or higher |

- A coarse scale merges neighbouring verdicts. The report keeps the four-way
  verdict beside the number so the merge does not hide the difference.
- A neutral midpoint is used only for a `major-revision` that the review cannot
  settle at overall confidence 3 or lower. The report then names the finding
  whose resolution decides which side of the midpoint the paper falls on.
- When the operator supplies the anchors of a scale (the descriptive text of
  each point), the review matches each anchor's wording to the findings, records
  which anchor it chose and why, and does not use the table above.
- A shape not listed here: ask the operator for the anchors; if none are
  available, use the nearest listed shape and say so.

### Reviewer confidence

Report confidence on a 1 to 5 scale beside every axis verdict and the overall
verdict.

| Level | Meaning |
| ----- | ------- |
| 1 | A guess; the material is outside the reviewer's field or was not read. |
| 2 | A partial read, or a field the reviewer knows only at the surface. |
| 3 | Read in full; some load-bearing claims were not checkable. |
| 4 | Read in full; the key claims were checked against the paper's evidence. |
| 5 | Expert-level fit; every load-bearing claim was checked. |

When a venue asks for confidence on a different scale, the report translates
by an explicit mapping and prints it.

## Standing limits

- A mapped score is this review's reading of the paper. It does not forecast a
  venue's decision, and the report says so beside the score.
- The review is a model-assisted reading, never peer review, and is never
  listed as a reviewer or a review, per
  `rules/authoritative-referencing-provenance.md` §6.
