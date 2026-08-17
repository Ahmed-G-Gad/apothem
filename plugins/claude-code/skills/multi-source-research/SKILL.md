---
name: "multi-source-research"
version: "0.1.0"
updated: "2026-06-09"
description: "Multi-source research harness — matched when the operator asks to 'research X deeply', 'investigate', 'find sources on', 'gather evidence about', 'fact-check', or any phrasing that demands a fanned-out, cross-verified, cited report rather than a single answer recalled from memory. Runs a five-step pipeline: decompose the question into testable sub-questions, fan out parallel source-discovery queries through a Research Team agent dispatch, fetch and extract claims per source, adversarially verify each claim against two or more independent sources, and synthesize a cited report where every claim carries its sources, a HIGH/MEDIUM/LOW confidence level, and an open-questions list. A single-source claim never closes at HIGH; an unverifiable claim is reported at LOW with the gap named, never papered over with an invented citation. User-invocable directly. NOT a single-answer lookup, a code generator, a plan-suite generator, a documentation generator, or a single-source summarizer."
archetype: "research-template"
userInvocable: true
argument-hint: "[research question]"
disable-model-invocation: true
allowed-tools: "Read, Write, Edit, Glob, Grep, Bash, WebSearch, WebFetch, Agent"
---

<!-- SPDX-License-Identifier: MIT -->

## Purpose

Answer a research question with a cited, cross-verified report rather than a single recalled answer. The skill decomposes the question into sub-questions, discovers sources in parallel, extracts claims per source, verifies each claim against two or more *independent* sources, and synthesizes the findings into a report where every claim carries its sources and a confidence level.

The load-bearing discipline is **adversarial verification**: a claim is not closed until independent evidence confirms it, contradictions are surfaced rather than silently resolved, and the absence of corroboration is reported as low confidence — never hidden behind an invented citation.

## Detection Signal

Triggers when the operator asks to "research X deeply", "investigate", "find sources on", "gather evidence about", "fact-check", or any phrasing that demands a fanned-out, cross-verified, cited report — never a single answer recalled from memory. The signal is the demand for *sourced, multi-source evidence* over a single-shot reply.

## Non-Goals

This skill carries a deliberately narrow surface. It is NOT:

- **Not a single-answer lookup.** A one-shot recalled answer is a different surface; this skill exists when the answer must be sourced and cross-verified.
- **Not a code generator.** The skill emits a research report, never codebase artifacts. Code emission is the host's `/plan-execute` surface.
- **Not a plan-suite generator.** Phase decomposition and plan structure belong to the `/plan` pipeline stages; this skill consumes no plan template and writes no plan-suite artifact.
- **Not a documentation generator.** The report is working research evidence, not user-facing documentation. User-facing docs land at the host's documentation surfaces per `rules/host-discovery.md`.
- **Not a single-source summarizer.** A claim resting on one source is reported at the lowest confidence with the dependency named; one source never closes a claim.

## Workflow

1. **Decompose the question.** Split the research question into testable sub-questions, each answerable by sourced evidence. Record the sub-question set before any search. When the question is underspecified (scope, region, timeframe, or definition ambiguous), STOP and surface the clarifying choices through the structured-inquiry channel before fanning out — fanning out against an ambiguous question wastes the fan-out budget.
2. **Fan out parallel source-discovery queries.** Dispatch one `WebSearch` per sub-question through parallel Agent fan-out per `rules/agent-orchestration.md` — a Research Team, full-parallel, structured-summary return contract. Each agent returns candidate source URLs with relevance notes.
3. **Fetch and extract per source.** `WebFetch` each candidate source; extract the specific claims it asserts, each bound to its source URL and the quoted or paraphrased passage that carries it. When a required source is paywalled, login-gated, purchase-only, or otherwise inaccessible after the `WebFetch` attempt, do NOT silently substitute a lower-trust accessible source — STOP and request the full source content from the operator through the structured-inquiry channel per `rules/source-accessibility.md` (trust outranks reachability); a claim left resting on an unreachable trusted source is reported at LOW confidence with the gap named, never papered over. Record the source-trust decision (which source, its trust tier, whether the trusted source was reachable, why a substitute was used) in the disclosure ledger per `rules/disclosure-ledger.md`.
4. **Adversarially verify each claim against two or more independent sources.** For every extracted claim, seek at least two independent sources that confirm or contradict it. Sources sharing a single upstream origin do not count as independent. Contradictions are surfaced, never silently resolved in favor of one side.
5. **Synthesize a cited report with confidence levels.** Assemble the verified claims into a report. Each claim carries its sources, a confidence level from the closed three-tier scale below, and an open-questions list naming what the evidence did not settle.

