<!-- SPDX-License-Identifier: MIT -->

### Step 4: Quality Gates

Deploy a Quality Team (CM-25A) — parallel gates: linting, formatting, type-checking, testing, security scanning, dead-code detection, import validation. Scope scales with seriousness (`CLAUDE.md` Section 4). Each agent returns pass/fail + failure details (CM-25C).

If a gate fails: diagnose, fix, re-run (up to 2 cycles — one cycle is one pass of: run all gates, diagnose all failures, fix all root causes, re-run all gates). If diagnosis reveals a root cause outside phase scope, STOP and invoke the structured-inquiry channel per `rules/interactive-questions.md` to confirm disposition — log the out-of-scope dependency in PLAN-NOTES.md. If failures persist after 2 cycles → STOP, record failure details in PLAN-NOTES.md, then invoke the structured-inquiry channel: question `Quality gates remain failing after the retry budget is exhausted; how should the phase proceed?`; header `Gate fail`; options:

- `Mark phase BLOCKED (Recommended)`:
  rationale: Emits the BLOCKED phase report via Step 7's BLOCKED path, skipping Steps 5 and 6 so downstream phases can proceed around the blocker once it is resolved.
  recommendation: recommended — cites class 5 rule citation: `rules/operational-mandates.md` CM-18 (Error Recovery — escalate after 3 failures) and class 6 observed-state: the 2-cycle retry budget is exhausted, indicating the failure is not transient.
  default-pointer: Mark phase BLOCKED — safe because the BLOCKED state is reversible via blocker resolution and a re-execute pass per Step 2's status table.
- `Override and proceed`:
  rationale: Accepts the known gate failures, logs them as watch items in PROGRESS.md, and continues execution.
  recommendation: discouraged — cites class 5 rule citation: `rules/operational-mandates.md` CM-1 (Critical Evaluation — push back when suboptimal) and class 6 observed-state: known failing gates compound into systemic defects across downstream phases.
  default-pointer: Mark phase BLOCKED — overriding is a documented escape hatch, not the safe default.
- `Abort execution`:
  rationale: Halts the pipeline; the next session resumes from the same task per the resumption pointer.
  recommendation: acceptable
  default-pointer: Mark phase BLOCKED — aborting forces a full re-bootstrap, while BLOCKED preserves the work-in-progress state and unblocks the dependency graph cleanly.
`multiSelect: false`.

**Commit fixes immediately (CM-13B).**

**Gate evidence.** A gate claim is valid only with three items recorded beside it in the phase `REPORT.md` and `PROGRESS.md`: the command that ran, its output (exit status plus the summary lines), and the SHA of HEAD when it ran. A claim missing any of the three is unverified, whatever it says. A gate result goes stale the moment HEAD moves past its recorded SHA, whether through a fix commit, an amend, or a rebase, and a stale result is re-run before anything relies on it, in particular after the Step 6.9 commit gate and before the phase is marked COMPLETE, when the recorded SHA must equal HEAD. Gate state is never edited by hand: no flipping a status, no rewriting a SHA, no pasting output from another run. The only way to change recorded gate state is to run the gate again and record that run.
