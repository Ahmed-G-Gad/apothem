<!-- SPDX-License-Identifier: MIT -->

# Research-Suite Directory Structure

Reference surface for the [`research-suite`](../SKILL.md) skill. Houses the
research-suite directory-structure table the `/research` pipeline stages
resolve when they need to know where each artifact lands. Loads selectively,
beside `SKILL.md`, so the router's entry-point stays tight.

Research-suite **working state** reuses the plan-suite scaffold under
`<project-root>/.apothem/plans/{suite}/` per the suite-locality invariant at
`rules/context-management.md` §2.6.1, with research-specific subdirectories.
**Deliverables** — the paper, raw data, figures and tables, code — land at
**host-natural locations** discovered per `rules/host-discovery.md`, never
inside `.apothem/plans/`.

| Surface | Location | Holds |
|---------|----------|-------|
| Ideation | `{suite}/_inputs/ideation.md` | Problem formulation, candidate questions, invalidated-prior-hypothesis scan |
| Research spec | `{suite}/_spec/research-spec.md` | Question, falsifiable hypotheses, scope, inclusion/exclusion criteria, success metrics, glossary |
| Theory framework | `{suite}/_inputs/theory.md` | Conceptual / theoretical framework, theory-of-change, defined constructs and relations (R10) |
| Per-source extractions | `{suite}/sources/<id>.md` | One file per source: extracted claims, provenance, authority/recency/relevance score |
| Source ledger | `{suite}/_inputs/source-ledger.md` | Ranked, screened, deduplicated source index with citation keys |
| Synthesis | `{suite}/_inputs/synthesis.md` | SOTA map, literature matrix, explicit gap statement |
| Proposal | `{suite}/_inputs/proposal.md` | Objectives → plan-of-record, SMART aims, feasibility, resource/risk plan, impact pathway (R10), preregistration plan (R5), EQUATOR pre-selection (R9) |
| Study design | `{suite}/_inputs/study-design.md` | Operationalized predictions, variables, controls, sample, instruments, power analysis, threats-to-validity |
| Preregistration | `{suite}/_inputs/preregistration.md` | Frozen analysis plan fixed before data collection (R5) |
| Handoff Manifest | `{suite}/_inputs/handoff-manifest.yml` | Stage-to-stage chain per `src/apothem/schemas/handoff-manifest.yaml` |
| Experiment log | `{suite}/_outputs/experiment-log.md` + `{suite}/_outputs/reproducibility-manifest.md` | Run log + env/seed/protocol/version pins (R2) |
| Experiment program | `{suite}/_outputs/<deliverable>-program/` (`setup/` `pilot/` `comparison/` `ablation/` `sensitivity/` `statistics/`) | Per-deliverable empirical-program working records; one program subtree per deliverable — see [`experiment-program-scaffold.md`](experiment-program-scaffold.md). Raw per-run data + figures land host-natural (see the bottom row) |
| Analysis | `{suite}/_outputs/analysis.md` | Preregistered tests, effect sizes + CIs, robustness checks, disclosed deviations |
| Review report | `{suite}/_outputs/review-report.md` | Reviewer scorecard + severity-triaged required-revision list |
| Publication record | `{suite}/_outputs/publication-record.md` | Submission package manifest, archival/DOI plan, submission checklist |
| Dissemination plan | `{suite}/_outputs/dissemination-plan.md` | Post-acceptance dissemination and impact pathway, preprint, archival, altmetrics tracking, rebuttal / revision loop, registered-report stage-2 (R8/R10) |
| Paper · data · figures · code | host-natural (`paper/`, `data/`, `analysis/figures/`, …) | The published deliverables, discovered per host-discovery |

The underscore-prefixed directories (`_spec/`, `_inputs/`, `_outputs/`) carry
the closed-purpose semantics of `rules/context-management-scratch.md`;
`sources/` is a research-specific working subdirectory holding per-source
extraction state. Working state is gitignored per the canonical `.gitignore`
snippet; deliverables follow the host's tracking conventions.

## Bindings (§0.j five-direction)

- **Drives →** ● Every `/research` stage's artifact placement decision (the table is the canonical layout map).
- **Satisfies →** ● The [`research-suite`](../SKILL.md) skill's reference-surface obligation (the directory map loads selectively, beside the router).
- **Established by ↑** ● [`research-suite/SKILL.md`](../SKILL.md) (the knowledge surface this reference extends).
- **Cross-bound with ↔** ↔ `rules/context-management.md` §2.6.1 (suite-locality invariant). ↔ `rules/context-management-scratch.md` (closed-purpose `_spec/` / `_inputs/` / `_outputs/` semantics). ↔ `rules/host-discovery.md` (host-natural deliverable locations). ↔ [`experiment-program-scaffold.md`](experiment-program-scaffold.md) + [`compute-utilization.md`](compute-utilization.md) (the experiment-program subtree and its execution plan).
