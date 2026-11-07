<!-- SPDX-License-Identifier: MIT -->

# Advancement Gate

Reference surface for the [`research-suite`](../SKILL.md) skill. Houses the
explicit definition-of-done gate a deliverable clears before it advances, and
the auditable runbook that records each clearance. Loads selectively, beside
`SKILL.md`, so the router's entry-point stays tight.

This surface adds operational detail to two existing rigor mandates — R7
(statistical rigor) and R5 (preregistration discipline) — and introduces no new
R-mandate; R1–R10 is a closed set of ten. The advance gate is the point where
statistical thresholds and required artifacts are checked together, and where
the decision to promote a deliverable is recorded before the next one opens.

## The advance gate — definition of done

A deliverable advances only when it clears an **explicit** gate. The gate has
two clauses, and both MUST hold:

- **Statistical thresholds.** The contribution MUST beat its comparators
  convincingly *and* significantly on the target metrics, with a meaningful
  effect size — the thresholds and the tests are the ones stated in
  [`references/empirical-comparison-rigor.md`](empirical-comparison-rigor.md).
  A significant-but-negligible margin, or a large-but-non-significant margin,
  does not clear the gate; the deliverable is redesigned and re-run.
- **Required artifacts present.** The evidence package MUST carry the raw
  records, the computed statistics, the figures, the reproducibility manifest,
  and the comparator provenance. A missing artifact blocks the advance as
  firmly as a failed threshold does.

A deliverable that does not clear the gate is **redesigned and re-run**, never
advanced. There is no partial pass: a near-miss is a not-yet, and it routes
back to design.

## Auditable runbook

Each gate clearance MUST be logged in a per-deliverable runbook so that every
advance is auditable after the fact. The runbook records:

- **The checks that passed** — each threshold clause and each required-artifact
  clause, with its pass state.
- **The supporting evidence** — as paths to the raw records, the statistics,
  and the figures, not as restated numbers, so the audit resolves to the
  primary artifact.
- **The advance decision** — the explicit promote-or-redesign verdict and the
  moment it was recorded.

For an autonomous campaign, the runbook IS the results journal of
[`references/autonomous-experiment-loop.md`](autonomous-experiment-loop.md):
the append-only journal that records each trial's identifier, metric, resource,
status, and description is the same auditable trace the gate reads. The manual
runbook and the autonomous journal are one surface under two entry paths.

## Contribution parsimony and distinctness

The gate also holds the shape of the claim itself:

- **Parsimony.** The contribution under study SHOULD be the minimal-yet-effective
  set of ablatable components and tunable parameters. Excess parts and excess
  knobs weaken the claim: each added component is a surface the comparator can
  attribute the gain to, and each added knob is a degree of freedom that
  invites post-hoc flexibility per R5.
- **Distinctness.** Each claimed contribution MUST be distinct and substantial —
  not an increment of another contribution in the same program, and not a
  near-duplicate of one. Two contributions that collapse into one under
  examination are one contribution, and the program states them as such rather
  than double-counting.

## Rigor scaled to venue ambition

The depth of the rigor floor scales to the target-venue ambition. That ambition
is set upstream at `/research-spec` and `/research-proposal`; the gate inherits
it and does not re-decide it. A higher-ambition target raises the bar the
statistical thresholds and the required-artifact set MUST meet, so the
reproducibility-evidence outputs SHOULD be prepared to directly scaffold the
deliverable's evidence package — the artifacts the gate collects are the same
artifacts the package ships, assembled once.

## Sequential program and 1:1 mapping

In a multi-deliverable program, deliverables clear the gate sequentially:

- Each result MUST map 1:1 to its target deliverable — one result, one
  deliverable, no result standing in for two claims.
- An advance MUST be recorded in the runbook before the next deliverable opens,
  so the program never runs two open gates at once and every advance has a
  fixed, ordered provenance.

## Bindings (§0.j five-direction)

- **Drives →** ● The promotion/advance decision at `/research-analysis`
  (Phase 5). ● The orchestration advance-gate lens in the `/research` wrapper
  (verify the stage attestation, not recompute the statistics). ● The
  accept-as-advance-gate verdict at `/research-review`.
- **Satisfies →** ● The [`research-suite`](../SKILL.md) skill's reference-surface
  obligation (the advancement gate loads selectively, beside the router).
- **Established by ↑** ● [`research-suite/SKILL.md`](../SKILL.md) (the knowledge
  surface this reference extends). ● [`references/rigor-mandates.md`](rigor-mandates.md)
  (the R7 and R5 mandates this surface operationalizes).
- **Cross-bound with ↔** ↔ [`references/empirical-comparison-rigor.md`](empirical-comparison-rigor.md)
  (the statistical thresholds the gate checks). ↔ [`references/autonomous-experiment-loop.md`](autonomous-experiment-loop.md)
  (its results journal is the autonomous runbook). ↔ [`references/comparator-provenance.md`](comparator-provenance.md)
  (a required artifact the gate confirms present).
