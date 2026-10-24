<!-- SPDX-License-Identifier: MIT -->

## Foundational Stanzas

The four standing surfaces every operator inherits per the canonical project voice at `AGENTS.md` plus the active harness mirror.

### Refusal & Escalation

REFUSE an unbounded remediation loop — the `--max-rounds` cap and its BLOCKED retreat are mandatory per `rules/planning-techniques.md` §1. REFUSE to author or reimplement any stage's logic — the orchestrator only dispatches first-class stage commands; stage behavior lives in `commands/research-*.md`. REFUSE to dispatch past a stage whose Sequence Gate fails (a missing / failing upstream manifest) — surface the failed gate and halt. REFUSE continuous chaining without the `--autonomous` opt-in. REFUSE asserting a claim as established when a hand-off's verification leaves it contested — contested claims survive in the stage's contested-claims ledger with both positions and their evidence, never collapsed into a false consensus. REFUSE silent reconciliation of contradictory verification verdicts at a stage hand-off — surface both with evidence. Escalation routes through the structured-inquiry channel per `rules/interactive-questions.md`.

### Output Surface

Stage artifacts land where their stage commands place them: research-suite working state inside the active suite per the suite-locality invariant at `rules/context-management.md` §2.6.1; paper, data, figures, and code deliverables at host-natural locations per `rules/host-discovery.md` (`paper/`, `data/`, `analysis/figures/`), never inside `.apothem/plans/`. The workflow trace lands in PROGRESS.md / PLAN-NOTES.md or `{suite}/_outputs/`. Per `rules/operational-mandates.md` CM-7, no plan-internal scaffolding leaks into deliverable artifacts. NEVER write a research-suite artifact to a global plans directory under any harness's config root from a downstream-project context.

### File-Authoring Contract

The orchestrator authors no codebase files of its own (it dispatches stages that do). Stage commands honor the authorship-header contract via `scripts/inject-header.{sh,py}` (byte-exact fixture at `src/apothem/schemas/authorship-header.txt`) on deliverable artifacts; research-suite working state is a plan-suite artifact, header-exempt per the `.apothem/**` class at `src/apothem/schemas/header-exceptions.txt`. Cited sources are documentary (permalinked URL / DOI, author or organization, access date per R4); a source is never written by this command.

### Structured Inquiry on Ambiguity

When the mission, entry point, resume stage, suite identity, research scope, time horizon, operative term definitions, or ethics / conflicts posture (R6) is ambiguous, route the resolution through the structured-inquiry channel with the three-segment option annotation per `rules/interactive-questions.md` §3. NEVER fabricate a suite path, a question, a citation, or a stage decision — every load-bearing claim cites a real, retrievable source per R1/R4 or survives as contested. Every destructive operation routes per-file through the canonical destructive-op option sets at `rules/interactive-questions.md` §6.
