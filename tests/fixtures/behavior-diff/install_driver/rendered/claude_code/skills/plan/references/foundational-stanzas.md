<!-- SPDX-License-Identifier: MIT -->

## Foundational Stanzas

The four standing surfaces every operator inherits per the canonical project voice at `AGENTS.md` plus the active harness mirror.

### Refusal & Escalation

REFUSE an unbounded remediation loop — the `--max-rounds` cap and its BLOCKED retreat are mandatory per `rules/planning-techniques.md` §1. REFUSE to author or reimplement any stage's logic — the orchestrator only dispatches first-class stage commands; stage behavior lives in `commands/plan-*.md`. REFUSE to dispatch past a stage whose Sequence Gate fails (a missing or failing upstream manifest) — surface the failed gate and halt. REFUSE continuous chaining without the `--autonomous` opt-in. REFUSE silent reconciliation of contradictory verification verdicts at a hand-off — surface both with evidence. Escalation routes through the structured-inquiry channel per `rules/interactive-questions.md`.

### Output Surface

Stage artifacts land where their stage commands place them (inside the active suite per the suite-locality invariant at `rules/context-management.md` §2.6.1); the workflow trace lands in PROGRESS.md / PLAN-NOTES.md or `{suite}/_outputs/`. Per `rules/operational-mandates.md` CM-7, no plan-internal scaffolding leaks into codebase artifacts. NEVER write a plan artifact to a global plans directory under any harness's config root from a downstream-project context.

### File-Authoring Contract

The orchestrator authors no codebase files of its own (it dispatches stages that do). Stage commands honor the authorship-header contract via `scripts/inject-header.{sh,py}` (byte-exact fixture at `src/apothem/schemas/authorship-header.txt`); the workflow trace is a plan-suite artifact, header-exempt under the `.apothem/**` class at `src/apothem/schemas/header-exceptions.txt`.

### Structured Inquiry on Ambiguity

When the mission, entry point, resume stage, suite identity, or whether to dispatch the CONDITIONAL `plan-design` stage (architecture-bearing suites only) is ambiguous, route the resolution through the structured-inquiry channel with the three-segment option annotation per `rules/interactive-questions.md` §3. NEVER fabricate a suite path, a mission, or a stage decision. Every destructive operation routes per-file through the canonical destructive-op option sets at `rules/interactive-questions.md` §6.
