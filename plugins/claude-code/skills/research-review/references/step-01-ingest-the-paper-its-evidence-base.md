<!-- SPDX-License-Identifier: MIT -->

### Phase 1 — Ingest the Paper & Its Evidence Base

Read the paper deliverable in full per the locate-before-read discipline at `rules/large-file-reading.md`, then read the suite evidence artifacts its claims rest on:

- `{suite}/_inputs/synthesis.md` — the SOTA map the novelty claim depends on.
- `{suite}/_inputs/study-design.md` + `{suite}/_inputs/preregistration.md` — the frozen plan the method section must match.
- `{suite}/_outputs/analysis.md` — the confirmed results the paper reports.

Resolve the target venue and its standard from the paper's stated target or `--venue`; when both are silent, ratify the standard through the structured-inquiry channel *before* scoring — the novelty and rigor bars are venue-relative. Build the **claim inventory**: every load-bearing assertion (each contribution claim, method step, reported result, and citation) paired with the suite artifact whose evidence it cross-checks against. Externalise it to `{suite}/_inputs/review-claims.md` (a free-form `{kebab-case-topic}.md` scratch file per `rules/context-management-scratch.md` §1) when the paper exceeds what a single pass holds.
