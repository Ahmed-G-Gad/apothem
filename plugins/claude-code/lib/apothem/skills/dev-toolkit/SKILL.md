---
name: "dev-toolkit"
version: "0.1.0"
updated: "2026-10-02"
description: "Engineering-discipline toolkit — matched when the operator asks to 'diagnose a bug', 'debug systematically', 'do TDD / write a failing test first', 'break this into vertical slices', 'turn this into a PRD / issues', 'decompose this work', or otherwise needs a disciplined software-engineering loop rather than an ad-hoc fix. Sequences four named, gated, composable loops — structured debugging (reproduce → minimize → hypothesize → instrument → fix root cause), test-first red-green-refactor (red observed before green), vertical-slice decomposition (independently-shippable testable units), and requirement-to-issue breakdown (goal → testable requirement set → tracked issues + ADR) — selected by --mode or by the request. Cross-references (never duplicates) sibling owners: orchestration → /workflow, diagrams → diagram-authoring, minimal-diff guarding → surgical-guard. Harness-agnostic; deterministic output; drives the host's discovered toolchain."
archetype: "engineering-template"
userInvocable: true
argument-hint: "[task or defect] [--mode diagnose|tdd|slice|decompose]"
disable-model-invocation: true
allowed-tools: "Read, Glob, Grep, TodoWrite"
---

<!-- SPDX-License-Identifier: MIT -->

## Purpose

Apply a disciplined software-engineering loop to a task or defect instead of an ad-hoc fix. The skill sequences four core loops into one composable, gated procedure:

- **structured debugging** — reproduce → minimize → hypothesize → instrument → fix root cause;
- **test-first development** — red → green → refactor (red observed, never assumed);
- **vertical-slice decomposition** — break work into independently-shippable, independently-testable units;
- **requirement-to-issue breakdown** — turn a goal into a testable requirement set, then tracked issues + an ADR.

Its value is **expressiveness**: the loops are *named and sequenced* so the engineering intent is legible, rather than scattered across unrelated one-off commands.

## Detection Signal

The operator asks to diagnose / debug systematically, write a failing test first (TDD), break work into vertical slices, turn a goal into a PRD / issues, or decompose a non-trivial task. A request that one direct edit resolves is below this skill's threshold.

## Non-Goals

Each boundary routes the out-of-scope work to its canonical owner — encoding the EF-2 single-source-of-truth principle. The source toolkits this skill is reauthored from bundled orchestration, diagramming, and guarding together; apothem keeps each capability with its owner and cross-references rather than duplicating.

- **Not a multi-agent orchestrator.** Parallel agent dispatch, background-agent management, and git-worktree isolation route to `/workflow` (the orchestration owner) — this skill applies the engineering loops, it does not orchestrate agents.
- **Not a diagram tool.** Technical diagrams (architecture, sequence, data-flow) route to `diagram-authoring` — this skill references a diagram, it does not render one.
- **Not a guard / surgical-edit tool.** Minimal-diff editing discipline and post-edit quality guarding route to `surgical-guard` — this skill produces the change, that skill guards how it lands.
- **Not a host-tool replacement.** It drives the host's discovered test runner / linter / type-checker; it ships none of its own. The toolchain is discovered, not assumed.

## Conformity Posture

- **Discover-don't-assume preamble (M1).** Discover the host's test runner, linter, type-checker, and issue / ADR conventions per `rules/host-discovery.md`; the loops drive the host's ratified tools, not assumed ones. Record discoveries with provenance.
- **Search-before-implement (CM-4).** Before authoring a fix or a slice, search the codebase for the reusable component — the engineering loops begin from the host's actual state.

## Procedure

The skill selects the loop by `--mode` (or by the request when `--mode` is unset); the loops compose. Every loop is **gated** — a step does not advance until its gate is satisfied.

### Mode: diagnose — Structured Debugging

`reproduce → minimize → hypothesize → instrument → fix → verify`

Reproduce the defect (a failing observation) → minimize to the smallest reproducing case → hypothesize the root cause → instrument to confirm or refute the hypothesis → fix the **root cause** (not the symptom, per CM-8) → verify the reproduction now passes. **Gates:** no fix before a confirmed hypothesis; no "done" before the minimized reproduction passes.

### Mode: tdd — Red-Green-Refactor

`red → green → refactor`

Write a behavioral test that **fails first** (red — observed failing, never assumed) → implement the minimum to pass (green) → refactor with the test as the safety net (refactor). **Gate:** the red observation — a green claimed without a prior observed red is non-conformant.

### Mode: slice — Vertical-Slice Decomposition

Break the work into independently-shippable, independently-testable vertical slices — each delivers observable value end-to-end and carries its own acceptance criteria + test. **Gate:** surface the slice boundaries for approval where they are non-obvious.

### Mode: decompose — Requirement-to-Issue Breakdown

