<!-- SPDX-License-Identifier: MIT -->

### Step 9: STOP — Wait for Approval

**STOP. Never apply changes without user approval.** Present:

- Total number of proposed revisions
- Breakdown by severity
- The single most impactful revision highlighted
- Clear instruction that no changes will be made until the user approves

Invoke the structured-inquiry channel: question `Which proposed revisions should apply to the plan suite?`; header `Revisions`; options:

- `Approve all (Recommended)`:
  rationale: Applies every proposed revision in Step 10; the revision-impact map and post-revision verification cover the entire revision set as one cohesive cohort.
  recommendation: recommended — cites class 5 rule citation: `commands/plan-review.md` Step 8 (Propose Revisions — every revision is documented with severity, rationale, and blast radius, satisfying the prerequisite for cohesive application) and class 6 observed-state: Step 6's Findings Registry surfaces every finding with evidence, indicating the proposed revision set is the operator-reviewable cohesive cohort.
  default-pointer: Approve all — safe because Step 11 Final Verification re-scores every audited dimension, catching any regression introduced by the revisions.
- `Approve a subset`:
  rationale: User specifies which revisions to apply and which to reject via Other-text or follow-up; only approved revisions apply in Step 10, rejected revisions are logged with rationale in PLAN-NOTES.md, and Step 11 re-runs on the partial revision set.
  recommendation: acceptable
  default-pointer: Approve all — partial approval requires the operator to map per-revision dispositions, while the cohesive revision set is the operator-reviewable cohort.
- `Reject all revisions`:
  rationale: Proceeds to the Step 6.5 path; the existing plan suite is preserved at its current state with the operator's rationale logged in PLAN-NOTES.md.
  recommendation: discouraged — cites class 5 rule citation: `rules/operational-mandates.md` CM-1 (Critical Evaluation — push back when suboptimal) and class 6 observed-state: Step 6 surfaced findings with severity classifications, indicating substantive defects exist that rejection leaves unresolved.
  default-pointer: Approve all — rejecting all revisions leaves the surfaced findings unresolved, propagating risk into downstream execution; approval addresses the findings cohesively.
`multiSelect: false`.
