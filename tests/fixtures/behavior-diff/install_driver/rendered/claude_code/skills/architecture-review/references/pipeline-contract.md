<!-- SPDX-License-Identifier: MIT -->

## Pipeline Contract

**Pipeline position.** **Terminal review-fortress command.** Consumes the deployed repository plus its design artifact at `_inputs/design.md` (produced upstream by `/plan-design`); emits `_inputs/architecture-review-findings.md` consumed by remediation phases. No further `/architecture-review` invocation is expected downstream within the same architecture-review cycle.

**Audit-fortress sequence position.** **Upstream:** `/perf-audit`. **Downstream:** `/ux-review`. Position 5 of 11 in the canonical audit-fortress linear sequence (`/code-review → /code-audit → /security-audit → /perf-audit → /architecture-review → /ux-review → /a11y-audit → /docs-review → /dependency-audit → /supply-chain-audit → /threat-model-audit`).

**Handoff Manifest.**

- **Consumed.** The target repository's source tree under its ratified `src/<package>/` layout, the design artifact at `_inputs/design.md`, the suite's `_inputs/handoff-manifest.yml` per `src/apothem/schemas/handoff-manifest.yaml`. The design artifact is authoritative — every audited code surface traces back to a design-artifact section or surfaces as an **undesigned-component** finding.
- **Emitted.** The findings report at `_inputs/architecture-review-findings.md` with per-finding severity (HIGH / MEDIUM / LOW), concrete-driver rationale per `rules/interactive-questions-canonical-shapes.md` §3.2.1, design-section back-reference, and recommended remediation surface. The handoff manifest is augmented with the findings-report path and the per-axis attestation against the seven-axes-of-breadth taxonomy.

**Pre-flight inquiry set.** Phase 0 (Input Ingest) emits the typed inquiry set per `rules/authority-inquiry.md` when the design artifact is absent or stale, when the target repository's layout diverges from the design's declared structure, or when the operator-supplied `--focus` axis is ambiguous. Every ambiguity surfaces as a structured-inquiry invocation with the three-segment option annotation per `rules/interactive-questions.md` §3.

**Pre-emission gate.** Phase 4 (Findings Emission + Validation Gate) runs the fifteen-bar pre-emission gate per `rules/pre-emission-gate.md` against the candidate findings report before promotion. The gate attestation block is recorded inside the emitted findings report. Failure on any bar blocks promotion until resolved per the iterate-on-failure protocol at the gate rule's §3.

### Inquiry Cadence (D4)

This command operates at **maximal structured-inquiry saturation**. Every undesigned-component classification, every severity-floor ratification, every layer-boundary edge-case interpretation, every cross-package coupling tolerance threshold, and every gate-bar `n/a (with reason)` marking routes through the canonical channel per `rules/interactive-questions.md` §1 (free-form prose questions as primary input are forbidden). Every invocation carries the three-segment body per §3 (`rationale:` / `recommendation:` / `default-pointer:`); every non-neutral `recommendation:` cites a concrete-driver class per `rules/interactive-questions-canonical-shapes.md` §3.2.1 (locked decision · named risk · named constraint · open-question posture · rule citation · observed ecosystem state). Up to four questions may batch per invocation. **Question-fatigue-optimization is FORBIDDEN.**
