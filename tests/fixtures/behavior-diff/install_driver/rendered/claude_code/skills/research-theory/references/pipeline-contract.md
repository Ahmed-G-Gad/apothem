<!-- SPDX-License-Identifier: MIT -->

## Pipeline Contract

**Pipeline position.** **Stage 3 of 13.** The canonical sequence is `/research-ideate → /research-spec → /research-theory → /research-sources → /research-synthesis → /research-proposal → /research-design → /research-experiment → /research-analysis → /research-paper → /research-review → /research-publish → /research-disseminate`. This stage consumes the framed spec and emits the theoretical framework the systematic search and synthesis stages ground their search and gap statement against. SOTA framing: the [NWO Impact Plan Approach](https://www.nwo.nl/en/impact-plan-approach) theory-of-change discipline and the [CGIAR Theory of Change & Impact Pathways](https://pim.cgiar.org/impact/theory-of-change-impact-pathways/) logic-model methodology.

**Handoff Manifest.**

- **Consumed.** `{suite}/_spec/research-spec.md` (the framed question, falsifiable hypotheses, scope, and glossary from `/research-spec`). The Handoff Manifest at `{suite}/_inputs/handoff-manifest.yml` per `src/apothem/schemas/handoff-manifest.yaml` is read for the predecessor stage's attestation block.
- **Emitted.** `{suite}/_inputs/theory.md` — the conceptual / theoretical framework, the theory-of-change / logic model, the constructs with their operational definitions, and the conceptual-model diagram. The manifest's `invocation_sequence` increments, `downstream` names `/research-sources`, and the attestation records R10 / R1 / R3 coverage.

**Pre-flight inquiry set.** Phase 1 (Ingest) emits the typed inquiry set per `rules/authority-inquiry.md` when the theoretical framework admits more than one defensible choice, when a construct's operational definition rests on a threshold the spec leaves unstated, or when the theory-of-change's outcome boundary is underspecified. Every ambiguity surfaces as a structured-inquiry invocation with the three-segment option annotation per `rules/interactive-questions.md` §3. Scope-direction and naming-of-constructs inquiries block emission until answered.

**Pre-emission gate.** Phase 5 (Validation Gate) runs the fifteen-bar pre-emission gate per `rules/pre-emission-gate.md` against the candidate `_inputs/theory.md` before the manifest update. The gate attestation block is recorded inside the emitted theory artifact. Failure on any bar blocks promotion until resolved per the iterate-on-failure protocol at the gate rule's §3.
