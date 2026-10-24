<!-- SPDX-License-Identifier: MIT -->

# Thirteen-Stage Research Lifecycle

Reference surface for the [`research-suite`](../SKILL.md) skill. Houses the
thirteen-stage lifecycle and the per-stage invoking-surfaces table the
`/research` pipeline stages chain against. Loads selectively, beside
`SKILL.md`, so the router's entry-point stays tight.

The `/research` pipeline stages chain through thirteen stages by Sequence
Gates and Handoff Manifests, mirroring the `/plan` pipeline. The canonical
chain is `/research-ideate → /research-spec → /research-theory →
/research-sources → /research-synthesis → /research-proposal →
/research-design → /research-experiment → /research-analysis → /research-paper
→ /research-review → /research-publish → /research-disseminate`. Resolving
this surface yields the lifecycle in one fixed order — the same cold
invocation always yields the same load:

1. `/research-ideate` — problem space → `_inputs/ideation.md` (problem formulation, question generation, scan for invalidated prior hypotheses; the lifecycle Plan stage per the Princeton research-lifecycle and NNLM data-lifecycle framings).
2. `/research-spec` — raw question → `_spec/research-spec.md` (falsifiable hypotheses, scope, criteria, metrics).
3. `/research-theory` — spec → `_inputs/theory.md` (conceptual / theoretical framework, theory-of-change, defined constructs and their relations per R10).
4. `/research-sources` — spec + theory → `sources/<id>.md` + `_inputs/source-ledger.md` (discovery via `research-scout`, extraction via the `multi-source-research` skill).
5. `/research-synthesis` — ledger + sources → `_inputs/synthesis.md` (SOTA map, gap statement; `fact-checker`-verified; uses the `source-synthesis` skill).
6. `/research-proposal` — synthesis + theory → `_inputs/proposal.md` (objectives → plan-of-record with SMART aims, feasibility, resource and risk plan, impact pathway per R10, preregistration plan per R5, EQUATOR guideline pre-selection per R9).
7. `/research-design` — proposal + spec → `_inputs/study-design.md` + `_inputs/preregistration.md` (frozen plan per R5).
8. `/research-experiment` — design + preregistration → `_outputs/experiment-log.md` + raw data + `_outputs/reproducibility-manifest.md` (R2).
9. `/research-analysis` — raw data + preregistration → `_outputs/analysis.md` + figures/tables (effect sizes + CIs per R7; deviations disclosed).
10. `/research-paper` — synthesis + design + analysis → the paper deliverable at a host-natural location (every citation verified per R4; reporting-guideline conformance per R9).
11. `/research-review` — paper → `_outputs/review-report.md` (adversarial, refute-by-default reviewer scorecard + severity-triaged revisions).
12. `/research-publish` — paper + review report → venue-formatted submission package + `_outputs/publication-record.md` + archival/DOI plan (FAIR deposit per R8).
13. `/research-disseminate` — publication record → `_outputs/dissemination-plan.md` (post-acceptance dissemination and impact, preprint, archival, altmetrics tracking, rebuttal / revision loop, registered-report stage-2 per R8).

Each stage's surface anchor (its Step-0 consumption point in the Invoking
Surfaces table below) resolves against this skill's `research-template.md` by
path. A cold stage that cannot resolve this skill STOPs per the Resolution &
Recovery clause; it does not proceed on assumed context.

## Invoking Surfaces

The thirteen `/research` pipeline stages consume this skill's
`research-template.md` by direct path resolution:

