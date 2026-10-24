<!-- SPDX-License-Identifier: MIT -->

### Step 2: Verify Prerequisites and Conformity

Deploy an Audit Team (CM-25A) for parallel conformity checks. Return pass/fail verdicts only (CM-25C return contract: max 200 tokens per agent).

- Confirm prerequisites complete in PROGRESS.md. If prerequisites are incomplete (a dependent phase is still Pending/In Progress/Blocked): STOP. Invoke the structured-inquiry channel: question `Prerequisite phases are incomplete; how should execution proceed?`; header `Prereq stop`; options:
  - `Execute prerequisite first (Recommended)`:
    rationale: Runs the blocking phase's tasks before resuming this one, satisfying the dependency edge and preserving the dependency-graph order.
    recommendation: recommended — cites class 5 rule citation: `rules/operational-mandates.md` CM-11 (Plan Integrity — dependencies must match the graph) and class 6 observed-state: a downstream phase consuming an upstream phase's outputs cannot operate correctly when those outputs are absent.
    default-pointer: Execute prerequisite first — safe because completing the prerequisite is reversible (the prerequisite's outputs are produced once and consumed by the dependent phase).
  - `Override`:
    rationale: Proceeds despite the incomplete prerequisite; the rationale is logged in PLAN-NOTES.md alongside a watch item in PROGRESS.md.
    recommendation: discouraged — cites class 5 rule citation: `rules/operational-mandates.md` CM-11 (a dependency violation propagates risk to every downstream phase that consumes the missing output) and class 6 observed-state: overriding without satisfying the dependency leaves the consuming phase to operate on unverified inputs.
    default-pointer: Execute prerequisite first — overriding is a documented escape hatch, not the safe default; the prerequisite-first path produces verified inputs.
  - `Abort`:
    rationale: Halts the pipeline; the next session can resume after the prerequisite is satisfied independently.
    recommendation: acceptable
    default-pointer: Execute prerequisite first — aborting forces a full re-bootstrap, while satisfying the prerequisite preserves the in-progress state and resumes cleanly.
  `multiSelect: false`. Name the incomplete prerequisite phases in the question body.
- **Target phase status:** If the target phase is not Pending, STOP and inform the user of the recorded state, then offer the options below (record rationale in PLAN-NOTES.md for any override/re-execute path):

  | Status | Inform user of | Option (a) | Option (b) | Option (c) |
  | ------ | -------------- | ---------- | ---------- | ---------- |
  | COMPLETE | phase already complete | re-execute | resume from a specific task | abort |
  | BLOCKED | recorded blocker | resolve blocker and re-execute | force-execute | abort |
  | SKIPPED | upstream blocker that caused the skip | resolve upstream blocker first | force-execute | abort |
  | IN PROGRESS | last-completed task (per Resumption Contract) | resume from next incomplete task (default) | re-execute from phase start | abort |

- Confirm inputs exist. If inputs are missing and not caught by the prerequisite check: STOP and invoke the structured-inquiry channel: question `A declared input is missing from the producing phase's outputs; how should the phase proceed?`; header `Missing input`; options:
  - `Execute producing phase first (Recommended)`:
    rationale: Runs the phase that was to produce the missing output, restoring the dependency chain before the dependent phase resumes.
    recommendation: recommended — cites class 5 rule citation: `rules/operational-mandates.md` CM-11 (Plan Integrity — inputs must resolve to outputs) and class 6 observed-state: a missing declared input means the producing phase has not yet emitted its deliverable.
    default-pointer: Execute producing phase first — safe because producing the input through the declared producer preserves the dependency-graph contract.
  - `Provide manually`:
    rationale: User supplies the missing input via Other-text or an external placement; the phase resumes with the manually provided artifact.
    recommendation: acceptable
    default-pointer: Execute producing phase first — manual provision bypasses the producing phase's verification, which the dependency-graph contract relies on.
  - `Abort`:
    rationale: Halts the pipeline; the next session can resume after the input is produced.
    recommendation: acceptable
    default-pointer: Execute producing phase first — aborting forces a re-bootstrap; producing the input directly resumes execution cleanly.
  `multiSelect: false`. Name the absent inputs in the question body.
- Read Scope — IN vs. OUT. Do not exceed scope.
- Identify the phase's success metric. If no success metric is defined in the phase file, use the Scope's "Success looks like" statement; if that is also absent, log it as a watch item and proceed.
- **Pre-Execution Conformity (CM-11):** Dependencies match the graph, inputs resolve to outputs, decisions match records, tasks align with the preamble. Fail → STOP, recommend `/plan-review`. Near-misses → log as watch items.
- **Review Gate:** At EXPLORING: no scorecard check. At SHARED+ seriousness, verify scorecards exist in PLAN-NOTES.md — check `## Review Scorecards` first; if absent, fall back to `## Generation Scorecards`. Review scorecards take precedence when both exist. If Review Scorecards include a `Review Scope:` field with unaudited dimensions: at PUBLIC_LAUNCH → STOP, require full `/plan-review` before execution; at SHARED → notify the user that unaudited dimensions exist and recommend full `/plan-review` before proceeding. If no scorecards are found at PUBLIC_LAUNCH → STOP, recommend `/plan-review` before execution. If no scorecards are found at SHARED → invoke the structured-inquiry channel: question `No review scorecards were found; should execution proceed without a prior review?`; header `No review`; options:
  - `Run /plan-review first (Recommended)`:
    rationale: Defers execution until the review completes and scorecards are generated, satisfying the SHARED+ Review Gate's evidence requirement.
    recommendation: recommended — cites class 5 rule citation: `rules/operational-mandates.md` CM-11 (Plan Integrity — review scorecards are the prerequisite evidence for execution at SHARED+) and class 6 observed-state: missing scorecards mean the plan's prose-fidelity and internal-consistency status is unknown.
    default-pointer: Run /plan-review first — safe because review is non-destructive and produces the evidence the gate requires.
  - `Proceed without review`:
    rationale: Execution continues; the operator's rationale is logged in PLAN-NOTES.md alongside a watch item flag.
    recommendation: discouraged — cites class 5 rule citation: `rules/operational-mandates.md` CM-11 (proceeding without review evidence weakens downstream conformity checks) and class 6 observed-state: the absence of scorecards leaves prose fidelity and internal consistency unverified.
    default-pointer: Run /plan-review first — proceeding without review is a documented escape hatch, not the safe default.
  - `Abort`:
    rationale: Halts execution; the next session can resume after the review is run independently.
    recommendation: acceptable
    default-pointer: Run /plan-review first — aborting forces a full re-bootstrap; running the review preserves the in-progress state cleanly.
  `multiSelect: false`. If either scorecard is FAIL: at PUBLIC_LAUNCH → hard block, no override — STOP, recommend `/plan-review`; at SHARED → STOP and invoke the structured-inquiry channel: question `A review scorecard failed; the override path requires rationale. How should execution proceed?`; header `Scorecard fail`; options:
  - `Run /plan-review and resolve failures (Recommended)`:
    rationale: Fixes the failing dimensions before proceeding so the gate's evidence is restored to PASS.
    recommendation: recommended — cites class 5 rule citation: `rules/operational-mandates.md` CM-11 (a FAIL scorecard surfaces a structural defect; resolving the failure addresses the root cause) and class 6 observed-state: a FAIL scorecard is direct evidence of a plan-integrity defect.
    default-pointer: Run /plan-review and resolve failures — safe because resolution restores the gate to PASS and unblocks execution cleanly.
  - `Product Owner override`:
    rationale: Proceeds with the failing scorecard in force; the operator's rationale captured via Other-text is logged in PLAN-NOTES.md and a watch-item note is added to PROGRESS.md.
    recommendation: discouraged — cites class 5 rule citation: `rules/operational-mandates.md` CM-11 (overriding a FAIL scorecard propagates the underlying defect into execution artifacts) and class 6 observed-state: known plan defects compound during execution.
    default-pointer: Run /plan-review and resolve failures — Product Owner override is a documented escape hatch, not the safe default.
  - `Abort`:
    rationale: Halts execution; the next session can resume after the failing dimensions are resolved independently.
    recommendation: acceptable
    default-pointer: Run /plan-review and resolve failures — aborting forces a full re-bootstrap; resolving the failure preserves the work and unblocks execution.
  `multiSelect: false`. At PERSONAL_USE: if scorecards exist (from either source) and either is FAIL, notify the user (advisory only — do not block).
- If `--dry-run`: analyze and report what would be done. **STOP.**
