<!-- SPDX-License-Identifier: MIT -->

### Phase 5 — Validation Gate

Run the fifteen-bar pre-emission gate per `rules/pre-emission-gate.md` against the candidate analysis; the bars that bite hardest at this stage:

- **M5 authority** — zero fabricated numbers; every effect, interval, and corrected threshold traces to a reproducible computation on the raw data (R2).
- **M8 definitiveness** — no hedging in the results prose; every result is a definitive reported effect with its interval, and a null is stated as a null, not softened.
- **M9 visual leverage** — every effect-size-with-CI distribution is a figure (forest plot, interval plot, or host-discovered equivalent) and the per-test results are a table, each carrying the metadata header per `rules/visual-leverage.md`; where a method spends a budget or repeats stochastically, the figure set also carries the **convergence curves**, the **per-condition distribution plots** (box or violin), and — when more than two methods are ranked across instances — the **rank critical-difference diagram** (`skills/research-suite/references/empirical-comparison-rigor.md`).
- **Advancement gate** — before a headline result may anchor the paper, it MUST clear an explicit advancement gate: the contribution beats its declared comparators convincingly *and* significantly under the Phase 3 nonparametric battery with a meaningful effect size, meeting the preregistered thresholds, and the required evidence artifacts (raw records, computed statistics, figures, reproducibility manifest, comparator provenance) are present. A significant-but-negligible margin or a large-but-non-significant margin does not clear the gate; the result routes to §7 Null & Fragile and is never promoted. Each clearance is logged as an auditable runbook entry — the passed clauses, the supporting-evidence paths, and the promote-or-redesign verdict (R5/R7; `skills/research-suite/references/advancement-gate.md`).
- **M13 code craft** — the analysis code passes the host's lint / format / type-check and pins its statistics-toolchain versions (R2).
- **M14 systemicity** — the analysis declares its upstream (raw data + preregistration), downstream (`/research-paper`), peers (sibling research-suite artifacts), and enforcers (the `fact-checker` pass + the reproducibility manifest).

Iterate on failure per the gate rule's §3 until every bar passes or its three-round cap returns BLOCKED; record the attestation block inside the analysis and update the Handoff Manifest. Apply incremental generation per `rules/large-file-generation.md` when the analysis exceeds 500 lines.
