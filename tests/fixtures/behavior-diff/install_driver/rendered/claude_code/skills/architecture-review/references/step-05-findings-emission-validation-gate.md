<!-- SPDX-License-Identifier: MIT -->

### Phase 4 — Findings Emission + Validation Gate

Emit the target's `_inputs/architecture-review-findings.md` with the canonical sections:

1. **`## §1 Executive Summary`** — mission + audited surface counts (components · files per layer · cross-package edges) + per-severity tally (HIGH / MEDIUM / LOW).
2. **`## §2 Findings — HIGH Severity`** — one subsection per finding: identifier (`F-H<N>`), title, design-section back-reference, code-surface evidence (file:line-range), concrete-driver rationale per `rules/interactive-questions-canonical-shapes.md` §3.2.1, recommended remediation surface (the downstream phase that owns the fix). Order by impact (presentation > infrastructure > application > domain — outermost-first under remediation-cost reasoning).
3. **`## §3 Findings — MEDIUM Severity`** — §2 shape (`F-M<N>`).
4. **`## §4 Findings — LOW Severity`** — §2 shape (`F-L<N>`).
5. **`## §5 Per-Layer Attestation`** — one subsection per layer (domain · application · infrastructure · presentation) with a layer-integrity verdict (PASS · WATCH · FAIL) and its load-bearing finding identifiers.
6. **`## §6 Seven-Axes Coverage`** — per-axis verdict against the seven-axes-of-breadth taxonomy (`rules/cognitive-identity.md` §1).
7. **`## §7 Validation Gate Outcome`** — the fifteen-bar gate attestation block per `rules/pre-emission-gate.md` §2.
8. **`## §8 Bindings (§0.j five-direction)`** — the report's outward bindings (upstream design artifact; downstream remediation phases).

Apply incremental generation per `rules/large-file-generation.md` above 500 lines (plan sections first; Write the first; Edit-append the rest; verify transition coherence at each boundary).

**Validation gate.** Run the fifteen-bar gate per `rules/pre-emission-gate.md`; the canonical per-bar table is at `rules/pre-emission-gate-bars.md` §1. Architecture-review deltas: **M5** (every cited file path, line range, and import statement is verified to exist; zero fabrication); **M9** (the package dependency graph carries a Mermaid `graph LR` diagram per `rules/visual-leverage.md` — **not** n/a for this command); **M10** (every finding's design-section back-reference closes reciprocally); **M14** (every finding declares its upstream design-section + downstream remediation surface). N/A (reason recorded): M11 (single-sprint), M13 (no executable code), M15 (findings precede production-readiness). Iterate on failure per `rules/pre-emission-gate-bars.md` §3 until every bar passes or its three-round cap returns BLOCKED.
