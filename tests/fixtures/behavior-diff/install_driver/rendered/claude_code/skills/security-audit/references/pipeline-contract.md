<!-- SPDX-License-Identifier: MIT -->

## Pipeline Contract

**Pipeline position.** **Terminal review-fortress command.** This command consumes the deployed repository at its current HEAD and emits the security-audit findings artifact downstream operators consume during fortress triage. It does not feed a further `/plan` stage; its output is the ratified record of the security posture at audit time.

**Audit-fortress sequence position.** **Upstream:** `/code-audit`. **Downstream:** `/perf-audit`. Position 3 of 11 in the canonical audit-fortress linear sequence (`/code-review → /code-audit → /security-audit → /perf-audit → /architecture-review → /ux-review → /a11y-audit → /docs-review → /dependency-audit → /supply-chain-audit → /threat-model-audit`).

**Handoff Manifest.**

- **Consumed.** The consuming suite's `_inputs/handoff-manifest.yml` per the schema at `src/apothem/schemas/handoff-manifest.yaml` when invoked from a plan-suite context. The manifest names the repository path, the audit scope (full / focused via `--focus`), and any prior audit's findings artifact for delta comparison.
- **Emitted.** The same manifest augmented with the findings-artifact path (`_inputs/security-audit-findings.md`), the per-category severity counts (HIGH / MEDIUM / LOW), the OWASP ASVS coverage attestation, the CWE Top 25 coverage attestation, and the Phase 5 validation-gate attestation block.

**Pre-flight inquiry set.** Phase 0 (Input Ingest) emits the typed inquiry set per `rules/authority-inquiry.md`. Every authority-bearing audit decision — secrets-rotation cadence, accepted-risks list, trusted-action allowlist, MCP-server auth endpoint specifics, false-positive triage outcomes — surfaces as a structured-inquiry invocation with the three-segment option annotation per `rules/interactive-questions.md` §3.

**Pre-emission gate.** Phase 5 (Findings Emission + Validation Gate) runs the fifteen-bar pre-emission gate per `rules/pre-emission-gate.md` against the candidate findings artifact before promotion. The gate attestation block is recorded inside the emitted findings artifact and surfaced in the Handoff Manifest. Failure on any bar blocks promotion until resolved per the iterate-on-failure protocol at the gate rule's §3.

### Inquiry Cadence (D4)

This command operates at **maximal structured-inquiry saturation**. Every HIGH/MEDIUM-boundary classification, every accepted-risk ratification, every false-positive disposition, every dependency-CVE waiver, every CodeQL triage, and every gate-bar `n/a (with reason)` marking routes through the canonical channel per `rules/interactive-questions.md` §1 (free-form prose questions as primary input are forbidden). Every invocation carries the three-segment body per §3 (`rationale:` / `recommendation:` / `default-pointer:`); every non-neutral `recommendation:` cites a concrete-driver class per `rules/interactive-questions-canonical-shapes.md` §3.2.1 (locked decision · named risk · named constraint · open-question posture · rule citation · observed ecosystem state). Up to four questions may batch per invocation. **Question-fatigue-optimization is FORBIDDEN.**
