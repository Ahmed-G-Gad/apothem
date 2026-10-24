<!-- SPDX-License-Identifier: MIT -->

## Pipeline Contract

**Pipeline position.** Terminal review-fortress command at the final slot; its PASS verdict ratifies TIER 3 review-fortress convergence. It consumes the architectural surface plus the security-, dependency-, and supply-chain-audit findings, and emits read-only threat-model diagnostics for downstream remediation. It modifies no source.

**Audit-fortress sequence.** Position **11 of 11 (final, terminal)**. **Upstream:** `/supply-chain-audit`. **Downstream:** none. Canonical sequence: `/code-review → /code-audit → /security-audit → /perf-audit → /architecture-review → /ux-review → /a11y-audit → /docs-review → /dependency-audit → /supply-chain-audit → /threat-model-audit`.

**Handoff Manifest.**

- **Consumed.** The architectural surface — source layout, integration adapters, external-interface declarations, configuration (env vars, secrets, network endpoints, file-system paths), CI workflow surface (build/release trust boundaries). Plus the upstream fortress artifacts at `_inputs/security-audit-findings.md`, `_inputs/dependency-audit-findings.md`, and `_inputs/supply-chain-audit-findings.md` — the per-vulnerability inventory the threat model contextualizes. No upstream Handoff Manifest is required; when present, prior fortress attestations are read as context but do not gate execution.
- **Emitted.** The findings artifact at `_inputs/threat-model-audit-findings.md`, plus an optional Handoff Manifest augmentation carrying the per-threat finding count, per-severity breakdown, trust-boundary inventory, STRIDE-coverage matrix, per-axis seven-axes attestation, and the audit's `verified:` date.

**Pre-flight inquiry.** Phase 0 emits the typed inquiry set per `rules/authority-inquiry.md` when the surface is ambiguous (threat-actor taxonomy unstated; residual-risk acceptance authority undeclared; data-classification scheme absent). Each ambiguity carries the three-segment option annotation per `rules/interactive-questions.md` §3.

**Pre-emission gate.** Phase 4 runs the fifteen-bar pre-emission gate (`rules/pre-emission-gate.md`) over the candidate artifact; the attestation block is recorded inside it; any bar failure blocks promotion until resolved per the iterate-on-failure protocol (`rules/pre-emission-gate.md` §3).

### Inquiry Cadence (D4)

Operate at **maximal structured-inquiry saturation**. Every severity ratification, threat-actor classification (nation-state vs financially-motivated vs opportunistic vs insider), STRIDE-category interpretation (Tampering vs Elevation-of-privilege on a borderline data-write path), residual-risk-acceptance vs open-mitigation call, axis-attestation gap, and gate-bar `n/a (with reason)` marking routes through the canonical channel (`rules/interactive-questions.md` §1) — free-form prose questions as primary input are forbidden. Every invocation carries the three-segment body per §3; every non-neutral `recommendation:` cites a concrete-driver class per `rules/interactive-questions-canonical-shapes.md` §3.2.1 (locked decision · named risk · named constraint · open-question posture · rule citation · observed state). Up to four questions batch per invocation. Question-fatigue-optimization is FORBIDDEN.
