<!-- SPDX-License-Identifier: MIT -->

### Step 11.5: End-of-Command Synthesis (D6)

Just before review-report finalization at Step 12 handoff, fire ONE structured inquiry per D6 (Q-022) with the spec §7.4 form. The invocation MUST satisfy `rules/interactive-questions.md` §2 (canonical schema) + §3 (three-segment body) + §4.1 (closed recommendation taxonomy) + the H4/H6 invariants from `rules/interactive-questions-sweep-matchers.md` (every option carries all three body segments; the `(Recommended)` label postfix bidirectionally binds the body `recommendation: recommended` value):

- `question:` `Review complete. Are there any deferred findings or improvements to surface before finalization?`
- `header:` `End synthesis`
- `multiSelect:` `false`
- Option `All clear (Recommended)`:
  - `rationale:` No deferred findings; review report is finalized and the augmented Handoff Manifest emits.
  - `recommendation:` recommended — cites class 6 observed-state: Step 11 Final Verification confirmed post-revision PASS scorecards across every audited dimension.
  - `default-pointer:` no-default: user decision required (review's final-finding ratification surface).
- Option `Surface findings`:
  - `rationale:` Operator surfaces additional findings before finalization; agent extends the Findings Registry and re-runs partial verification on the new findings.
  - `recommendation:` acceptable
  - `default-pointer:` no-default: user decision required.
- Option `Defer findings`:
  - `rationale:` Operator notes findings but defers; agent appends `[Deferral — out-of-scope: <description>; tracking: <PLAN-NOTES.md or follow-up issue>]` per `rules/disclosure-ledger.md`.
  - `recommendation:` acceptable
  - `default-pointer:` no-default: user decision required.

The selection routes the post-synthesis flow: `All clear` proceeds directly to Step 12 handoff and Manifest emission only when the Findings Registry has zero open findings; `Surface findings` extends the Findings Registry, re-runs the affected dimension's audit (Steps 2/3/4 as applicable), and re-runs Step 11 Final Verification on the augmented finding set; `Defer findings` appends the deferral marker to the disclosure ledger and proceeds to Step 12 only when the finding is explicitly out of scope for the source suite and routed via the augmented Manifest's `deferrals` field per `rules/disclosure-ledger.md`.
