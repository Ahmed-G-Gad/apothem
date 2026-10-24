<!-- SPDX-License-Identifier: MIT -->

### Phase 5 — Validation Gate

Run the fifteen-bar pre-emission gate per `rules/pre-emission-gate.md` against the assembled manuscript; the bars that bite hardest at this stage:

- **M5 authority** — zero invented citations, authors, or affiliations; every reference resolves to a real source and every author traces to operator-supplied identity (R4, R6).
- **M8 definitiveness** — no hedging in the manuscript prose; the contribution is a definitive claim the confirmed results support, and a limitation is stated as a limitation, not softened.
- **M9 visual leverage** — the method's design diagram and the results' effect-with-CI figure carry the metadata header per `rules/visual-leverage.md`.
- **M13 code craft** — any manuscript-build or figure-embed code passes the host's lint / format / type-check; the prose passes the host's prose-lint per `rules/code-craft-markdown.md`.
- **M14 systemicity** — the manuscript declares its upstream (synthesis + study design + analysis), downstream (`/research-review`), peers (sibling research-suite artifacts), and enforcers (the `fact-checker` pass + the reference ledger).

Confirm the selected EQUATOR reporting checklist is **complete** — every item satisfied or marked not-applicable with a reason — and ships with the manuscript (R9). Confirm the structured abstract carries its headings (or preserves the structure in prose where the venue requires unstructured), and confirm the author block carries each author's ORCID iD and CRediT roles (R6). Confirm the ethics, conflict-of-interest, and data/code-availability declarations are present (R6).

**Run the anonymization-completeness check when `--anonymized` is set (R6).** When `--anonymized` is active, run a gated double-blind-readiness check per `skills/research-suite/references/blinding-and-disclosure.md` that clears only when every bar holds: no residual author, institution, funding, or system/tool identifier leaks into the manuscript body — not in prose, captions, acknowledgements, metadata, or repository/artifact handles that reconstruct identity; every self-citation is phrased de-anonymization-safe (a neutral third-person reference to a prior contribution, never a first-person one that reveals authorship); and the held-out identity is recorded as the designated de-anonymization payload in the attestation so the publish stage restores it exactly. A manuscript that does not clear every bar is not double-blind-ready and does not advance until the leak is remediated and the check is re-run.

Iterate on failure per the gate rule's §3 until every bar passes or its three-round cap returns BLOCKED; record the attestation block in `{suite}/_outputs/paper-attestation.md` and update the Handoff Manifest.
