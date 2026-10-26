<!-- SPDX-License-Identifier: MIT -->

# Autonomous Experiment Loop

Reference surface for the [`research-suite`](../SKILL.md) skill. Houses the
opt-in, default-off autonomous iterate-and-decide loop that drives a mutable
target against a frozen harness until a stop condition is met. Loads
selectively, beside `SKILL.md`, so the router's entry-point stays tight.

This surface adds operational detail to existing rigor mandates — it
operationalizes R2 (reproducibility), R5 (preregistration discipline), and R7
(statistical rigor) for the autonomous-campaign case, and applies R3
(falsifiability) to every trial's prediction and journal row — and introduces
**no new R-mandate**: R1–R10 is a closed set of ten, catalogued at
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
operator **MUST** confirm these surfaces:

- **The single mutable target.** The one artifact the loop is permitted to
  change.
- **The frozen harness.** The evaluation harness, data preparation, runtime
  utilities, and dependency set that are off-limits, identified by a version or
  content hash that every journal row carries.
- **The primary metric.** The confound-invariant quantity each trial is scored
  by, with its direction stated.
- **The evaluation sets.** The search set, the admission set, and the final
  untouched set — or an explicit statement that none exists, which confines the
  result to a development finding — as defined under "Search and admission
  signals" below.
- **The acceptance rule.** The repetitions per trial and the noise margin a
  trial MUST clear, as defined under "Noise-aware acceptance rule" below.
- **The per-trial budget.** The fixed resource ceiling every trial runs under.
- **The campaign workspace.** The isolated branch and working tree, under an
  operator-agreed tag, the campaign runs on.

The operator **MAY** also fix **campaign stop criteria** at the same gate: a
cumulative-spend ceiling, a trial-count ceiling, a **no-gain window** (the
number of consecutive trials without a retained gain after which the loop
stops), or any combination. No default value is set for any of them; the
operator names the number or omits the criterion. A retained simplification
that only ties does not reset a no-gain window.

After that single confirmation the loop runs **non-stopping**. It **MUST NOT**
re-ask each iteration; re-confirming per trial defeats the autonomous posture
the operator opted into. The stops are exactly three: the operator's interrupt,
an exhausted idea queue after the renewal steps below, and a stop criterion the
operator fixed at the gate. A stop criterion that is reached is a
pre-authorized stop, not a question: the loop writes the close-out record
(see "Close-out record" below) and ends. With no criterion fixed, the
loop runs until the operator interrupts. A change in the frozen-harness stamp
(see the results journal) is an integrity halt, not a stop the operator chose.

## Isolated campaign workspace — version control as ledger

Each campaign runs on its **own isolated branch and working tree** under the
operator-agreed tag, starting from a **clean tip**. Version control **IS** the
experiment ledger:

- **A trial is one commit.** Each proposed change lands as a single commit so
  the trial history is the campaign history.
- **The incumbent is the branch tip.** The current best-retained state is
  whatever the tip points at. The acceptance rule below compares against a
  separate **reference incumbent** — the state at the most recent gain — which
  differs from the tip after a retained tie.
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

The definitions of the search set, the admission set, and the final untouched
set belong to the frozen harness. A trial **MUST NOT** move an instance between
sets, add or remove one, or change how the metric is computed on any of them.

The **operating baseline of the loop** — its own instructions and context — is
a curated, human-refined surface **separate from the mutable target**. The loop
refines the target; a human refines the loop's operating baseline. The two
**MUST NOT** be conflated.

## Search and admission signals — keeping the selector off the test

A loop that retains a change only when it beats the incumbent is an adaptive
selector: each retained change was chosen because of what the evaluation said,
so the set that decides retention is no longer independent of the retained
result. The loop therefore reads two signals from two sets and holds a third
back. The three sets are **disjoint** and are defined in the frozen harness
before the first trial. In the terms of
[`references/compute-utilization.md`](compute-utilization.md) (Automated
Configuration on Disjoint Splits), the search set and the admission set are
both tuning-side, because each is consulted to shape or to retain a
configuration, and only the final untouched set is a test split, which MUST NOT
enter selection.

