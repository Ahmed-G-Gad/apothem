<!-- SPDX-License-Identifier: MIT -->

## Pipeline Contract

**Pipeline position.** **Stage 2 of 13.** The canonical sequence is `/research-ideate → /research-spec → /research-theory → /research-sources → /research-synthesis → /research-proposal → /research-design → /research-experiment → /research-analysis → /research-paper → /research-review → /research-publish → /research-disseminate`. This command consumes the ideation that `/research-ideate` produced, accepts a free-form question, raw notes, or an ad-hoc research idea as input, and emits the Handoff Manifest the downstream stages consume.

**Handoff Manifest.**

- **Consumed.** `{suite}/_inputs/ideation.md` (the ideation from `/research-ideate`) when present, otherwise the research question or notes source the operator supplies (see the Sequence Gate). When `/research-ideate` ran, the Handoff Manifest at `{suite}/_inputs/handoff-manifest.yml` per `src/apothem/schemas/handoff-manifest.yaml` is read for its attestation block.
- **Emitted.** `{suite}/_inputs/handoff-manifest.yml` per the schema at `src/apothem/schemas/handoff-manifest.yaml`. The manifest carries the authored `_spec/research-spec.md` path, the spec's section completeness (question · hypotheses · scope · inclusion/exclusion criteria · success metrics · glossary), the Question-Resolution Audit's open-vs-resolved counts, the Deferral Ledger's downstream routing entries, and the rigor-mandate attestation block (R1–R7 applicability per §Mandates).

**Pre-flight inquiry set.** The suite-name inquiry surfaces before any spec write per `rules/interactive-questions.md`. Every implicit hypothesis form, every unstated scope boundary, every undefined success threshold enters the inquiry set; every authoritative-data gap surfaces as a `USER-CONFIRM` placeholder (the canonical `kind=`-tagged form) per the canonical-channel rule.

**Pre-emission gate.** The fifteen-bar pre-emission gate per `rules/pre-emission-gate.md` runs against the candidate `_spec/research-spec.md` before promotion. The Handoff Manifest carries the gate attestation block; failure on any bar blocks promotion until resolved.
