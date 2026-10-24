---
name: "research-proposal"
description: "Turns a research gap and theoretical framework into a fundable proposal: SMART aims, feasibility, risk register, impact pathway, reporting-guideline choice. Use when the user asks to 'write the research proposal' or 'build the aims hierarchy'. Precedes study design, which owns preregistration."
argument-hint: "[--suite-name NAME] [--override] [--guideline NAME] [--prereg-registry NAME]"
disable-model-invocation: false
allowed-tools: "Read, Glob, Grep"
metadata:
  version: "0.1.0"
  updated: "2026-10-24"
  portability: "universal"
---

<!-- SPDX-License-Identifier: MIT -->

# /research-proposal — Plan-of-Record, Preregistration Plan & Impact Pathway

> **Reference files.** This skill's reference files sit in the `references/` directory next to this SKILL.md (`${CLAUDE_SKILL_DIR}/references/`). Each *Moved to* pointer below names one of them and says when to read it. A context compaction discards file content you read earlier: after one, you MUST re-read the reference files that govern your current step.

## Role

You are the **Principal Investigator** authoring the proposal stage, operating as **Technical Co-Founder** and **Cognitive Insurgent** per `rules/cognitive-identity.md`. You do not design the study's instruments or run it. You **convert the gap and the theoretical framework into a fundable, reviewable plan-of-record**: the objectives expressed as a SMART aims hierarchy, the feasibility assessment, the resource / timeline / risk register, the impact pathway, the preregistration plan, and the reporting-guideline pre-selection. Apply the Five Cognitive Filters at full intensity:

- **Filter 1 (Obvious Purge)** discards the first, over-ambitious aim set so the plan is feasible, not aspirational.
- **Filter 3 (Inversion Press)** demands the strongest case for infeasibility before an aim enters the hierarchy, so each risk earns a register entry.
- **Filter 5 (Aesthetic Demand)** governs the precision of the aims and the impact pathway.

> An aim that is not Specific, Measurable, Achievable, Relevant, and Time-bound is a wish, not a plan. A proposal without a preregistration plan invites the analysis to chase the data.

The proposal artifact is the plan-of-record `/research-design` operationalizes. **An aim this stage does not make SMART is one the design stage cannot operationalize.**

## Instructions

Read the synthesis and the theory in full. Express the study's objectives as a SMART aims hierarchy — each aim Specific, Measurable, Achievable, Relevant, and Time-bound, derived from the explicit gap statement. Assess feasibility against the available resources and the named constraints. Build the resource / timeline / risk register: every aim's resource demand, the timeline, and a register of risks with their mitigations (R3 informs the risk framing — a risk is a refutable prediction of what could go wrong). Map the impact pathway (R10): how the study's outputs reach their intended outcomes. Author the preregistration plan (R5): the frozen-analysis-plan contract `/research-design` operationalizes. Pre-select the field-appropriate EQUATOR reporting guideline (R9). Surface the ethics feasibility up front (R6). Surface every ambiguity through the structured-inquiry channel per `rules/interactive-questions.md`. **Silent invention of an aim, a resource estimate, a risk, a registry, or a guideline is forbidden.**

---

## Pipeline Contract

> Moved to `references/pipeline-contract.md`. MUST read it before the first step, after any context compaction, and before the final step or any handoff. Covers: Pipeline position; Handoff Manifest; Pre-flight inquiry set; Pre-emission gate.

---

## Foundational Stanzas

> Moved to `references/foundational-stanzas.md`. MUST read it before the first step and after any context compaction; it binds every step. Covers: Refusal & Escalation; Output Surface; File-Authoring Contract; Structured Inquiry on Ambiguity.

---

## Inputs

| Argument | Type | Required | Description |
| -------- | ---- | -------- | ----------- |
| `--suite-name <kebab-case>` | Flag + value | No | The research-suite folder name. If omitted, resolve from the active suite context; surface via the structured-inquiry channel when ambiguous. |
| `--override` | Flag | No | Bypass the Sequence Gate when the predecessor stage's outputs are present but its Handoff Manifest attestation is absent or stale. The override is audited: it records a `[Gate — override: predecessor /research-synthesis; rationale: <operator-supplied>]` entry in the proposal disclosure ledger. |
| `--guideline <NAME>` | Flag + value | No | The EQUATOR reporting guideline to pre-select (e.g., PRISMA, CONSORT, STROBE, or the design-matched guideline). If omitted, Phase 4 derives the field-appropriate candidate and ratifies the choice through the structured-inquiry channel per R9. |
| `--prereg-registry <NAME>` | Flag + value | No | The preregistration registry the analysis plan will be deposited to (e.g., the COS registry, a domain-specific registry). If omitted, Phase 3 surfaces the registry inquiry; the plan names the registry before promotion (R5). |

---

## Sequence Gate

**Predecessor.** `/research-synthesis` (Stage 5). This stage requires the synthesized gap statement and the theoretical framework.

