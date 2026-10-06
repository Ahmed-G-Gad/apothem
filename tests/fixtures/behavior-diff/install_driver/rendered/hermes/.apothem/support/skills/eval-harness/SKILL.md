---
name: "eval-harness"
version: "0.1.0"
updated: "2026-10-02"
description: "Build and run a reproducible LLM evaluation harness — matched when the operator asks to 'build an eval', 'measure the model', set up an 'evaluation harness', 'score outputs', benchmark a prompt or model variant, regression-test generation quality, or compare candidate models on a labeled task. Defines four artifacts: a versioned labeled dataset, a scorer (exact-match / rubric / LLM-judge) with an explicit pass criterion, a candidate runner, and a metrics report with pass-rate, a Wilson confidence interval, per-category breakdowns, and regressions against a prior run. Every run stamps the dataset version, scorer, candidate, and seed, so identical inputs return an identical verdict. Harness- and model-agnostic: drives any provider through its native invocation surface. NOT for fine-tuning or training pipelines, authoring the prompt under test, live-monitoring dashboards, one-shot un-versioned benchmarks, or scoring against an undefined pass criterion. User-invocable directly."
archetype: "ai-template"
userInvocable: true
argument-hint: "[--dataset PATH] [--scorer NAME]"
disable-model-invocation: true
allowed-tools: "Read, Glob, Grep"
---

<!-- SPDX-License-Identifier: MIT -->

## Purpose

Build and run a reproducible evaluation harness that measures an LLM candidate against a labeled dataset under an explicit scorer. The harness emits a metrics report — pass-rate, per-category breakdown, confidence interval, regression list — that any reader reproduces by re-running the same dataset and scorer over the same candidate.

Reproducibility is the load-bearing discipline. Every run records four reproducibility coordinates — **dataset version · scorer definition · candidate identifier · random seed** — so two runs over identical inputs return an identical verdict. An eval that cannot be re-run to the same number is a sample, not a measurement.

## Detection Signal

Triggers when the operator asks to "build an eval", "measure the model", set up an "evaluation harness", "score outputs", benchmark a prompt or model variant, regression-test generation quality, or compare two candidate models on a labeled task. The signal is the demand to *measure* a candidate against labeled ground truth under a stated pass bar — not to author the prompt, tune weights, or watch production traffic.

## Non-Goals

This skill carries a deliberately narrow surface. It is NOT:

- **Not provider-coupled.** The harness drives any candidate through its native invocation surface — HTTP endpoint, SDK call, local runtime, or CLI. It never assumes a vendor, API shape, or model identifier; the candidate is a parameter, discovered or inquired per `rules/host-discovery.md`.
- **Not a training or fine-tuning pipeline.** The harness measures behavior; it does not adjust weights, curate training data, or run gradient steps.
- **Not a prompt-authoring tool.** The harness scores outputs against a dataset. Authoring the prompt under test is the operator's upstream responsibility.
- **Not a one-shot benchmark.** A single un-versioned run is a sample, not an eval. The harness stamps the four reproducibility coordinates so runs are comparable across time.
- **Not a live-monitoring dashboard.** The harness emits a point-in-time report; continuous production telemetry is the host's observability surface, not this skill's.

## Workflow

1. **Define the eval dataset.** Author a versioned set of labeled cases — each case carries an input, an expected label (or rubric reference), and a category tag that drives the per-category breakdown. Discover the host's existing dataset format and location per `rules/host-discovery.md` and honor it. A dataset below the host's ratified floor (default: 20 cases) surfaces as a confidence-coverage finding — too few cases yield a confidence interval too wide to act on.
2. **Define a scorer with a pass criterion.** Choose exactly one scorer class per metric from the closed set:
   - **exact-match** — string or structured equality against the expected label.
   - **rubric** — named criteria, each with a per-criterion threshold.
   - **LLM-judge** — a judge prompt emitting a deterministic verdict schema; the judge candidate and seed are pinned so judge verdicts are themselves reproducible.

   State the pass criterion explicitly: a case passes iff the scorer's verdict meets the named threshold. A scorer requested without a pass criterion is REFUSED per the Refusal & Escalation stanza — an eval without a threshold measures nothing.
