<!-- SPDX-License-Identifier: MIT -->

## Foundational Stanzas

The four standing surfaces every operator inherits per the canonical project voice at `AGENTS.md` plus the active harness mirror. Spelled out inline here so this command honors them at the surface, not via cross-reference alone.

### Refusal & Escalation

REFUSE any task whose scope exceeds this command's stated mission (critiquing the paper against the venue bar, scoring the five axes, and emitting a severity-triaged required-revision list). Refusal is explicit: name what was refused, name the mission boundary the request crossed, and surface an escalation option through the structured-inquiry channel per `rules/interactive-questions.md`. REFUSE reviewing when the paper deliverable is absent or the predecessor Sequence Gate is unsatisfied — route back to `/research-paper` first. REFUSE rewriting the paper to fix a finding: this stage critiques and prescribes revisions; the author's revision pass is a separate action, and a reviewer who silently patches the manuscript has stopped reviewing it. REFUSE accepting a claim because the paper asserts it confidently — confidence is not evidence; every passed claim traces to the manuscript's own data or a cited source (refute-by-default).

### Output Surface

The review report lands at `{suite}/_outputs/review-report.md` per the suite-locality invariant at `rules/context-management.md` §2.6.1, never inside the paper deliverable and never inside `.apothem/plans/` outside the suite. Plan-internal files are header-exempt per the `.apothem/**` exception class enumerated at `src/apothem/schemas/header-exceptions.txt`; the injector at `scripts/inject-header.{sh,py}` is therefore NOT invoked on the review report's emission. NEVER write the review outside the suite folder; NEVER write to a global plans directory under any harness's config root from a downstream-project context; NEVER write to any other global-ecosystem location.

### File-Authoring Contract

The review report is header-exempt per the `.apothem/**` exception class; the command never invokes the authorship-header injector at `scripts/inject-header.{sh,py}` on its own `_outputs/` emission. This stage authors no code and no host-natural deliverable — it reads the paper and the suite's evidence artifacts and writes one report. Every finding traces to a reproducible locus: the report records the manuscript section, line, figure, or table the defect sits in, and the suite artifact whose evidence the finding cross-checks against, so the author re-finds each defect without re-reading the whole paper (R2, R4). Exemptions are enumerated at `src/apothem/schemas/header-exceptions.txt`.

### Structured Inquiry on Ambiguity

When uncertain about the target venue and its standard, whether a claimed contribution clears the novelty bar, whether an ethics concern blocks the critique, or whether a finding's severity is HIGH or MEDIUM at the margin, route the resolution through the structured-inquiry channel with the three-segment option annotation per `rules/interactive-questions.md` §3. Host-ratified conventions (the venue, the citation style, the reproducibility expectations) are discovered from the paper and the suite artifacts, not invented, per `rules/host-discovery.md`. Free-form prose questions as primary input are forbidden. NEVER fabricate a finding — every required revision cites the manuscript locus it targets and the standard it fails against, or it is not a finding (R4).
