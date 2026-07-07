<!-- SPDX-License-Identifier: MIT -->

# Autonomous Experiment Loop

Reference surface for the [`research-suite`](../SKILL.md) skill. Houses the
opt-in, default-off autonomous iterate-and-decide loop that drives a mutable
target against a frozen harness until an operator interrupts. Loads
selectively, beside `SKILL.md`, so the router's entry-point stays tight.

This surface adds operational detail to existing rigor mandates — it
operationalizes R2 (reproducibility), R5 (preregistration discipline), and R7
(statistical rigor) for the autonomous-campaign case — and introduces **no new
R-mandate**: R1–R10 is a closed set of ten, catalogued at
[`references/rigor-mandates.md`](rigor-mandates.md). The loop is a mode of
executing an already-designed study, not a new obligation.

## Opt-in, default-off posture

The autonomous loop is **opt-in and default-off**. A clean run **MUST NOT**
auto-invoke it; the loop is entered only on explicit operator opt-in through
the `/research-experiment` autonomous mode (Phase 2), consistent with the
opt-in default-off posture specified at `rules/multi-agent-workflow.md`. A
stage that silently escalates a designed study into a non-stopping campaign is
a structural failure.

## One confirmation gate, then non-stopping

Entry is confirmation-gated **exactly once**. Before the loop starts, the
operator **MUST** confirm five surfaces:

- **The single mutable target.** The one artifact the loop is permitted to
  change.
- **The frozen harness.** The evaluation harness, data preparation, runtime
  utilities, and dependency set that are off-limits.
- **The primary metric.** The confound-invariant quantity each trial is scored
  by.
- **The per-trial budget.** The fixed resource ceiling every trial runs under.
- **The campaign workspace.** The isolated branch and working tree, under an
  operator-agreed tag, the campaign runs on.

After that single confirmation the loop runs **non-stopping until the operator
interrupts**. It **MUST NOT** re-ask each iteration; re-confirming per trial
defeats the autonomous posture the operator opted into. The operator's
interrupt is the only stop signal short of an exhausted idea queue.

## Isolated campaign workspace — version control as ledger

Each campaign runs on its **own isolated branch and working tree** under the
operator-agreed tag, starting from a **clean tip**. Version control **IS** the
experiment ledger:

- **A trial is one commit.** Each proposed change lands as a single commit so
  the trial history is the campaign history.
- **The incumbent is the branch tip.** The current best-retained state is
  whatever the tip points at.
- **Retain advances the tip; revert resets it.** Acceptance moves the incumbent
  forward; rejection resets the working tree to the prior tip.

The campaign **MUST** start from a clean tip so the first recorded reference
point is unmodified.

## Frozen harness versus mutable target

Exactly **one** target is mutable. The evaluation harness, data preparation,
runtime utilities, and dependency set are **FROZEN and off-limits** for two
reasons that the loop **MUST** preserve:

- **The metric cannot be gamed.** Freezing the harness that measures the metric
  removes the shortcut of editing the ruler instead of the work.
- **No new dependency is introduced.** The dependency set is fixed, so a trial
  cannot buy an apparent gain by importing capability from outside the frozen
  boundary.

The **operating baseline of the loop** — its own instructions and context — is
a curated, human-refined surface **separate from the mutable target**. The loop
refines the target; a human refines the loop's operating baseline. The two
**MUST NOT** be conflated.

## The loop: propose, commit, run, extract, decide

Each iteration runs a fixed sequence:

- **Propose.** Propose one change to the mutable target.
- **Commit.** Land the change as a single trial commit.
- **Run.** Execute under the fixed per-trial budget, capturing full output to a
  per-trial **run log** — the loop **MUST NOT** flood stdout with run output.
- **Extract.** Read the primary metric from the run log **mechanically**, not
  by narrative judgment. The primary metric is **confound-invariant** — chosen
  to isolate the effect under study so a measured change reflects the change to
  the target, not a shifted condition.
- **Decide.** Route the trial through the decision gate below.

## Decision gate — gain against complexity

The gate **retains** a trial (advancing the tip) only if it **beats the
incumbent** on the primary metric; otherwise it **reverts** (resetting to the
prior tip). The gate weighs metric **gain** against **complexity** cost, so
that parsimony acts as a regularizer:

- **Simplification that holds the metric is retained.** A change that keeps the
  metric while reducing complexity is a keep.
- **A deletion-driven improvement is a strong keep.** A change that improves
  the metric by removing surface is the strongest class of retention.
- **A marginal gain bought with disproportionate complexity is reverted.** A
  small metric gain that costs a large complexity increase does not clear the
  gate.

## Budget and resource discipline

The loop runs under the fixed per-trial budget and the **hard timeout at a
multiple of that budget** specified at
[`references/compute-utilization.md`](compute-utilization.md); a trial that
exceeds the hard timeout is a failed run, not an extended one. Secondary
resource ceilings are soft constraints per that surface. The budget itself is
never optimized.

## Crash handling

On a run that yields **no metric**, the loop **MUST** inspect the run log's
tail for the cause and then act bounded:

- **Fix trivial breakage and re-run** when the log tail shows an obvious,
  in-target defect the loop introduced.
- **Record a crash status and move on** otherwise — the trial is logged as a
  crash and the loop proceeds to the next idea.

The loop **MUST NOT** loop indefinitely on an unfixable trial; an
un-diagnosable run is a crash-status record, not a retry spiral.

## Results journal — the auditable runbook

An **append-only results journal** records, per trial:

- **The identifier / commit** the trial landed as.
- **The primary metric** the run produced.
- **The resource cost** the trial consumed.
- **The status** — one of `keep`, `discard`, or `crash`.
- **A short description** of the change attempted.

The **first row is the unmodified baseline** with status `keep`, establishing
the reference point every later trial is measured against. The journal is
**campaign-local working state** (gitignored) and **IS the auditable runbook**
of the advancement gate — the same runbook discipline specified at
[`references/advancement-gate.md`](advancement-gate.md), materialized as the
loop's trial log.

## Idea generation when the queue empties

When the idea queue empties, the loop **MUST** attempt renewal before halting
rather than stopping at the first dry spell:

- **Mine the reference corpus** for method families and structural ideas not
  yet tried.
- **Re-read the in-scope surfaces** to recover context the queue drifted from.
- **Combine near-miss trials** whose individual metric gains fell short of the
  gate.
- **Attempt higher-variance structural changes** rather than more of the same
  marginal tweaks.

Before queuing any candidate, the loop **MUST** review the journal to avoid
re-running an explored variation.

## Bindings (§0.j five-direction)

- **Drives →** ● The opt-in autonomous experiment mode of `/research-experiment` (Phase 2 iterate-and-decide loop).
- **Satisfies →** ● The [`research-suite`](../SKILL.md) skill's reference-surface obligation (the autonomous-experiment-loop surface loads selectively, beside the router).
- **Established by ↑** ● [`research-suite/SKILL.md`](../SKILL.md) (the knowledge surface this reference extends). ● [`references/rigor-mandates.md`](rigor-mandates.md) (the R2 / R5 / R7 mandates this surface operationalizes).
- **Cross-bound with ↔** ↔ [`references/advancement-gate.md`](advancement-gate.md) (the runbook and decision discipline the journal materializes). ↔ [`references/compute-utilization.md`](compute-utilization.md) (the fixed per-trial budget and hard timeout the loop runs under). ↔ `rules/multi-agent-workflow.md` (the opt-in default-off posture the loop inherits).
