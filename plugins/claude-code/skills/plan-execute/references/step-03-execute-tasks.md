<!-- SPDX-License-Identifier: MIT -->

### Step 3: Execute Tasks

Per-task externalization (CM-24B): commit + compact summary before the next task. Deploy an Implementation Team (CM-25A) for independent subtasks — non-overlapping files only (CM-25E).

**Resume checkpoint:** If the Resumption Contract indicates this phase was previously IN PROGRESS (task in progress is not "none"), skip all completed tasks and begin at the task named in the Contract's "Next action" field. If task status is "partial", re-execute the indicated task from scratch (partial work may be inconsistent) — run `git status` to identify uncommitted modifications in the task's file scope, show the exact candidate file list and `git diff -- <files>` summary, then for each file in the list invoke the structured-inquiry channel once per file (per the §6 per-file floor of `rules/interactive-questions.md` — no `multiSelect`, no cross-file batching) with the §6.7 canonical Revert-Uncommitted option set; per invocation:

- `Discard`:
  rationale: Executes `git restore --source=HEAD --worktree -- <file>`; uncommitted edits are dropped from the working tree and the revert is logged to PLAN-NOTES.md Recovery Log.
  recommendation: destructive-no-default — cites class 5 rule citation: `rules/context-management.md` §6 Blind Execution Protocol (clean re-execute is the documented recovery path for partial task state) and class 6 observed-state: the resumption pointer's task-status field marks this task `partial`, indicating inconsistent intermediate state.
  default-pointer: no-default: user decision required
- `Keep`:
  rationale: Retains the uncommitted edits at their current paths for operator triage; the file scope remains as the operator left it.
  recommendation: acceptable
  default-pointer: no-default: user decision required
- `Stash-for-later`:
  rationale: Stashes the uncommitted edits via `git stash push -- <file>` for later retrieval via `git stash pop`.
  recommendation: acceptable
  default-pointer: no-default: user decision required
- `Defer`:
  rationale: Halts and re-invokes the destructive-op decision wave once the operator re-engages; no filesystem change now.
  recommendation: acceptable
  default-pointer: no-default: user decision required
`multiSelect: false` (per §6.8 of the canonical-channel rule — destructive-op invocations forbid `multiSelect: true`).

Verify each skipped task's declared outputs exist on disk before proceeding.

**Sub-phase iteration:** If the target phase contains sub-phase folders (e.g., `phases/02-topic/02A-subtopic/`), iterate sub-phases in lexicographic order, executing Steps 3.1–3.7 for each sub-phase's tasks. Compact between sub-phases at PERSONAL_USE+. Steps 4–8 execute once after all sub-phases complete (quality gates and verification cover the full parent phase scope). Sub-phases marked parallelizable in the dependency graph may execute via an Implementation Team (one agent per sub-phase, non-overlapping file scopes).

**3.1 — Clarify:** Purpose, acceptance criteria, expected output. Check PLAN-NOTES.md. For any ambiguity, invoke the structured-inquiry channel per `rules/interactive-questions.md` (up to 4 questions per invocation; option-framed answers with the implicit Other escape for free-text). If tests exist, use them as the behavioral specification; if absent, write behavioral assertions before implementing.

**3.2 — Search Before Implement:** Find reusable components. Flag existing similar logic.

**3.3 — Implement:** Per phase specs + preamble standards. Best solution with rationale. Strict logical rigor. All values configurable. **Plan-internal isolation (CM-7):** enforce per the canonical forbidden-terms and protected-artifacts lists in `CLAUDE.md` CM-7. Every artifact reads as natural domain-language with zero trace of planning structure. **Cognitive-filter application:** Filters 1+5 always-on; the full suite for non-trivial decisions. Seriousness scaling per `rules/cognitive-identity.md` Section 2.

**3.4 — Verify Integration:** Imports resolve, interfaces match, types align, no regressions. Run tests immediately. If unfixable without design changes beyond scope → STOP and consult the user.

**3.5 — Agent Offloading:** Follow phase hints (per the phase file's Agent Offloading Hints table). Return contracts: compact deliverables only.

**3.6 — Commit (CM-13A) — code-bearing phases:** After each task that modifies codebase files, commit immediately. Conventional commits in natural domain terms — CM-7 plan-internal isolation applies to all git artifacts. Valid, buildable, testable state. Plan-suite files are NOT auto-committed. When subtasks execute in parallel via an Implementation Team, serialize git commits — parallel agents return completed file changes to the orchestrating context, which stages and commits each task's changes sequentially (or use `isolation: "worktree"` per CM-25 §5.1 for independent staging areas). If a commit fails (pre-commit hook, merge conflict): diagnose the output, fix, retry; if a structural git issue → consult the user. At PERSONAL_USE: if per-task commits were deferred, all codebase changes for the phase MUST be committed as a single per-phase commit at the end of Step 3 before Step 4. At EXPLORING: commits are optional during tasks but recommended — if any codebase changes exist, offer to commit at the end of Step 3. **Non-code phases** carry no per-task commit obligation: each task's deliverable (a research finding, a written section, a documentation-only artifact) is recorded in the phase report (Step 7) rather than committed. When a non-code task nonetheless emits a version-controlled artifact the host tracks (e.g., a Markdown document under the repo), commit it under the same conventional-commit discipline; the exemption removes the per-task code-commit cadence, not the duty to commit artifacts the host version-controls.

**3.7 — Track:** Update the PROGRESS.md Resumption Contract with the current task number after each task commit. Update the full PROGRESS.md tracker after every 3 tasks or at least once mid-phase, whichever comes first. (PROGRESS.md updates are independent of the per-task compaction summaries in the Step 3 header.)
