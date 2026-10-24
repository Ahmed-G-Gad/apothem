<!-- SPDX-License-Identifier: MIT -->

## Pipeline Contract

**Pipeline position.** Terminal review-fortress command at the a11y slot. It consumes the deployed web surface state — every reachable rendered page under the operator-supplied root — and emits read-only accessibility diagnostics for downstream remediation. It modifies no source.

**Audit-fortress sequence.** Position **7 of 11**. **Upstream:** `/ux-review`. **Downstream:** `/docs-review`. Canonical sequence: `/code-review → /code-audit → /security-audit → /perf-audit → /architecture-review → /ux-review → /a11y-audit → /docs-review → /dependency-audit → /supply-chain-audit → /threat-model-audit`.

**Handoff Manifest.**

- **Consumed.** The deployed web surface (filesystem path to a rendered static site, staging URL, or production URL). No upstream manifest is required; the command operates against deployed state. When a Handoff Manifest exists at `_inputs/handoff-manifest.yml`, prior fortress attestations are read as context but do not gate execution.
- **Emitted.** The findings artifact at `_inputs/a11y-audit-findings.md`, plus an optional Handoff Manifest augmentation carrying the per-page finding count, per-severity breakdown, per-WCAG-criterion attestation, per-axis seven-axes attestation, and the audit's `verified:` date.

**Pre-flight inquiry.** Phase 0 emits the typed inquiry set per `rules/authority-inquiry.md` when the deployed-surface shape is ambiguous (the root URL returns no reachable pages; the focus argument points at a non-existent page; the rendered site requires authentication credentials the audit does not carry). Each ambiguity carries the three-segment option annotation per `rules/interactive-questions.md` §3.

**Pre-emission gate.** Phase 4 runs the fifteen-bar pre-emission gate (`rules/pre-emission-gate.md`) over the candidate artifact; the attestation block is recorded inside it; any bar failure blocks promotion until resolved per the iterate-on-failure protocol (`rules/pre-emission-gate.md` §3).

### Inquiry Cadence (D4)

Operate at **maximal structured-inquiry saturation**. Every severity ratification, borderline WCAG-conformance call (e.g. contrast at 4.49:1 versus the 4.5:1 floor), axis-attestation gap, and gate-bar `n/a (with reason)` marking routes through the canonical channel (`rules/interactive-questions.md` §1) — free-form prose questions as primary input are forbidden. Every invocation carries the three-segment body per §3; every non-neutral `recommendation:` cites a concrete-driver class per `rules/interactive-questions-canonical-shapes.md` §3.2.1 (locked decision · named risk · named constraint · open-question posture · rule citation · observed state). Up to four questions batch per invocation. Question-fatigue-optimization is FORBIDDEN.
