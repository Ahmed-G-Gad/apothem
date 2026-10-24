<!-- SPDX-License-Identifier: MIT -->

### Phase 5 — Validation Gate

Run the fifteen-bar pre-emission gate per `rules/pre-emission-gate.md` against the candidate review report; the bars that bite hardest at this stage:

- **M5 authority** — zero fabricated findings; every required revision cites the manuscript locus it targets and the standard it fails against (R4).
- **Review completeness (stage check beyond the fifteen bars)** — both logged passes are present, the could-not-judge list and the 1-5 confidence are filled for every axis, and the pre-screen figures are recorded.
- **M7 option annotation** — the overall verdict is an annotated decision (`accept` · `minor-revision` · `major-revision` · `reject`) with the recommended verdict marked and its concrete-driver rationale per `rules/option-annotation.md`.
- **M8 definitiveness** — no hedging in the critique prose; every finding is a definitive defect at a named locus, not a softened suggestion.
- **M9 visual leverage** — the seven-axis scorecard is a table and the finding-severity distribution is a table or chart, each carrying the metadata header per `rules/visual-leverage.md`.
- **M14 systemicity** — the report declares its upstream (paper + suite evidence), downstream (`/research-publish`), peers (sibling research-suite artifacts), and enforcers (the `fact-checker` pass).

Iterate on failure per the gate rule's §3 until every bar passes or its three-round cap returns BLOCKED; record the attestation block inside the report and update the Handoff Manifest. Apply incremental generation per `rules/large-file-generation.md` when the report exceeds 500 lines.
