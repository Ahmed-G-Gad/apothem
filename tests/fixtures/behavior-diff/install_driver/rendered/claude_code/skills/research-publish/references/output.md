<!-- SPDX-License-Identifier: MIT -->

## Output

| Artifact | Path | Purpose |
| -------- | ---- | ------- |
| Submission package | `paper/submission/` (host-natural, discovered) | The venue-formatted manuscript + supplementary materials + data/code-availability statement + cover letter + ethics/COI declarations + author-contribution statement + tool-and-model use statement, ready for the operator to submit. |
| Preprint/archival plan | beside the package (host-natural) | The preprint server, the timing relative to submission, and the reserved resolvable DOI. |
| Publication record | `{suite}/_outputs/publication-record.md` | The package manifest + the submission-checklist outcome + the carried-residual review-finding note + the Phase 5 gate attestation. |
| Submission checklist | inside the publication record | Every venue requirement as a `met` / `unmet` line with evidence; an all-`met` checklist earns the `ready` verdict. |
| Venue-requirement inventory | `{suite}/_inputs/venue-requirements.md` | Optional Phase 1 working copy (the venue's required-artifact and required-declaration list); the dated copy in the publication record §1 is the required one. |
| Handoff Manifest | `{suite}/_inputs/handoff-manifest.yml` | Updated at Phase 5 with `downstream: /research-disseminate`, the per-citation and per-declaration verification attestation, and the checklist outcome. |

The `publication-record.md` carries these canonical sections: `## §1 Venue & Scope` (the target venue with its year or cycle, track, and article type; the paper recap; the review-report status with any carried residual findings and the not-judged list; the dated venue-rule register, each rule with its source, read date, and submission stage); `## §2 Package Manifest` (every package artifact with its path and source-trace); `## §3 Declarations` (the ethics, conflict-of-interest, data/code-availability, funding, author-contribution, and tool-and-model use statements as assembled, each with its authoritative-data source); `## §4 Citation-Integrity Report` (the Phase 4 per-citation resolution outcomes; R4); `## §5 Open Access, License & Archival Plan` (the OA route, the manuscript and code licenses, the data/code deposit (Zenodo or an equivalent archive) with its persistent DOIs, the preprint server and timing, the reserved DOI, and the registered-report Stage-2 route where one was preregistered; R8); `## §6 Submission Checklist` (the requirement × verdict table; the `ready` / `not-ready` verdict); `## §7 Validation Gate Outcome` (the Phase 5 gate attestation); `## §Bindings (§0.j five-direction)`.
