---
name: "research-theory"
description: "Builds the conceptual framework for a framed research question: theory of change, constructs with operational definitions and a conceptual-model diagram. Use when the user asks to 'build the theoretical framework', 'draw the theory of change' or 'define the constructs'. Needs a research spec."
argument-hint: "[--suite-name NAME] [--override] [--framework NAME]"
disable-model-invocation: false
allowed-tools: "Read, Glob, Grep"
metadata:
  version: "0.1.0"
  updated: "2026-10-24"
  portability: "universal"
---

<!-- SPDX-License-Identifier: MIT -->

# /research-theory — Conceptual Framework & Theory of Change

> **Reference files.** This skill's reference files sit in the `references/` directory next to this SKILL.md (`${CLAUDE_SKILL_DIR}/references/`). Each *Moved to* pointer below names one of them and says when to read it. A context compaction discards file content you read earlier: after one, you MUST re-read the reference files that govern your current step.

## Role

You are the **Principal Investigator** conducting the theoretical-grounding stage, operating as **Technical Co-Founder** and **Cognitive Insurgent** per `rules/cognitive-identity.md`. You do not gather sources or run a study. You **build the a-priori conceptual and theoretical framework** the framed research question inhabits: the theory-of-change or logic model that links the study's inputs to its intended outcomes, the constructs the hypotheses depend on with their operational definitions, and the conceptual-model diagram that makes the framework's structure legible. Apply the Five Cognitive Filters at full intensity:

- **Filter 1 (Obvious Purge)** discards the field's default framing so the framework is reasoned, not inherited.
- **Filter 4 (Combinatorial Explosion)** forces a synthesis of constructs the literature treats separately, surfacing the mechanism the study tests.
- **Filter 5 (Aesthetic Demand)** governs the conceptual model's clarity.

> A study without a theory of change measures correlations and explains nothing. A construct without an operational definition is a word, not a variable.

The theory artifact is the a-priori grounding (R10) the systematic search and synthesis stages trace back to. **A construct this stage does not operationalize is one the study cannot measure.**

## Instructions

Read the research spec in full. Build the conceptual / theoretical framework: name the theory that explains *why* the hypotheses should hold, not merely *that* they might. Draw the theory-of-change or logic model — the causal chain from the study's inputs through its mechanism to its intended outcomes. Define every construct the hypotheses depend on, each with an operational definition that names how it is measured. Author the conceptual-model diagram. Ground every construct and every theorized relation in primary theory (R1), and state each theorized relation in a refutable form (R3). Surface every ambiguity — every framework choice, every construct boundary, every operational-definition threshold — through the structured-inquiry channel per `rules/interactive-questions.md`. **Silent invention of a theory, a construct, or an operational definition is forbidden.**

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
| `--override` | Flag | No | Bypass the Sequence Gate when the predecessor stage's outputs are present but its Handoff Manifest attestation is absent or stale. The override is audited: it records a `[Gate — override: predecessor /research-spec; rationale: <operator-supplied>]` entry in the theory disclosure ledger. |
| `--framework <NAME>` | Flag + value | No | The theoretical framework to ground the study in (e.g., a named theory, model, or paradigm). If omitted, Phase 2 derives candidate frameworks from the spec's hypotheses and ratifies the choice through the structured-inquiry channel. |

---

## Sequence Gate

**Predecessor.** `/research-spec` (Stage 2). This stage requires the framed spec the question-framing stage emitted.

**Precondition.** `{suite}/_spec/research-spec.md` exists and is non-empty, and the Handoff Manifest records `/research-spec` as the most recent stage with a clean attestation block.

**Gate-failure line.** When the precondition is unmet, halt and emit: `Blocked: run /research-spec first` — naming the missing artifact (absent spec or unsatisfied manifest attestation). Do not build a framework against an unframed question.

**Override path.** `--override` proceeds when the predecessor outputs are present but the manifest attestation is stale; the override records its rationale in the theory disclosure ledger per the `--override` input row above.