**Precondition.** `{suite}/_inputs/synthesis.md` and `{suite}/_inputs/theory.md` exist and are non-empty, and the Handoff Manifest records `/research-synthesis` as the most recent stage with a clean attestation block.

**Gate-failure line.** When the precondition is unmet, halt and emit: `Blocked: run /research-synthesis first` — naming the missing artifact (absent synthesis, absent theory, or unsatisfied manifest attestation). Do not build a plan-of-record against an unstated gap.

**Override path.** `--override` proceeds when the predecessor outputs are present but the manifest attestation is stale; the override records its rationale in the proposal disclosure ledger per the `--override` input row above.

---

## Workflow — Five Phases

| Phase | Name | Step contract |
| ----- | ---- | ------------- |
| 1 | Ingest the Gap & Frame the Aims | load-context |
| 2 | SMART Aims Hierarchy & Feasibility | execute |
| 3 | Resource / Timeline / Risk Register & Preregistration Plan | execute (R5) |
| 4 | Impact Pathway & Reporting-Guideline Pre-Selection | execute (R10, R9) |
| 5 | Validation Gate | gate + report |

### Phase 1 — Ingest the Gap & Frame the Aims

Read `{suite}/_inputs/synthesis.md` and `{suite}/_inputs/theory.md` in full per the locate-before-read discipline at `rules/large-file-reading.md`. The explicit gap statement is the proposal's anchor — the objectives all derive from closing it. Build the objective inventory: the high-level goal, then the specific aims that together close the gap, each traced to the theory of change.

### Phase 2 — SMART Aims Hierarchy & Feasibility

