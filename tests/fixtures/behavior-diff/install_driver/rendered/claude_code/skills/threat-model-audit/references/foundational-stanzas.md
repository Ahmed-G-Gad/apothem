<!-- SPDX-License-Identifier: MIT -->

## Foundational Stanzas

The four standing surfaces every operator inherits per the canonical project voice at `AGENTS.md` plus the active harness mirror.

### Refusal & Escalation

REFUSE any task exceeding this command's mission (the per-threat findings artifact for a deployed repository). Refusal is explicit: name what was refused, name the mission boundary crossed, and surface an escalation option through the structured-inquiry channel. REFUSE audit against a repository whose architecture is undocumented to the point where trust boundaries cannot be identified (the STRIDE walk presumes identifiable trust-boundary edges). REFUSE authoring remediation patches — the surface is diagnostic only; remediation routes through `/plan-execute` or operator-initiated edits. REFUSE attributing a residual-risk acceptance to an authority the operator has not ratified — surface as an inquiry instead.

### Output Surface

The findings artifact lands at the consuming suite's `_inputs/threat-model-audit-findings.md` per the suite-locality invariant (`rules/context-management.md` §2.6.1). Plan-internal files are header-exempt per the `.apothem/**` class at `src/apothem/schemas/header-exceptions.txt`, so `scripts/inject-header.{sh,py}` is NOT invoked. NEVER write outside the suite folder; NEVER write to a global plans directory under any harness's config root from a downstream-project context; NEVER write to any other global-ecosystem location; NEVER modify any architectural artifact.

### File-Authoring Contract

The findings artifact is header-exempt per the `.apothem/**` class; the command never invokes the authorship-header injector on its emissions. Every architectural citation is documentary (`adapter:line` or `boundary:edge`); the underlying source is never written.

### Structured Inquiry on Ambiguity

Route through the structured-inquiry channel with the three-segment annotation (`rules/interactive-questions.md` §3) on any uncertainty about trust-boundary scope, focus boundary, borderline STRIDE-category severity, threat-actor classification, residual-risk attribution, or multi-axis attestation. Free-form prose questions as primary input are forbidden. NEVER fabricate findings — every finding cites a concrete trust-boundary edge, a STRIDE category, and (where applicable) a MITRE ATT&CK technique ID.
