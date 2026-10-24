<!-- SPDX-License-Identifier: MIT -->

## Pipeline Contract

**Pipeline position.** **Stage 7 of 13.** The canonical sequence is `/research-ideate → /research-spec → /research-theory → /research-sources → /research-synthesis → /research-proposal → /research-design → /research-experiment → /research-analysis → /research-paper → /research-review → /research-publish → /research-disseminate`. This stage consumes the proposal the proposal stage produced and the spec's falsifiable hypotheses, and emits the operationalized design plus the frozen analysis plan the experiment stage executes against.

**Handoff Manifest.**

- **Consumed.** The proposal `/research-proposal` produced (the framed study rationale, aims, and significance), `{suite}/_inputs/synthesis.md` (the SOTA map + literature matrix + consolidated theoretical model + explicit gap statement from `/research-synthesis`), and `{suite}/_spec/research-spec.md` (the falsifiable hypotheses, scope, inclusion/exclusion criteria, and success metrics from `/research-spec`). The Handoff Manifest at `{suite}/_inputs/handoff-manifest.yml` per `src/apothem/schemas/handoff-manifest.yaml` is read for the predecessor stage's attestation block.
- **Emitted.** `{suite}/_inputs/study-design.md` — the operationalized predictions, the variable specification (independent / dependent / control), the sample frame, the instruments, the power analysis, and the threats-to-validity ledger; and `{suite}/_inputs/preregistration.md` — the frozen analysis plan (hypotheses, primary and secondary outcomes, statistical tests, stopping rule, multiple-comparison correction). The manifest's `invocation_sequence` increments, `downstream` names `/research-experiment`, and the attestation records the preregistration freeze timestamp.

**Pre-flight inquiry set.** Phase 1 (Ingest) emits the typed inquiry set per `rules/authority-inquiry.md` when the design type is underspecified, when the effect-size assumption feeding the power analysis is not grounded in the synthesis, when the sample frame touches human or animal subjects (R6), or when a hypothesis admits more than one operational measure. Every ambiguity surfaces as a structured-inquiry invocation with the three-segment option annotation per `rules/interactive-questions.md` §3. Scope-direction, security/ethics-posture, and primary-outcome-naming inquiries block emission until answered.

**Pre-emission gate.** Phase 6 (Validation Gate) runs the fifteen-bar pre-emission gate per `rules/pre-emission-gate.md` against both candidate artifacts before the manifest update. The gate attestation block is recorded inside the study design. Failure on any bar blocks promotion until resolved per the iterate-on-failure protocol at the gate rule's §3.