**Confidence scale (closed, three-tier):**

- **HIGH** — confirmed by two or more independent sources.
- **MEDIUM** — one strong source plus weak corroboration.
- **LOW** — single source, or contested across sources.

## Return Contract

A cited research report with four required elements:

- **Claims** — each stated definitively, with the sub-question it answers.
- **Sources** — per claim, the independent source URLs and the passages that carry the claim.
- **Confidence** — per claim, HIGH / MEDIUM / LOW per the Step 5 scale, with the reason.
- **Open questions** — what the evidence did not settle, and which sub-question remains unanswered.

A claim without sources, or a single-source claim presented as HIGH confidence, is non-conformant.

## Foundational Stanzas

The four standing surfaces every invocation inherits.

### Refusal & Escalation

REFUSE any request that asks the skill to act outside its research mission — code generation, plan-suite authoring, documentation production, or asserting an unsourced answer as fact. Refusal is explicit: name what was refused, name the mission boundary crossed, and surface escalation through the structured-inquiry channel per `rules/interactive-questions.md` (canonical channel; three-segment option annotation; free-form prose as primary input is forbidden). When a research question is underspecified, STOP and surface the clarifying choices through the same channel before fanning out.

### Output Surface

The skill's primary output is the cited research report (markdown), written to STDOUT for direct invocation. When the operator requests a durable artifact, the report lands at the host's research-evidence location per `rules/host-discovery.md` — never at a global-ecosystem location, never inside a downstream project's `.apothem/plans/` from this skill's context. Intermediate source dumps and extraction scratch are session-local and released after synthesis.

### File-Authoring Contract

When the skill emits a NEW file, the file routes through `scripts/inject-header.py` so the canonical `SPDX-License-Identifier` `MIT` header per `src/apothem/schemas/authorship-header.txt` is injected at the head; the injector is idempotent and detects the filetype variant automatically. Exempt classes — LICENSE, JSON configuration files, lockfiles, generated assets, vendored trees, ephemera, `.keep` markers, binary files — are enumerated at `src/apothem/schemas/header-exceptions.txt`.

### Structured Inquiry on Ambiguity

When the skill reaches a decision in any of the seven authoritative-data categories per `rules/authority-inquiry.md` — identity, scope direction, preference, security, naming of public surfaces, infrastructure endpoints, version pins — and the host is silent, it routes the resolution through the structured-inquiry channel with the three-segment option annotation per `rules/interactive-questions.md` §3 (rationale / recommendation / default-pointer). Free-form prose questions as primary input are forbidden. NEVER fabricate authoritative data, and NEVER fabricate a source — an unverifiable claim is reported at LOW confidence with the gap named, never papered over with an invented citation.

## Recommended Next Step

**Invoke the skill with the research question as its argument** to decompose, fan out, verify, and synthesize. When the question is underspecified, answer the surfaced clarifying choices first so the fan-out targets a well-scoped question.

## Bindings (§0.j five-direction)

- **Drives →** ● Every multi-source research engagement's decompose → fan-out → fetch → verify → synthesize workflow. ● Every cited report's claim / source / confidence / open-question shape. ● Every parallel source-discovery fan-out via the Research Team pattern.
- **Satisfies →** ● `CLAUDE.md` Source Layout row "multi-source-research" (skills/ class). ● The research cohort mission (fan-out, fetch, adversarially verify, synthesize a cited report).
- **Established by ↑** ● `CLAUDE.md` Source Layout (skills/ class declaration with the folder-with-`SKILL.md` convention). ● `CLAUDE.md` Ambiguity Handling (structured inquiry over fabrication).
- **Gated by ←** ● The harness's WebSearch / WebFetch / Agent tool surfaces (the skill fans out and fetches through them). ● The structured-inquiry channel for underspecified questions.
- **Cross-bound with ↔** ↔ `rules/agent-orchestration.md` (the Research Team fan-out pattern Step 2 dispatches). ↔ `rules/interactive-questions.md` (the structured-inquiry channel for ambiguity). ↔ `skills/ecosystem-audit/SKILL.md` + `skills/plan-suite/SKILL.md` (sibling skills under the same registry section).
