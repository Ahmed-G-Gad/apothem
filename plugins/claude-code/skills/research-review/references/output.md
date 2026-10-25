<!-- SPDX-License-Identifier: MIT -->

## Output

| Artifact | Path | Purpose |
| -------- | ---- | ------- |
| Review report | `{suite}/_outputs/review-report.md` | The seven-axis scorecard + severity-triaged required-revision list + reproducibility-package and re-run verdict + citation-integrity audit + overall verdict, ready for `/research-publish` consumption. |
| Claim inventory | `{suite}/_inputs/review-claims.md` | Optional Phase 1 working file (the claim-to-evidence cross-check inventory) for a paper exceeding a single pass. |
| Handoff Manifest | `{suite}/_inputs/handoff-manifest.yml` | Updated at Phase 5 with `downstream: /research-publish`, the per-finding verification attestation, and the HIGH-finding count. |

The `review-report.md` carries these canonical sections: `## §1 Scope & Venue` (the paper recap, the resolved venue standard and any venue profile applied, the evidence artifacts cross-checked, the four pre-screen figures); `## §2 Reviewer Scorecard` (the seven-axis table — novelty · rigor · reproducibility · clarity · ethics · statistical review · reporting-guideline conformance, each with its scored verdict, justifying loci, reviewer confidence 1-5, and the could-not-judge list); `## §3 Reproducibility Re-Run` (the reproducibility-package completeness check, the headline-number re-derivation against the analysis, the data/code-pointer resolution); `## §4 Citation-Integrity Audit` (every citation's resolve verdict against the source ledger); `## §5 Required Revisions` (the severity-triaged list — HIGH / MEDIUM / LOW, each finding with its locus, the standard it fails, and its concrete-driver rationale); `## §6 Overall Verdict` (the annotated `accept` · `minor-revision` · `major-revision` · `reject` decision with the recommended verdict and its rationale); `## §7 Verification Record` (the `Pass log` of the two scoring passes, the per-finding fact-checker verdicts and the blind-reconciliation delta where `--blind` ran); `## §8 Validation Gate Outcome` (the Phase 5 gate attestation); `## §Bindings (§0.j five-direction)`.