| Command | Consumption point | What the command reads |
|---------|-------------------|------------------------|
| `/research-ideate` | Step 0 (surface anchor) | R3 / R10 mandates governing problem formulation, question generation, and invalidated-prior-hypothesis scanning |
| `/research-spec` | Step 0 (surface anchor) | R1 / R3 / R4 mandates governing question framing and falsifiable-hypothesis authoring |
| `/research-theory` | Step 0 (surface anchor) | R10 conceptual-framework / theory-of-change / construct-definition criteria |
| `/research-sources` | Step 0 (surface anchor) | R1 / R4 source-authority and citation-integrity criteria + source-ledger skeleton; operationalizing detail: [`references/comparator-provenance.md`](comparator-provenance.md) (executed-comparator provenance ledger) |
| `/research-synthesis` | Step 0 (surface anchor) | R1 / R4 adversarial-verification floor + synthesis / gap-statement structure |
| `/research-proposal` | Step 0 (surface anchor) | R5 / R9 / R10 mandates governing objectives, SMART aims, impact pathway, preregistration plan, and EQUATOR pre-selection |
| `/research-design` | Step 0 (surface anchor) | R3 / R5 / R7 mandates governing study design, preregistration, and power analysis; operationalizing detail: [`references/experiment-program-scaffold.md`](experiment-program-scaffold.md), [`references/empirical-comparison-rigor.md`](empirical-comparison-rigor.md), [`references/compute-utilization.md`](compute-utilization.md), [`references/advancement-gate.md`](advancement-gate.md) |
| `/research-experiment` | Step 0 (surface anchor) | R2 / R6 mandates governing reproducibility-manifest and ethics declarations; operationalizing detail: [`references/experiment-program-scaffold.md`](experiment-program-scaffold.md), [`references/compute-utilization.md`](compute-utilization.md), [`references/empirical-comparison-rigor.md`](empirical-comparison-rigor.md), [`references/autonomous-experiment-loop.md`](autonomous-experiment-loop.md) |
| `/research-analysis` | Step 0 (surface anchor) | R5 / R7 mandates governing preregistered analysis and statistical rigor; operationalizing detail: [`references/empirical-comparison-rigor.md`](empirical-comparison-rigor.md), [`references/advancement-gate.md`](advancement-gate.md) |
| `/research-paper` | Step 0 (surface anchor) | R1 / R4 / R9 citation-verification and reporting-guideline floor + paper-section structure; operationalizing detail: [`references/blinding-and-disclosure.md`](blinding-and-disclosure.md), [`references/advancement-gate.md`](advancement-gate.md) |
| `/research-review` | Step 0 (surface anchor) | R1–R10 reviewer-scorecard rubric + severity-triage convention; operationalizing detail: [`references/advancement-gate.md`](advancement-gate.md), [`references/empirical-comparison-rigor.md`](empirical-comparison-rigor.md), [`references/blinding-and-disclosure.md`](blinding-and-disclosure.md) |
| `/research-publish` | Step 0 (surface anchor) | R4 / R6 / R8 mandates governing the submission package, FAIR deposit, and archival/DOI plan; operationalizing detail: [`references/blinding-and-disclosure.md`](blinding-and-disclosure.md) |
| `/research-disseminate` | Step 0 (surface anchor) | R8 / R10 mandates governing dissemination, impact pathway, altmetrics, and registered-report stage-2; operationalizing detail: [`references/blinding-and-disclosure.md`](blinding-and-disclosure.md) |

No agent invokes the skill directly; the `/research` pipeline commands are the
canonical consumption surface.

## Bindings (§0.j five-direction)

- **Drives →** ● Every `/research` stage's lifecycle-order resolution and Handoff-Manifest chaining. ● Every stage's Step-0 surface-anchor consumption point.
- **Satisfies →** ● The [`research-suite`](../SKILL.md) skill's reference-surface obligation (the lifecycle + invoking-surfaces tables load selectively, beside the router).
- **Established by ↑** ● [`research-suite/SKILL.md`](../SKILL.md) (the knowledge surface this reference extends).
- **Cross-bound with ↔** ↔ `commands/research-ideate.md` … `commands/research-disseminate.md` (the thirteen consumer commands whose Step-0 anchors resolve this lifecycle). ↔ `agents/research-scout.md` + `agents/fact-checker.md` (the discovery / verification surfaces the stages dispatch). ↔ [`references/empirical-comparison-rigor.md`](empirical-comparison-rigor.md) + [`references/comparator-provenance.md`](comparator-provenance.md) + [`references/experiment-program-scaffold.md`](experiment-program-scaffold.md) + [`references/compute-utilization.md`](compute-utilization.md) + [`references/autonomous-experiment-loop.md`](autonomous-experiment-loop.md) + [`references/advancement-gate.md`](advancement-gate.md) + [`references/blinding-and-disclosure.md`](blinding-and-disclosure.md) (the operationalizing detail surfaces the empirical stages load at Step 0).
