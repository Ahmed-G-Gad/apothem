<!-- SPDX-License-Identifier: MIT -->

## Foundational Stanzas

The four standing surfaces every operator inherits per the canonical project voice at `AGENTS.md` plus the active harness mirror, spelled out inline so this command honors them without relying on cross-reference alone. This command is read-only by mission; the stanzas adapt accordingly.

### Refusal & Escalation

REFUSE any task whose scope exceeds this command's stated mission (a read-only health-check of an existing plan suite). Refusal is explicit: name what was refused, name the mission boundary the request crossed, and surface an escalation option through the structured-inquiry channel per `rules/interactive-questions.md` (canonical channel; three-segment option annotation; never free-form prose as primary input). REFUSE any request that would require a write — reach for `/plan-execute` or `/plan-review` instead. When a tracking file is malformed or missing required sections, surface the gap as a finding within the prose output rather than synthesizing or repairing it — repair belongs to the writeful commands.

### Output Surface

This command emits NO files — its output is prose written to the operator's terminal / output stream. No `<project-root>/.apothem/plans/` updates, no updates to any harness's config root, no host-project file mutations of any kind. The `--verbose` health-grade emission is prose-only; the spot-check evidence cited in the report points to existing files (markdown links, line ranges, commit SHAs) without creating, modifying, or deleting any. The read-only invariant is the conformity guarantee per the §Pipeline Contract pre-emission-gate exemption.

### File-Authoring Contract

Writes nothing. The injector at `scripts/inject-header.{sh,py}` is never invoked from this command's surface. The contract applies to any orchestrator that materializes this command's findings into files — that orchestrator routes the new file (audit report, dashboard markdown, status.json) through the injector per the canonical authorship-header policy and lands it at a non-plan-internal path under the host's documentation tree.

### Structured Inquiry on Ambiguity

The dominant mode is non-interactive (read tracking files, emit prose). When uncertain about identity / scope / preference / security / naming / infrastructure / version data — or when a tracking file is malformed in a way that admits multiple plausible interpretations — route the resolution through the structured-inquiry channel with the three-segment option annotation per `rules/interactive-questions.md` §3 (rationale / recommendation / default-pointer). Free-form prose questions as primary input are forbidden. NEVER fabricate authoritative data — when a field is absent or contradicts across files, the report names the absence / contradiction explicitly and points to the writeful commands as the resolution path.
