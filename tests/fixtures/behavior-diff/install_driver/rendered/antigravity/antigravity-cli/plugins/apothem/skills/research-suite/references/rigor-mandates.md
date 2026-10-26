<!-- SPDX-License-Identifier: MIT -->

# The Ten Rigor Mandates (R1–R10)

Reference surface for the [`research-suite`](../SKILL.md) skill. Houses the
closed set of ten rigor mandates the `/research` pipeline stages honor and
attest. Loads selectively, beside `SKILL.md`, so the router's entry-point
stays tight.

The research-suite floor — a closed set of ten. Every stage honors the
mandates that apply to its surface, and each stage's pre-emission gate attests
R1–R10 coverage in the artifact's working trace.

- **R1 — Authoritative sources.** Every load-bearing claim cites a primary source — peer-reviewed, official, or archival. Folklore is excluded; the `fact-checker` agent adversarially verifies each claim against its cited source.
- **R2 — Reproducibility.** Method, environment, seed, and protocol log are recorded so an independent party re-runs the work and reaches the same result. Reproducibility is a deliverable, not an afterthought.
- **R3 — Falsifiability.** Hypotheses are stated as testable, refutable predictions — never as unfalsifiable assertions. Null results are recorded, never suppressed.
- **R4 — Citation integrity.** Every citation resolves to a real source — permalinked, DOI-stamped, or commit-pinned. Phantom citations are structural failures, bound to `rules/ten-dimension-check.md` dimension 9.
- **R5 — Preregistration discipline.** The analysis plan is frozen before data collection. Every deviation from the frozen plan is disclosed per `rules/disclosure-ledger.md`, never silently applied.
- **R6 — Ethics & conflicts.** Human / animal / data-privacy considerations, conflict-of-interest declarations, and data / code availability are stated before publication, not in response to a reviewer.
- **R7 — Statistical rigor.** Effect sizes and confidence intervals accompany every inferential claim — not p-values alone — with assumption checks and multiple-comparison correction where applicable.
- **R8 — Open science & FAIR data.** Data and code are FAIR — Findable, Accessible, Interoperable, Reusable — with persistent identifiers, released open-access where the venue and consent permit, and archived in a citable repository (e.g. Zenodo); the registered-report option is offered where the design supports it. Cite: Wilkinson et al. (2016), *Scientific Data*, [doi:10.1038/sdata.2016.18](https://www.nature.com/articles/sdata201618); [TOP Guidelines](https://www.cos.io/initiatives/top-guidelines).
- **R9 — Reporting-guideline conformance.** The field-appropriate EQUATOR reporting guideline is selected and conformed to — PRISMA for evidence synthesis, CONSORT for trials, STROBE for observational studies, and the matching guideline for every other design — with a structured abstract, CRediT contributor-role taxonomy, and ORCID identifiers for every author. Cite: [EQUATOR Network](https://www.equator-network.org/reporting-guidelines/); [ICMJE](https://www.icmje.org); [COPE](https://publicationethics.org).
- **R10 — Theoretical grounding & impact.** An a-priori conceptual / theoretical framework — theory-of-change or logic model — anchors the work at the front, and a dissemination-and-impact pathway is planned at the tail. Cite: [NWO Impact Plan Approach](https://www.nwo.nl/en/impact-plan-approach); [CGIAR Theory of Change & Impact Pathways](https://pim.cgiar.org/impact/theory-of-change-impact-pathways/).

## Operationalizing surfaces

The ten mandates above are a **closed set of ten**. The reference surfaces
below add operational detail to specific mandates for empirical, comparison-
and run-heavy studies, and for the search, planning, reporting, and
dissemination work around them; they introduce **no new R-mandate**, and a stage
loads one only when its work needs that detail. One table maps each surface to
the mandates it operationalizes; a surface that serves several mandates appears
on each row.

| Mandate | Operationalizing reference surface(s) |
|---------|----------------------------------------|
| R1 / R4 — authoritative sources & citation integrity | [`comparator-provenance.md`](comparator-provenance.md) (executed-baseline provenance); `skills/paper-toolkit/references/bibliography-entries.md` (reference entries built from opened records); [`talk-and-poster.md`](talk-and-poster.md) (a public claim matches the published paper) |
| R2 — reproducibility | [`compute-utilization.md`](compute-utilization.md); [`experiment-program-scaffold.md`](experiment-program-scaffold.md); [`empirical-comparison-rigor.md`](empirical-comparison-rigor.md) (repetition regime); [`autonomous-experiment-loop.md`](autonomous-experiment-loop.md) (frozen-harness identity and the per-trial journal); [`search-record.md`](search-record.md) (the search is a re-runnable method); [`study-allocation-and-structure.md`](study-allocation-and-structure.md) (recorded allocation schedule and run order); [`power-and-sample-size.md`](power-and-sample-size.md) (every sizing input recorded); [`analysis-discipline.md`](analysis-discipline.md) (independent units counted); [`figure-integrity.md`](figure-integrity.md) and [`talk-and-poster.md`](talk-and-poster.md) (a figure is a view of recorded data) |
| R3 — falsifiability | [`autonomous-experiment-loop.md`](autonomous-experiment-loop.md) (a falsifiable prediction and a discard-preserving journal row per trial); [`plan-branching-and-contingencies.md`](plan-branching-and-contingencies.md) (plan-level risk triggers and stress test) |
| R5 — preregistration discipline | [`experiment-program-scaffold.md`](experiment-program-scaffold.md); [`advancement-gate.md`](advancement-gate.md); [`autonomous-experiment-loop.md`](autonomous-experiment-loop.md); [`analysis-discipline.md`](analysis-discipline.md) (preregistered fallback, missing-data handling); [`study-allocation-and-structure.md`](study-allocation-and-structure.md) (allocation, masking, and controls frozen); [`power-and-sample-size.md`](power-and-sample-size.md) (sizing goal and inputs frozen); [`plan-branching-and-contingencies.md`](plan-branching-and-contingencies.md) (contingencies written into the plan) |
| R6 — ethics & conflicts | [`blinding-and-disclosure.md`](blinding-and-disclosure.md) (anonymization & staged disclosure); [`study-allocation-and-structure.md`](study-allocation-and-structure.md) (masking and monitoring for human and animal subjects) |
| R7 — statistical rigor | [`empirical-comparison-rigor.md`](empirical-comparison-rigor.md); [`advancement-gate.md`](advancement-gate.md); [`autonomous-experiment-loop.md`](autonomous-experiment-loop.md); [`analysis-discipline.md`](analysis-discipline.md) (test selection, unit of analysis, missing data, null reading, Bayesian plans, result-level bias); [`figure-integrity.md`](figure-integrity.md) (figure honesty, disclosure, and accessibility floor); [`study-allocation-and-structure.md`](study-allocation-and-structure.md) (analysis that respects the design's structure); [`power-and-sample-size.md`](power-and-sample-size.md) (sizing for the planned analysis); [`talk-and-poster.md`](talk-and-poster.md) (qualifiers survive condensation) |
| R8 — open science & FAIR data | `skills/paper-toolkit/references/bibliography-entries.md` (persistent identifiers on entries for the study's own deposited data and code) |
| R9 — reporting-guideline conformance | [`search-record.md`](search-record.md) (search reporting, flow counts, risk-of-bias record) |

## Bindings (§0.j five-direction)

- **Drives →** ● Every `/research` stage's R1–R10 coverage attestation in its pre-emission gate trace.
- **Satisfies →** ● The [`research-suite`](../SKILL.md) skill's reference-surface obligation (the rigor-mandate catalog loads selectively, beside the router).
- **Established by ↑** ● [`research-suite/SKILL.md`](../SKILL.md) (the knowledge surface this reference extends).
- **Cross-bound with ↔** ↔ `rules/ten-dimension-check.md` dimension 9 (R4 citation-integrity anchor). ↔ `rules/disclosure-ledger.md` (R5 deviation disclosure). ↔ `agents/fact-checker.md` (R1 adversarial verification). ↔ [`empirical-comparison-rigor.md`](empirical-comparison-rigor.md) + [`comparator-provenance.md`](comparator-provenance.md) + [`experiment-program-scaffold.md`](experiment-program-scaffold.md) + [`compute-utilization.md`](compute-utilization.md) + [`autonomous-experiment-loop.md`](autonomous-experiment-loop.md) + [`advancement-gate.md`](advancement-gate.md) + [`blinding-and-disclosure.md`](blinding-and-disclosure.md) + [`study-allocation-and-structure.md`](study-allocation-and-structure.md) + [`power-and-sample-size.md`](power-and-sample-size.md) + [`analysis-discipline.md`](analysis-discipline.md) + [`figure-integrity.md`](figure-integrity.md) + [`search-record.md`](search-record.md) + [`plan-branching-and-contingencies.md`](plan-branching-and-contingencies.md) + [`talk-and-poster.md`](talk-and-poster.md) (the operationalizing detail surfaces mapped above). ↔ `skills/paper-toolkit/references/bibliography-entries.md` (the entry guide mapped to R4 and R8 above).
