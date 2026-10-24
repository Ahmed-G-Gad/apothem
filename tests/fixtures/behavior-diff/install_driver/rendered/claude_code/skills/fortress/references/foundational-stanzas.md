<!-- SPDX-License-Identifier: MIT -->

## Foundational Stanzas

The four standing surfaces every operator inherits per the canonical project voice at `AGENTS.md` plus the active harness mirror.

### Refusal & Escalation

REFUSE to author or reimplement any detector, remediator, or gate — the orchestrator only dispatches first-class commands and skills. REFUSE to remediate a finding whose refute-by-default verification leaves it contested — a contested finding survives with both positions and their evidence, never a silent fix. REFUSE an unbounded re-audit loop — the `--max-rounds` cap and its deterministic retreat are mandatory per `rules/planning-techniques.md` §1. REFUSE any irreversible or outward-facing remediation, and any remediation touching a high-risk always-gate class per `rules/authority-inquiry-categories.md`, without per-action confirmation — this floor holds even under `--autonomous`, routed per-file through the destructive-op option sets at `rules/interactive-questions.md` §6. REFUSE continuous remediation without the `--autonomous` opt-in. REFUSE silent reconciliation of contradictory verification verdicts — surface both with evidence. Escalation routes through the structured-inquiry channel per `rules/interactive-questions.md`.

### Output Surface

Detect / findings artifacts land where their commands place them (the consuming suite's `_inputs/` per the suite-locality invariant at `rules/context-management.md` §2.6.1); remediations land in place at each finding's owning surface in the host source; the fortress-posture report + workflow trace land at `{suite}/_outputs/fortress-report-<date>.md` or PLAN-NOTES.md. Per `rules/operational-mandates.md` CM-7, no plan-internal scaffolding leaks into codebase artifacts. NEVER write a hardening artifact to a global plans directory under any harness's config root from a downstream-project context.

### File-Authoring Contract

The orchestrator authors no codebase files of its own; the remediations it routes land through the minimal-diff `surgical-guard` skill, which preserves each file's existing authorship-header banner and routes any NEW file through `scripts/inject-header.{sh,py}` (byte-exact fixture at `src/apothem/schemas/authorship-header.txt`; exempt classes at `src/apothem/schemas/header-exceptions.txt`). The fortress-posture report is a plan-suite artifact, header-exempt under the `.apothem/**` class.

### Structured Inquiry on Ambiguity

When the target repository, the scope weighting, a finding's in-scope status, or the aggressiveness of a remediation is ambiguous, route the resolution through the structured-inquiry channel with the three-segment option annotation per `rules/interactive-questions.md` §3. NEVER fabricate a target path, a finding, or a remediation. Every destructive operation routes per-file through the canonical destructive-op option sets at `rules/interactive-questions.md` §6.
