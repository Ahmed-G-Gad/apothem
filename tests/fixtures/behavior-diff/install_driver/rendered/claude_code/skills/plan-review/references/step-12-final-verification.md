<!-- SPDX-License-Identifier: MIT -->

### Step 11: Final Verification

Deploy an Audit Team (CM-25A) for parallel re-scoring. This step re-applies the same rigorous, blind, exhaustive methodology from Steps 2–3 — not a cursory re-check. Re-check only dimensions that were audited (i.e., steps that executed per `--focus` scope).

**11A — Prose Fidelity Recheck.** If Step 2 executed: re-score the full traceability matrix on the revised plan. The post-revision score MUST be ≥ the pre-revision score. If post < pre (a revision degraded prose fidelity): identify the offending revision(s), revert them, re-score, and escalate to the user if still regressing.

**11B — Internal Consistency Recheck.** If Step 3 executed: re-score ALL consistency dimensions on the revised plan. The post-revision score MUST be ≥ the pre-revision score. If post < pre: same revert-and-escalate procedure. Pay particular attention to consistency dimensions the revisions touched — a revision that touches one consistency dimension also touches every dimension that cross-references it, and a fix in one dimension can introduce a new inconsistency in any of the cross-referencing dimensions.

**11B.1 — Update Stored Scorecards.** Write post-revision scorecard grades to PLAN-NOTES.md `## Review Scorecards` (overwriting pre-revision grades). Update PROGRESS.md Review Summary with post-revision grades so downstream commands (plan-execute, plan-status) read current scores. If `--focus` narrowed scope, include a `Review Scope:` field listing audited and unaudited dimensions — plan-execute uses this to detect partial coverage at SHARED+.

**11C — Collective Coherence.** Final coherence verification:

- Appendix checklist: verify all mandatory files exist and are properly cross-referenced.
- Verification assertions: run the key assertions from the Master Plan.
- Verify the Revision History row was appended with the correct classification (STRUCTURAL/REFINEMENT/PATCH per Step 10.2) and the plan version bumped accordingly.
- If revisions were applied: compare pre-revision and post-revision scorecards side by side (confirm post ≥ pre for each audited dimension).
- If no revisions (clean-bill path): confirm scorecards from executed audit steps meet gate thresholds and present as final scores.
- Findings Registry: verify zero `open` findings remain. If any finding remains open, return to Step 8 or exit BLOCKED; do not hand off to `/plan-execute`.
- **Final Completeness Assertion:** revisit the Pre-Audit Baseline registry from Step 1. Confirm every in-scope element has been individually verified. If any in-scope element remains unverified, the review is incomplete — examine it now. If `--focus` narrowed scope, state explicitly which dimensions were audited and which remain unaudited.
