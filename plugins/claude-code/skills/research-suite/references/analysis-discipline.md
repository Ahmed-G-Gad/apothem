<!-- SPDX-License-Identifier: MIT -->

# Analysis Discipline

Reference surface for the [`research-suite`](../SKILL.md) skill, read by
`/research-analysis` (Phases 2 and 3), by `/research-design` when it freezes the
test family, and by `/research-review` on the statistical-review axis. Houses
the choices that sit between a frozen plan and a reportable number: which test
fits the design, what counts as an independent unit, how missing data and a
Bayesian plan are handled, how a null is read once the data are in, and the unit
at which bias is judged. Loads selectively, beside `SKILL.md`, so the router's
entry-point stays tight.

This surface adds operational detail to existing rigor mandates: it
operationalizes **R7 — Statistical rigor**, with the fallback and missing-data
rules serving **R5 — Preregistration discipline** and the dependence rule
serving **R2 — Reproducibility**. It introduces no new R-mandate; R1–R10 is a
closed set of ten. It names methods by family and fixes no numeric default; a
threshold, a level or a count comes from the preregistration or the host's
ratified toolchain, never from this file. Every test below reports its effect
with an interval, as R7 requires.

## Test Selection by Design

The preregistration MUST name the test family for each primary claim, ratified at
design time. The table gives the default family for each design; a preregistration
that departs from the default MUST state why.

