<!-- SPDX-License-Identifier: MIT -->

## Pipeline Contract

**Pipeline position.** **Terminal review-fortress command.** This command consumes the deployed repository (post-execution code at the host's canonical layout) and emits the cross-file forensic findings artifact downstream review-fortress consumers read.

**Audit-fortress sequence position.** **Upstream:** `/code-review` (per-file craft hand-off). **Downstream:** `/security-audit`. Position 2 of 11 in the canonical audit-fortress linear sequence (`/code-review → /code-audit → /security-audit → /perf-audit → /architecture-review → /ux-review → /a11y-audit → /docs-review → /dependency-audit → /supply-chain-audit → /threat-model-audit`).

**Handoff Manifest.**

- **Consumed.** The consuming suite's `_inputs/handoff-manifest.yml` per the schema at `src/apothem/schemas/handoff-manifest.yaml`. The upstream manifest carries the per-phase REPORTs and the production-deployment attestation. The Phase 0 input-ingest step at `## Workflow` reads the deployed-repository manifest as prerequisite evidence; a deployment whose CI gate fails blocks audit emission until resolved.
- **Emitted.** The same manifest augmented with the findings-artifact path (`_inputs/code-audit-findings.md`), the per-severity finding counts (HIGH / MEDIUM / LOW), the per-phase tool-output attestations (`mypy --strict` exit code · `vulture` finding count · duplicate-code finding count · coverage report path), and the Phase 5 validation-gate attestation block. Downstream review-fortress consumers read the findings artifact at every audit-bearing surface.

**Pre-flight inquiry set.** Phase 1 (Cross-File Dependency Walk) emits the typed inquiry set per `rules/authority-inquiry.md`. Every audit-scope gap — ambiguous module boundaries, undeclared layer assignments, missing test-coverage baseline, unratified severity thresholds — surfaces as a structured-inquiry invocation with the three-segment option annotation per `rules/interactive-questions.md` §3.

**Pre-emission gate.** Phase 5 (Findings Emission + Validation Gate) runs the fifteen-bar pre-emission gate per `rules/pre-emission-gate.md` against the candidate findings artifact before promotion. The gate attestation block is recorded inside the emitted artifact and surfaced in the Handoff Manifest. Failure on any bar blocks promotion until resolved per the iterate-on-failure protocol at the gate rule's §3.

### Inquiry Cadence (D4)

This command operates at **maximal structured-inquiry saturation**. Every severity-threshold ratification, every layer-assignment ambiguity, every dead-code-vs-public-API disambiguation, every duplicate-code consolidation choice, and every gate-bar `n/a (with reason)` marking routes through the canonical channel per `rules/interactive-questions.md` §1 (free-form prose questions as primary input are forbidden). Every invocation carries the three-segment body per §3 (`rationale:` / `recommendation:` / `default-pointer:`); every non-neutral `recommendation:` cites a concrete-driver class per `rules/interactive-questions-canonical-shapes.md` §3.2.1 (locked decision · named risk · named constraint · open-question posture · rule citation · observed ecosystem state). Up to four questions may batch per invocation. **Question-fatigue-optimization is FORBIDDEN.**
