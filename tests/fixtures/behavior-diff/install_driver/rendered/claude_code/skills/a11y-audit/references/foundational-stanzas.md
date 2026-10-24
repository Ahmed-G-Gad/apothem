<!-- SPDX-License-Identifier: MIT -->

## Foundational Stanzas

The four standing surfaces every operator inherits per the canonical project voice at `AGENTS.md` plus the active harness mirror.

### Refusal & Escalation

REFUSE any task exceeding this command's mission (the per-page accessibility findings artifact for a deployed web surface against WCAG 2.2 AA). Refusal is explicit: name what was refused, name the mission boundary crossed, and surface an escalation option through the structured-inquiry channel. REFUSE audit against a surface whose page set is genuinely unbounded without operator-supplied focus narrowing (the crawl must terminate). REFUSE authoring remediation patches — the surface is diagnostic only; remediation routes through `/plan-execute` or operator-initiated edits. REFUSE audit against a higher conformance level (WCAG 2.2 AAA) without explicit operator ratification — WCAG 2.2 AA is the canonical default.

### Output Surface

The findings artifact lands at the consuming suite's `_inputs/a11y-audit-findings.md` per the suite-locality invariant (`rules/context-management.md` §2.6.1). Plan-internal files are header-exempt per the `.apothem/**` class at `src/apothem/schemas/header-exceptions.txt`, so `scripts/inject-header.{sh,py}` is NOT invoked. NEVER write outside the suite folder; NEVER write to a global plans directory under any harness's config root from a downstream-project context; NEVER write to any other global-ecosystem location; NEVER modify any rendered page or underlying source.

### File-Authoring Contract

The findings artifact is header-exempt per the `.apothem/**` class; the command never invokes the authorship-header injector on its emissions. Every page/URL citation is documentary (`page:selector`); the underlying source file is never written.

### Structured Inquiry on Ambiguity

Route through the structured-inquiry channel with the three-segment annotation (`rules/interactive-questions.md` §3) on any uncertainty about page-set scope, focus boundary, borderline contrast / focus-visibility / heading-hierarchy severity, or multi-axis attestation. Free-form prose questions as primary input are forbidden. NEVER fabricate findings — every finding cites a concrete `page:selector` (or `page:line` for source-mapped findings), a WCAG 2.2 success criterion, and the detecting tool (ax-core rule ID, Pa11y issue ID, Lighthouse audit ID).
