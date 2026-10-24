<!-- SPDX-License-Identifier: MIT -->

### Phase 1 — Ingest the Synthesis, Design & Analysis

Read the three upstream artifacts in full per the locate-before-read discipline at `rules/large-file-reading.md`:

- `{suite}/_inputs/synthesis.md` — the SOTA map and the explicit gap statement the introduction and related-work sections build on.
- `{suite}/_inputs/study-design.md` — the operationalized method the method section reproduces.
- `{suite}/_outputs/analysis.md` — the confirmed results, **and only the confirmed results**, that the results section reports.

Build the **manuscript inventory**: the contribution claim the abstract makes (traced to the gap statement and the confirmed results that close it); the prior-art set related work positions against (from the synthesis literature matrix and the source ledger); the method elements the study design fixed; the per-result evidence set the results section carries (effect sizes, CIs, and disclosed deviations from `_outputs/analysis.md`); and the fragile/null results bound for the limitations section.

**Set the depth target from the target-venue ambition (N17).** The target-venue ambition tier sets the depth target for the evidence the Results and Method sections carry: a higher-ambition target venue demands deeper reproducibility detail, fuller statistical reporting, and a more complete reproducibility-evidence package. Record the tier in the manuscript inventory so the reproducibility-evidence outputs the Method and Results sections carry scaffold the deliverable evidence package the target venue expects. When the operator has not supplied the target-venue ambition, carry it as `TODO(clarify): target-venue ambition` and surface it through the structured-inquiry channel rather than inventing it.

Discover the host's manuscript convention (format, path, citation style) per `rules/host-discovery.md`; surface the venue or authorship identity through the structured-inquiry channel when the host is silent and the operator has not supplied them. **Gather the author roster under the CRediT taxonomy and ORCID (R6).** For each author the operator supplies, record the name, the affiliation, the **ORCID iD** (the persistent researcher identifier), and the **CRediT contributor roles** (Conceptualization, Methodology, Software, Validation, Formal analysis, Investigation, Data curation, Writing — original draft, Writing — review & editing, Supervision, and the rest of the fourteen-role taxonomy) each author holds. Author names, affiliations, ORCID iDs, and contribution roles trace to operator-supplied identity through the structured-inquiry channel — none is invented (R6). Externalise the inventory to `{suite}/_inputs/paper-outline.md` (a free-form `{kebab-case-topic}.md` scratch file per `rules/context-management-scratch.md` §1) when the manuscript exceeds what a single pass holds.