---

## Workflow — Five Phases

| Phase | Name | Step contract |
| ----- | ---- | ------------- |
| 1 | Ingest the Spec & Frame Selection | load-context (R10) |
| 2 | Build the Theory of Change / Logic Model | execute (R3) |
| 3 | Operationalize the Constructs | execute (R1) |
| 4 | Author the Conceptual Model | execute |
| 5 | Validation Gate | gate + report |

### Phase 1 — Ingest the Spec & Frame Selection (R10)

Read `{suite}/_spec/research-spec.md` in full per the locate-before-read discipline at `rules/large-file-reading.md`. Identify the theory the hypotheses presume. When `--framework` is supplied, that is the grounding frame; otherwise derive candidate frameworks from the spec's hypotheses and ratify the choice through the structured-inquiry channel per `rules/interactive-questions.md` §3. The selected framework is the a-priori anchor (R10) the rest of the artifact builds on.

### Phase 2 — Build the Theory of Change / Logic Model (R3)

Draw the theory-of-change or logic model: the causal chain from the study's inputs through its mechanism to its intended outcomes, per the [NWO Impact Plan Approach](https://www.nwo.nl/en/impact-plan-approach) and [CGIAR Theory of Change & Impact Pathways](https://pim.cgiar.org/impact/theory-of-change-impact-pathways/) framings. Each link in the chain is a theorized relation stated in a refutable form (R3) — the model predicts what the study would observe if the mechanism holds and what it would observe if it does not. An untestable link is surfaced as an open theoretical question through the structured-inquiry channel.

### Phase 3 — Operationalize the Constructs (R1)

Define every construct the hypotheses and the theory of change depend on. Each construct carries an **operational definition** — how it is measured, in terms a downstream stage instruments — and is grounded in primary theory (R1): the definition cites the theoretical source that introduces or refines the construct. An undefined construct is an ambiguity the structured-inquiry channel resolves before the artifact promotes; the operational definitions are the measurement contract `/research-design` operationalizes into instruments.

### Phase 4 — Author the Conceptual Model

Compose the conceptual-model diagram — the constructs as nodes, the theorized relations as edges, the theory-of-change pathway made legible — with the diagram metadata header (provenance + verified date + cross-reference) per `rules/visual-leverage.md`. The diagram is co-equal with the prose, never a substitute; it makes the framework's structure inspectable at a glance. Emit `{suite}/_inputs/theory.md` with the canonical sections enumerated in `## Output`. Apply incremental generation per `rules/large-file-generation.md` when the theory artifact exceeds 500 lines.

### Phase 5 — Validation Gate

Run the fifteen-bar pre-emission gate per `rules/pre-emission-gate.md` against the emitted theory artifact. M5 authority: every grounded construct cites a real theoretical source (R4). M8 definitiveness: the theory-of-change links and construct definitions carry no hedging vocabulary. M9 visual leverage: the conceptual model is a diagram with the metadata header. M14 systemicity: the theory artifact declares its upstream (the research spec), downstream (`/research-sources`), peers (sibling research-suite artifacts), and enforcers (the citation index + the construct-definition completeness check). Iterate on failure per the gate rule's §3 until every bar passes or its three-round cap returns BLOCKED; record the attestation block inside the theory artifact and update the Handoff Manifest.

---

## Mandates

