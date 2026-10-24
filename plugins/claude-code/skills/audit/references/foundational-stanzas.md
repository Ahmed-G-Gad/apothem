<!-- SPDX-License-Identifier: MIT -->

## Foundational Stanzas

The four standing surfaces every operator inherits per the canonical project voice at `AGENTS.md` plus the active harness mirror.

### Refusal & Escalation

REFUSE to remediate — `/audit` is report-only; it surfaces and routes findings but never edits source (remediation is `/elevate`'s remit or the owning surface's). REFUSE to author or reimplement any audit's logic — the orchestrator only dispatches first-class audit commands. REFUSE silent reconciliation of contradictory verification verdicts on a finding — surface both with evidence. REFUSE continuous parallel dispatch without the `--autonomous` opt-in. Escalation routes through the structured-inquiry channel (`rules/interactive-questions.md`).

### Output Surface

Per-dimension findings artifacts land where their audit commands place them (the consuming suite's `_inputs/` per the suite-locality invariant at `rules/context-management.md` §2.6.1); the synthesized report + workflow trace land at `{suite}/_outputs/audit-report-<date>.md` or PLAN-NOTES.md. Per `rules/operational-mandates.md` CM-7, no plan-internal scaffolding leaks into codebase artifacts. NEVER write an audit artifact to a global plans directory under any harness's config root from a downstream-project context.

### File-Authoring Contract

The orchestrator authors no codebase files of its own (it dispatches report-only audits that author findings artifacts). The synthesized report is a plan-suite artifact, header-exempt per the `.apothem/**` class at `src/apothem/schemas/header-exceptions.txt`; any non-plan artifact honors the authorship-header contract via `scripts/inject-header.{sh,py}`.

### Structured Inquiry on Ambiguity

Route through the structured-inquiry channel with the three-segment annotation (`rules/interactive-questions.md` §3) when the target repository, the dimension scope, or a finding's in-scope status is ambiguous. NEVER fabricate a target path, a dimension, or a finding.
