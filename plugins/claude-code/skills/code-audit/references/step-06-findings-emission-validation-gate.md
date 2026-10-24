<!-- SPDX-License-Identifier: MIT -->

### Phase 5 — Findings Emission + Validation Gate

Emit the consuming suite's `_inputs/code-audit-findings.md` with the canonical sections:

1. **`## §1 Executive Summary`** — audit scope + per-severity counts (HIGH / MEDIUM / LOW) + per-phase tool-output attestations (`mypy --strict` exit code, `vulture` count, duplicate-code count, coverage % against critical paths) + any `--focus` narrowing.
2. **`## §2 HIGH-Severity Findings`** — each as `Finding-NN: <one-sentence summary>` + Location (file:line-range) · Rationale (concrete-driver class per `rules/interactive-questions-canonical-shapes.md` §3.2.1) · Recommended Remediation · Reversibility note · Recurrence count.
3. **`## §3 MEDIUM-Severity Findings`** — §2 shape.
4. **`## §4 LOW-Severity Findings`** — §2 shape.
5. **`## §5 Per-Phase Tool-Output Attestations`** — per forensic phase, the tool invocation, exit code, and parsed finding count (provenance trail).
6. **`## §6 Open Audit Questions`** — every deferred structured-inquiry question with its inquiry-id and recommended option.
7. **`## §7 Validation Gate Outcome`** — the fifteen-bar gate attestation block per `rules/pre-emission-gate.md` §2.
8. **`## §8 Bindings (§0.j five-direction)`** — the artifact's outward bindings.

Apply incremental generation per `rules/large-file-generation.md` above 500 lines (plan sections first; Write the first; Edit-append the rest; verify transition coherence at each boundary).

Run the fifteen-bar gate per `rules/pre-emission-gate.md`; the canonical per-bar table is at `rules/pre-emission-gate-bars.md` §1. Audit-tier deltas: **M5** (every finding cites a verified `file:line`; no fabrication); **M7** (every severity-threshold / layer-assignment / dead-code-vs-API call carries `**Recommended**` + concrete-driver rationale); **M14** (declare upstream `/code-review` + deployed repo, downstream `/security-audit` + remediation, peers fortress siblings, enforcers `mypy` / `vulture` / `pylint` / coverage). N/A (reason recorded): M11 (single-sprint), M15 (production-ready applies at remediation). Iterate on failure until every bar passes within the three-round cap of `rules/pre-emission-gate-bars.md` §3 (then BLOCKED), then emit the attestation block.
