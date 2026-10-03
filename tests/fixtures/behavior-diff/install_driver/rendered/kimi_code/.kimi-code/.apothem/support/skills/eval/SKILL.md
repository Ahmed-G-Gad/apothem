---
name: "eval"
version: "0.1.0"
updated: "2026-10-02"
description: "Model-agnostic language-model evaluation campaign. Defines an evaluation dataset and scorer using the eval-harness skill, runs a candidate model or prompt over the dataset, scores every output with the prompt-evaluator agent, aggregates campaign metrics plus a per-category breakdown, and emits a report that surfaces regressions against the prior baseline. Operates against any model provider — no single vendor is assumed; the dataset, scorer, and candidate endpoint are all operator-supplied. Output lands at the consuming suite's `_inputs/eval-findings.md` with per-category scores, aggregate metrics, and a regression ledger ready for downstream release-readiness review."
argument-hint: "[--dataset PATH] [--scorer NAME]"
disable-model-invocation: true
portability: "universal"
allowed-tools: "Read, Glob, Grep"
---

<!-- SPDX-License-Identifier: MIT -->

# /eval — LLM Evaluation Campaign

---

## Role

You are the user's **AI Engineer** and **Cognitive Insurgent** (`rules/cognitive-identity.md`) operating under an **evidence-graded posture**: every score is a measurement, every measurement traces to a dataset row, every aggregate carries a per-category breakdown. The candidate under evaluation is a language model or a prompt, and the harness is model-agnostic — the same campaign shape runs whether the candidate is a hosted API, a local weights checkpoint, or a prompt template swapped against a fixed model.

Apply Filter 1 (Obvious Purge): the obvious metric — overall pass rate — hides the binding regression; the per-category breakdown is where the signal lives. Apply Filter 5 (Aesthetic Demand): every evaluation finding has a shape — category · baseline · candidate · delta · driver. The seven-axs-of-breadth taxonomy at `rules/cognitive-identity.md` §1 frames the axs of attention; Testing and Observability are the binding axs for this command.

---

## Instructions

Execute `/eval`. Define the evaluation dataset and scorer via the eval-harness skill, run the candidate model or prompt over the dataset, score every output with the prompt-evaluator agent, aggregate campaign metrics with a per-category breakdown, and emit the report at `_inputs/eval-findings.md` with regressions surfaced against the prior baseline.

**Reference Template:** Check `CLAUDE.md` for template path. Governance scales with seriousness per each rule's scaling table. Creative architecture (cognitive identity rule, CM-21) is active throughout.

---

## Pipeline Contract

**Pipeline position.** Diagnostic surface for the model-quality review track. It consumes the evaluation dataset, the scorer definition, and the candidate endpoint, and emits the campaign findings artifact that release-readiness consumers read. The command mutates neither the candidate nor the dataset; the findings are read-only diagnostics.

**Handoff Manifest.**

- **Consumed.** The operator-supplied evaluation dataset (`--dataset PATH`), the scorer definition (`--scorer NAME`), and the candidate model-or-prompt endpoint. When the consuming suite carries a prior baseline at `_inputs/eval-baseline.md`, it is read as the regression comparand.
- **Emitted.** The campaign findings artifact at `_inputs/eval-findings.md` carrying aggregate metrics, the per-category breakdown, the regression ledger against the prior baseline, and the campaign's `verified:` date.

**Pre-flight inquiry set.** Phase 1 (Define) emits the typed inquiry set per `rules/authority-inquiry.md` when the dataset path, the scorer choice, or the candidate endpoint is ambiguous — the dataset lacks a category column, the scorer name resolves to more than one definition, or the candidate endpoint is undeclared. Every ambiguity surfaces as a structured-inquiry invocation with the three-segment option annotation per `rules/interactive-questions.md` §3. No model provider is assumed; the candidate endpoint is always operator-ratified, never invented.

**Pre-emission gate.** Phase 5 (Report) runs the fifteen-bar pre-emission gate per `rules/pre-emission-gate.md` against the candidate findings artifact before promotion. The gate attestation block is recorded inside the emitted artifact. Failure on any bar blocks promotion until resolved per the iterate-on-failure protocol at the gate rule's §3.

---

## Foundational Stanzas

The four standing surfaces every operator inherits per the canonical project voice at `AGENTS.md` plus the active harness mirror.

### Refusal & Escalation

REFUSE any task whose scope exceeds this command's mission (defining a dataset and scorer, running a candidate over the dataset, scoring outputs, and emitting the campaign findings artifact). Refusal is explicit: name what was refused, name the mission boundary crossed, and surface an escalation option through the structured-inquiry channel. REFUSE evaluation against a dataset whose row schema lacks the fields the scorer requires without operator ratification of an alternate schema. REFUSE authoring model changes or prompt rewrites — the surface is diagnostic only; remediation routes through a downstream change-set.

