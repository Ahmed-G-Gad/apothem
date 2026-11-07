<!-- SPDX-License-Identifier: MIT -->

# Experiment-Program Scaffold

Reference surface for the [`research-suite`](../SKILL.md) skill. Houses the
per-deliverable experiment-program layout — the ordered setup → pilot →
comparison → ablation → sensitivity → statistics sub-stages every empirical
deliverable follows. Loads selectively, beside `SKILL.md`, so the router's
entry-point stays tight.

This surface adds operational detail to the reproducibility mandate (R2) and
the preregistration-discipline mandate (R5); it introduces **no new
R-mandate** — R1–R10 is a closed set of ten. It fixes the on-disk shape and
the ordered execution of an empirical program so that an independent party
re-runs it to the same observations (R2) and so that the plan frozen before
data collection (R5) maps mechanically onto the records that answer it.

## One Program Subtree Per Deliverable

Each deliverable carrying an empirical program **MUST** own a distinct program
subtree, and its records **MUST** map 1:1 to that target deliverable — one
program subtree per deliverable, never a shared or merged tree. The subtree
carries a stable, kebab-case sub-stage layout that is identical across
deliverables so the structure is predictable rather than reinvented:

- **`setup/`** — the fixed frame of the program: the problems and instances
  under study, the metrics **as the host defines them**, the environment, the
  seeds, and the hardware. Everything downstream reads from this frozen frame;
  nothing below `setup/` redefines an instance, a metric, or a seed.
- **`pilot/`** — small-scale calibration runs. A pilot **MUST** run before the
  full comparison to fix the budget, the parameter ranges, and the
  configurations. A pilot calibrates; it **MUST NOT** be reported as a result
  and **MUST NOT** enter the headline claim. Pilot records are retained for
  provenance, marked as calibration, and excluded from the comparison tables.
- **`comparison/`** — the full head-to-head: all comparators, across all
  instances, under one unified budget. The budget parity and the fairness of
  the split are governed by [`references/compute-utilization.md`](compute-utilization.md);
  the inferential treatment of the resulting records is governed by
  [`references/empirical-comparison-rigor.md`](empirical-comparison-rigor.md).
- **`ablation/`** — the marginal-attribution runs. Each ablation variant
  **MUST** disable or remove exactly one component at a time, so the delta
  isolates the marginal contribution of that one component — one variant per
  removed component, never two removals folded into a single run.
- **`sensitivity/`** — the robustness sweeps. Each tunable parameter **MUST**
  be swept over a principled range, and the deliverable **MUST** report how the
  primary metric responds across that range — robustness, not a single point.
- **`statistics/`** — the inferential battery from
  [`references/empirical-comparison-rigor.md`](empirical-comparison-rigor.md),
  computed over the raw records. This stage reads `raw/` and writes the effect
  sizes, confidence intervals, paired tests, omnibus ranks, and correction
  outcomes; it never re-runs a comparator.
- **`raw/`** — the immutable per-run records the sub-stages above consume. A
  record is written once and never rewritten; the statistics stage reads it,
  the figures stage plots from it.
- **`figures/`** — the plots derived from `raw/` and `statistics/`
  (convergence curves, distribution plots, critical-difference diagrams). A
  figure is a view of the records, never an independent source of a number.

## Ordered Execution

The sub-stages execute in order — setup, then pilot, then comparison, then
ablation, then sensitivity, then statistics. Each stage's inputs are frozen by
the stages above it:

- **Setup precedes everything.** The problems, instances, metrics,
  environment, seeds, and hardware are fixed before a single measured run.
- **Pilot precedes comparison.** The budget, parameter ranges, and
  configurations are calibrated on small-scale runs **before** the full
  comparison opens; calibration decisions are recorded, and the calibrated
  values become inputs the comparison consumes unchanged.
- **Comparison, ablation, and sensitivity all read the same frozen frame.**
  They draw instances, metrics, seeds, and the unified budget from `setup/`;
  none of them may quietly re-tune a value the pilot already fixed.
- **Statistics reads raw, never re-runs.** The inferential battery operates
  over the recorded `raw/` records; a missing or malformed record is a defect
  surfaced, not a silently re-run trial.

## Record Naming

Sub-stage directories are kebab-case and identical across deliverables. Every
per-run record filename **MUST** encode the method, the instance, and the seed
that produced it, so a record is self-identifying and the statistics stage can
group it without an external index — for example, `method--instance--seed`.
A record that cannot state its method, instance, and seed from its own name is
a provenance defect (R2), not an acceptable record.

## Bindings (§0.j five-direction)

- **Drives →** ● The program-layout decision and the pilot / comparison / ablation / sensitivity planning in `/research-design` (Phase 3). ● The execution of that program in `/research-experiment` (Phases 1–2).
- **Satisfies →** ● The [`research-suite`](../SKILL.md) skill's reference-surface obligation (the experiment-program scaffold loads selectively, beside the router).
- **Established by ↑** ● [`research-suite/SKILL.md`](../SKILL.md) (the knowledge surface this reference extends). ● [`references/rigor-mandates.md`](rigor-mandates.md) (the R2 reproducibility and R5 preregistration-discipline mandates this surface operationalizes).
- **Cross-bound with ↔** ↔ [`references/empirical-comparison-rigor.md`](empirical-comparison-rigor.md) (the statistics stage). ↔ [`references/compute-utilization.md`](compute-utilization.md) (the unified budget and execution plan). ↔ [`references/directory-structure.md`](directory-structure.md) (where the program subtree lands on disk).
