<!-- SPDX-License-Identifier: MIT -->

### Phase 1 — Ingest the Paper, the Review, & the Venue

**Read the review first.** Open `{suite}/_outputs/review-report.md` in full: confirm the HIGH-severity required-revision items are resolved in the current paper, and record any residual MEDIUM/LOW findings the operator chose to carry as a known-state note in the publication record. Then read the paper deliverable at the host-natural location per the locate-before-read discipline at `rules/large-file-reading.md`, and resolve the venue from `--venue`, the suite context, or the structured-inquiry channel.

**The venue is the authority over the package shape.** Its author guidelines fix the template, the page or word limit, the bibliography style, the figure-format requirements, the anonymization rule (single- vs. double-blind), the required declarations (ethics, COI, data/code availability, author contributions, funding), and the preprint policy. Build the **venue-requirement inventory** — every artifact the venue demands and every declaration it requires — and externalise it to `{suite}/_inputs/venue-requirements.md` (a free-form `{kebab-case-topic}.md` scratch file per `rules/context-management-scratch.md` §1).

**Gather the authoritative declaration data** (author names, affiliations, emails, ethics-approval identifiers, funding sources, COI facts) from the suite where recorded and from the operator via required-category inquiry where absent — these are never invented (R6, `rules/authority-inquiry.md`).
