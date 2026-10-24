<!-- SPDX-License-Identifier: MIT -->

### Step 6: Synthesis

**6.1 — Findings Registry.** Compile EVERY finding from all executed steps into a single registry. If `--focus` narrowed scope, note which dimensions were audited and which were excluded. Each finding includes:

- **ID:** sequential (F1, F2, ...)
- **Category:** Prose Fidelity / Consistency / Quality / Risk / Creative
- **Severity:** Critical (blocks execution, structural failure) / Important (degrades quality, creates risk) / Advisory (improvement opportunity, minor inconsistency)
- **Evidence:** exact quote, file location, cross-reference target
- **Impact:** what goes wrong if this finding is not addressed
- **Location:** specific file(s) and section(s) affected
- **Fix Action:** specific proposed remediation, not a vague "review" or "address"
- **Remediation Class:** mechanical / judgment / defer / waive
- **Status:** open / resolved / operator-waived / deferred-to-maintenance

**6.2 — Gate Determination.** Gate only on audited dimensions. If Step 3 ran: Internal Consistency ≥ CONDITIONAL required. If Step 2 ran: Prose Fidelity ≥ CONDITIONAL required. If either executed scorecard is FAIL: at PUBLIC_LAUNCH → execution is hard-blocked, no override; at SHARED → execution is blocked until addressed, but Product Owner override is permitted (log rationale in PLAN-NOTES.md); at PERSONAL_USE → advisory only, warn the user but do not block. If `--focus` excluded a dimension, that dimension's gate is deferred — neither passed nor failed, and must be audited in a subsequent full review before execution at SHARED+.

**6.2.1 — Strict Zero-Open-Finding Terminal Gate.** Independent of per-scorecard CONDITIONAL tolerance, the terminal handoff verdict to `/plan-execute` is PASS only when the post-remediation Findings Registry has zero `open` findings. Every finding is `resolved`, `operator-waived` with logged rationale in PLAN-NOTES.md, or `deferred-to-maintenance` with an explicit out-of-scope rationale and source anchor. A CONDITIONAL scorecard that still carries open findings is not passing; it loops through remediation or exits BLOCKED. Write the terminal verdict and open-finding count to the Handoff Manifest and PROGRESS.md Review Summary.

**6.3 — Summary.** Present findings grouped by category and severity. State the single biggest structural issue in the plan — the one finding that, if fixed, would improve the plan more than any other.

**6.4 — Clean Bill.** If ZERO findings across all executed steps: (a) in normal runs, write scorecard grades (all PASS) to PLAN-NOTES.md `## Review Scorecards` and PROGRESS.md Review Summary, then skip Steps 7–10, proceed directly to Step 11C (skipping 11A/11B since no revisions were applied), then continue to Step 12; (b) in `--dry-run`, do not write files and report the would-write targets only, then proceed directly to Step 6.6 and STOP. A clean bill requires that EVERY in-scope element in the Pre-Audit Baseline registry (Step 1) has been individually verified and marked clean. If any in-scope element was not examined, the review is incomplete — not clean. If `--focus` narrowed scope, the clean bill applies only to audited dimensions — state explicitly which dimensions were not audited and include a `Review Scope:` field listing audited/unaudited dimensions.

**6.5 — User Rejects All Revisions.** If findings exist but the user rejects all proposed revisions → skip Steps 10–11A/11B, proceed to Step 11C with pre-revision scores as final, then continue to Step 12. Log the user's rationale in PLAN-NOTES.md.

**6.6 — Dry-Run Exit.** If `--dry-run`: present scorecards, findings registry, risk assessment, and gate determination. **Do NOT write any files, create or evolve artifacts, or proceed to Q&A or revisions. STOP.**
