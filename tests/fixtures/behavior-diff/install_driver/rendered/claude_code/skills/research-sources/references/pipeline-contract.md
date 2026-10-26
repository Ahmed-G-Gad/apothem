<!-- SPDX-License-Identifier: MIT -->

## Pipeline Contract

**Pipeline position.** **Stage 4 of 13.** The canonical sequence is `/research-ideate → /research-spec → /research-theory → /research-sources → /research-synthesis → /research-proposal → /research-design → /research-experiment → /research-analysis → /research-paper → /research-review → /research-publish → /research-disseminate`. This command consumes the theoretical grounding and the spec's screening contract and emits the qualified evidence base the synthesis stage maps.

**Handoff Manifest.**

- **Consumed.** `{suite}/_spec/research-spec.md` (the ratified research spec: aims-and-objectives hierarchy, falsifiable hypotheses, scope, inclusion/exclusion criteria, success metrics, glossary) plus the theoretical grounding `/research-theory` produced (which frames the evidence the search prioritizes). The upstream `{suite}/_inputs/handoff-manifest.yml` per `src/apothem/schemas/handoff-manifest.yaml` records `/research-theory` as the producing stage; this command refuses to proceed when the manifest is absent, malformed, or carries unresolved P0/P1 markers.
- **Emitted.** `{suite}/sources/<id>.md` (one provenance-bearing extraction per surviving source) plus `{suite}/_inputs/source-ledger.md` (the ranked, screened, deduplicated ledger with a citation index, a dedup record, the search record, and the report-to-study map). The Handoff Manifest is amended at stage exit with the emitted paths, the screened-in vs. screened-out counts, the dedup-collapse count, and the R1/R4 attestation block. `/research-synthesis` consumes both surfaces.

**Pre-flight inquiry set.** Phase 1 emits the pre-flight inquiry set — the source-budget ceiling (`--max-sources`) surfaces when neither the flag nor a spec-declared ceiling fixes it; every inclusion/exclusion criterion the spec leaves under-specified surfaces as a screening-criterion confirmation placeholder per `rules/interactive-questions.md` (canonical channel; three-segment option annotation). A spec gap that blocks screening blocks emission until resolved.

**Pre-emission gate.** Phase 5 runs the fifteen-bar pre-emission gate per `rules/pre-emission-gate.md` against the candidate `source-ledger.md` and the per-source extractions before stage exit. The Handoff Manifest carries the gate attestation block; failure on any bar holds emission until resolved. The R4 citation-integrity check (every citation resolves) is a **hard bar** — a phantom citation blocks emission.
