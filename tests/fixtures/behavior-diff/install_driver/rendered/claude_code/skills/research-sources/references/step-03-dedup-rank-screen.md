<!-- SPDX-License-Identifier: MIT -->

### Phase 3 — Dedup, Rank, Screen

**Deduplicate.** Collapse candidates that resolve to the same source across facets (same DOI, same canonical URL, same archival ID; a preprint and its published version are the same source — record both identifiers, keep the published version as canonical). Every collapse lands in the dedup record with both identifiers and the collapse reason.

**Rank.** Score each surviving candidate on three axes:

- **Authority** — primary/peer-reviewed/official/archival outranks secondary; a named, attributable author/organization outranks anonymous; a permalinked/DOI/commit-pinned reference outranks a mutable one (R1, R4).
- **Recency** — within the spec's temporal scope, newer outranks older; a superseded source is recorded with its successor.
- **Relevance** — direct evidence for a spec hypothesis outranks tangential mention; the relevance score names which hypothesis or sub-query the source bears on.

**Screen via a PRISMA-style flow.** Apply the spec's inclusion/exclusion criteria uniformly to the ranked set through the four-stage **PRISMA** screening flow — **identification** (raw candidate count across all facets), **screening** (title/abstract pass against the inclusion criteria), **eligibility** (full-text pass against the exclusion criteria), **included** (survivors retained) — per the EQUATOR/PRISMA reporting guideline at <https://www.equator-network.org/reporting-guidelines/prisma/>. Each stage records its in/out counts so the flow reconstructs as a PRISMA-style diagram in the ledger; every screened-out candidate lands with the specific criterion and the stage it failed at. Screening is auditable, never a silent drop. Apply the `--max-sources` ceiling after the `included` stage, retaining the highest-ranked survivors.

**Assess per-source risk of bias (R9).** For every `included` source, record a **risk-of-bias assessment** against a domain-appropriate instrument (the per-design tool the venue or the field ratifies — e.g., the Cochrane RoB classes for trials, a checklist-based judgment for observational or computational work). Each source carries a per-domain low/some-concerns/high judgment with the locus that justifies it; the assessment is a documentary field the synthesis stage weights, never a silent rank adjustment here.
