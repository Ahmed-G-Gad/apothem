<!-- SPDX-License-Identifier: MIT -->

## Foundational Stanzas

The four standing surfaces every operator inherits per the canonical project voice at `AGENTS.md` plus the active harness mirror — honored inline here, not by cross-reference alone.

### Refusal & Escalation

REFUSE any task whose scope exceeds this command's mission (forensic audit and refinement of an existing plan suite — prose fidelity / internal consistency / quality / risk / standards / domain / architecture). Refusal is explicit: name what was refused, name the mission boundary crossed, and surface an escalation option through the structured-inquiry channel per `rules/interactive-questions.md` (three-segment annotation; never free-form prose as primary input). The Blind Review Mandate forbids inherited trust from prior generation; any pressure to soften a finding because the operator generated the plan themselves is itself a refusable scope-overreach.

### Output Surface

Review outputs are plan-suite-internal: scorecards write to `<project-root>/.apothem/plans/{suite}/PLAN-NOTES.md` `## Review Scorecards`, the Review Summary writes to `<project-root>/.apothem/plans/{suite}/PROGRESS.md`, the augmented Manifest writes to `<project-root>/.apothem/plans/{suite}/_inputs/handoff-manifest.yml`, concise per-finding revision-impact maps land in PLAN-NOTES.md, and durable large review reports or evidence tables land in `<project-root>/.apothem/plans/{suite}/_outputs/` per the suite-locality invariant at `rules/context-management.md` §2.6.1 (which governs `_inputs/`, `_outputs/`, and `_spec/` siblings). Findings disposition surfaces via structured-inquiry invocations whose answers are externalized to PLAN-NOTES.md inline. NEVER write review artifacts outside the suite folder, NEVER write to a global plans directory under any harness config root from a downstream-project context, and NEVER write to any other global-ecosystem location.

### File-Authoring Contract

Plan-suite review artifacts (PLAN-NOTES.md scorecard updates, PROGRESS.md Review Summary updates, the per-phase REPORT.md when revisions touch one, the augmented Manifest) are plan-internal and header-exempt per the `.apothem/**` exception class at `src/apothem/schemas/header-exceptions.txt`. The injector at `scripts/inject-header.{sh,py}` is therefore NOT invoked on review emissions. The contract applies to any orchestrator that materializes this command's findings into a non-plan artifact (a separate audit report at the host's documentation surface, for example) — that orchestrator routes the new file through the injector per the canonical authorship-header policy.

### Structured Inquiry on Ambiguity

When uncertain about identity / scope / preference / security / naming / infrastructure / version data — or any branch-point, deletion decision, or judgment call that materially affects the outcome — route the resolution through the structured-inquiry channel with the three-segment annotation per `rules/interactive-questions.md` §3 (rationale / recommendation / default-pointer). Free-form prose questions as primary input are forbidden. NEVER fabricate authoritative data. Step 7 (User Clarification Batches) is the dominant inquiry surface — every finding above the disposition threshold surfaces through one batched invocation per thematic group; per-revision approval at Step 9 routes through the canonical channel. REINTERPRETED prose-fidelity findings always require operator confirmation.
