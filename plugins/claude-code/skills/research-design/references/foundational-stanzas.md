<!-- SPDX-License-Identifier: MIT -->

## Foundational Stanzas

The four standing surfaces every operator inherits per the canonical project voice at `AGENTS.md` plus the active harness mirror. Spelled out inline here so this command honors them at the surface, not via cross-reference alone.

### Refusal & Escalation

REFUSE any task whose scope exceeds this command's stated mission (operationalizing the gap into a study design and freezing the analysis plan in a preregistration). Refusal is explicit: name what was refused, name the mission boundary the request crossed, and surface an escalation option through the structured-inquiry channel per `rules/interactive-questions.md`. REFUSE running design when the synthesis gap statement is absent or the predecessor Sequence Gate is unsatisfied — route back to `/research-synthesis` first. REFUSE freezing a preregistration whose hypotheses are not falsifiable predictions (R3) — a hypothesis that no observable outcome refutes is returned for restatement, never preregistered. REFUSE collecting or referencing data of any kind within this stage — the preregistration freezes the plan *before* data collection; any task that begins data collection belongs to `/research-experiment`.

### Output Surface

The study design lands at `{suite}/_inputs/study-design.md` and the preregistration at `{suite}/_inputs/preregistration.md`, both per the suite-locality invariant at `rules/context-management.md` §2.6.1. Plan-internal files are header-exempt per the `.apothem/**` exception class enumerated at `src/apothem/schemas/header-exceptions.txt`; the injector at `scripts/inject-header.{sh,py}` is therefore NOT invoked on emission. NEVER write either artifact outside the suite folder; NEVER write to a global plans directory under any harness's config root from a downstream-project context; NEVER write to any other global-ecosystem location.

### File-Authoring Contract

Both emitted artifacts are header-exempt per the `.apothem/**` exception class; the command never invokes the authorship-header injector at `scripts/inject-header.{sh,py}` on its own emissions. Every prediction, variable, and threat cites its provenance — the synthesis gap, the spec hypothesis, or the literature source ID it derives from; the citation is documentary, and no source is authored or rewritten by this command. Exemptions are enumerated at `src/apothem/schemas/header-exceptions.txt`.

### Structured Inquiry on Ambiguity

When uncertain about the design type, the operational measure for a construct, the effect size feeding the power analysis, the sample frame's ethics posture, or whether a borderline hypothesis is falsifiable, route the resolution through the structured-inquiry channel with the three-segment option annotation per `rules/interactive-questions.md` §3. Host-ratified conventions are discovered, not invented, per `rules/host-discovery.md`. Free-form prose questions as primary input are forbidden. NEVER fabricate an effect size, a sample size, or a statistical assumption — each traces to the synthesis, a spec metric, or an operator-supplied value, or surfaces as a `USER-CONFIRM` placeholder (the canonical `kind=`-tagged form) until supplied (R1, R7).
