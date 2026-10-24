<!-- SPDX-License-Identifier: MIT -->

### Phase 5 — Validation Gate

Run the fifteen-bar pre-emission gate per `rules/pre-emission-gate.md` against the publication record and the assembled package; the bars that bite hardest at this stage:

- **M5 authority** — zero fabricated declarations; every author name, affiliation, ethics identifier, funding source, COI fact, and DOI traces to operator-supplied or suite-recorded data, with no unfilled authority-inquiry placeholder remaining (R6).
- **M8 definitiveness** — the cover letter and declarations carry no hedging; the data/code-availability statement is definitive about where artifacts live and under what terms.
- **M9 visual leverage** — the submission checklist renders as a requirement × verdict table and the package manifest as a table, each carrying the metadata header per `rules/visual-leverage.md`.
- **M13 code craft** — any packaging/build scripts pass the host's lint / format / build.
- **M14 systemicity** — the publication record declares its upstream (paper + review report), downstream (`/research-disseminate`, after the operator-submission hand-off), peers (sibling research-suite artifacts), and enforcers (the `fact-checker` citation-and-declaration pass + the submission checklist).
- **M15 production-readiness** — the package is complete and venue-conformant in the same emission; no "I'll add the COI statement later".

Iterate on failure per the gate rule's §3 until every bar passes or its three-round cap returns BLOCKED; record the attestation block inside the publication record and update the Handoff Manifest with `downstream: /research-disseminate`. Apply incremental generation per `rules/large-file-generation.md` when the publication record exceeds 500 lines.
