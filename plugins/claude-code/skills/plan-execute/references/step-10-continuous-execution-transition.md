<!-- SPDX-License-Identifier: MIT -->

### Step 10: Continuous Execution Transition (CM-16)

**10A — Granular Amendment Loop (D5 / Q-021):** Consumed at every phase boundary AND every sub-phase boundary. Read the persisted `**Execution mode (this session):**` value from the PROGRESS.md Resumption Contract (set at Step 1A). Skip the amendment-loop question — and proceed silently to the compaction + next-phase-dispatch logic below — when mode is `continuous` OR when the `--no-pause` invocation flag is set (wrapper-driven). Skip at parent-phase boundaries only when mode is `granular-sub-phase-only`. Skip at sub-phase boundaries only when mode is `granular-phase-only`. In every other combination, fire the structured inquiry below and iterate until the operator selects Continue (per D5 verbatim: `again and again until user select to end the phase/sub-phase`):

- `question:` `Phase <NN-topic> sub-phase <NNL-subtopic> complete; amendments before continuing?` (omit the sub-phase clause at parent-phase boundaries)
- `header:` `Phase amend`
- `multiSelect:` `false`
- Option `Continue (Recommended)`:
  - `rationale:` Phase verification PASS; advance to the next phase or sub-phase per the dependency graph.
  - `recommendation:` recommended — cites class 6 observed-state: phase Verification section completed clean and the per-phase commit-task mapping is satisfied at PUBLIC_LAUNCH.
  - `default-pointer:` no-default: user decision required (the boundary gate is the operator's per-phase control point; silent advance bypasses the granular pause Q-021 ratifies).
- Option `Amend`:
  - `rationale:` Operator surfaces an amendment to the just-completed phase's outputs; the agent loops back to apply the amendment, re-runs verification, then re-fires the boundary question (looping until the operator selects Continue).
  - `recommendation:` acceptable
  - `default-pointer:` no-default: user decision required.
- Option `Stop session`:
  - `rationale:` Halts the execute session; the PROGRESS.md Resumption Contract preserves current state; the operator resumes in a later session via a fresh `/plan-execute` invocation.
  - `recommendation:` destructive-no-default — cites class 5 rule citation: `rules/interactive-questions.md` §6.2 + §7.3 (destructive-irreversible class — once a session halts, intra-session active-context state is lost; the Resumption Contract is the only recovery surface and only captures externalised state) and class 6 observed-state: at PUBLIC_LAUNCH, a session halt mid-phase forfeits intra-session decisions not yet externalised to PROGRESS.md per CM-24 §2.5.
  - `default-pointer:` no-default: user decision required (per the §6 destructive-op floor — the verbatim marker is required because the Stop-session leg is the destructive option of the set).

After Continue is selected (or the question is skipped under continuous / `--no-pause`):

**Mandatory compaction** between phases. Externalize all state first (CM-24B — verify no unexternalized decisions, observations, or state exist only in active context). Before compaction: verify the Phase Exit Protocol (Step 8) is fully satisfied — Resumption Contract written, Phase Output Registry updated. After compaction: execute Blind Bootstrap (Step 1B) for the next phase as if this were a fresh session.

If any context-health signal from `rules/context-management.md` §1 or any regression-detection mismatch from `rules/context-management-protocol.md` §3.4 fires before the next phase starts, execute the recovery cycle first: externalize, compact or restart the harness session, re-run Blind Bootstrap, and rerun the relevant output/input validation. Continue when the signal clears; mark BLOCKED only when durable state remains contradictory or a validation gate still fails after that cycle.

- **Single-phase invocation:** If the user specified a specific phase number (e.g., `/plan-execute my-plan/ 05`), STOP after completing that phase — do not trigger continuous execution. Continuous execution applies only to full-suite invocations (no phase number specified).
- **Next phase exists (full-suite):** Immediately proceed to Step 1 for the next phase. No user confirmation (at SHARED+). Sub-phases within a phase execute in lexicographic order (per Step 3's sub-phase iteration construct) before the next top-level phase begins.
- **Final phase:** Present COMPLETION.md (generated in Step 7). **Pipeline handoff (CM-20):** recommend `/code-review` as the canonical audit-fortress entry point (audit-fortress linear sequence: `/code-review → /code-audit → /security-audit → /perf-audit → /architecture-review → /ux-review → /a11y-audit → /docs-review → /dependency-audit → /supply-chain-audit → /threat-model-audit`). For an orthogonal read-only health snapshot, `/plan-status --verbose` is also recommended. Halt.
- **BLOCKED phase:** Log in PROGRESS.md. Walk the dependency graph transitively — mark every phase that depends on the BLOCKED phase (directly or transitively) as SKIPPED with reason "blocked upstream: Phase NN." Skip to the next phase with no dependency on the BLOCKED phase or any transitively blocked phase. If no such phase exists, inform the user that the remaining plan is fully blocked and halt.
