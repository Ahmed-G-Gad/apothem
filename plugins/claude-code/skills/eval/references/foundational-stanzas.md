<!-- SPDX-License-Identifier: MIT -->

## Foundational Stanzas

The four standing surfaces every operator inherits per the canonical project voice at `AGENTS.md` plus the active harness mirror.

### Refusal & Escalation

REFUSE any task whose scope exceeds this command's mission (defining a dataset and scorer, running a candidate over the dataset, scoring outputs, and emitting the campaign findings artifact). Refusal is explicit: name what was refused, name the mission boundary crossed, and surface an escalation option through the structured-inquiry channel. REFUSE evaluation against a dataset whose row schema lacks the fields the scorer requires without operator ratification of an alternate schema. REFUSE authoring model changes or prompt rewrites — the surface is diagnostic only; remediation routes through a downstream change-set.

### Output Surface

The findings artifact lands at the consuming suite's `_inputs/eval-findings.md` per the suite-locality invariant at `rules/context-management.md` §2.6.1. Plan-internal files are header-exempt per the `.apothem/**` exception class enumerated at `src/apothem/schemas/header-exceptions.txt`; the injector at `scripts/inject-header.py` is therefore NOT invoked on emission. NEVER write the findings artifact outside the suite folder; NEVER write to a global plans directory under any harness's config root from a downstream-project context; NEVER write to any other global-ecosystem location; NEVER mutate the candidate endpoint or the evaluation dataset.

### File-Authoring Contract

The findings artifact is header-exempt per the `.apothem/**` exception class; the byte-exact fixture and the exception list live at `src/apothem/schemas/header-exceptions.txt`. The command never invokes the authorship-header injector (`scripts/inject-header.py`) on its own emissions. When a finding cites a dataset row or a candidate output, the citation is documentary; the source is never written by this command.

### Structured Inquiry on Ambiguity

When uncertain about the dataset schema, the scorer definition, the candidate endpoint, the category taxonomy, or a borderline score-boundary call, route the resolution through the structured-inquiry channel with the three-segment option annotation per `rules/interactive-questions.md` §3. Free-form prose questions as primary input are forbidden. NEVER fabricate a score — every score traces to a dataset row scored by the prompt-evaluator agent. NEVER assume a model provider — the candidate endpoint is operator-supplied per `rules/host-discovery.md`.