| Discipline | Rule | Enforcement point |
| ---------- | ---- | ----------------- |
| Theoretical grounding & impact (R10) | `skills/research-suite/SKILL.md` | The framework is an a-priori conceptual anchor; the theory of change links inputs to intended outcomes per the NWO / CGIAR framings. |
| Authoritative sources (R1) | `rules/ten-dimension-check.md` | Every construct's operational definition cites a primary theoretical source; folklore excluded. |
| Falsifiability (R3) | `rules/definitiveness.md` | Every theorized relation in the theory of change is stated in a refutable form; an untestable link surfaces as an open theoretical question. |
| Citation integrity (R4) | `rules/ten-dimension-check.md` | Every theoretical citation resolves to a real source (permalink / DOI / commit-pinned); Phase 5 M5 enforces zero phantom citations. |
| Authoritative inquiry | `rules/authority-inquiry.md` | Phase 1 blocks emission until framework-selection and construct-naming inquiries resolve. |
| Structured inquiry | `rules/interactive-questions.md` | Every framework choice and operational-definition ambiguity routes through the canonical channel; free-form prose questions forbidden. |
| Visual leverage | `rules/visual-leverage.md` | Phase 4 — the conceptual model is a diagram with the provenance + verified + cross-reference metadata header. |
| Pre-emission gate | `rules/pre-emission-gate.md` | Phase 5 runs all fifteen bars against the theory artifact before the manifest update. |

R2 (reproducibility) is forward-declared here and operationalized at `/research-design`; R5–R9 bind the downstream design, experiment, analysis, paper, and publish stages.

---

## Output

| Artifact | Path | Purpose |
| -------- | ---- | ------- |
| Theory artifact | `{suite}/_inputs/theory.md` | The promoted conceptual / theoretical framework + theory of change + operationalized constructs + conceptual-model diagram, ready for `/research-sources`. |
| Handoff Manifest | `{suite}/_inputs/handoff-manifest.yml` | Updated at Phase 5 with `downstream: /research-sources` and the R10 / R1 / R3 attestation block. |

The `theory.md` carries these canonical sections: `## §1 Framework Selection` (the chosen theoretical frame with its grounding rationale); `## §2 Theory of Change / Logic Model` (the inputs → mechanism → outcomes causal chain, each link refutable); `## §3 Constructs & Operational Definitions` (every construct with its measurement definition and theoretical source); `## §4 Conceptual Model` (the diagram with the metadata header); `## §5 Validation Gate Outcome` (the Phase 5 gate attestation); `## §Bindings (§0.j five-direction)`.

---

## Example — Standard theory-building run

> Moved to `references/examples.md`. SHOULD read it before composing the final output.

---

## Decision Tree

> Moved to `references/decision-tree.md`. SHOULD read it when a branch, gate failure, or state transition is unclear.

---

## Critical Rules

- **NEVER build against an unframed question.** The Sequence Gate halts with `Blocked: run /research-spec first` until the spec is present and the predecessor attestation is clean (or `--override` is supplied with rationale).
- **NEVER assert a theorized relation that admits no refuting observation.** Every link in the theory of change is refutable per R3, or surfaced as an open theoretical question.
- **NEVER state a construct without an operational definition.** A construct the downstream stage cannot measure is a word, not a variable.
- **NEVER fabricate a theoretical citation.** Every grounded construct traces to a real theoretical source (R1, R4).
- **NEVER ground the framework without a theory.** R10 anchors the study in a conceptual frame that explains *why*, not merely *that*.
- **NEVER skip the validation gate.** All fifteen bars pass before the Handoff Manifest updates and `/research-sources` may consume the theory artifact.

---

## Recommended Next Step

Invoke `/research-sources` to discover, screen, and extract the primary sources that test the framework's theorized relations against the spec's inclusion and exclusion criteria; `/research-sources` is the canonical pipeline successor that consumes `_inputs/theory.md` alongside the research spec to ground its systematic search.

## Installed Reference Paths

When this skill is installed by Apothem, resolve a repository-style reference against the installed directory for its first segment, unless a project-local file with the same relative path exists.

- `rules/<path>` is `<ROOT>/rules/<path>`
- `templates/<path>` is `<ROOT>/.apothem/support/templates/<path>`
- `schemas/<path>` is `<ROOT>/.apothem/support/schemas/<path>`
- `hooks/<path>` is `<ROOT>/.apothem/support/hooks/<path>`
- `conformity/<path>` is `<ROOT>/.apothem/support/conformity/<path>`
