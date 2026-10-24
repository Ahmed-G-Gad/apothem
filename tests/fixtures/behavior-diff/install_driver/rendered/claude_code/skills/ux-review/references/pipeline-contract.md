<!-- SPDX-License-Identifier: MIT -->

## Pipeline Contract

**Pipeline position.** Terminal review-fortress command inside the developer-experience cluster. It consumes the deployed host repository plus its operator-facing surfaces and emits the developer-experience findings ledger the fortress phase aggregates alongside sibling reviews (`/a11y-audit`, `/docs-review`, etc.). It modifies no source.

**Audit-fortress sequence.** Position **6 of 11**. **Upstream:** `/architecture-review`. **Downstream:** `/a11y-audit`. Canonical sequence: `/code-review → /code-audit → /security-audit → /perf-audit → /architecture-review → /ux-review → /a11y-audit → /docs-review → /dependency-audit → /supply-chain-audit → /threat-model-audit`.

**Handoff Manifest.**

- **Consumed.** The deployed repository at the supplied path — the installed CLI binary, the install/update/uninstall scripts at the repo root, the rendered documentation site (or the source Markdown when no site is built), the README header, and every CLI subcommand's `--help` output. When a Handoff Manifest exists at `_inputs/handoff-manifest.yml`, the upstream design artifact's CLI-surface declarations are honored as the ratified contract the review measures against.
- **Emitted.** The findings ledger at `_inputs/ux-review-findings.md` carrying per-finding severity (HIGH/MEDIUM/LOW), concrete-driver rationale, observed surface (file path + line range or CLI invocation + stderr capture), and proposed remediation. The downstream fortress phase reads it as one of N sibling review outputs.

**Pre-flight inquiry.** Phase 0 emits the typed inquiry set per `rules/authority-inquiry.md`. Every scope ambiguity — target harness (POSIX/PowerShell/both), the documentation site's rendered URL when build artifacts are absent, the supported-versions matrix, the deployment mode (local checkout / installed binary / containerized) — surfaces with the three-segment option annotation per `rules/interactive-questions.md` §3.

**Pre-emission gate.** Phase 4 runs the fifteen-bar pre-emission gate (`rules/pre-emission-gate.md`) over the candidate ledger; the attestation block is recorded inside it and surfaced in the Handoff Manifest; any bar failure blocks promotion until resolved per the iterate-on-failure protocol.

### Inquiry Cadence (D4)

Operate at **maximal structured-inquiry saturation**. Every review-scope decision, severity ratification, concrete-driver citation choice, diagram-provenance choice, and gate-bar `n/a (with reason)` marking routes through the canonical channel (`rules/interactive-questions.md` §1) — free-form prose questions as primary input are forbidden. Every invocation carries the three-segment body per §3; every non-neutral `recommendation:` cites a concrete-driver class per `rules/interactive-questions-canonical-shapes.md` §3.2.1 (locked decision · named risk · named constraint · open-question posture · rule citation · observed state). Up to four questions batch per invocation. **Question-fatigue-optimization is FORBIDDEN.**
