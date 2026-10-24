<!-- SPDX-License-Identifier: MIT -->

## Pipeline Contract

**Pipeline position.** Terminal review-fortress command at the supply-chain slot. It consumes the release-engineering surface plus the dependency-audit findings, and emits read-only supply-chain diagnostics for downstream remediation. It modifies no source.

**Audit-fortress sequence.** Position **10 of 11**. **Upstream:** `/dependency-audit`. **Downstream:** `/threat-model-audit`. Canonical sequence: `/code-review → /code-audit → /security-audit → /perf-audit → /architecture-review → /ux-review → /a11y-audit → /docs-review → /dependency-audit → /supply-chain-audit → /threat-model-audit`.

**Handoff Manifest.**

- **Consumed.** The release-engineering surface — `.github/workflows/*.yml`, release scripts (`scripts/`, `Makefile`), signing config (`cosign.pub`, `.sigstore/`), SBOM config (CycloneDX/SPDX), REUSE config (`REUSE.toml`, `.reuse/`), and OpenSSF Scorecard config. Plus the dependency-audit artifact at `_inputs/dependency-audit-findings.md` (CVE inventory + license matrix). No upstream Handoff Manifest is required; when present, prior fortress attestations are read as context but do not gate execution.
- **Emitted.** The findings artifact at `_inputs/supply-chain-audit-findings.md`, plus an optional Handoff Manifest augmentation carrying the per-axis finding count, per-severity breakdown, SLSA-level attestation, Scorecard-score snapshot, per-axis seven-axes attestation, and the audit's `verified:` date.

**Pre-flight inquiry.** Phase 0 emits the typed inquiry set per `rules/authority-inquiry.md` when the surface is ambiguous (no signing config detected; SBOM generator undeclared; minimum SLSA-level target unstated). Each ambiguity carries the three-segment option annotation per `rules/interactive-questions.md` §3.

**Pre-emission gate.** Phase 4 runs the fifteen-bar pre-emission gate (`rules/pre-emission-gate.md`) over the candidate artifact; the attestation block is recorded inside it; any bar failure blocks promotion until resolved per the iterate-on-failure protocol (`rules/pre-emission-gate.md` §3).

### Inquiry Cadence (D4)

Operate at **maximal structured-inquiry saturation**. Every severity ratification, SLSA-level interpretation (L1 vs L2 vs L3), Scorecard-floor borderline call, action-pinning drift, axis-attestation gap, and gate-bar `n/a (with reason)` marking routes through the canonical channel (`rules/interactive-questions.md` §1) — free-form prose questions as primary input are forbidden. Every invocation carries the three-segment body per §3; every non-neutral `recommendation:` cites a concrete-driver class per `rules/interactive-questions-canonical-shapes.md` §3.2.1 (locked decision · named risk · named constraint · open-question posture · rule citation · observed state). Up to four questions batch per invocation. Question-fatigue-optimization is FORBIDDEN.
