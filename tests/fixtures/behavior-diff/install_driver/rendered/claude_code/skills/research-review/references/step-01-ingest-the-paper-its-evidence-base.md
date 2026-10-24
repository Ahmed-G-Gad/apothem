<!-- SPDX-License-Identifier: MIT -->

### Phase 1 — Ingest the Paper & Its Evidence Base

Read the paper deliverable in full per the locate-before-read discipline at `rules/large-file-reading.md`, then read the suite evidence artifacts its claims rest on:

- `{suite}/_inputs/synthesis.md` — the SOTA map the novelty claim depends on.
- `{suite}/_inputs/study-design.md` + `{suite}/_inputs/preregistration.md` — the frozen plan the method section must match.
- `{suite}/_outputs/analysis.md` — the confirmed results the paper reports.

Resolve the target venue and its standard from the paper's stated target or `--venue`; when both are silent, ratify the standard through the structured-inquiry channel *before* scoring — the novelty and rigor bars are venue-relative. **Apply a venue profile when one exists.** A venue profile is an optional file at `{suite}/_inputs/venue-profile.md` (or the path `--venue` names) holding the venue's per-axis weights and its submission checklist. When present, the weights set how the axis verdicts combine into the overall verdict and the checklist becomes a list of pass/fail items scored in Phase 2; when absent, the axes weigh equally and the venue's published criteria stand in for the checklist. Never invent weights for a venue that publishes none.

**Run a numeric pre-screen before the full read.** Compute and record four figures: citation recency (share of references from the last five years, with the oldest and newest year), structure (which of the venue's expected sections are present, absent, or out of order), anonymisation (count of residual identity strings in the body, expected to be zero at double-blind venues), and statistics reporting (count of reported effects that carry an effect size and interval, over the count of reported effects). The figures steer attention, not the verdict: a low figure opens a line of inquiry in Phase 2 and is never a finding without a locus.

Build the **claim inventory**: every load-bearing assertion (each contribution claim, method step, reported result, and citation) paired with the suite artifact whose evidence it cross-checks against. Externalise it to `{suite}/_inputs/review-claims.md` (a free-form `{kebab-case-topic}.md` scratch file per `rules/context-management-scratch.md` §1) when the paper exceeds what a single pass holds.
