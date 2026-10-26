<!-- SPDX-License-Identifier: MIT -->

# Plan Branching and Contingencies

Reference surface for the [`research-suite`](../SKILL.md) skill, read by
`/research-proposal` Phase 3 when it builds the resource / timeline / risk
register. Houses the stress test that runs one plan decision through a set of
bounded futures, the evidence labels on the numbers the plan rests on, and the
contingency record that closes each register row. Loads selectively, beside
`SKILL.md`, so the router's entry-point stays tight.

This surface adds operational detail to two existing rigor mandates — R3
(falsifiability) and R5 (preregistration discipline) — and uses R1 for the
evidence labels on plan inputs. It introduces no new R-mandate; R1–R10 is a
closed set of ten. R3 makes each register risk a refutable prediction; this
surface gives each prediction an observable trigger, a tested set of futures,
and a response whose cost and timing are known before data collection. R5
freezes the analysis plan before data; a contingency written into the frozen
plan is a planned adaptation, where the same response improvised later is a
deviation.

The procedure is qualitative. It assigns no probability, no weight, and no
default count of branches; every figure it carries is supplied by the operator
or read from a cited source (R6, `rules/authority-inquiry.md`).

## Stating the Perturbation

The stress test takes one plan decision at a time and changes one thing about
it.