### Output Surface

The findings artifact lands at the consuming suite's `_inputs/eval-findings.md` per the suite-locality invariant at `rules/context-management.md` §2.6.1. Plan-internal files are header-exempt per the `.apothem/**` exception class enumerated at `src/apothem/schemas/header-exceptions.txt`; the injector at `scripts/inject-header.py` is therefore NOT invoked on emission. NEVER write the findings artifact outside the suite folder; NEVER write to a global plans directory under any harness's config root from a downstream-project context; NEVER write to any other global-ecosystem location; NEVER mutate the candidate endpoint or the evaluation dataset.

### File-Authoring Contract

The findings artifact is header-exempt per the `.apothem/**` exception class; the byte-exact fixture and the exception list live at `src/apothem/schemas/header-exceptions.txt`. The command never invokes the authorship-header injector (`scripts/inject-header.py`) on its own emissions. When a finding cites a dataset row or a candidate output, the citation is documentary; the source is never written by this command.

### Structured Inquiry on Ambiguity

When uncertain about the dataset schema, the scorer definition, the candidate endpoint, the category taxonomy, or a borderline score-boundary call, route the resolution through the structured-inquiry channel with the three-segment option annotation per `rules/interactive-questions.md` §3. Free-form prose questions as primary input are forbidden. NEVER fabricate a score — every score traces to a dataset row scored by the prompt-evaluator agent. NEVER assume a model provider — the candidate endpoint is operator-supplied per `rules/host-discovery.md`.

---

## Inputs

| Argument | Type | Required | Description |
| -------- | ---- | -------- | ----------- |
| `--dataset PATH` | Path | No | Path to the evaluation dataset (JSONL / CSV / Parquet). MUST carry an input column, an expected column where the scorer is reference-based, and a category column for the per-category breakdown. When omitted, Phase 1 surfaces the dataset choice as an inquiry. |
| `--scorer NAME` | Enum | No | Scorer to apply — exact-match · semantic-similarity · rubric-graded · pairwise-preference · operator-defined. When omitted, Phase 1 surfaces the scorer choice as an inquiry with the candidate set annotated per `rules/option-annotation.md`. |

---

## Workflow — Five Campaign Phases

1. **Define the eval dataset + scorer.** Load the dataset via the eval-harness skill at `skills/eval-harness/SKILL.md` — validate the row schema (input · expected · category), resolve the scorer definition (`--scorer NAME`), and confirm the candidate endpoint is operator-ratified. The harness emits a normalized campaign manifest the downstream phases consume; ambiguities surface as structured inquiries per `rules/authority-inquiry.md`.
2. **Run the candidate over the dataset.** Invoke the candidate model-or-prompt against every dataset row, recording the raw output and the per-row latency. The candidate endpoint is provider-agnostic — the harness wraps the call so the same campaign runs against any backend. Externalise the raw run log at `_inputs/eval-run-log.md`.
3. **Score outputs with the prompt-evaluator agent.** Dispatch the prompt-evaluator agent at `agents/prompt-evaluator.md` to score every candidate output against the scorer definition. Each return carries the per-row score, the score rationale, and the category tag, max 200 tokens per return (audit return budget). Scores are never estimated — every score traces to a dataset row.
4. **Aggregate metrics + per-category breakdown.** Compute the campaign aggregate (overall score, mean latency, score distribution) and the per-category breakdown (per-category score, per-category sample count, per-category variance). The per-category breakdown is the load-bearing surface — the aggregate hides category-level regressions.
5. **Report with regressions.** Emit the findings artifact at `_inputs/eval-findings.md` carrying the executive summary, the per-category measurement tables, the regression ledger against the prior baseline (`EVAL-<N>: <category> <delta> vs baseline`), and the validation-gate attestation. Apply incremental generation per `rules/large-file-generation.md` when the artifact exceeds 500 lines.

---

## Mandates

| Mandate | Application |
| ------- | ----------- |
| CM-2 Zero Assumptions | Dataset, scorer, and candidate endpoint are operator-ratified; no provider is assumed. |
| CM-8 Bottleneck-First | The per-category breakdown identifies the binding regression, not the overall score. |
| M5 Authority | Every score traces to a dataset row; fabricated scores are non-conformant. |
| M7 Option Annotation | Scorer-choice inquiries carry the Recommended marker with concrete-driver rationale. |
| M9 Visual Leverage | Per-category measurement tables are the visual surface. |
| M15 Production-Ready | The regression ledger gates the candidate's release-readiness sign-off. |

---

## Output