Turn the goal into a structured requirement set (each requirement testable) → then into tracked issues at the host's discovered issue surface → recording an ADR where the decomposition embeds a durable design decision. Domain vocabulary is captured once (a shared context document) so the requirements read coherently. **Gate:** no requirement without a testable acceptance criterion.

### Self-Check (every mode)

Run the host's discovered quality gates (lint / type-check / test) and the fifteen-bar pre-emission gate per `rules/pre-emission-gate.md` against every emitted artifact. Emit the change / decomposition plus the single recommended next move.

## Arguments

- `[task or defect]` — the task to engineer or the defect to diagnose, in natural language.
- `--mode diagnose|tdd|slice|decompose` — the engineering loop (default: selected by the request).

## Return Contract

The mode's deliverable, plus the host-gate results, the fifteen-bar attestation, and a single `## Recommended Next Step`:

| `--mode` | Deliverable |
|----------|-------------|
| `diagnose` | the root-cause fix + the passing-reproduction verification |
| `tdd` | the red→green→refactor change (with the observed-red evidence) |
| `slice` | the slice set, each with acceptance criteria + a test |
| `decompose` | the requirement set + tracked issues + the ADR |

Deterministic per `rules/determinism.md` — the same task + host state yields the same loop output.

## Foundational Stanzas

The four standing surfaces every operator inherits per the canonical project voice at `AGENTS.md` plus the active harness mirror.

### Refusal & Escalation

REFUSE any request beyond the engineering loops — name what was refused, name the boundary crossed, surface an escalation option through the structured-inquiry channel per `rules/interactive-questions.md`. REFUSE a "fix" that addresses a symptom when the structured-debugging loop has not isolated the root cause — surface the unfinished diagnosis instead. REFUSE marking a TDD cycle green when the test was not first observed failing (red).

### Output Surface

Code changes, tests, and decomposition artifacts land at their domain-natural host locations per `rules/host-discovery.md`. Per CM-7, every artifact carries natural domain language — zero engineering-process-internal scaffolding. NEVER write a plan artifact outside the active suite.

### File-Authoring Contract

Every NEW code / test file routes through `scripts/inject-header.{sh,py}` for the canonical SPDX banner (fixture at `src/apothem/schemas/authorship-header.txt`); exempt classes at `src/apothem/schemas/header-exceptions.txt`. Edits preserve any existing banner; the header-inject-guard hook enforces the contract. Code honors the host's per-language code-craft conventions (discovered).

### Structured Inquiry on Ambiguity

When the task's acceptance criteria, the slice boundaries, the reproduction steps, or the requirement scope are ambiguous, route the resolution through the structured-inquiry channel with the three-segment option annotation per `rules/interactive-questions.md` §3. NEVER fabricate a reproduction, a requirement, or a test expectation.

## Recommended Next Step

**Invoke the `dev-toolkit` skill via the Skill tool** with `<task> --mode <diagnose|tdd|slice|decompose>` — run the selected loop to its gate, then route any surfaced orchestration to `/workflow`, any diagram to the `diagram-authoring` skill, and the change's landing discipline to the `surgical-guard` skill. Re-run in `decompose` mode first when the task is large enough to need slicing before implementation.

## Bindings (§0.j five-direction)

- **Drives →** ● Every disciplined engineering loop applied to a host task or defect. ● The host's discovered quality gates at the Self-Check step. ◐ Cross-references to `/workflow`, `diagram-authoring`, `surgical-guard` for the out-of-scope overlaps (EF-2 boundary).
- **Satisfies →** ● `CLAUDE.md` Source Layout row "dev-toolkit" (skills/ class). ● The elevation dimension **expressiveness** (named, sequenced, composable engineering loops vs. a loose bag of commands). ● `rules/operational-mandates.md` (CM-4 search-before-implement; CM-8 root-cause-not-symptom).
- **Established by ↑** ● `CLAUDE.md` Source Layout (skills/ folder-with-`SKILL.md` class). ● `CLAUDE.md` Ambiguity Handling (structured inquiry over fabrication). ● `rules/own-voice-reimplementation.md` (zero-verbatim; `reference-token-grep` = 0). ● `rules/agnostic-posture.md` (17-harness agnostic floor).
- **Gated by ←** ● The host's discovered test runner / linter / type-checker (the gap is surfaced where absent). ● The per-mode gates (no fix before confirmed hypothesis; no green before red). ● The host's structured-inquiry + Edit + Write + Bash tool surface.
- **Cross-bound with ↔** ↔ `skills/workflow/SKILL.md` (orchestration owner — overlaps route there). ↔ `skills/diagram-authoring/SKILL.md` (diagram owner). ↔ `skills/surgical-guard/SKILL.md` (minimal-diff + guard owner; this skill produces the change, that skill guards how it lands). ↔ `rules/own-voice-reimplementation.md` + `rules/agnostic-posture.md` (own-voice + agnostic floors). ↔ `skills/document-authoring/SKILL.md` (sibling own-voice authoring skill).
