<!-- SPDX-License-Identifier: MIT -->

## Output

| Artifact | Path | Purpose |
| -------- | ---- | ------- |
| Dissemination plan | `{suite}/_outputs/dissemination-plan.md` | The dissemination-and-impact record: preprint announcement + public-artifact plan + FAIR archival deposit record + altmetrics/impact-tracking plan + rebuttal/revision loop + registered-report stage-2 path + the readiness-checklist outcome, ready for the operator to execute. |
| Public artifacts | host-natural (a blog draft, a talk script, a poster source) | Optional artifact drafts authored at the host-natural location, each restating the paper's claims. |
| Dissemination-requirement inventory | `{suite}/_inputs/dissemination-requirements.md` | Optional Phase 1 working file (the public-artifact, archival, and impact-tracking requirement list). |
| Handoff Manifest | `{suite}/_inputs/handoff-manifest.yml` | Closed at Phase 5 with `downstream: operator dissemination (terminal)`, the per-identifier and per-claim verification attestation, and the readiness-checklist outcome. |

The `dissemination-plan.md` carries these canonical sections: `## §1 Publication Recap & Preprint Announcement` (the `ready` package recap, the reserved DOI, the preprint server and timing); `## §2 FAIR Archival Deposit` (the repository, the persistent identifier, the access terms and any restriction basis; R8); `## §3 Public Artifacts` (the talk / poster / blog plan, each claim traced to the paper; for a talk, the intake, time budget, cut plan, and question and backup list; for a poster, the budgets, section-to-panel map, and dropped list; the figure-provenance table; the compiled-artifact outcome); `## §4 Altmetrics & Impact Tracking` (the reach-and-impact measurement plan traced to the impact pathway; R10); `## §5 Rebuttal / Revision Loop & Registered-Report Path` (the route back through `/research-review` and the stage-2 path); `## §6 Identifier-Integrity Report` (the Phase 4 per-identifier resolution outcomes; R8); `## §7 Dissemination-Readiness Checklist` (the requirement × verdict table; the `ready` / `not-ready` verdict); `## §8 Validation Gate Outcome` (the Phase 5 gate attestation); `## §Bindings (§0.j five-direction)`.