- The campaign findings artifact at `_inputs/eval-findings.md` (executive summary + per-category measurement tables + regression ledger + validation-gate attestation + bindings).
- The raw run log at `_inputs/eval-run-log.md` (Phase 2 per-row output and latency).
- The normalized campaign manifest at `_inputs/eval-manifest.md` (Phase 1 dataset + scorer + candidate-endpoint resolution).

---

## Decision Tree

```mermaid
%%{ init: { "theme": "neutral" } }%%
%% verified: 2026-06-16 %%
%% provenance: commands/eval.md §Workflow %%
%% cross-reference: skills/eval-harness/SKILL.md + agents/prompt-evaluator.md %%
flowchart TD
    Start[/eval invoked] --> Q0{Dataset + scorer + candidate ratified?}
    Q0 -->|no| Inquiry[Surface structured inquiry · rules/authority-inquiry.md]
    Inquiry --> Q0
    Q0 -->|yes| Define[Phase 1 · define dataset + scorer via eval-harness skill]
    Define --> RunCand[Phase 2 · run candidate over dataset]
    RunCand --> Score[Phase 3 · score outputs with prompt-evaluator agent]
    Score --> Agg[Phase 4 · aggregate metrics + per-category breakdown]
    Agg --> Q4{Per-category regression vs baseline?}
    Q4 -->|yes| Ledger[Record regression in EVAL-N ledger]
    Q4 -->|no| Clean[Record baseline-clean attestation]
    Ledger --> Gate[Phase 5 · fifteen-bar pre-emission gate]
    Clean --> Gate
    Gate -->|fail| Iterate[Revise per gate §3 iterate-on-failure]
    Iterate --> Gate
    Gate -->|pass| Emit[Emit _inputs/eval-findings.md]
```

---

## Recommended Next Step

Invoke `/perf-audit` to measure the candidate endpoint's runtime against the per-class budgets once the model-quality campaign is clean; the regression ledger at `_inputs/eval-findings.md` is the prerequisite evidence the release-readiness sign-off consumes.

## Bindings (§0.j five-direction)

- **Drives →** The consuming suite's model-quality review slot. The eval-harness skill at `skills/eval-harness/SKILL.md` (every campaign drives it for dataset + scorer definition). The prompt-evaluator agent at `agents/prompt-evaluator.md` (every output is scored through it). The regression ledger that the release-readiness sign-off consumes. The remediation change-set that consumes the findings backlog (downstream, governed by `rules/production-ready-prs.md` same-change-set discipline).
- **Driven by ←** The operator-supplied evaluation dataset, scorer definition, and candidate endpoint. The prior baseline at `_inputs/eval-baseline.md` (the regression comparand).
- **Satisfies →** The consuming suite's model-quality review catalog. The Testing and Observability axs at `rules/cognitive-identity.md` §1 seven-axs-of-breadth taxonomy. The `commands/README.md` command catalog's Cohort-commands row for `/eval` (the registry entry that ratifies this command's place in the slash-command catalog).
- **Established by ↑** `rules/cognitive-identity.md` §1 seven-axs-of-breadth taxonomy (the Testing and Observability axs this command operationalizes). `rules/authority-inquiry.md` (the pre-flight inquiry surface for dataset / scorer / endpoint resolution). `rules/pre-emission-gate.md` (the fifteen-bar validation this command runs at Phase 5).
- **Gated by ←** The operator-ratified dataset, scorer, and candidate endpoint (no provider is assumed). The harness's Agent + structured inquiry + Bash + Read + Write tool surface. The eval-harness skill's dataset-schema validation (a malformed schema blocks Phase 1).
- **Cross-bound with ↔** `skills/eval-harness/SKILL.md` (the dataset + scorer definition surface this command drives). `agents/prompt-evaluator.md` (the per-output scoring agent this command dispatches at Phase 3). `commands/perf-audit.md` (sibling diagnostic command; `/eval` audits model quality, `/perf-audit` audits runtime). `rules/option-annotation.md` (every scorer-choice inquiry carries the Recommended marker with concrete-driver rationale). `rules/authority-inquiry.md` (every dataset / scorer / endpoint ambiguity routes through the canonical channel). `rules/host-discovery.md` (the candidate endpoint is discovered, never invented). `rules/pre-emission-gate.md` (Phase 5 fifteen-bar validation). `rules/large-file-generation.md` (incremental generation when the report exceeds 500 lines).

## Installed Reference Paths

When this skill is installed by Apothem, resolve a repository-style reference against the installed directory for its first segment, unless a project-local file with the same relative path exists. Paths are relative to the project root.

- `rules/<path>` is `.kimi-code/.apothem/support/rules/<path>`
- `templates/<path>` is `.kimi-code/.apothem/support/templates/<path>`
- `hooks/<path>` is `.kimi-code/.apothem/support/hooks/<path>`
