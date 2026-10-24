<!-- SPDX-License-Identifier: MIT -->

## Pipeline Contract

**Pipeline position.** Terminal review-fortress command at the performance slot. It consumes the deployed repository plus the benchmark-suite outputs and emits the per-class audit report for downstream consumers and the operator's release-readiness sign-off. It modifies no source.

**Audit-fortress sequence.** Position **4 of 11**. **Upstream:** `/security-audit`. **Downstream:** `/architecture-review`. Canonical sequence: `/code-review → /code-audit → /security-audit → /perf-audit → /architecture-review → /ux-review → /a11y-audit → /docs-review → /dependency-audit → /supply-chain-audit → /threat-model-audit`.

**Handoff Manifest.**

- **Consumed.** The deployed source tree (`hooks/`, `tools/`, `tests/`, `agents/`, `hooks/lib/` shell stubs), the four benchmark drivers under `src/apothem/benchmarks/` (`bench_hooks.py`, `bench_validate_ecosystem.py`, `bench_tests.py`, `bench_agents.py`), and the per-class budget table at `rules/performance-discipline.md` §1.
- **Emitted.** The audit report at `_inputs/perf-audit-findings.md` carrying per-class measurements, exceedance deltas, USE-method hot-path identification, severity-classified findings, and a remediation backlog ratified for the fortress-phase consumer.

**Pre-flight inquiry.** Phase 1 surfaces every budget-override candidate (operator amendments per `rules/performance-discipline.md` §4) through the structured-inquiry channel (`rules/authority-inquiry.md`). Phase 2 surfaces every host-environment ambiguity (Python interpreter selection, shell availability, parallel-worker count) through the canonical channel with the three-segment annotation per `rules/interactive-questions.md` §3.

**Pre-emission gate.** Phase 4 runs the fifteen-bar pre-emission gate (`rules/pre-emission-gate.md`) over the candidate report; the attestation block is recorded inside it and surfaced in the audit handoff; any bar failure blocks promotion until resolved per the iterate-on-failure protocol (`rules/pre-emission-gate.md` §3).

### Inquiry Cadence (D4)

Operate at **maximal structured-inquiry saturation**. Every budget-override candidate, benchmark-driver invocation parameter, USE-axis classification choice (utilization vs saturation vs errors), severity-boundary edge case (a measurement landing at exactly 25% or 100%), and gate-bar `n/a (with reason)` marking routes through the canonical channel (`rules/interactive-questions.md` §1) — free-form prose questions as primary input are forbidden. Every invocation carries the three-segment body per §3; every non-neutral `recommendation:` cites a concrete-driver class per `rules/interactive-questions-canonical-shapes.md` §3.2.1 (locked decision · named risk · named constraint · open-question posture · rule citation · observed state). Up to four questions batch per invocation. **Question-fatigue-optimization is FORBIDDEN.**
