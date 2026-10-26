<!-- SPDX-License-Identifier: MIT -->

## Output

| Artifact | Path | Purpose |
| -------- | ---- | ------- |
| Proposal | `{suite}/_inputs/proposal.md` | The promoted plan-of-record + SMART aims hierarchy + feasibility + resource/timeline/risk register with contingencies + impact pathway + preregistration plan + data management and sharing plan + EQUATOR pre-selection, ready for `/research-design`. |
| Call-requirement matrix | `{suite}/_inputs/call-requirements.md` | Optional Phase 1 working file, built when `--call` supplies a funder call: each requirement mapped to its proposal section, draft location, and status. |
| Handoff Manifest | `{suite}/_inputs/handoff-manifest.yml` | Updated at Phase 5 with `downstream: /research-design` and the R5 / R9 / R10 / R6 / R8 attestation block. |
| Resubmission response | `{suite}/_outputs/resubmission-response.md` | `--resubmission` only: the limits rows, the revision matrix, and the propagation check. No manifest update. |

The `proposal.md` carries these canonical sections: `## §1 Objectives & Gap Anchor` (the high-level goal traced to the explicit gap statement); `## §2 SMART Aims Hierarchy` (each aim with its S/M/A/R/T attributes); `## §3 Feasibility Assessment` (each aim's achievability against resources and constraints); `## §4 Resource / Timeline / Risk Register` (resource demand, timeline, and risk → mitigation register, with the stress test, the contingency records, and any budget reconciliation); `## §5 Preregistration Plan` (the registry, the freeze-before-collection contract; R5); `## §6 Impact Pathway` (the outputs → outcomes → impact route diagram; R10); `## §7 Reporting-Guideline Pre-Selection & Ethics Feasibility` (the EQUATOR guideline per R9, the data management and sharing plan per R8, the rigor floor and reproducibility-evidence outputs pre-committed to the target-venue ambition per `skills/research-suite/references/advancement-gate.md`, and the ethics considerations per R6); `## §8 Validation Gate Outcome` (the Phase 5 gate attestation); `## §Bindings (§0.j five-direction)`.
