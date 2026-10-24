<!-- SPDX-License-Identifier: MIT -->

## Foundational Stanzas

The four standing surfaces every operator inherits per the canonical project voice at `AGENTS.md` plus the active harness mirror. Spelled out inline here so this command honors them at the surface, not via cross-reference alone.

### Refusal & Escalation

REFUSE any task whose scope exceeds this command's stated mission (executing the preregistered analysis, reporting effect sizes and CIs, applying multiplicity correction, running robustness checks, and disclosing deviations). Refusal is explicit: name what was refused, name the mission boundary the request crossed, and surface an escalation option through the structured-inquiry channel per `rules/interactive-questions.md`. REFUSE running analysis when the raw data is absent or the predecessor Sequence Gate is unsatisfied — route back to `/research-experiment` first. REFUSE running an unplanned test as if it were confirmatory: a test absent from the preregistration is exploratory by construction, labeled exploratory in the artifact, and never reported as a confirmatory result (R5). REFUSE reporting a bare p-value as the result — every reported effect carries its effect size and confidence interval (R7).

### Output Surface

The analysis artifact lands at `{suite}/_outputs/analysis.md` per the suite-locality invariant at `rules/context-management.md` §2.6.1; figures and tables land at the host-natural location discovered per `rules/host-discovery.md` (`analysis/figures/`, `analysis/tables/`), never inside `.apothem/plans/`. Plan-internal files are header-exempt per the `.apothem/**` exception class enumerated at `src/apothem/schemas/header-exceptions.txt`; the injector at `scripts/inject-header.{sh,py}` is therefore NOT invoked on the analysis artifact's emission, while host-natural figure/table source files honor the host's authorship-header convention per `rules/host-discovery.md`. NEVER write the analysis outside the suite folder or its discovered host-natural deliverable locations; NEVER write to a global plans directory under any harness's config root from a downstream-project context; NEVER write to any other global-ecosystem location.

### File-Authoring Contract

The analysis artifact is header-exempt per the `.apothem/**` exception class; the command never invokes the authorship-header injector at `scripts/inject-header.{sh,py}` on its own `_outputs/` emissions. Analysis code and figure/table source files authored at the host-natural location are subject to the host's discovered file-header and code-craft conventions per `rules/host-discovery.md` and `rules/code-craft-python.md` (or the host's per-language sibling), and pass the host's lint / format / type-check unmodified. Every reported number traces to a reproducible computation: the analysis records the test invocation, the input data slice, the seed where stochastic, and the software version pins so an independent party re-runs it (R2). Exemptions are enumerated at `src/apothem/schemas/header-exceptions.txt`.

### Structured Inquiry on Ambiguity

When uncertain about a test parameter the preregistration left open, the correction method for a comparison family, whether a failed assumption check justifies a deviation, or whether a data-triggered exclusion is in or out of scope, route the resolution through the structured-inquiry channel with the three-segment option annotation per `rules/interactive-questions.md` §3. Host-ratified conventions (the statistics toolchain, the figure format, the table format) are discovered, not invented, per `rules/host-discovery.md`. Free-form prose questions as primary input are forbidden. NEVER fabricate a number — every reported effect, interval, and corrected threshold traces to a reproducible computation on the raw data, or is recorded as a null or unverified result (R2, R3, R7).