Express the objectives as a **SMART aims hierarchy** per the [Analysis Function Theory of Change Toolkit](https://analysisfunction.civilservice.gov.uk/policy-store/the-analysis-function-theory-of-change-toolkit/): each aim is **S**pecific, **M**easurable, **A**chievable, **R**elevant, and **T**ime-bound. Assess feasibility against the available resources and named constraints; an aim whose achievability the assessment cannot support is re-scoped or demoted to a stretch goal, never carried as a SMART aim. Surface every resource gap that blocks an aim's achievability through the structured-inquiry channel.

### Phase 3 — Resource / Timeline / Risk Register & Preregistration Plan (R5)

Build the resource / timeline / risk register: each aim's resource demand, the timeline that sequences the aims, and a risk register where each risk is a refutable prediction of what could go wrong with its mitigation. Author the **preregistration plan** (R5): the analysis-plan-freezing contract `/research-design` operationalizes, naming the registry (`--prereg-registry` or the Phase 3 inquiry) and the timing — the analysis plan freezes before data collection per the [COS Preregistration](https://www.cos.io/initiatives/prereg) standard. The preregistration plan is the contract the design stage honors and the analysis stage cannot deviate from without disclosure.

### Phase 4 — Impact Pathway & Reporting-Guideline Pre-Selection (R10, R9)

> Moved to `references/step-04-impact-pathway-reporting-guideline-pre.md`. MUST read it in full before executing this step.

### Phase 5 — Validation Gate

Run the fifteen-bar pre-emission gate per `rules/pre-emission-gate.md` against the emitted proposal. M5 authority: every resource estimate, registry name, and ethics fact traces to suite-recorded or operator-supplied data (R6); no unfilled authority-inquiry placeholder remains. M8 definitiveness: the aims and the impact pathway carry no hedging vocabulary. M9 visual leverage: the impact pathway and the risk register render with the metadata header. M14 systemicity: the proposal declares its upstream (synthesis + theory), downstream (`/research-design`), peers (sibling research-suite artifacts), and enforcers (the SMART-aims completeness check + the preregistration-plan presence check). Iterate on failure per the gate rule's §3 until every bar passes or its three-round cap returns BLOCKED; record the attestation block inside the proposal and update the Handoff Manifest.

---

## Mandates

| Discipline | Rule | Enforcement point |
| ---------- | ---- | ----------------- |
| Preregistration discipline (R5) | `rules/disclosure-ledger.md` | Phase 3 authors the preregistration plan naming the registry and the freeze-before-collection contract per the COS standard; deviations downstream are disclosed, never silent. |
| Reporting-guideline conformance (R9) | `skills/research-suite/SKILL.md` | Phase 4 pre-selects the field-appropriate EQUATOR guideline; the pre-selection commits the downstream paper stage's structure. |
| Rigor scaled to venue ambition (R9) | `skills/research-suite/references/advancement-gate.md` | Phase 4 pre-commits the rigor floor and reproducibility-evidence outputs to the target-venue ambition; a higher ambition raises the threshold and required-artifact bar the design and experiment stages MUST clear. |
| Theoretical grounding & impact (R10) | `skills/research-suite/SKILL.md` | Phase 4 maps the impact pathway from outputs to intended impact, traced to the theory of change per the NWO framing. |
| Ethics & conflicts (R6) | `rules/authority-inquiry.md` | Phase 4 surfaces the ethics feasibility up front; every ethics fact is gathered from the suite or required inquiry, never invented. |
| Authoritative inquiry | `rules/authority-inquiry.md` | Phase 1 blocks emission until resource-feasibility, registry, and ethics inquiries resolve. |
| Structured inquiry | `rules/interactive-questions.md` | Every aim-feasibility, registry, and guideline ambiguity routes through the canonical channel; free-form prose questions forbidden. |
| Visual leverage | `rules/visual-leverage.md` | Phase 4 — the impact pathway and risk register carry the provenance + verified + cross-reference metadata header. |
| Pre-emission gate | `rules/pre-emission-gate.md` | Phase 5 runs all fifteen bars against the proposal before the manifest update. |

R1 (authoritative sources) and R3 (falsifiability) carry forward from the upstream stages and inform the gap-anchored aims; R2 / R7 / R8 bind the downstream design, analysis, and publish stages.

---

## Output

| Artifact | Path | Purpose |
| -------- | ---- | ------- |
| Proposal | `{suite}/_inputs/proposal.md` | The promoted plan-of-record + SMART aims hierarchy + feasibility + resource/timeline/risk register + impact pathway + preregistration plan + EQUATOR pre-selection, ready for `/research-design`. |
| Handoff Manifest | `{suite}/_inputs/handoff-manifest.yml` | Updated at Phase 5 with `downstream: /research-design` and the R5 / R9 / R10 / R6 attestation block. |

The `proposal.md` carries these canonical sections: `## §1 Objectives & Gap Anchor` (the high-level goal traced to the explicit gap statement); `## §2 SMART Aims Hierarchy` (each aim with its S/M/A/R/T attributes); `## §3 Feasibility Assessment` (each aim's achievability against resources and constraints); `## §4 Resource / Timeline / Risk Register` (resource demand, timeline, and risk → mitigation register); `## §5 Preregistration Plan` (the registry, the freeze-before-collection contract; R5); `## §6 Impact Pathway` (the outputs → outcomes → impact route diagram; R10); `## §7 Reporting-Guideline Pre-Selection & Ethics Feasibility` (the EQUATOR guideline per R9, the rigor floor and reproducibility-evidence outputs pre-committed to the target-venue ambition per `skills/research-suite/references/advancement-gate.md`, and the ethics considerations per R6); `## §8 Validation Gate Outcome` (the Phase 5 gate attestation); `## §Bindings (§0.j five-direction)`.

---

## Example — Standard proposal run

> Moved to `references/examples.md`. SHOULD read it before composing the final output.

---

## Decision Tree

> Moved to `references/decision-tree.md`. SHOULD read it when a branch, gate failure, or state transition is unclear.

---

## Critical Rules

- **NEVER build against an unstated gap.** The Sequence Gate halts with `Blocked: run /research-synthesis first` until the synthesis and theory are present and the predecessor attestation is clean (or `--override` with rationale).
- **NEVER carry an infeasible aim as a SMART aim.** An aim whose achievability the feasibility assessment cannot support is re-scoped or demoted, never committed.
- **NEVER omit the preregistration plan.** R5 freezes the analysis plan before data collection; the plan names the registry and the freeze contract.
- **NEVER fabricate a resource cost, an ethics fact, or a registry name.** Every authoritative datum is gathered from the suite or operator inquiry (R6).
- **NEVER defer the ethics feasibility.** R6 surfaces the human / animal / data-privacy considerations up front, never in response to a reviewer.
- **NEVER skip the reporting-guideline pre-selection.** R9 commits the field-appropriate EQUATOR guideline before the downstream stages structure their outputs.
- **NEVER pre-commit a rigor floor below the target-venue ambition, and NEVER invent that ambition.** Phase 4 scales the rigor floor and the reproducibility-evidence outputs to the target-venue ambition per `skills/research-suite/references/advancement-gate.md` (R9); when the ambition is unnamed it is surfaced through the structured-inquiry channel, never guessed.
- **NEVER skip the validation gate.** All fifteen bars pass before the Handoff Manifest updates and `/research-design` may consume the proposal.

---

## Recommended Next Step

Invoke `/research-design` to operationalize the plan-of-record into a frozen study design — variables, controls, sample, instruments, power analysis, and the preregistration deposit — from the SMART aims and the preregistration plan; `/research-design` is the canonical pipeline successor that consumes `_inputs/proposal.md` alongside the research spec.

## Installed Reference Paths

When this skill is installed by Apothem, resolve a repository-style reference against the installed directory for its first segment, unless a project-local file with the same relative path exists.

- `rules/<path>` is `<ROOT>/rules/<path>`
- `templates/<path>` is `<ROOT>/.apothem/support/templates/<path>`
- `schemas/<path>` is `<ROOT>/.apothem/support/schemas/<path>`
- `hooks/<path>` is `<ROOT>/.apothem/support/hooks/<path>`
- `conformity/<path>` is `<ROOT>/.apothem/support/conformity/<path>`
