<!-- SPDX-License-Identifier: MIT -->

## Pipeline Contract

**Pipeline position.** Entry diagnostic surface of the audit-fortress sequence. Consumes the deployed repository's source tree under `src/` + `scripts/` + `tools/`; emits the read-only findings artifact that remediation cycles consume. Modifies no source.

**Audit-fortress sequence position.** `/code-review` is the **entry point** of the canonical 11-command audit-fortress linear sequence (`/code-review → /code-audit → /security-audit → /perf-audit → /architecture-review → /ux-review → /a11y-audit → /docs-review → /dependency-audit → /supply-chain-audit → /threat-model-audit`). **Upstream:** none from the fortress (entered from `/plan-execute`'s Step 9 handoff). **Downstream:** `/code-audit`.

**Handoff Manifest.**

- **Consumed.** The deployed repository's source tree. No upstream manifest required — the command operates against on-disk state. A Handoff Manifest at `_inputs/handoff-manifest.yml`, when present, is read as context but does not gate execution.
- **Emitted.** The findings artifact at `_inputs/code-review-findings.md`, plus an optional manifest augmentation carrying the per-file finding count, the per-severity breakdown, the per-axis attestation against the seven-axes-of-breadth taxonomy, and the review's `verified:` date.

**Pre-flight inquiry set.** Phase 0 emits the typed inquiry set per `rules/authority-inquiry.md` when the source-tree shape is ambiguous (e.g., `src/` absent, or `--focus` points at a non-existent path). Every ambiguity surfaces through the structured-inquiry channel with the three-segment option annotation per `rules/interactive-questions.md` §3.

**Pre-emission gate.** Phase 4 runs the fifteen-bar pre-emission gate per `rules/pre-emission-gate.md` against the candidate artifact before promotion; the attestation block is recorded inside the emitted artifact. Any bar failure blocks promotion until resolved per the iterate-on-failure protocol at `rules/pre-emission-gate-bars.md` §3.

### Inquiry Cadence (D4)

This command operates at **maximal structured-inquiry saturation**. Every severity ratification (HIGH / MEDIUM / LOW), every borderline idiom-conformance call, every axis-attestation gap, and every gate-bar `n/a (with reason)` marking routes through the canonical channel per `rules/interactive-questions.md` §1 (free-form prose questions as primary input are forbidden). Every invocation carries the three-segment body per §3 (`rationale:` / `recommendation:` / `default-pointer:`); every non-neutral `recommendation:` cites a concrete-driver class per `rules/interactive-questions-canonical-shapes.md` §3.2.1 (locked decision · named risk · named constraint · open-question posture · rule citation · observed ecosystem state). Up to four questions may batch per invocation. **Question-fatigue-optimization is FORBIDDEN.**
