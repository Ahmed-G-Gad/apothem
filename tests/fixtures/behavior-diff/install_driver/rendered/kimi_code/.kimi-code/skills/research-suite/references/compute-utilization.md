<!-- SPDX-License-Identifier: MIT -->

# Compute-Utilization Plan

Reference surface for the [`research-suite`](../SKILL.md) skill. Houses the
compute-utilization plan every comparative `/research` engagement runs its
trials under — the unified budget, the tuning-split discipline, the execution
plan, and the reproducibility floor. Loads selectively, beside `SKILL.md`, so
the router's entry-point stays tight.

This surface adds operational detail to an existing rigor mandate; it
operationalizes **R2 (reproducibility)** and introduces no new R-mandate —
R1–R10 is a closed set of ten. Where a comparison spends compute unevenly
across the methods it pits against each other, the winner reflects the budget,
not the contribution; where a run cannot be re-executed to the same
observations, the result is unverifiable. This plan fixes both: it makes every
compared method spend the same measured budget, and it records the environment,
seeds, and hardware so an independent party reproduces the study under an
equivalent plan.

## Unified Budget Parity

One budget governs every method in a comparison; the budget is not a
per-method privilege.

- **One budget across all compared methods.** The comparison MUST allot each
  method the same per-trial budget, measured as equal wall-clock time AND —
  where an evaluation count is meaningful for the method family — equal
  evaluation count. When both measures apply, the study MUST report BOTH so a
  reader sees the comparison is fair on each axis; a study that reports only
  one axis MUST state why the other does not apply.
- **The budget is fixed in advance, not an optimization target.** The
  per-trial budget MUST be set before the runs and MUST NOT itself be tuned to
  favor one method. A fixed budget is what makes trials comparable across
  methods and bounds throughput to a known, plannable quantity; a budget
  adjusted mid-campaign to rescue a lagging method is a disclosed deviation, not
  a silent one.
- **Secondary resource costs are soft constraints.** Memory and comparable
  secondary costs are soft constraints, not the primary budget. A modest
  secondary-cost increase is acceptable when it buys a real contribution gain; a
  dramatic blowup in a secondary cost SHOULD be rejected even when the primary
  metric improves, and the trade-off MUST be recorded.
- **A hard timeout bounds every run.** A hard timeout set at a stated multiple
  of the per-trial budget MUST terminate any run that overruns it, and the
  terminated run MUST be recorded as a failure — never dropped silently and
  never allowed to consume unbounded compute. A run that survives only by
  exceeding its budget is not a comparable result.

## Automated Configuration on Disjoint Splits

Where a method exposes tunable parameters, the tuning is itself part of the
fair comparison and MUST be disclosed.

- **Tune on a training split under an equal, stated budget.** Where a method
  exposes tunable parameters, the study SHOULD tune them with an automated
  configurator on a designated training split, under a stated tuning budget
  that is EQUAL across every method the comparison tunes. Hand-tuning one method
  while auto-tuning another is not a fair comparison.
- **Evaluate on a disjoint test split.** After tuning, the study MUST evaluate
  on a test split that is DISJOINT from the training split. Test-split
  instances MUST NOT enter tuning under any circumstance — a parameter chosen
  with sight of a test instance makes that instance's result an artifact of the
  tuning, not a measure of the method.
- **Record the tuning protocol.** The study MUST record the tuning protocol,
  the tuning budget, and the training/test split definition into the working
  trace, so the tuning is reproducible and its fairness is auditable.
- **Disclose untuned comparator use as a limitation.** Where a comparator is
  run at its untuned default configuration rather than tuned on the training
  split, that choice MUST be disclosed as a limitation — an untuned comparator
  may understate its own contribution, and the comparison MUST not present its
  result as the comparator's best.

## Execution Plan

Before any run, the campaign states how it will spend the machine — and the
spending is result-invariant.

- **State the allocation before running.** Before running, the plan MUST state
  the core allocation, the memory ceiling per worker, and the parallelization
  scheme for independent repetitions. An execution plan authored after the runs
  is a reconstruction, not a plan.
- **Maximize machine use safely.** The plan SHOULD spend the available machine
  fully while keeping runs parallel yet safe: no core oversubscription, no
  memory exhaustion, and a stated headroom margin below the machine's limits.
  Oversubscribed cores and exhausted memory distort wall-clock measurements and
  corrupt the very budget parity the comparison rests on.
- **Parallelization is result-invariant.** Running repetitions in parallel MUST
  NOT change any repetition's result. Each repetition MUST carry its own fixed,
  recorded seed and its own fixed per-trial budget, enforced per-run and never
  shared across co-resident runs — so a repetition yields the same observation
  whether it ran alone or beside others.

## Reproducibility Floor

The plan closes on a recorded floor that an independent party can stand on.

- **Pin the environment, fix the seeds, log the hardware.** The campaign MUST
  run under a pinned environment (version-pinned dependencies and runtime), with
  fixed and recorded seeds, and with the hardware logged. These three together
  are the reproducibility floor for a comparative study.
- **Record the floor into the manifest.** The pinned environment, the seeds,
  and the logged hardware MUST all be recorded into the reproducibility
  manifest, so an independent party reproduces the study under an equivalent
  plan and reaches the same observations. A floor that is followed but not
  recorded satisfies nothing an external reader can check.

## Bindings (§0.j five-direction)

- **Drives →** ● The budget-parity, tuning-split, parallelization, and reproducibility-floor decisions in `/research-design` (Phase 4). ● The Phase 1 compute plan and the Phase 4 reproducibility manifest in `/research-experiment`.
- **Satisfies →** ● The [`research-suite`](../SKILL.md) skill's reference-surface obligation (the compute-utilization plan loads selectively, beside the router).
- **Established by ↑** ● [`research-suite/SKILL.md`](../SKILL.md) (the knowledge surface this reference extends). ● [`references/rigor-mandates.md`](rigor-mandates.md) (the R2 mandate this surface operationalizes).
- **Cross-bound with ↔** ↔ [`references/empirical-comparison-rigor.md`](empirical-comparison-rigor.md) (the runs this plan governs). ↔ [`references/experiment-program-scaffold.md`](experiment-program-scaffold.md) (the program it executes). ↔ `{suite}/_outputs/reproducibility-manifest.md` (where the plan is logged).
