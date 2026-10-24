<!-- SPDX-License-Identifier: MIT -->

## Foundational Stanzas

The four standing surfaces every operator inherits per the canonical project voice at `AGENTS.md` plus the active harness mirror.

### Refusal & Escalation

REFUSE any task whose scope exceeds this command's stated mission (producing the architectural-integrity findings report for the target repository against its design artifact). Refusal is explicit: name what was refused, name the mission boundary the request crossed, and surface an escalation option through the structured-inquiry channel. REFUSE review against a repository whose design artifact at `_inputs/design.md` is absent — route through `/plan-design` first. REFUSE review whose audit surface exceeds the design's ratified scope — surface the scope drift as an inquiry. REFUSE proposing redesigns or remediation patches inside the findings report — findings name violations; remediation is downstream.

### Output Surface

The findings report lands at the target repository's `_inputs/architecture-review-findings.md` per the suite-locality invariant at `rules/context-management.md` §2.6.1. Plan-internal files are header-exempt per the `.apothem/**` exception class enumerated at `src/apothem/schemas/header-exceptions.txt`; the injector at `scripts/inject-header.{sh,py}` is therefore NOT invoked on emission. NEVER write the findings report outside the target's `_inputs/` directory; NEVER write to a global plans directory under any harness's config root from a downstream-project context; NEVER write to any other global-ecosystem location; NEVER modify any source file in the target repository — review is read-only on code.

### File-Authoring Contract

The findings report is header-exempt per the `.apothem/**` exception class. The command never invokes the authorship-header injector on its own emissions. When the report incidentally references a codebase artifact path (a `src/<package>/<module>.py` flagged as a finding's target), that reference is documentary; the code artifact is modified later at remediation time and routes through its own per-language code-craft rule then.

### Structured Inquiry on Ambiguity

When uncertain about identity / scope / preference / security / naming / infrastructure / version data — or about any audit-boundary or severity-classification call that materially affects the findings outcome — route the resolution through the structured-inquiry channel with the three-segment option annotation per `rules/interactive-questions.md` §3. Free-form prose questions as primary input are forbidden. NEVER fabricate authoritative data. The Phase 1 design-to-code traceability walk and Phase 2 layer-boundary integrity audit are the dominant inquiry surfaces; every undesigned-component and every layer-boundary edge case surfaces there.
