<!-- SPDX-License-Identifier: MIT -->

# Viewpoint roster, brief, and return template

Detail for steps 2 to 6 of the perspectives workflow. Read it when choosing viewpoints and writing the briefs.

## Roster

A viewpoint is a stance with a stake and a place to look, not a character. Give it no name, voice, or backstory. The stake is what it protects or optimises; two viewpoints with the same stake add length, not coverage.

| Role | Stance | Stake | Where it looks |
|------|--------|-------|----------------|
| Advocate | Builds the strongest honest case for the proposition | The benefit if the proposition is right | Cases where it worked, the mechanism by which it pays off, evidence of demand |
| Skeptic | Builds the strongest honest case against it | The cost of being wrong | Failure cases, hidden assumptions, evidence that contradicts the mechanism |
| Domain expert | States what the field's evidence and accepted practice say, including known pitfalls | Accuracy within the field | Primary sources, standards, measurements, the repository itself |
| Pragmatist | Asks what can be done with the people, time, and money on hand, and what can be undone | Delivery | Cost, schedule, current constraints, the migration path, exit costs |
| Affected party | Speaks for the people who live with the result | Their burden and their choices | Reports from users or operators, support history, usage data |
| Steward | Looks two years out at upkeep, drift, and who inherits it | Long-term maintainability | Maintenance load, dependencies, how similar things aged |
| Base-rate analyst | Asks how comparable attempts turned out | Calibration | Comparable cases and their outcomes, not this case's story |
| Reframer | Asks whether this is the right question and what lies outside it | The question itself | The goal behind the question, alternatives nobody listed |

Use at most one reframer, and only when the dispute may be about framing. An advocate and a skeptic are almost always both present.

### Fit to the question

| Question type | Starting set |
|---------------|--------------|
| Technical design or architecture | Advocate, skeptic, domain expert, pragmatist |
| Process, policy, or team practice | Advocate, skeptic, affected party, steward |
| Strategy or a bet under uncertainty | Advocate, skeptic, base-rate analyst, pragmatist |
| A claim or hypothesis in a field | Advocate, skeptic, domain expert, reframer |

Swap one role for the viewpoint that most opposes the user's leaning when the starting set lacks it. A set of three keeps the advocate, the skeptic, and the role that fits the question best.

## Brief

Each viewpoint receives exactly these parts, and nothing from any other viewpoint:

1. **Question.** The neutral one-sentence form from step 1.
2. **Role.** The stance, the stake, and the places to look from the roster.
3. **Context.** The same facts for every viewpoint: files to read, constraints, figures the user gave. State them as given, not as established.
4. **Evidence rule.** Argue from evidence. Open what you cite. Label every claim with how its evidence was reached, using the access labels of `rules/authoritative-referencing-provenance.md`: `read in full`, `abstract only`, `search-result summary`, `repository or code inspected`, `reasoning alone`. A figure or fact recalled from memory is `reasoning alone` and is also marked unchecked. Do not write a source you did not open as if you had.
5. **Limits.** At most three claims and about 250 words. Do not refer to any other viewpoint.
6. **Return template** below.

The brief never states the user's leaning or which answer the user hopes for.

## Return template

```text
role:            <role>
position:        <one sentence>
claims:          1. <claim> | evidence: <pointer> | label: <access label> | checked: yes/no
                 2. ...
strongest objection to this position: <the best counter, stated fairly>
would change my mind: <the specific finding that would move this position>
confidence:      low | medium | high, with the reason in one line
relies on unchecked: <list, or none>
```

## Contamination checks

Before reconciling, confirm for each viewpoint:

- It names no other viewpoint and quotes none.
- Its claims are not copies of another viewpoint's claims with the sign flipped.
- Its confidence is not tied to how many others agree.
- In sequential mode, its block was completed before the next began and was not edited afterwards.

A viewpoint that fails any check is rerun with a fresh brief or reported as contaminated.

## Reconciliation worksheet

```text
Agreement
  point | held by | rests on: separate evidence / same source / same assumption

Disagreements
  point | between | kind: fact / priority / definition / forecast
        | evidence that would settle it | cost to get it | fetched now? result

Recommendation
  position | confidence tier | assumptions | reverses if

Strongest dissent
  viewpoint | its argument in its own words | why the recommendation still stands, or does not
```

When every viewpoint ends in the same place, treat that as a warning: check that the roster really spanned opposed stakes, and say in the record that the panel did not find a disagreement rather than that none exists.