| Design and outcome | Default family |
|--------------------|----------------|
| Two independent groups, continuous outcome | A comparison of means that allows unequal variances |
| More than two independent groups | An omnibus model that tolerates unequal variances, then the preregistered contrasts under the declared correction |
| Paired or matched measurements | An analysis of the within-pair differences |
| Factorial | One model that contains the interaction, with the primary term named in the plan; a main effect is read as an average over the other factor only where the interaction is negligible or that average is the estimand, otherwise the effects are reported as simple effects |
| Repeated, longitudinal or nested | A model with the unit as a random effect, or aggregation to the unit (see [Unit of Analysis and Dependence](#unit-of-analysis-and-dependence)) |
| Binary outcome | Risk difference, risk ratio or odds ratio, with an interval that holds at small counts |
| Count outcome | A rate model with the exposure as an offset, overdispersion checked |
| Unordered categories | A test of association with a named association measure |
| Time to event | A survival model with censoring declared and justified as independent of the outcome; the plan names the summary to use if the proportional-hazards condition fails |
| Continuous association | A regression or correlation of the stated form; a rank correlation only when the claim is monotonic association |

**Agreement and reliability of coded or rated data** take their own families,
because a correlation or a percent-agreement figure does not measure agreement:

- **Categorical codes.** Two raters use a chance-corrected coefficient; more raters,
  or ratings with gaps, use a coefficient that admits them. The report names the
  coefficient, gives its interval and the marginal distribution of the codes (a
  chance-corrected value depends on how common each code is), and never offers
  percent agreement alone.
- **Continuous ratings.** The intraclass correlation names its model form — which
  raters and targets are sampled, single or averaged ratings, consistency or
  absolute agreement — and carries its interval.
- **Two measurement methods.** Report the mean difference and the limits of
  agreement, each with an interval, rather than the correlation.

Two principles govern how the table is used:

- **Diagnostics inform judgement; they do not choose the test.** The preregistered
  primary test SHOULD be one that does not lean on a distributional or
  equal-variance assumption. Wherever the analysis path branches on a diagnostic,
  the plan MUST name the fallback and the condition that triggers it. A residual
  plot, a variance ratio or a normality screen informs how the model is read. A screen
  that fails to reject does not verify the assumption it probes, and choosing the
  test from a screen's outcome alters the error rates of the test that follows. A
  move to the named fallback is a planned adaptation of the frozen analysis
  plan, recorded in the disclosed-deviation ledger when it is executed; a move
  to anything else is a deviation (R5).
- **A rank test addresses ordering, not location.** It asks whether draws from one
  group tend to exceed draws from another. It does not test equality of means, and
  it tests equality of medians only under the added assumption that the
  distributions differ in location alone. The claim MUST name the quantity the test
  addresses; where the claim concerns a mean or a median, the analysis estimates
  that quantity directly. For a paired comparison across instances, the report
  states which quantity the effect size estimates and how ties are counted.

## Unit of Analysis and Dependence

- **Name the independent unit.** The analysis inventory MUST name, for every test,
  the thing that was randomised, sampled or assigned, and every n counts those
  units. The results table gives units beside observations and, for clustered data,
  the cluster count and the range of cluster sizes.
- **Dependent observations MUST NOT be counted as replicates.** Repeated measures,
  sub-samples, technical replicates, cluster members and seeds on one instance are
  correlated; counting them as independent inflates n and narrows every interval
  (pseudoreplication).
- **Aggregate or model the dependence.** Either aggregate to the unit and analyse
  the aggregates, or model the dependence with a random effect for the unit, a
  covariance structure suited to the repeated measure, or cluster-aware errors.
  Cluster-aware errors are reliable only with enough clusters; with few or unequal
  clusters, model the clustering directly or aggregate, and report the cluster
  count.
- **Stochastic-method corollary.** Repetitions of one method on one instance
  replicate the method's randomness. An interval over them supports a claim about
  the method on the instances run. A claim that generalises to a population of
  instances takes the instance as the unit: aggregate the repetitions per instance,
  then compare across instances. The analysis MUST state which claim it makes.
- **Late discovery is a deviation.** Dependence found after the freeze enters the
  ledger (R5).

## Missing Data

- **Report the pattern first.** Give the count and share missing per variable and
  per condition, with the reason where known. A unit removed by a preregistered
  exclusion rule is reported apart from a missing value. The record keeps each
  missing value marked missing with its reason; a filled-in value lives only in the
  analysis model and is never written back to the record (R2).
- **State the assumed mechanism.** Name it as missing completely at random, missing
  at random given named observed variables, or missing not at random, with the
  evidence available (for example, complete and incomplete units compared on the
  observed variables). The observed data cannot confirm that a loss is ignorable;
  the statement says so.
- **Justify the handling against the mechanism.** Complete-case analysis is
  justified only where the stated mechanism leaves the estimate unbiased for the
  estimand. Otherwise use multiple imputation, a likelihood-based model fitted to
  all observed data, or weighting; an imputation model includes every variable of
  the analysis model. A single filled-in value is not treated as observed, and
  last-value carry-forward and mean substitution are not the primary handling.
- **Run a sensitivity analysis when the mechanism is doubtful or the loss differs
  across conditions.** Re-analyse under at least one departure from the primary
  assumption (a stated shift for the missing outcomes, or best-case and worst-case
  fills) and report whether the headline direction and interval survive; a result
  that does not is fragile, with the departure named.
- **Fix the handling before outcomes are compared across conditions.** A
  preregistration silent on missing data or exclusions is a Phase 1 inquiry item
  and a ledger entry (R5).

## Reading a Null After the Data Are In

- **Observed power MUST NOT be computed or reported.** Power calculated from the
  effect the study happened to observe restates the p-value and explains nothing
  about why a test did not reject.
- **Every null carries a sensitivity statement.** It gives the smallest effect
  detectable at the achieved analysed n (units after exclusions and attrition), the
  preregistered alpha and the preregistered power, and any shortfall against the
  planned n. Power computed for the achieved n at an effect fixed before the data,
  such as the SESOI, is a sensitivity statement; power computed at the observed
  effect is not.
- **Read the null through three results together.** The effect-size interval, the
  SESOI-bounded equivalence result and the sensitivity statement separate "no
  effect of interest" from "the study cannot tell".

## Bayesian Plans

- **A Bayesian analysis MUST come from the preregistration.** The plan declares the
  model, each prior, the interval type and the practical-equivalence region. A
  switch from a frequentist plan after the results are seen is a deviation (R5).
- **The credible interval is the R7 interval.** Under a preregistered Bayesian plan
  it satisfies R7's interval requirement, names its type (equal-tailed or
  highest-density) and level, and accompanies the posterior estimate. A posterior
  probability or a Bayes factor never stands alone.
- **Set priors in the outcome's units and record their source** (the synthesis, the
  SESOI, or a stated weakly informative choice). Report each prior beside the
  posterior, and re-fit under at least one defensible alternative prior; a
  conclusion that follows the prior is reported as prior-dependent.