3. **Run candidates over the dataset.** Invoke the candidate over every case, recording the raw output, the case identifier, and the run seed. Re-running the same dataset and seed over the same candidate returns identical raw outputs where the candidate is deterministic; any non-determinism is recorded with the sampling parameters (temperature, top-p, seed) that drive it.
4. **Aggregate metrics.** Compute pass-rate over the full dataset, the per-category pass-rate breakdown, and the passing/failing case counts per category. Aggregation is deterministic — identical raw outputs under an identical scorer return identical metrics.
5. **Report with confidence and regressions.** Emit the metrics report naming pass-rate with its Wilson-score confidence interval (at the host's ratified level; default 95%), the per-category breakdown, and — when a prior run's report is supplied — the **regression list** (cases that passed in the prior run and fail in this one) and the **improvement list** (the inverse).

## Return Contract

The harness returns three artifacts:

- **Dataset** — the versioned labeled-case set at the host's ratified location, carrying a version stamp and a case count.
- **Scorer** — the scorer definition (class · criteria · pass threshold · judge pin where applicable) as a re-runnable specification.
- **Metrics report** — pass-rate with its Wilson confidence interval, the per-category breakdown, and the regression/improvement lists against any supplied prior report.

The report is reproducible: a reader re-running the recorded dataset version and scorer over the recorded candidate and seed reaches the same metrics. A report omitting the confidence interval, or presenting a sub-floor dataset's pass-rate without the coverage caveat, is non-conformant.

## Foundational Stanzas

The four standing surfaces every invocation inherits.

### Refusal & Escalation

REFUSE any request that asks the harness to act outside its mission — fine-tuning, prompt authoring, production monitoring, or scoring against an undefined pass criterion. Refusal is explicit: name what was refused, name the mission boundary crossed, and route the operator to the appropriate surface through the structured-inquiry channel per `rules/interactive-questions.md` (canonical channel; three-segment option annotation; free-form prose as primary input is forbidden). A scorer requested without a pass criterion is REFUSED as underspecified, and the criterion is surfaced as a required inquiry before any run.

### Output Surface

The harness emits the dataset and scorer at the host's ratified eval location (discovered per `rules/host-discovery.md`; never assumed) and the metrics report to STDOUT or the host's report surface. Candidate outputs and run logs are run-scoped working state under the host's ratified eval-run directory. NEVER write eval artifacts to a global-ecosystem location; NEVER couple an artifact to a specific provider's identifier where the host expects a parameter.

### File-Authoring Contract

Every NEW file the harness creates routes through `scripts/inject-header.py` so the canonical `SPDX-License-Identifier` `MIT` header is injected in the comment family matching the filetype; the injector is idempotent and detects the variant from the byte-exact fixture at `src/apothem/schemas/authorship-header.txt`. Exempt classes — LICENSE, JSON configuration files, lockfiles, generated assets, vendored trees, `.audit/` ephemera, `.apothem/plans/` ephemera, `.keep` / `.gitkeep` markers, binaries — are enumerated at `src/apothem/schemas/header-exceptions.txt`. Generated run logs and metrics reports are header-exempt under the generated-asset class.

### Structured Inquiry on Ambiguity

When the harness reaches a decision in any of the seven authoritative-data categories per `rules/host-discovery.md` and `rules/interactive-questions.md` — identity; scope direction; preference (dataset format, scorer class, confidence level); security (judge-candidate credentials, allowed network egress); naming of public surfaces (dataset name, scorer name); infrastructure endpoints (candidate invocation surface); version pins (candidate identifier, judge pin) — and the host is silent, it routes the resolution through the structured-inquiry channel with the three-segment option annotation per `rules/interactive-questions.md` §3 (rationale / recommendation / default-pointer). Free-form prose questions as primary input are forbidden. NEVER fabricate authoritative data — a guessed candidate identifier or invented endpoint corrupts every downstream metric.

## Recommended Next Step

**Run the harness over the defined dataset and scorer**, then supply the resulting report as the prior-run baseline on the next invocation to activate regression detection.

## Bindings (§0.j five-direction)

- **Drives →** ● Every eval-dataset definition under the host's ratified eval location. ● Every scorer specification (exact-match / rubric / LLM-judge) with its pass criterion. ● Every metrics report's reproducibility stamp (dataset version, scorer, candidate, seed).
- **Satisfies →** ● `CLAUDE.md` Source Layout row "eval-harness" (skills/ class). ● The ai-engineering cohort's reproducible-LLM-evaluation mission.
- **Established by ↑** ● `CLAUDE.md` Source Layout (skills/ class declaration with the folder-with-`SKILL.md` convention). ● `CLAUDE.md` Ambiguity Handling (structured inquiry over fabrication).
- **Gated by ←** ● The harness's tool surface (Read / Write / Edit / Glob / Grep / Bash). ● The host's ratified eval-dataset format and candidate-invocation surface, discovered per `rules/host-discovery.md`.
- **Cross-bound with ↔** ↔ `rules/host-discovery.md` (M1 — dataset format, candidate surface, confidence level discovered, never invented). ↔ `rules/interactive-questions.md` (M5 — undefined pass criteria and authoritative-data gaps route through the structured-inquiry channel). ↔ `rules/definitiveness.md` (M8 — the pass criterion is a stated threshold, never a hedged expectation). ↔ `skills/ecosystem-audit/SKILL.md` (sibling skill under the same registry section).
