<!-- SPDX-License-Identifier: MIT -->

# Power & Sample Size

Reference surface for the [`research-suite`](../SKILL.md) skill, loaded by
`/research-design` (Phases 4 and 5). Houses the inputs a sample-size
computation records, the analysis it sizes for, and the allowances it carries
before the number is final. Loads selectively, beside `SKILL.md`, so the
router's entry-point stays tight.

This surface adds operational detail to three existing rigor mandates: **R7**
(an inferential claim rests on a sizing that matches the analysis actually
planned), **R2** (every sizing input is recorded so an independent party
re-derives the number), and **R5** (the sizing goal and inputs are frozen with
the analysis plan). It introduces no new R-mandate; R1–R10 is a closed set of
ten. Phase 4 of `/research-design` sizes the study against the smallest effect
size of interest (SESOI); the rules below fix what that sizing records and
what it covers. Power is computed at design time, from the plan and the assumed
effect.

## Recorded Inputs

- **Record every input.** The sizing MUST record the inferential goal, the SESOI and its provenance, the outcome variability and its provenance, the per-test threshold after any correction, the target power, the sidedness, the allocation ratio, the test family, the within-cluster correlation and loss rate where they apply, and the computing tool with its version. An input with no provenance is a `USER-CONFIRM` placeholder (the canonical `kind=`-tagged form) until supplied; none is invented (R7).
- **Declare the inferential goal and size for it.** Each primary claim is superiority, non-inferiority, or equivalence, stated with its margin. The sample size MUST be computed for that goal. A plan sized for superiority that later reads a null result through an equivalence test runs a test the study was never sized for. An equivalence claim is sized by the power of the equivalence procedure itself at the assumed true effect, which is recorded; the equivalence bounds are the SESOI (Lakens 2017, <https://doi.org/10.1177/1948550617697177>).
- **Ratify sidedness.** Sidedness is ratified with the same weight as alpha. A one-sided test requires a written justification: the direction is fixed by theory before the data, and an effect in the opposite direction would lead to the same decision as no effect. A directional prediction in Phase 2 does not by itself justify a one-sided test.
- **Carry the allocation ratio.** An unequal allocation ratio MUST be recorded and carried into the computation, and the per-arm counts reported. A computation that assumes equal arms while the design allocates unequally sizes the wrong study.

## Effect-Size Provenance

- **The SESOI is not a prior estimate.** The SESOI is the smallest effect that matters in practice (set in `/research-design` Phase 4). An effect reported by a prior study or a pilot informs the *plausible* range of the true effect and never replaces the SESOI as the sizing target.
- **Carry the imprecision.** A single study or a pilot estimates the effect imprecisely, and an estimate selected for significance overstates it (Albers and Lakens 2018, <https://doi.org/10.1016/j.jesp.2017.09.004>). The estimate's uncertainty MUST enter the sensitivity range below; its point value MUST NOT be reused as the target.
- **Record conversions.** Any conversion of a reported statistic into the metric of the planned test is a re-derivation input: the source statistic, the formula, and the assumption the conversion makes are recorded.
- **No conventional label stands in.** A size label ("small", "medium", "large") MUST NOT replace a grounded SESOI. Without grounding, the effect-size placeholder stays open.

## Sensitivity of the Sample Size to the Effect

- **Report n across the plausible range.** The design MUST report the required analysed n across the plausible effect range — the SESOI, the bounds of the plausible true effect, and the points between — as a table or curve, so a reader sees how fast n rises as the effect shrinks.
- **When feasibility caps n, report what the cap detects.** If the achievable n falls below the requirement at the SESOI, the design reports the smallest effect detectable at that n and the target power. The study then states that the SESOI is not powered; it does not relabel the detectable effect as the SESOI.
- This table varies the assumed effect. It is distinct from the parameter sweeps of `/research-design` Phase 3, which vary the method.

## Sizing the Analysis as Planned

- **Size at the corrected threshold.** Where the preregistration declares a multiplicity family, n MUST be computed at the per-test threshold the correction leaves, or by simulating the whole procedure (below). An n computed at the uncorrected threshold and corrected afterwards is undersized for the plan it ships with.
- **State which claims are powered.** Every primary claim is powered at its own SESOI and goal, and the study's n is the largest of the resulting requirements. Where the study counts as a success only if every co-primary claim succeeds, the power target applies to that joint event, which is lower than the power of any single claim, and the sizing accounts for the correlation between the outcomes. A secondary outcome that is not sized is labelled exploratory in the preregistration. An interaction claim is sized as the interaction contrast, which is its own estimand with its own standard error and SESOI; the n that powers the main effects does not power it.
- **Size the pipeline's own tests.** The tests the analysis stage will run on the primary claims — including the SESOI-bounded equivalence test on a null result — are the tests the sizing covers. The sizing reports the power of that equivalence test at the planned n; where it falls short of the target, the preregistration states that a null result is reported as inconclusive and not as equivalence.

## Correlated Units and Clustering

- **Count independent units.** The sizing counts independent units as named under [`study-allocation-and-structure.md`](study-allocation-and-structure.md). Counting repeated measurements, subsamples, or seeds as subjects overstates power.
- **Inflate for within-cluster correlation.** When units are correlated within clusters, the independent-unit n MUST be multiplied by the design effect, 1 + (m − 1)ρ, for clusters of equal size m and within-cluster correlation ρ. This is a planning approximation and is stated as one. Adding members to a cluster buys less information than adding clusters, so the cluster count has its own floor set by the planned analysis.
- **Model few or unequal clusters directly.** The approximation assumes equal cluster sizes and many clusters. With few or unequal clusters the sizing MUST model the planned analysis directly, by simulation or an exact method for that analysis.
- **Repeated measures.** A repeated-measures design is sized with the within-unit correlation of the planned model; more repeats per unit do not multiply the n of units.
- **ρ carries provenance.** The correlation comes from the synthesis, a comparable study's report, or a pilot with its imprecision; the plausible range of ρ enters the sensitivity table.

## Attrition and Unusable Units

- **Derive the collection target from the analysed n.** The sizing yields the analysed n. The enrolment or collection target MUST be derived from it through an expected loss rate — the analysed n divided by one minus the loss rate, rounded up, per arm.
- **Record the loss rate as an input.** The loss rate covers participants lost to follow-up, animals withdrawn, samples that fail quality control, and runs excluded by a preregistered rule. It carries provenance and is never invented.
- **Fix the handling in the plan.** The preregistration names the analysed population and how missing outcomes are handled, consistent with the loss rate used in sizing. Loss that differs between arms is an internal-validity threat recorded in the threats ledger. A handling strategy chosen after seeing which units dropped is a disclosed deviation (R5).

## Simulation-Based Power

- **Simulate where no closed form matches.** For a planned analysis with no matching closed form (mixed-effects, generalised linear, cluster-randomised, survival, multi-stage, or sequential procedures), power MUST be estimated by simulation: generate data from the stated assumed truth (effect, variance components, correlation, loss), analyse each simulated dataset with the exact planned model and decision rule, and take the share of simulations that meet the rule.
- **Check the null first.** Simulate with no effect and confirm the procedure's false-positive rate matches its nominal level within Monte Carlo error before reading any power figure. A procedure that inflates the false-positive rate has no meaningful power.
- **Report the Monte Carlo error.** The replicate count MUST be large enough that the Monte Carlo standard error of the power estimate is small against the gap between the estimate and the target, and the error is reported (Morris et al. 2019, <https://doi.org/10.1002/sim.8086>).
- **Record for re-derivation.** The tool and its version, the seed, the assumed truth, and the replicate count are recorded (R2). The assumptions carry provenance like any other input.

## Sequential and Adaptive Looks

- **A look is a look.** Examining accumulating data against the effect before the planned n is complete is a look, and stopping on a favourable result is a sequential design with an uncontrolled error rate. A fixed-N design plans no looks; one taken anyway is a disclosed deviation (R5).
- **Fix the looks in advance.** The preregistration MUST fix how many looks occur, at what sample counts or information fractions, and the boundary family or alpha-spending function, with its efficacy and futility criteria (Lan and DeMets 1983, <https://doi.org/10.1093/biomet/70.3.659>). The sizing target is the maximum n of the sequential design.
- **Verify the operating characteristics by simulation.** The whole procedure — looks, boundaries, and any adaptation — MUST be simulated under the null and the assumed effect, and the false-positive rate, power, and expected sample size recorded.
- **Keep the looker independent of the effect.** In human-subject work an independent monitor sees the unmasked interim data and the investigators do not. Elsewhere a script applies the preregistered rule and no analyst reads the effect by arm.
- **Re-estimate size without reading the effect.** A preregistered re-estimation of n uses pooled nuisance quantities (variability, loss rate) computed without arm labels, not the observed effect. A re-estimation that reads the effect is an adaptive design whose rule is simulated and preregistered.
- **Enumerate the permitted adaptations.** Only the adaptations the preregistration lists — dropping an arm, enriching a subgroup, adaptive allocation, re-estimating n — are permitted, each with its rule. An unlisted adaptation is a disclosed deviation (R5).
- Boundary derivations and package recipes for computing them are textbook content; the design cites the text it follows (Jennison and Turnbull, *Group Sequential Methods with Applications to Clinical Trials*, Chapman & Hall/CRC).

## Bindings (§0.j five-direction)

- **Drives →** ● The sample-size inputs, the effect sensitivity table, the clustering and attrition allowances, the simulation and sequential-look rules in `/research-design` (Phase 4), and the sizing and stopping-rule content frozen in the preregistration (Phase 5). ● The planned equivalence and interaction tests that `/research-analysis` (Phase 2) later runs.
- **Satisfies →** ● The [`research-suite`](../SKILL.md) skill's reference-surface obligation (the power-and-sample-size rules load selectively, beside the router).
- **Established by ↑** ● [`research-suite/SKILL.md`](../SKILL.md) (the knowledge surface this reference extends). ● [`references/rigor-mandates.md`](rigor-mandates.md) (the R7, R2, and R5 mandates this surface operationalizes).
- **Cross-bound with ↔** ↔ [`references/study-allocation-and-structure.md`](study-allocation-and-structure.md) (the unit, allocation procedure, and clustering the sizing counts). ↔ [`references/empirical-comparison-rigor.md`](empirical-comparison-rigor.md) (the repetition regime for stochastic methods, a separate question from the sample size of units). ↔ [`references/experiment-program-scaffold.md`](experiment-program-scaffold.md) (the pilot sub-stage, whose records stay calibration and stay out of the headline claim). ↔ [`references/advancement-gate.md`](advancement-gate.md) (the thresholds the gate reads).