- **Check before reporting a posterior.** Computation diagnostics (for example chain
  agreement, effective sample size, and divergent transitions where the sampler
  reports them) are judged against criteria fixed before the run, and a
  posterior-predictive check confirms that data simulated from the fitted model
  resemble the observed data. A fit that fails either check is not reported as a
  result; the failure and the model revision it forces are ledgered (R5).
- **Fix the practical-equivalence region from the SESOI before results.** The plan
  also fixes the decision threshold on the posterior mass inside the region. The
  report gives the mass inside and outside it, which stands in for the Phase 3
  equivalence test.
- **Choose the quantity by the question.** A Bayes factor answers which of two fully
  specified hypotheses the data favour; it applies only where the prior under each
  is substantive and preregistered, and it moves with the prior's width, so it is
  reported with a prior-sensitivity range. A posterior distribution answers how
  large the effect is. A Bayes factor under a default prior chosen for convenience
  is not reported alone. The plan states its multiplicity treatment.

## Result-Level Bias Appraisal

- **The unit of judgement is the result.** A bias judgement attaches to an outcome
  in a comparison at a time point, not to the study; one study can carry low
  concern for one result and high concern for another.
- **Judge each headline result by domain, with the instrument that fits the
  design.** For a comparison with assigned units the domains are the assignment
  process, departures from the planned protocol, missing outcome data
  ([Missing Data](#missing-data)), measurement of the outcome, and the selection of
  the reported result among the analyses run (the pre-specified-versus-exploratory
  split). A comparison without assignment adds confounding and the selection of
  units into the study; a computational comparison substitutes the domains of the
  checklist-based judgement for that work, such as leakage between tuning and
  evaluation data and unequal tuning effort. Rate each domain low, some concerns or
  high, with the locus that justifies it. A threat the design's threats ledger
  already records is carried into the matching domain, not appraised twice.
- **Do not collapse domains into a score.** The overall judgement follows the
  instrument's own rule, shows the domain judgements beside it and names the domain
  that drives it; a high-concern domain is carried into the claim's wording and the
  limitations.
- **Record the instrument.** A published instrument is recorded by name and by the
  edition or date its own source states, with the signalling answers and the locus
  behind each; the current edition is re-checked at the time of use. This is the
  same record [`search-record.md`](search-record.md) §12 keeps for each included
  source, applied here to the study's own results.

## Bindings (§0.j five-direction)

- **Drives →** ● The test family, fallback and unit of analysis frozen in `/research-design` (Phases 4 and 5). ● The tests, missing-data handling, null reading, Bayesian reporting and result-level bias judgements in `/research-analysis` (Phases 2, 3 and 4). ● The statistical-review axis of `/research-review`.
- **Satisfies →** ● The [`research-suite`](../SKILL.md) skill's reference-surface obligation (the analysis-discipline floor loads selectively, beside the router).
- **Established by ↑** ● [`research-suite/SKILL.md`](../SKILL.md) (the knowledge surface this reference extends). ● [`references/rigor-mandates.md`](rigor-mandates.md) (the R7 mandate this surface operationalizes, with its R5 and R2 aspects).
- **Cross-bound with ↔** ↔ [`references/empirical-comparison-rigor.md`](empirical-comparison-rigor.md) (the rank-based protocol for head-to-head comparison that the rank-test principle and the stochastic-method corollary qualify). ↔ [`references/advancement-gate.md`](advancement-gate.md) (the gate whose statistical thresholds these tests feed). ↔ [`references/power-and-sample-size.md`](power-and-sample-size.md) (the design-time sizing whose achieved-n counterpart is the sensitivity statement). ↔ [`references/plan-branching-and-contingencies.md`](plan-branching-and-contingencies.md) (a response written into the frozen plan is a planned adaptation; a register contingency fires on an operational measure, where the fallback here fires on a diagnostic of the analysed data). ↔ [`references/search-record.md`](search-record.md) (§12, the source-side risk-of-bias record whose discipline the result-level appraisal applies to the study's own results). ↔ [`references/figure-integrity.md`](figure-integrity.md) (the figure floor for the results reported here). ↔ `rules/disclosure-ledger.md` (planned contingencies and deviations). ↔ `agents/fact-checker.md` (adversarial re-derivation of every reported result).