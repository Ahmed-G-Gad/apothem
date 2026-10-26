<!-- SPDX-License-Identifier: MIT -->

# Study Allocation & Structure

Reference surface for the [`research-suite`](../SKILL.md) skill, loaded by
`/research-design` (Phases 2, 3, and 5). Houses the design-time rules for which
unit carries the replication, which condition each unit receives, who is
masked, how nuisance variation is laid out, how several factors are varied, and
which control conditions the design fixes. Loads selectively, beside `SKILL.md`,
so the router's entry-point stays tight.

This surface adds operational detail to four existing rigor mandates: **R2**
(the allocation schedule and run order are recorded so an independent party
reproduces them), **R5** (allocation, masking, and controls are frozen with the
analysis plan), **R6** (masking and monitoring protect human and animal
subjects), and **R7** (the analysis respects the structure the design built).
It introduces no new R-mandate; R1–R10 is a closed set of ten. A test applied
after the data exist cannot separate what the layout confounded or restore
independence the layout never had, so each decision below is made, and frozen,
before the first unit is touched.

The rules cover human, animal, field, and computational studies. Where a rule
names participants and the study has none, it binds the nearest analogue — the
instance, input, prompt, or run.

## The Experimental Unit

- **Name the unit.** The design MUST name the **experimental unit** — the entity that is assigned a condition independently of every other entity — and record it in the study design. Replication is counted in these units and in no others.
- **Repeats and subsamples are not replicates.** Repeated or subsampled measurements on one unit (several readings per participant, several steps from one run, several items cut from one source document) MUST NOT be counted as independent units. They sharpen the measurement of that unit; they add no unit (Hurlbert 1984, <https://doi.org/10.2307/1942661>).
- **Assign at the level the condition acts.** When a condition acts on a group as a whole (a classroom, a cage, a site, a machine, a batch), the group is the unit of randomisation and its members are correlated; they MUST NOT be analysed as independent.
- **Computational comparisons.** Where methods are paired by instance, the instance is the unit, and independent seeds are repetitions of a stochastic method on that unit (see [`empirical-comparison-rigor.md`](empirical-comparison-rigor.md)), not extra instances. Benchmark items drawn from one source document, template, or generator form one cluster.
- **State both units, and carry them into the test.** The design records the unit of randomisation and the unit of analysis; they MUST be the same, or the analysis MUST model the difference. The preregistered test or model MUST carry the design's blocks, strata, clusters, and repeated measures, and a plan that treats such observations as independent is not admissible. The sample-size consequence is in [`power-and-sample-size.md`](power-and-sample-size.md).

## Allocation

- **Allocate by a stated procedure.** Where separate units are assigned to conditions, the design MUST fix the procedure and its rationale:
  - *Simple randomisation* fits only when a chance imbalance in arm size or in a known prognostic factor cannot change the comparison.
  - *Permuted blocks* hold arm sizes level while units enrol one after another. The block sizes are recorded; where the assignment is not fully concealed, the block size SHOULD vary and be withheld from the enrolling party, because a fixed visible block lets its last assignments be predicted.
  - *Stratified randomisation* randomises within strata of a few strong prognostic factors. Keep the strata few against the sample size, because partly filled strata forfeit the balance they were meant to buy.
  - *Minimization* balances several factors in a small sample. A random element MUST remain so the next assignment is not fully predictable, and the minimization factors MUST enter the analysis.
  - *Cluster allocation* assigns whole groups, per the unit rules above.
- **Generate the schedule from a recorded seed before the first enrolment.** The seed, the generating tool and its version, the block sizes, and the strata MUST be recorded so an independent party regenerates the identical schedule (R2). The preregistration fixes the procedure and its structure. Where concealment applies, the seed and the generated schedule sit in a sealed allocation record kept by someone independent of enrolment until unmasking.
- **Conceal the upcoming assignment from whoever enrols.** When units enter one after another and the person deciding whether a unit enters can learn or infer its assignment, the design MUST hide the sequence from that person until the unit is irrevocably enrolled, through central allocation or an equivalent mechanism the enrolling party cannot open. Concealment protects the assignment before it happens; masking (below) protects the outcome after. When every unit is in hand before any is assigned, concealment does not apply and the design says so.
- **Check balance, describe it, never redraw it.** Before outcomes are examined, the arms are compared on the baseline characteristics the preregistration names, descriptively: a significance test of baseline difference between arms assigned by chance tests a null that holds by construction (Moher et al. 2010, <https://doi.org/10.1136/bmj.c869>). An imbalance is handled by the preregistered adjustment set. A schedule redrawn because its balance looks unwelcome is a disclosed deviation (R5). A design that wants constrained balance preregisters the balance criterion and the rule that applies it, and the analysis accounts for that constraint.

## Masking

Masking concerns who knows the assignment while the study runs. It is unrelated to the author-and-institution anonymization of [`blinding-and-disclosure.md`](blinding-and-disclosure.md).

- **State who knows what.** For participants, those delivering the condition, outcome assessors, and the analyst, the design MUST state whether each knows the assignment. Where one does, it records why masking is infeasible and what limits the resulting bias (R6 where the units are human or animal).
- **Mask the assessor first.** When the outcome rests on judgment — a clinical rating, a coded behaviour, a grade given to a system's output — the assessor MUST be masked to the condition whenever masking is feasible. An objective outcome needs no assessor masking, and the design says so.
- **Judging system outputs.** When people or model judges rate the outputs of different systems, the rating design MUST strip system identity from what the judge sees, randomise the order and position of the outputs, and keep the mapping from output to system out of the judge's reach. A judge that is one of the compared systems, or shares a lineage with one, SHOULD be avoided and is disclosed as a limitation when unavoidable.
- **Mask the analyst by plan.** Where arm labels can stay coded until the frozen plan has run, the design says so; otherwise the frozen plan stands in for analyst masking, and any departure from it is a disclosed deviation.
- **Produce what the guideline asks.** The reporting guideline selected under R9 (CONSORT for trials, ARRIVE for animal studies) asks for sequence generation, concealment, and masking; the design produces each one.

## Nuisance Factors, Layout, and Run Order

- **Enumerate the nuisance factors.** The design MUST list every source of variation that is not the factor under study and can shift the outcome: batch, session or day, operator, instrument or reagent lot, site, position within a carrier (a well on a plate), time of day, and processing order. Computational work adds the host machine, co-tenant load, library build, and clock.
- **Block, randomise, or hold constant — for each.** The design states, per factor, whether it is blocked (each level under every condition, balanced), randomised across conditions, or held constant. A nuisance factor aligned with a condition — one operator running only the control arm, one machine running only one method, all treated units processed before all untreated ones — cannot be separated from the condition effect, and the design MUST NOT contain one.
- **Randomise or interleave the run order.** Units and conditions MUST run in an order randomised or interleaved across conditions, not condition by condition, so drift in an instrument, environment, or hardware spreads across conditions instead of aligning with one. For a computational comparison, interleave the methods across machines and time and block on machine; the isolation and headroom of [`compute-utilization.md`](compute-utilization.md) keep each run clean, and interleaving keeps drift from aligning with a method. The realised order and host are logged per run.
- **Carry reference samples where the field does.** Where a measurement drifts between batches and the field uses a reference or calibration sample, one MUST be included in every batch and its result kept, so a batch shift is estimated and not assumed away.
- **Layout and adjustment are two controls.** The layout above prevents a confound from forming; the DAG-derived adjustment set of `/research-design` Phase 3 corrects for measured covariates afterwards. A design needs both.

## Within-Unit Designs

- **Fix the order structure.** Where each unit meets more than one condition and the order can be varied, the design MUST counterbalance it — each condition in each position the same number of times through a balanced set of sequences, units assigned to sequences at random — and the preregistered model MUST test for order and period effects. Where the order is fixed by the question (before and after, a follow-up series), time enters the model as a factor and any time trend is recorded as a threat to validity.
- **Plan for carry-over.** Where a condition can leave a residue (learning, fatigue, adaptation, retained state, a lingering agent), the design inserts a washout long enough for the residue to clear, justified from the synthesis or a pilot, or replaces the within-unit design with a between-unit one.
- **Repeated observations are correlated.** The preregistered model MUST carry the unit, as a random effect or through a paired within-unit test; treating observations on one unit as independent misstates the error.
- **Hard-to-change factors restrict the randomisation.** A factor that is costly to reset between runs cannot be randomised run by run. The design treats each setting of it as a group of runs (a split-plot structure), and the analysis carries the extra level of error that structure creates.

## Multi-Factor Designs

- **Vary factors jointly when they can interact.** One-factor-at-a-time variation estimates each factor only at the baseline setting of the others and cannot estimate an interaction. Where the synthesis or a mechanism makes an interaction plausible, the design MUST cross the factors in question in a factorial layout, which also estimates each main effect from every run.
- **Screen, then refine.** With many candidate factors and a budget that rules out the full crossing, the design screens with a fractional layout and states which effects are aliased with which; a layout whose aliasing is unstated cannot be read. It then refines the survivors with a crossed layout, a response-surface layout where curvature is expected, or a space-filling layout where the system is a simulator with many continuous inputs. The rule that moves a factor from screen to refinement is fixed before the screen runs.
- **Ablations and sweeps are one-at-a-time by construction.** The one-component-per-variant ablation rule and the per-parameter sweeps of `/research-design` Phase 3 keep their form and cannot show interactions. Where components or parameters are suspected to interact, the design adds a joint layout over the suspect set — a crossed ablation over the suspected components, a joint grid or space-filling sample over the interacting parameters — and preregisters which interaction is claimed.
- **A searched interaction is confirmed, not read off the search.** An interaction found by a parameter search, including the loop of [`autonomous-experiment-loop.md`](autonomous-experiment-loop.md), is confirmed by a preregistered joint layout before it is claimed.
- Layout catalogues (Latin and Williams squares, resolution tables, central-composite geometry) and design-matrix generation are textbook content; the design names the layout and cites the text it follows (for example Montgomery, *Design and Analysis of Experiments*, Wiley).

## Control Conditions

`/research-design` Phase 3 *controls* (covariates and held-constant factors) are distinct from the control *conditions* planned here.

- **Choose each comparator for what it isolates.** The design states what every control condition isolates. A concurrent control — same period, population, and procedure — is the default. A historical or external comparator replaces it only when a concurrent one is infeasible, and the design records the drift in population, procedure, or measurement since as an internal-validity threat.
- **Separate the active ingredient from its delivery.** Where delivering the condition can itself change the outcome — a carrier, a sham procedure, a placebo, setup overhead, a prompt wrapper or harness around a model — the design MUST include a control that delivers everything except the active ingredient (a vehicle, sham, placebo, or inert wrapper), so no effect of the delivery is attributed to the ingredient.
- **Plan the positive and negative controls here.** A positive control (a condition expected to produce the effect) shows the measurement can detect it; a negative control (a condition expected to produce none) shows the apparatus does not manufacture it. The design names each control, the outcome it expects, and the criterion by which a failing control invalidates the run. The preregistration freezes them, and `/research-experiment` executes the controls the preregistration fixed; a control added after the freeze is a disclosed deviation (R5), because the controls decide whether a result is trusted.
- **A control arm is an arm.** It is sized, allocated, and masked like any other.

## What the Preregistration Carries

The frozen preregistration MUST record, where the design has the element: the experimental unit, the unit of analysis, and the test or model that carries the blocks, strata, clusters, and repeated measures; the allocation procedure with its strata and block structure, and the concealment mechanism or the statement that concealment does not apply; who is masked, how masking is kept, and the unmasking rule; the nuisance-factor plan and the run-order rule; the order structure and washout of a within-unit design; the joint layouts planned for suspected interactions and the screen-to-refinement rule; and every control condition with its expected outcome and the criterion by which it invalidates a run.

## Bindings (§0.j five-direction)

- **Drives →** ● The unit, allocation, masking, nuisance-factor, run-order, and control-condition decisions in `/research-design` (Phases 2, 3, and 5) and the preregistration content they freeze. ● The execution of the schedule, the run order, and the preregistered controls in `/research-experiment` (Phase 2). ● The structure-respecting test family in `/research-analysis` (Phase 2).
- **Satisfies →** ● The [`research-suite`](../SKILL.md) skill's reference-surface obligation (the allocation-and-structure rules load selectively, beside the router).
- **Established by ↑** ● [`research-suite/SKILL.md`](../SKILL.md) (the knowledge surface this reference extends). ● [`references/rigor-mandates.md`](rigor-mandates.md) (the R2, R5, R6, and R7 mandates this surface operationalizes).
- **Cross-bound with ↔** ↔ [`references/power-and-sample-size.md`](power-and-sample-size.md) (the sizing that follows from the unit, allocation ratio, and clustering fixed here). ↔ [`references/compute-utilization.md`](compute-utilization.md) (isolation and headroom per run; this surface adds interleaving across machine and time). ↔ [`references/experiment-program-scaffold.md`](experiment-program-scaffold.md) (the ablation and sensitivity sub-stages this surface extends with joint layouts). ↔ [`references/empirical-comparison-rigor.md`](empirical-comparison-rigor.md) (the repetition regime and the paired-by-instance unit). ↔ [`references/blinding-and-disclosure.md`](blinding-and-disclosure.md) (peer-review anonymization, distinct from the masking defined here). ↔ [`references/autonomous-experiment-loop.md`](autonomous-experiment-loop.md) (the parameter search whose interactions a joint layout confirms).
