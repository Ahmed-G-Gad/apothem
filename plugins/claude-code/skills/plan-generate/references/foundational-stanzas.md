<!-- SPDX-License-Identifier: MIT -->

## Foundational Stanzas

The four standing surfaces every operator inherits per the canonical project voice at `AGENTS.md` plus the active harness mirror — honored inline here, not by cross-reference alone.

### Refusal & Escalation

REFUSE any task whose scope exceeds this command's mission (generating a plan suite from an authored `_spec/spec.md` or operator-supplied prose). Refusal is explicit: name what was refused, name the mission boundary crossed, and surface an escalation option through the structured-inquiry channel per `rules/interactive-questions.md` (three-segment annotation; never free-form prose as primary input). Generation never proceeds against an `_inputs/` file (e.g., a `forge.md` mid-elicitation) — the upstream Forge must promote to `_spec/spec.md` first per the suite-locality invariant at `rules/context-management.md` §2.6.1.

### Output Surface

Plan suites land at `<project-root>/.apothem/plans/{suite}/` per the `CLAUDE.md` Plans Discipline (Plans Locality) and the suite-locality invariant at `rules/context-management.md` §2.6.1. The apothem source repo is itself the project root in the recursive Mirror-layout case (where the ecosystem repo IS its own project — for the claude_code harness that working tree is `~/.claude/`); in any downstream-project context, the command operates against the host project's `.apothem/plans/` tree. NEVER write a plan suite to a global-ecosystem location (`~/.config/`, `/etc/`, vendored language-runtime trees), and NEVER write across project boundaries within a single invocation. Every emitted infrastructure file (`PREAMBLE.md`, `MASTER-PLAN.md`, `PROGRESS.md`, `PLAN-NOTES.md`), every per-phase folder (`phases/NN-topic/PHASE.md`, sub-phases nested), and every generated-output directory (`_outputs/` when durable emissions exist) is suite-internal.

### File-Authoring Contract

Plan-suite infrastructure files (PREAMBLE, MASTER-PLAN, PROGRESS, PLAN-NOTES) and per-phase PHASE.md files are plan-internal artifacts; they are header-exempt per the `.apothem/**` exception class at `src/apothem/schemas/header-exceptions.txt`. The injector at `scripts/inject-header.{sh,py}` is therefore NOT invoked on plan-suite emissions. When this command incidentally augments a host-project artifact outside the suite folder (the canonical `<project-root>/.gitignore` snippet for the `.plans/` ignore is the only such case), the file is treated under the host's existing convention — append-with-comment if the snippet is absent, never overwrite.

### Structured Inquiry on Ambiguity

When uncertain about identity / scope / preference / security / naming / infrastructure / version data — or any branch-point, deletion decision, or judgment call that materially affects the outcome — route the resolution through the structured-inquiry channel with the three-segment annotation per `rules/interactive-questions.md` §3 (rationale / recommendation / default-pointer). Free-form prose questions as primary input are forbidden. NEVER fabricate authoritative data. Step 3 (Discovery — User Clarification Batches) is the dominant inquiry surface; suite-overwrite decisions at Step 4 route through the §6.4 canonical Delete option set per the destructive-op floor.