- **One decision, one perturbation.** A test MUST name the plan decision under test (an aim's scope, a sample commitment, a timeline commitment, a resource commitment, or a data-access dependency) and exactly one perturbation to it.
- **State the perturbation fully.** The perturbation MUST carry the quantity that changes, the magnitude and its unit, the horizon over which it holds, and the variables coupled to it. A perturbation missing any of the four is not testable and returns to the operator through the structured-inquiry channel.
- **Bound every future.** Each branch MUST give every driver it moves a lower value, an upper value, and a horizon. A branch without bounds is a narrative, not a test.

## Building the Branch Set

- **Baseline plus distinct branches.** The set MUST contain the baseline (the plan as written, perturbation absent), and each other branch MUST differ from every other branch in the value of at least one named driver. Two branches that differ only in wording are merged. The set is the smallest one that spans the perturbation's stated bounds; this surface fixes no default count.
- **Hold shared drivers consistent.** A driver that appears in more than one branch (recruitment rate, attrition, access date, staff availability, an effect-size assumption) MUST take the same value in every branch unless the perturbation moves it or a declared coupling does. The coupling table records the driver, the driver it moves, the direction, and the basis. Coupled variables change together in every branch that moves one of them; no branch moves one alone.
- **Audit with a driver table.** Render the set as a driver-by-branch table whose cells carry the value and its evidence status (below). A cell that differs between branches with neither the perturbation nor a declared coupling as its cause is a defect, repaired before the table is used.
- **Trace knock-on effects per branch.** For each branch, record the effect on the aims, the timeline, the resource demand, the preregistration plan, and the ethics feasibility, and cite the register row each effect belongs to. A loss or attrition driver takes its baseline from the loss-rate input of the sizing under [`power-and-sample-size.md`](power-and-sample-size.md), so the plan carries one loss figure; the consequence for the analysed n is flagged to `/research-design`, and this surface computes no power.
- **Report what holds.** An action **holds** when the aim it serves still meets its SMART attributes and its feasibility assessment in every tested branch; otherwise it is **branch-dependent**, and the report names the branches that break it. Every `holds` finding is scoped to the branches tested, and a future outside that set can still break the action.

Candidate responses, including keeping the plan unchanged, are compared with
`skills/decision-matrix`; dissent among the proposal's readers goes to
`skills/perspectives`. This surface decides which futures to test and what
survives them; it does not rank responses.

Cite: Lempert, Popper & Bankes (2003), [*Shaping the Next One Hundred Years*, RAND MR-1626](https://www.rand.org/pubs/monograph_reports/MR1626.html) (choosing actions that hold across many plausible futures); Marchau, Walker, Bloemen & Popper, eds. (2019), [*Decision Making under Deep Uncertainty*](https://doi.org/10.1007/978-3-030-05252-2) (methods for plans that stay sound when the future cannot be forecast).

## Evidence Status of Plan Inputs

Every number a branch or a register row rests on carries a status, in the way a
load-bearing claim carries access and status labels under
`rules/authoritative-referencing-provenance.md` §1.

- **Status.** One of `recorded` (read from a dataset, a pilot, or a record the suite holds), `projected` (output of a stated model or a reference-class estimate), or `assumed` (set by the operator or the author on neither basis). An input with no status is `assumed`. Use the weakest status that is true.
- **Date and population.** Each status carries the date of the reading or model run and the population, setting, or reference class the figure describes. A figure carried to a different population is `assumed` for the new one until it is checked there.
- **Source locator.** Each `recorded` and `projected` input names where it came from — a suite file, a cited source resolved per R4, or an operator statement — so a reader can open it.

## Likelihood and Confidence

- **Two separate fields.** Where a register row records the likelihood of an event, the row records the confidence in the evidence behind that likelihood as a separate field. The first describes the world; the second describes what is known about it, and one never stands in for the other.
- **Not estimated is a status.** Where no source supports a figure, the likelihood field reads `not estimated`. That is a definite status under `rules/definitiveness.md`, not a hedge. A row in that state receives no placeholder number, and the register orders it by consequence and lead time.
- **Never invent a probability.** A probability enters the register only from an operator statement, a suite record, or a cited source, with the status, date, and population above. A figure drawn from a reference class names the class.
- **Normalize only across a partition.** Likelihoods are made to sum to one only over outcomes that cannot co-occur and together cover every possibility (mutually exclusive and collectively exhaustive), with a residual outcome declared where the listed outcomes leave a remainder. The branches of a stress test are chosen to span a perturbation, not to partition outcomes, so no branch carries a probability presented as its share of the whole unless the set is declared a partition and shown to be one.

Cite: Mastrandrea et al. (2011), [*The IPCC AR5 guidance note on consistent treatment of uncertainties*](https://doi.org/10.1007/s10584-011-0178-6), *Climatic Change* 108, 675-691 (confidence in the evidence and likelihood of an outcome reported as two separate measures).

## Specifying a Contingency

A register row does not end at its mitigation. A mitigation acts ahead of time
on the chance or the consequence; a contingency is the response held in
reserve until the row's trigger fires. Every register row whose consequence
reaches an aim's achievability MUST carry a contingency record with these
fields:

- **Trigger.** An observable measure and a threshold that fire the response, fixed and dated before data collection and tied to a commit or checksum of the file that holds them, as a gate is fixed before results are seen under `rules/authoritative-referencing-assurance.md` §6.
- **Responsible role.** The role that decides to execute the response. The role comes from the suite or the operator; a person's name is never invented (R6).
- **Review date.** The date the trigger measure is next read.
- **Lead time.** The time between the decision to execute and the response taking effect.
- **Cost of the backup.** What it costs to have the response ready, whether or not it is ever used, as an operator-supplied figure with its unit or the status `not supplied`. The figure reconciles to a budget line under the Phase 3 reconciliation check.
- **Residual risk.** What remains of the row after the response executes, restated with the likelihood and confidence fields above.

Three rules bind the record.

- **The trigger reads an operational measure.** A trigger measure is operational (enrolment, retention, instrument or data availability, data quality) and does not expose outcome data by arm or unmask the analysis. A response conditioned on outcome data is a sequential or adaptive design: `/research-design` specifies it and the preregistration freezes it, and it is not a contingency. A preregistered fallback test, whose trigger is a diagnostic of the analysed data, is a branch of the analysis plan that `/research-design` freezes (`analysis-discipline.md`), not a register contingency; written into the frozen plan, either one is a planned adaptation.
- **Timing check.** The review date plus the lead time MUST fall before the last date on which the response can still take effect. A contingency that fails the check is `late`, and its review date is moved earlier or its response re-scoped before the register is called complete.
- **Write it into the frozen plan.** A contingency enters the proposal's register, and, where the response changes data collection or analysis, the preregistration plan as well. A response executed under an entry in every plan it changes is a planned adaptation. The same response taken without such an entry is a deviation under R5 and is disclosed per `rules/disclosure-ledger.md`.

## Chaining Branches

- **Expand only what the decision needs.** A branch is expanded into children only when the action under test is branch-dependent in it.
- **Children are stated given the parent.** Each child describes the world given its parent's outcome and inherits the parent's driver values except those its own perturbation moves. Where probabilities exist, a path's probability follows the chain rule: each step is conditioned on every step before it. A path built from marginal probabilities is valid only when the steps are independent, and that independence is then recorded with its basis.
- **Stop rule.** Expansion stops at the first level where every child leaves the action the register carries as it was. The register row records the level reached, the reason for stopping, and the check that would reopen the expansion.
- **Evidence ceiling.** A level whose inputs all carry the status `assumed` is the last level written down: deeper branches add narrative and no evidence. The row names the cheapest check that would raise an input's status.

## Where the Record Lands

The driver table, the coupling table, the holds-or-branch-dependent report, and
each contingency record land in `proposal.md` §4 beside the register. The
stress test is a pre-commitment on the plan; the per-parameter sensitivity
sweeps in `/research-design` are run later on the design's parameters, and the
driver bounds recorded here are the plan's statement of the range those
parameters can take.

## Bindings (§0.j five-direction)

- **Drives →** ● The scenario-conditioned rows and contingency fields of the resource / timeline / risk register in `/research-proposal` Phase 3. ● The driver bounds and trigger records in `proposal.md` §4 that `/research-design` reads with the rest of the plan-of-record.
- **Satisfies →** ● The [`research-suite`](../SKILL.md) skill's reference-surface obligation (the plan-branching surface loads selectively, beside the router).
- **Established by ↑** ● [`research-suite/SKILL.md`](../SKILL.md) (the knowledge surface this reference extends). ● [`references/rigor-mandates.md`](rigor-mandates.md) (the R3 falsifiability and R5 preregistration mandates this surface operationalizes for plan-level risk).
- **Cross-bound with ↔** ↔ `commands/research-proposal.md` (the Phase 3 register this surface completes). ↔ `commands/research-design.md` (reads the plan-of-record, including the driver bounds and triggers; owns sequential and adaptive designs). ↔ [`power-and-sample-size.md`](power-and-sample-size.md) (the loss-rate input a loss driver shares). ↔ `commands/research-experiment.md` (the deviation ledger where a response taken without a register entry is disclosed). ↔ `rules/authoritative-referencing-provenance.md` (the access and status labels the input-status labels parallel). ↔ `rules/authoritative-referencing-assurance.md` (the fixed-before-results gate the trigger follows). ↔ `rules/definitiveness.md` (the `not estimated` status). ↔ `rules/disclosure-ledger.md` (deviation disclosure). ↔ `skills/decision-matrix` + `skills/perspectives` (response comparison and dissent, which this surface does not duplicate).