- **Steering reads the search set.** The loop **MAY** read the search signal
  freely to shape the next proposal, diagnose a trial, or read a near-miss.
- **Retention reads the admission set.** A change that cleared the search
  stage is retained only when the admission signal confirms it. The set
  contributes the keep-or-revert verdict and the aggregate the gate records; per-instance admission results **MUST NOT**
  inform a proposal.
- **Admission queries are counted.** Each trial that reaches the admission set
  is one query, however many repetitions it runs (routing is set under
  "Noise-aware acceptance rule"). The journal counts them, and the count is
  disclosed beside every result the campaign reports: the more times the
  admission set has decided, the less independent it is of the incumbent.
- **A search gain that admission does not confirm is overfitting.** Such a
  trial is reverted with its cause recorded as selection overfitting, never
  kept because the search signal improved. A widening gap between the
  incumbent's gain on the search signal and on the admission signal is reported
  as an overfitting finding, not absorbed into the headline.
- **The final untouched set is read once.** No trial, proposal, or diagnosis
  reads it. At close-out the baseline and the final incumbent are each
  evaluated on it in a single evaluation event, run at the full Repetition
  Regime with seeds recorded, and that evaluation is the only estimate of the
  campaign's gain that selection has not touched. The set is sized for the
  smallest effect that matters under
  [`references/power-and-sample-size.md`](power-and-sample-size.md). Once read,
  it is spent: any further trial begins a new campaign with a new untouched set.
- **Without an untouched set, the result is selection-contaminated.** A
  campaign whose incumbent enters a method comparison **MUST** hold an
  untouched set, because the comparison needs a test split disjoint from tuning.
  A campaign that holds none reports its gain only as a development finding,
  labelled **selection-contaminated** and exploratory: the number was selected
  as the best of the trials the admission set was queried on. The label
  travels with the number into the experiment log and the analysis stage.

## The loop: propose, commit, run, extract, decide

Each iteration runs a fixed sequence:

- **Propose.** Propose one change to the mutable target, and state its
  **falsifiable prediction** before anything runs: the effect on the primary
  metric the change is expected to produce, the reason, and the observation
  that would refute it (R3). A proposal with no refuting outcome is not
  queued.
- **Commit.** Land the change as a single trial commit. The prediction goes in
  the commit message, so it is fixed before the outcome exists.
- **Run.** Execute under the fixed per-trial budget, at the repetitions the
  acceptance rule fixes, capturing full output to a per-trial **run log** — the
  loop **MUST NOT** flood stdout with run output.
- **Extract.** Read the primary metric from the run log **mechanically**, not
  by narrative judgment, as the search signal and, when the trial reaches the
  admission stage, the admission signal. The primary metric is
  **confound-invariant** — chosen to isolate the effect under study so a
  measured change reflects the change to the target, not a shifted condition.
- **Decide.** Route the trial through the decision gate below.

## Decision gate — gain against complexity

The gate **retains** a trial (advancing the tip) only if it clears the
acceptance rule below against the reference incumbent, at the search stage and
then at the admission stage; otherwise it **reverts** (resetting to the prior
tip). The gate weighs metric **gain** against **complexity** cost, so that
parsimony acts as a regularizer:

- **Simplification that holds the metric is retained.** A change that keeps the
  metric while reducing complexity is a keep.
- **A deletion-driven improvement is a strong keep.** A change that improves
  the metric by removing surface is the strongest class of retention.
- **A marginal gain bought with disproportionate complexity is reverted.** A
  small metric gain that costs a large complexity increase does not clear the
  gate.

## Noise-aware acceptance rule

A stochastic metric read from one run is a draw, not a measurement; a gate that
ranks single draws lets the incumbent climb on noise. The acceptance rule is
agreed at the confirmation gate and fixed for the campaign.

- **Repetitions are agreed, not assumed.** A deterministic target and evaluator
  run once per signal, and the journal row says so. A stochastic one runs the
  repetitions agreed at the gate, each with its own recorded seed, and the
  trial's value is the aggregate over them.
