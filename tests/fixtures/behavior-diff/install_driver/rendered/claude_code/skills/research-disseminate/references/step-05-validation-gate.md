<!-- SPDX-License-Identifier: MIT -->

### Phase 5 — Validation Gate

Run the fifteen-bar pre-emission gate per `rules/pre-emission-gate.md` against the dissemination plan; the bars that bite hardest at this stage:

- **M5 authority** — zero fabricated identifiers; every DOI, archival accession, and impact metric traces to a real deposit or operator-supplied data, with no unfilled authority-inquiry placeholder remaining (R8, R10).
- **M8 definitiveness** — the public artifacts and the impact-tracking plan carry no hedging; the FAIR deposit record is definitive about where artifacts live and under what terms.
- **M9 visual leverage** — the dissemination-readiness checklist renders as a requirement × verdict table and the impact-tracking plan as an impact-pathway diagram, each carrying the metadata header per `rules/visual-leverage.md`.
- **M14 systemicity** — the dissemination plan declares its upstream (the publication record), downstream (`operator dissemination` — terminal), peers (sibling research-suite artifacts), and enforcers (the `fact-checker` identifier-and-claim pass + the readiness checklist).
- **M15 production-readiness** — the dissemination plan is complete in the same emission; no "I'll add the FAIR deposit later".

Iterate on failure per the gate rule's §3 until every bar passes or its three-round cap returns BLOCKED; record the attestation block inside the dissemination plan and close the Handoff Manifest with `downstream: operator dissemination (terminal)`. Apply incremental generation per `rules/large-file-generation.md` when the dissemination plan exceeds 500 lines.
