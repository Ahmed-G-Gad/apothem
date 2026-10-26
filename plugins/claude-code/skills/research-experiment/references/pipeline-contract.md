<!-- SPDX-License-Identifier: MIT -->

## Pipeline Contract

**Pipeline position.** **Stage 8 of 13.** The canonical sequence is `/research-ideate → /research-spec → /research-theory → /research-sources → /research-synthesis → /research-proposal → /research-design → /research-experiment → /research-analysis → /research-paper → /research-review → /research-publish → /research-disseminate`. This stage consumes the operationalized design and the frozen analysis plan the design stage produced and emits the raw data plus the provenance the analysis stage consumes.

**Handoff Manifest.**

- **Consumed.** `{suite}/_inputs/study-design.md` (the operationalized predictions, variables, controls, sample, instruments, and threats-to-validity from `/research-design`) and `{suite}/_inputs/preregistration.md` (the frozen analysis plan per R5). The Handoff Manifest at `{suite}/_inputs/handoff-manifest.yml` per `src/apothem/schemas/handoff-manifest.yaml` is read for the predecessor stage's attestation block. The register row of a contingency that fires is read from `{suite}/_inputs/proposal.md` §4.
- **Emitted.** `{suite}/_outputs/experiment-log.md` (the timestamped protocol trace), the raw data at a host-natural location discovered per `rules/host-discovery.md` (e.g. `data/`), and `{suite}/_outputs/reproducibility-manifest.md` (the environment snapshot, the seed, the protocol log, and the version pins per R2). The manifest's `invocation_sequence` increments, `downstream` names `/research-analysis`, and the attestation records the protocol-adherence-vs-deviation outcome.

**Pre-flight inquiry set.** Phase 1 (Pre-Run Validation) emits the typed inquiry set per `rules/authority-inquiry.md` when the raw-data destination is undeclared (a real-world path binding per the Infrastructure inquiry category), when the seed source is unspecified for a stochastic protocol, when the protocol step the design names cannot execute as written, or when execution would touch human-subject, animal, or private data the ethics declaration does not yet cover (R6). Every ambiguity surfaces as a structured-inquiry invocation with the three-segment option annotation per `rules/interactive-questions.md` §3. Infrastructure (data destination), security (data-privacy posture), and any human-subject inquiry block emission until answered.

**Pre-emission gate.** Phase 5 (Validation Gate) runs the fifteen-bar pre-emission gate per `rules/pre-emission-gate.md` against the candidate `_outputs/experiment-log.md` and `_outputs/reproducibility-manifest.md` before the manifest update. The gate attestation block is recorded inside the emitted experiment log. Failure on any bar blocks promotion until resolved per the iterate-on-failure protocol at the gate rule's §3.
