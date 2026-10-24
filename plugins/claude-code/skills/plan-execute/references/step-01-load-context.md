<!-- SPDX-License-Identifier: MIT -->

### Step 1: Load Context

Deploy a Research Team (CM-25A) for parallel context loading. Return contract: structured summaries, max 500 tokens per agent (CM-25C), required fields (`status`, `summary`, `evidence`, `gaps`), and explicit failure behavior (`status=failed` + reason + partial coverage). Lean ingestion — execution-relevant data only (CM-12a, CM-24).

1. Verify mandatory files exist (PREAMBLE.md, MASTER-PLAN.md, PROGRESS.md, PLAN-NOTES.md, `phases/` directory). If missing: STOP → recommend `/plan-generate`.
2. **Classify the phase (code-bearing vs non-code).** Read the target phase file's Scope and deliverables: a phase is **code-bearing** when it produces or modifies source, tests, configs, schemas, build scripts, or any version-controlled software artifact; it is **non-code** when its deliverables are research, writing, documentation-only prose, analysis, or other non-software artifacts. Record the classification in the PROGRESS.md Resumption Contract under `**Phase class (this phase):** code-bearing | non-code`. For a **code-bearing** phase, verify a git repository — if not present: STOP → recommend `git init`. A **non-code** phase proceeds without the git gate (no STOP); its deliverables are recorded in the phase report rather than committed.
3. **Phase resolution:** If no phase number is specified, read PROGRESS.md to determine the next pending phase (skipping SKIPPED phases) and scan `phases/` for phase folders. If `phases/` exists but holds zero phase folders: STOP → inform the user the phases directory is empty and recommend `/plan-generate`. If all phases are complete or skipped, invoke the structured-inquiry channel: question `All phases are complete or skipped; how should execution proceed?`; header `Phase done`; options:
   - `Abort (Recommended)`:
     rationale: Halts execution; the pipeline state remains terminal until the operator explicitly invokes a re-run.
     recommendation: recommended — cites class 5 rule citation: `rules/operational-mandates.md` CM-1 (Critical Evaluation — do not re-execute completed work without explicit operator intent) and class 6 observed-state: zero pending phases means no substantive dispatch target exists.
     default-pointer: Abort — safe because halting preserves the completed state without overwriting prior phase outputs.
   - `Re-execute a specific phase`:
     rationale: User names the phase via Other-text; the named phase is re-executed from its first task, overwriting prior outputs at that phase's scope.
     recommendation: acceptable
     default-pointer: Abort — re-execution overwrites completed phase outputs and is appropriate only when the operator explicitly intends to re-run prior work.
   `multiSelect: false`. If multiple phases are pending with no dependency ordering preference, present them via the structured-inquiry channel with one option per pending phase (up to 4 options; if more exist, list the first four by readiness and use Other-text for the rest); each option's body carries the three-segment annotation per `rules/interactive-questions.md` §3 (`rationale:` describing what the phase produces · `recommendation:` from the closed taxonomy citing a concrete-driver class per `rules/interactive-questions-canonical-shapes.md` §3.2.1 · `default-pointer:` naming the dependency-graph-earliest pending phase as the safe default).
4. Load rules (`rules/*.md`) and relevant skills.
5. Read `PREAMBLE.md` — sections relevant to this phase.
6. Read `PROGRESS.md` — current state; verify prerequisites. If resuming: run the Session Start Protocol (CM-14), including rules from `rules/*.md`.
7. Read `PLAN-NOTES.md` — resolved decisions (DO NOT re-ask). Check the User Preferences section for communication style.
8. Read `MASTER-PLAN.md` Section 3 (Dependency Graph) — needed for BLOCKED transition handling in Step 10 and sub-phase ordering.
9. Read the target phase file (`phases/NN-kebab-topic/PHASE.md`). For sub-phases, read from nested folders (e.g., `phases/NN-kebab-topic/NNA-subtopic/PHASE.md`).
10. **Per-phase effort calibration (D3 / CM-12d):** Effort is operator-invoked — `/plan-execute` ships no effort preset (agnostic posture); the *recommended* tier for mechanical implementation is the middle one. Inspect the target PHASE.md frontmatter for an operator-authored `effort:` field. If present, it sets the effort tier for the duration of the phase, on the harness's own effort scale; record it in the PROGRESS.md Resumption Contract under a new line: `**Effort override (this phase):** <value> (recommended: the mechanical-implementation tier)`. If the field is absent, no Resumption Contract line is emitted. The calibration is per-phase scoped — it never persists across the granular-pause boundary into the next phase. See CM-12d.