- **The gate screens; the floor binds the reported number.** The repetitions
  agreed for the gate **MAY** fall below the floor of the Repetition Regime in
  [`references/empirical-comparison-rigor.md`](empirical-comparison-rigor.md),
  because a gate-time comparison is a screen. Any figure the campaign reports —
  the incumbent's gain over the baseline above all — **MUST** be re-measured at
  close-out under the full regime. A gate-time comparison is never a result.
- **The margin comes from the baseline's noise.** The baseline row runs at the
  agreed repetitions on both signals, so its spread is on record before the
  first trial; the baseline's admission read is the reference value for the
  admission stage and does not count as an admission query. The noise margin is
  set against that spread. Where the spread is nil because the target is
  deterministic, the gate states the margin explicitly, and it **SHOULD**
  reflect the sampling error of the instance set rather than default to zero,
  so the incumbent does not climb on a few flipped instances. The margin
  **MUST NOT** change after the first trial; a margin or repetition count
  changed mid-campaign is a deviation, disclosed per R5 in the experiment log,
  never a quiet adjustment made to rescue a stalled campaign.
- **Gain, tie, loss.** A trial is classified on a signal against the
  reference incumbent: the retained state at the most recent gain, or the
  baseline until the first gain. It **gains** when its aggregate beats the
  reference incumbent's by more than the margin, **ties** when it falls within
  the margin on either side, and **loses** when it falls short by more than the
  margin. A tie is not a gain: a tied trial that reduces complexity is retained
  under the simplification rule above, advancing the tip but not the reference
  incumbent, and a tied trial that does not is reverted. Because the reference
  incumbent does not move on a tie, a chain of tied simplifications cannot walk
  the metric down beyond one margin.
- **Two stages, one admission query.** At the search stage, a loss, a tie that
  does not reduce complexity, and a gain the complexity rule above reverts are
  reverted without an admission query; a gain, or a tie that reduces complexity,
  proceeds. At the admission stage, which costs one query, the trial is retained
  on a gain the complexity rule does not revert or on a tie that reduces
  complexity; any other outcome is reverted with its cause recorded.

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
  crash, with the cause the log tail supports or `undiagnosed` when it supports
  none, and the loop proceeds to the next idea.

The loop **MUST NOT** loop indefinitely on an unfixable trial; an
un-diagnosable run is a crash-status record, not a retry spiral.

## Results journal — the auditable runbook

An **append-only results journal** records, per trial:

- **The identifier / commit** the trial landed as.
- **The falsifiable prediction**, copied verbatim from the commit message and
  never rewritten after the outcome.
- **The signals.** The search signal and, when the trial reached the admission
  stage, the admission signal, each as the aggregate with its repetition count.
- **The stamps.** The seed of each repetition and the frozen-harness version.
- **The resource cost** the trial consumed.
- **The status** — one of `keep`, `discard`, or `crash`.
- **A short description** of the change attempted.
- **The lesson and the cause.** What the outcome taught, whether or not the
  prediction held, and for a discard or crash the cause, specific enough that a
  later reader can tell whether it applies to a new candidate. A discard
  without a cause is an incomplete row.

The **first row is the unmodified baseline** with status `keep` and no
prediction, run at the agreed repetitions, establishing the reference point and
the noise every later trial is measured against. A row whose frozen-harness
stamp differs from the baseline row's is not comparable to it: the harness has
moved. The loop **MUST** halt, **MUST NOT** journal that trial as a keep, **MUST
NOT** read the untouched set, and reports the integrity failure to the
operator.

The journal is **campaign-local working state** (gitignored) and **IS the
auditable runbook** of the advancement gate — the same runbook discipline
specified at [`references/advancement-gate.md`](advancement-gate.md),
materialized as the loop's trial log.

### Standing constraints

The journal carries a short **standing-constraints digest** as its own
append-only list. A falsified direction is a direction, not a variant: when a
trial's outcome refutes its prediction by more than the noise margin and its
lesson names a cause that reaches beyond the single change, the digest gains an
entry — the direction closed, the reason, and the journal row that showed it. A
tie falsifies nothing, and a crash with an undiagnosed cause closes nothing. An
entry is lifted only by a later entry that cites the row whose lesson
contradicts its reason, and is never dropped silently.

