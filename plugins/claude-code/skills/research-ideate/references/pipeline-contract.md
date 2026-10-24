<!-- SPDX-License-Identifier: MIT -->

## Pipeline Contract

**Pipeline position.** **Entry stage (1 of 13).** The canonical sequence is `/research-ideate → /research-spec → /research-theory → /research-sources → /research-synthesis → /research-proposal → /research-design → /research-experiment → /research-analysis → /research-paper → /research-review → /research-publish → /research-disseminate`. This stage accepts domain notes, a seed idea, or an opportunity sketch as input and emits the framed problem space plus the ranked candidate-question slate the framing stage consumes. SOTA framing: the research-lifecycle "Plan" stage per the [Princeton Research Lifecycle Guide](https://researchdata.princeton.edu/research-lifecycle-guide/research-lifecycle-guide) and the [NNLM Research Lifecycle](https://www.nnlm.gov/resources/data-glossary/research-lifecycle).

**Handoff Manifest.**

- **Consumed.** None (entry-position stage).
- **Emitted.** `{suite}/_inputs/handoff-manifest.yml` per the schema at `src/apothem/schemas/handoff-manifest.yaml`. The manifest carries the authored `_inputs/ideation.md` path, the ideation artifact's section completeness (framed problem space · opportunity-and-gap scan · invalidated-prior-hypothesis scan · ranked candidate-question slate · theoretical anchor), the Question-Resolution Audit's open-vs-resolved counts, and the rigor-mandate attestation block (R1 / R3 / R10 applicability per §Mandates), naming `downstream: /research-spec`.

**Pre-flight inquiry set.** The suite-name inquiry surfaces before any ideation write per `rules/interactive-questions.md`. Every undefined domain boundary, every theoretical-anchor choice, every ranking criterion enters the inquiry set; every authoritative-data gap surfaces as a `USER-CONFIRM` placeholder (the canonical `kind=`-tagged form) per the canonical-channel rule.

**Pre-emission gate.** The fifteen-bar pre-emission gate per `rules/pre-emission-gate.md` runs against the candidate `_inputs/ideation.md` before the manifest emits. The Handoff Manifest carries the gate attestation block; failure on any bar blocks emission until resolved.