**1A — Mode Selection:** Once per operator-driven session, resolve the execute-session pause cadence. Continuous advancement is opt-in, never the shipped default. Resolution order: (a) if the `--no-pause` invocation flag is set, OR the shared profile's `enforcement.continuous_execution` flag is `true`, mode is `continuous` and the question is skipped (the operator has opted in); (b) otherwise, read the persisted `**Execution mode (this session):**` line from PROGRESS.md Resumption Contract — if present and the value is one of the closed taxonomy `{continuous, granular, granular-phase-only, granular-sub-phase-only}`, adopt it without re-asking; (c) if no persisted mode exists, set mode to `granular-phase-only` — halt at each phase boundary by default — persist it, and proceed; (d) when the operator explicitly asks to change the pause cadence, fire the structured inquiry below and persist the selected override. The persisted value is consumed at every phase + sub-phase boundary by Step 10A.

structured inquiry:

- `question:` `How should this execute session proceed?`
- `header:` `Exec mode`
- `multiSelect:` `false`
- Option `Granular at phase only (Recommended)`:
  - `rationale:` Pause at every parent-phase boundary so you confirm each advance; sub-phase transitions auto-continue.
  - `recommendation:` recommended — cites class 5 rule citation: `rules/agnostic-posture.md` (continuous multi-step advancement ships default-off / opt-in) and class 6 observed-state: a clean install carries no continuous opt-in, so halting at each natural boundary is the default-off posture.
  - `default-pointer:` Granular at phase only — the default when no mode is persisted and no continuous opt-in is set.
- Option `Continuous autonomous`:
  - `rationale:` No pauses between phases or sub-phases; each boundary still externalizes, compacts, and re-bootstraps from durable state before the next dispatch.
  - `recommendation:` acceptable — opt-in advancement; runs only when you set the profile `enforcement.continuous_execution` flag, pass `--no-pause`, or request it here.
  - `default-pointer:` Granular at phase only — continuous advancement is an explicit opt-in, never the shipped default.
- Option `Granular`:
  - `rationale:` Pause at every phase boundary AND every sub-phase boundary; you confirm continue at each pause; full operator-control posture.
  - `recommendation:` acceptable
  - `default-pointer:` Granular at phase only — full-granular is an explicit pause-cadence override.
- Option `Granular at sub-phase only`:
  - `rationale:` Pause at every sub-phase boundary; parent-phase transitions auto-continue (relevant for phases that decompose into sub-phase chains).
  - `recommendation:` acceptable
  - `default-pointer:` Granular at phase only — sub-phase-only pausing is an explicit pause-cadence override.

**1B — Blind Bootstrap Validation (CM-24 §6):** Ensures the session can execute the target phase with zero prior conversation history.

(a) Read PROGRESS.md Resumption Contract — adopt convention anchors, active decisions, and the critical-files manifest.
(b) Read PROGRESS.md Phase Output Registry — for every Input declared in the target phase file, verify the producing phase's output exists in the registry as ✅ Verified. If any input is ❌ MISSING: before reporting, check whether the declared output file actually exists on disk at its expected path. If the file exists but the registry entry is absent or unverified, report a "stale registry" condition. In `--dry-run`, report-only and modify no files. Outside `--dry-run`, offer to update the registry entry to Verified and proceed. Only report "prerequisite output absent" when the file genuinely does not exist on disk.
(c) If the Resumption Contract lists "Critical Files for Next Phase", read those files (and only those files) in the listed order.
(d) Confirm: all information needed for this phase exists in durable files that have been loaded. No residual conversation context from a prior session is required.