## Idea generation when the queue empties

When the idea queue empties, the loop **MUST** attempt renewal before halting
rather than stopping at the first dry spell:

- **Mine the reference corpus** for method families and structural ideas not
  yet tried.
- **Re-read the in-scope surfaces** to recover context the queue drifted from.
- **Combine near-miss trials** whose individual metric gains fell short of the
  gate.
- **Re-read the lessons** for a cause shared by several discards, and propose
  against that cause.
- **Attempt higher-variance structural changes** rather than more of the same
  marginal tweaks.

Before queuing any candidate, the loop **MUST** read the standing-constraints
digest and the journal's lessons, not only the list of variants tried, and
**MUST NOT** queue a candidate whose prediction a standing constraint already
refutes unless the candidate states why the constraint's reason does not apply
to it, which makes its trial a test of the constraint. Among queued
candidates, the loop **SHOULD** run first the one whose outcome would teach
whichever way it falls — separating live explanations of an earlier result —
ahead of one chosen only for the likeliest gain.

## Close-out record

When the loop stops, it **MUST** write a **close-out record** before the
campaign workspace is left. The record carries:

- **The counts.** Trials, keeps, discards, crashes, and admission queries. The
  trial count is the number of variants the selection ran over, and the
  analysis stage needs it to judge how much selection the result carries.
- **The gain over the baseline.** The final incumbent's gain over the baseline
  on the search signal and on the admission signal, re-measured at close-out
  under the full regime and reported with an effect size and confidence
  interval per [`references/empirical-comparison-rigor.md`](empirical-comparison-rigor.md).
  Both figures are labelled selection-contaminated: the incumbent was chosen on
  them.
- **The untouched-set result,** the single evaluation event of the baseline and
  the incumbent, or the **selection-contaminated** label for the whole result
  when no untouched set is held or an integrity halt ended the campaign.
- **The incumbent to check out.** The branch and commit the campaign ended on.
- **The standing-constraints digest.**

The record **MUST** be entered in the experiment log (`/research-experiment`
§3 Trials & Observations), and the journal **MUST** be copied unaltered to the
raw-data destination, so that every discarded and crashed trial survives the
gitignored workspace (R3). A loop-selected number counts as pre-specified only
through the single untouched-set evaluation and only when the frozen
preregistration named that evaluation; every other loop-selected number is
exploratory by construction (R5).

## Bindings (§0.j five-direction)

- **Drives →** ● The opt-in autonomous experiment mode of `/research-experiment` (Phase 2 iterate-and-decide loop). ● The close-out record that `/research-analysis` (Phase 4) reads to classify a loop-selected result.
- **Satisfies →** ● The [`research-suite`](../SKILL.md) skill's reference-surface obligation (the autonomous-experiment-loop surface loads selectively, beside the router).
- **Established by ↑** ● [`research-suite/SKILL.md`](../SKILL.md) (the knowledge surface this reference extends). ● [`references/rigor-mandates.md`](rigor-mandates.md) (the R2 / R5 / R7 mandates this surface operationalizes, and the R3 mandate it applies per trial).
- **Cross-bound with ↔** ↔ [`references/advancement-gate.md`](advancement-gate.md) (the runbook and decision discipline the journal materializes). ↔ [`references/compute-utilization.md`](compute-utilization.md) (the fixed per-trial budget and hard timeout the loop runs under, and the disjoint-split discipline the three evaluation sets extend). ↔ [`references/empirical-comparison-rigor.md`](empirical-comparison-rigor.md) (the Repetition Regime floor the gate screens against and the close-out re-measures under). ↔ [`references/power-and-sample-size.md`](power-and-sample-size.md) (the sizing of the untouched set). ↔ `commands/research-analysis.md` (the pre-specified-versus-exploratory split the close-out record feeds). ↔ `rules/multi-agent-workflow.md` (the opt-in default-off posture the loop inherits).
