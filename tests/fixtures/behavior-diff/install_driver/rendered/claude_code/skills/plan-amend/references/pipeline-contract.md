<!-- SPDX-License-Identifier: MIT -->

## Pipeline Contract

**Pipeline position.** **Wrapping / orthogonal.** `/plan-amend` operates on a suite that already exists at any stage of the canonical sequence `/plan-spec → /plan-generate → /plan-review → /plan-design (CONDITIONAL — architecture-bearing suites only) → /plan-execute`. Invocable at any point once a suite exists; it inspects the suite's current stage and re-derives only the affected downstream artifacts. It never executes phase implementation work — it leaves the amended suite ready for re-review.

**Consumed.** The target suite's `_spec/spec.md`, `_inputs/handoff-manifest.yml`, infrastructure files (PREAMBLE.md, MASTER-PLAN.md, PROGRESS.md, PLAN-NOTES.md), `phases/**/PHASE.md`, and any existing phase reports. The PLAN-NOTES.md decision ledger is the authoritative record of prior resolved decisions and is read first.

**Emitted.** The re-derived subset of downstream artifacts the amendment touches (spec, master-plan, phase files, notes); an appended PLAN-NOTES.md decision-ledger entry recording the amendment mode, the affected artifacts, and the rationale; and an updated handoff manifest reflecting the amended suite shape. Artifacts the amendment does not touch are left byte-unchanged.
