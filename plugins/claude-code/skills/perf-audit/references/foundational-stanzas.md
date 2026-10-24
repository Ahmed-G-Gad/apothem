<!-- SPDX-License-Identifier: MIT -->

## Foundational Stanzas

The four standing surfaces every operator inherits per the canonical project voice at `AGENTS.md` plus the active harness mirror.

### Refusal & Escalation

REFUSE any task exceeding this command's mission (auditing a deployed repository against the per-class budgets and emitting the findings report). Refusal is explicit: name what was refused, name the mission boundary crossed, and surface an escalation option through the structured-inquiry channel. REFUSE audit against a repository whose `src/apothem/benchmarks/` directory is absent — surface the gap as an inquiry (the drivers are prerequisite evidence; missing drivers route to the gap-closure path at `rules/persistent-conventions-vigilance.md` §4 Ecosystem Gap Detection). REFUSE remediation authoring — this command identifies, classifies, and emits findings; remediation lands at a downstream change-set per the `rules/production-ready-prs.md` same-change-set discipline.

### Output Surface

The report lands at the consuming suite's `_inputs/perf-audit-findings.md` per the suite-locality invariant (`rules/context-management.md` §2.6.1). Plan-internal files are header-exempt per the `.apothem/**` class at `src/apothem/schemas/header-exceptions.txt`, so `scripts/inject-header.{sh,py}` is NOT invoked. NEVER write outside the suite folder; NEVER write to a global plans directory under any harness's config root from a downstream-project context; NEVER write to any other global-ecosystem location; NEVER mutate the deployed source tree (measurements happen via the benchmark drivers, never via source edits).

### File-Authoring Contract

The report is header-exempt per the `.apothem/**` class; the command never invokes the authorship-header injector on its emissions. Every deployed-repo path reference (e.g. `src/apothem/benchmarks/bench_hooks.py`) is documentary; the artifact remains unmodified.

### Structured Inquiry on Ambiguity

Route through the structured-inquiry channel with the three-segment annotation (`rules/interactive-questions.md` §3) on any uncertainty in identity / scope / preference / security / naming / infrastructure / version data, or any branch-point that materially affects the audit. Free-form prose questions as primary input are forbidden. NEVER fabricate authoritative data. NEVER invent a budget the rule does not declare; NEVER guess a benchmark-driver invocation form; NEVER classify a finding's severity without the measured exceedance percentage in hand.
