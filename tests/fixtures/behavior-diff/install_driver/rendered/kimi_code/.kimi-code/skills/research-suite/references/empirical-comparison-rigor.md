<!-- SPDX-License-Identifier: MIT -->

# Empirical-Comparison Rigor Floor

Reference surface for the [`research-suite`](../SKILL.md) skill. Houses the
statistical floor a head-to-head empirical comparison meets before its result
earns a claim — repetition regime, reporting statistics, figures, and the
significance-and-effect-size protocol. Loads selectively, beside `SKILL.md`, so
the router's entry-point stays tight.

This surface adds operational detail to an existing rigor mandate: it
operationalizes **R7 — Statistical rigor** (and the repetition aspect of
**R2 — Reproducibility**). It introduces no new R-mandate; R1–R10 is a closed
set of ten. What follows fixes the concrete floor a comparison meets so its
conclusion is defensible against an adversarial reader.

## Repetition Regime

- **Stochastic methods repeat.** A method whose outcome depends on a random draw — an initialization, a shuffle, a sampled trial — MUST be run at least thirty independent repetitions per instance, each with its own recorded seed, before any statistic derived from it is reported. Thirty is the floor, not the target.
- **Raise the count on high variance.** When the repetition spread on an instance is wide relative to the differences under test, the count MUST be raised until the reported summary statistics are stable; a comparison decided inside the noise band of too few repetitions is not decided.
- **Deterministic methods run once.** A method whose outcome is fixed given its inputs MUST be run exactly once per instance; repeating it fabricates a spurious distribution. The report states plainly which method-instances are deterministic and which are stochastic.
- **Independence is real.** Each repetition MUST be genuinely independent — a fresh seed, no shared mutable state across runs — so the repetition set is a sample and not a replay. Seeds are recorded to the reproducibility manifest per R2.

## Reporting Statistics

- **Report the full five per method-instance.** For every method-instance cell the report MUST carry the **best**, **mean**, **median**, **standard deviation**, and **worst** of the primary metric across repetitions. A lone mean hides skew and tail behavior; the five-number surface exposes them.
- **State the metric and its direction.** The primary metric MUST be named and its direction stated (higher-is-better or lower-is-better) so best and worst are unambiguous; a comparison that leaves direction implicit invites a misread.
- **Deterministic cells report the single value.** A deterministic method-instance reports its one observed value in place of the distribution, marked as deterministic so a reader does not mistake a point for a collapsed spread.

## Figures

- **Convergence curves.** Where a method spends a budget to reach its result, the report SHOULD present the primary metric as a function of the consumed budget — the convergence curve — so anytime behavior and the budget at which methods cross are legible, not only the terminal value.
- **Distribution plots.** The per-instance repetition distributions SHOULD be shown as box or violin plots so spread, skew, and outliers are visible at a glance rather than compressed into a mean.
- **Critical-difference visualization.** When more than two methods are ranked across instances, the report SHOULD present the ranking as a critical-difference visualization so which methods are statistically separable and which are tied is read directly from the figure.

## Significance and Effect Size

- **Pairwise uses a paired nonparametric test.** A two-method comparison across a shared set of instances MUST use a paired nonparametric signed-rank test; the pairing is by instance, and the nonparametric form avoids the distributional assumptions a parametric test would impose on metric samples that rarely satisfy them.
- **Many methods use an omnibus then a post-hoc correction.** A comparison of more than two methods MUST first apply an omnibus rank test across all methods; only on a positive omnibus result does it proceed to pairwise post-hoc tests, each carrying a multiple-comparison correction so the family-wise error rate is controlled.
- **Report a rank-based effect size with confidence intervals.** Every reported difference MUST carry a rank-based / stochastic-superiority effect size — the probability that a draw from one method beats a draw from the comparator — reported **with** its confidence interval. A p-value alone is never sufficient: significance without an effect size and its interval states that a difference exists without stating how large it is or how precisely it is known.
- **Null and negative results stand.** A comparison whose test does not clear its threshold, or whose effect size straddles the no-difference point, is recorded as that finding per R3 — never rerun until it flips, never quietly dropped.

## Bindings (§0.j five-direction)

- **Drives →** ● The repetition, statistics, and figure decisions in `/research-design` (Phase 4 preregistered repetition and reporting plan). ● The repetition regime in `/research-experiment` (Phase 2 stochastic repetition). ● The tests, effect sizes, and figures in `/research-analysis` (Phases 2, 3, and 5).
- **Satisfies →** ● The [`research-suite`](../SKILL.md) skill's reference-surface obligation (the empirical-comparison rigor floor loads selectively, beside the router).
- **Established by ↑** ● [`research-suite/SKILL.md`](../SKILL.md) (the knowledge surface this reference extends). ● [`references/rigor-mandates.md`](rigor-mandates.md) (the R7 mandate — with the R2 repetition aspect — this surface operationalizes).
- **Cross-bound with ↔** ↔ [`references/compute-utilization.md`](compute-utilization.md) (fair execution, budget parity, and disjoint tuning splits under which the repetitions run). ↔ [`references/experiment-program-scaffold.md`](experiment-program-scaffold.md) (where the runs, statistics, and figures land on disk). ↔ [`references/advancement-gate.md`](advancement-gate.md) (the thresholds the gate reads from this floor). ↔ `agents/fact-checker.md` (adversarial verification of every reported result).
