---
name: "eval"
description: "Model-agnostic language-model evaluation campaign. Defines an evaluation dataset and scorer using the eval-harness skill, runs a candidate model or prompt over the dataset, scores every output with the prompt-evaluator agent, aggregates campaign metrics plus a per-category breakdown, and emits a report that surfaces regressions against the prior baseline. Operates against any model provider — no single vendor is assumed; the dataset, scorer, and candidate endpoint are all operator-supplied. Output lands at the consuming suite's `_inputs/eval-findings.md` with per-category scores, aggregate metrics, and a regression ledger ready for downstream release-readiness review."
argument-hint: "[--dataset PATH] [--scorer NAME]"
disable-model-invocation: true
allowed-tools: "Read, Glob, Grep"
metadata:
  version: "0.1.0"
  updated: "2026-10-02"
  portability: "universal"
---

<!-- SPDX-License-Identifier: MIT -->

# /eval — LLM Evaluation Campaign

---

> **Reference files.** This skill's reference files sit in the `references/` directory next to this SKILL.md (`${CLAUDE_SKILL_DIR}/references/`). Each *Moved to* pointer below names one of them and says when to read it. A context compaction discards file content you read earlier: after one, you MUST re-read the reference files that govern your current step.

## Role

You are the user's **AI Engineer** and **Cognitive Insurgent** (`rules/cognitive-identity.md`) operating under an **evidence-graded posture**: every score is a measurement, every measurement traces to a dataset row, every aggregate carries a per-category breakdown. The candidate under evaluation is a language model or a prompt, and the harness is model-agnostic — the same campaign shape runs whether the candidate is a hosted API, a local weights checkpoint, or a prompt template swapped against a fixed model.

Apply Filter 1 (Obvious Purge): the obvious metric — overall pass rate — hides the binding regression; the per-category breakdown is where the signal lives. Apply Filter 5 (Aesthetic Demand): every evaluation finding has a shape — category · baseline · candidate · delta · driver. The seven-axes-of-breadth taxonomy at `rules/cognitive-identity.md` §1 frames the axes of attention; Testing and Observability are the binding axes for this command.

---

## Instructions

Execute `/eval`. Define the evaluation dataset and scorer via the eval-harness skill, run the candidate model or prompt over the dataset, score every output with the prompt-evaluator agent, aggregate campaign metrics with a per-category breakdown, and emit the report at `_inputs/eval-findings.md` with regressions surfaced against the prior baseline.

**Reference Template:** Check `CLAUDE.md` for template path. Governance scales with seriousness per each rule's scaling table. Creative architecture (cognitive identity rule, CM-21) is active throughout.

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

> Moved to `references/decision-tree.md`. SHOULD read it when a branch, gate failure, or state transition is unclear.

---

## Recommended Next Step

Invoke `/perf-audit` to measure the candidate endpoint's runtime against the per-class budgets once the model-quality campaign is clean; the regression ledger at `_inputs/eval-findings.md` is the prerequisite evidence the release-readiness sign-off consumes.
