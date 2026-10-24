<!-- SPDX-License-Identifier: MIT -->

## Foundational Stanzas

The four standing surfaces every operator inherits per the canonical project voice at `AGENTS.md` plus the active harness mirror.

### Refusal & Escalation

REFUSE any task whose scope exceeds this command's mission (authoring and running behavior-first tests against a deployed repository) — name what was refused, name the boundary crossed, and surface an escalation option through the structured-inquiry channel per `rules/interactive-questions.md`. REFUSE authoring tests against an ambiguous behavior contract the operator has not ratified — route the ambiguity through `rules/authority-inquiry.md`. REFUSE modifying source under test to make a failing test pass — this workflow authors tests, not source remediation; remediation routes through `/plan-execute`.

### Output Surface

The report lands at the consuming suite's `_inputs/test-suite-report.md` per the suite-locality invariant at `rules/context-management.md` §2.6.1. Authored test files land at the host's ratified test location discovered per `rules/host-discovery.md` (mirroring the source layout the host's existing tests follow). NEVER write the report outside the suite folder, to a global plans directory under any harness's config root, or to any other global-ecosystem location.

### File-Authoring Contract

Authored test files are codebase artifacts and carry the canonical `SPDX-License-Identifier: MIT` header in the comment family matching the filetype, injected via `scripts/inject-header.py --mode fix-in-place <path>` per the File Headers discipline. The exemption list at `src/apothem/schemas/header-exceptions.txt` governs which paths skip the banner; test files are not exempt. The report itself is header-exempt per the `.apothem/**` exception class.

### Structured Inquiry on Ambiguity

When uncertain about the host's test framework, the behavior contract under test, coverage-threshold targets, or test-location convention, route the resolution through the structured-inquiry channel with the three-segment option annotation per `rules/interactive-questions.md` §3. Free-form prose questions as primary input are forbidden. NEVER fabricate a behavior contract — every authored test asserts a contract the source observably carries or the operator has ratified.
