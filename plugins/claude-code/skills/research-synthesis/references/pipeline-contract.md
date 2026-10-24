<!-- SPDX-License-Identifier: MIT -->

## Pipeline Contract

**Pipeline position.** **Stage 5 of 13.** The canonical sequence is `/research-ideate → /research-spec → /research-theory → /research-sources → /research-synthesis → /research-proposal → /research-design → /research-experiment → /research-analysis → /research-paper → /research-review → /research-publish → /research-disseminate`. This stage consumes the source corpus the discovery stage assembled and emits the synthesis the proposal stage builds on before the design stage operationalizes it into testable predictions.

**Handoff Manifest.**

- **Consumed.** `{suite}/_inputs/source-ledger.md` (the ranked, screened, dedup'd source index from `/research-sources`) plus the per-source extractions under `{suite}/sources/<id>.md`. The Handoff Manifest at `{suite}/_inputs/handoff-manifest.yml` per `src/apothem/schemas/handoff-manifest.yaml` is read for the predecessor stage's attestation block.
- **Emitted.** `{suite}/_inputs/synthesis.md` — the SOTA map, the literature matrix, the GRADE-style certainty-of-evidence ratings, the consolidated theoretical model, the contested-findings ledger, and the explicit one-sentence gap statement. The manifest's `invocation_sequence` increments, `downstream` names `/research-proposal`, and the verification attestation records the per-claim refute-by-default outcomes.

**Pre-flight inquiry set.** Phase 1 (Ingest) emits the typed inquiry set per `rules/authority-inquiry.md` when the comparison dimensions for the literature matrix are underspecified, when two sources contest a load-bearing finding with comparable authority, or when the gap statement admits more than one defensible framing. Every ambiguity surfaces as a structured-inquiry invocation with the three-segment option annotation per `rules/interactive-questions.md` §3. Scope-direction and naming-of-the-gap inquiries block emission until answered.

**Pre-emission gate.** Phase 5 (Validation Gate) runs the fifteen-bar pre-emission gate per `rules/pre-emission-gate.md` against the candidate `_inputs/synthesis.md` before the manifest update. The gate attestation block is recorded inside the emitted synthesis. Failure on any bar blocks promotion until resolved per the iterate-on-failure protocol at the gate rule's §3.
