<!-- SPDX-License-Identifier: MIT -->

## Pipeline Contract

**Pipeline position.** **Terminal review-fortress command.** This command sits at the docs-fortress slot of the audit-fortress sequence. It consumes the deployed documentation corpus state — every Markdown page under the host docs source plus the host's ratified documentation singletons — and emits the findings artifact downstream remediation cycles consume. The command does not modify source; the findings are read-only diagnostics.

**Audit-fortress sequence position.** **Upstream:** `/a11y-audit`. **Downstream:** `/dependency-audit`. Position 8 of 11 in the canonical audit-fortress linear sequence (`/code-review → /code-audit → /security-audit → /perf-audit → /architecture-review → /ux-review → /a11y-audit → /docs-review → /dependency-audit → /supply-chain-audit → /threat-model-audit`).

**Handoff Manifest.**

- **Consumed.** The repository's documentation corpus (`site/content/docs/**/*.{md,mdx}` plus root-level documentation singletons for Apothem). No upstream manifest is required; the command operates against the on-disk state. When the consuming suite carries a Handoff Manifest at `_inputs/handoff-manifest.yml`, the prior fortress-phase attestations are read as context but do not gate execution.
- **Emitted.** The findings artifact at `_inputs/docs-review-findings.md` plus an optional Handoff Manifest augmentation with the per-page finding count, the per-severity breakdown, the per-dimension-failure breakdown (against the ten dimensions), the per-axis attestation against the seven-axes-of-breadth taxonomy, and the review's `verified:` date.

**Pre-flight inquiry set.** Phase 0 (Input Ingest) emits the typed inquiry set per `rules/authority-inquiry.md` when the documentation-corpus shape is ambiguous (e.g., the docs source directory is absent, the focus argument points at a non-existent path, the host's docs-site generator is not host-discoverable). Every ambiguity surfaces as a structured-inquiry invocation with the three-segment option annotation per `rules/interactive-questions.md` §3.

**Pre-emission gate.** Phase 4 (Validation Gate) runs the fifteen-bar pre-emission gate per `rules/pre-emission-gate.md` against the candidate findings artifact before promotion. The gate attestation block is recorded inside the emitted findings artifact. Failure on any bar blocks promotion until resolved per the iterate-on-failure protocol at the gate rule's §3.

### Inquiry Cadence (D4)

This command operates at **maximal structured-inquiry saturation**. Every severity ratification (HIGH / MEDIUM / LOW), every borderline hedge-elimination call, every broken-link / stale-citation triage call, every axis-attestation gap, and every gate-bar `n/a (with reason)` marking routes through the canonical channel per `rules/interactive-questions.md` §1 (free-form prose questions as primary input are forbidden). Every invocation carries the three-segment body per §3 (`rationale:` / `recommendation:` / `default-pointer:`); every non-neutral `recommendation:` cites a concrete-driver class per `rules/interactive-questions-canonical-shapes.md` §3.2.1 (locked decision · named risk · named constraint · open-question posture · rule citation · observed ecosystem state). Up to four questions may batch per invocation. **Question-fatigue-optimization is FORBIDDEN.**
