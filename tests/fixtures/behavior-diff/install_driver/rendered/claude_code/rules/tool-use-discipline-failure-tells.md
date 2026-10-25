---
name: "tool-use-discipline-failure-tells"
description: "Path-filtered companion to tool-use-discipline carrying the failure-tells enumeration for the three tool-loop disciplines — sequential-where-parallel, act-without-observe, no-verifiable-exit, fixed-count-stop, and false-sequencing — declared at the parent rule's §Failure-tells anchor; demand-loaded on rule, command, skill, agent, hook, and output-style authoring surfaces where tool-loop cadence is exercised."
pathFilter: "**/CLAUDE.md, **/AGENTS.md, **/rules/**/*.md, **/commands/**/*.md, **/skills/**/*.md, **/agents/**/*.md, **/hooks/**/*.md, **/output-styles/**/*.md"
alwaysApply: false
paths:
  - "**/CLAUDE.md"
  - "**/AGENTS.md"
  - "**/rules/**/*.md"
  - "**/commands/**/*.md"
  - "**/skills/**/*.md"
  - "**/agents/**/*.md"
  - "**/hooks/**/*.md"
  - "**/output-styles/**/*.md"
---

<!-- SPDX-License-Identifier: MIT -->

# Rule: Tool-Use Discipline — Failure Tells (Companion Sub-Rule)

## Purpose

Carry the failure-tells enumeration for the three tool-loop disciplines that `rules/tool-use-discipline.md` §1 (parallel calls), §2 (observe → decide → act), and §3 (verifiable exit) bind. The parent rule keeps the three standing directives; this companion carries the catalog of failure shapes that betray each discipline broken, so the parent stays lean while the diagnostic detail loads on the authoring surfaces where the tool-loop cadence is exercised. Path-filtered: it demand-loads when the assistant authors or edits a CLAUDE.md, AGENTS.md, rule, command, skill, agent, hook, or output-style file — the surfaces that specify or drive tool-loop behavior.

## Failure tells

Each tell names one broken discipline and the shape it takes in practice:

- **Sequential where parallel was correct (§1).** Three `Read` calls across three turns to answer one question — the calls share no input/output edge, so the correct form was one batch, not three turns.
- **Act without observe (§2).** An `Edit` to a file the agent has not read in the current loop — the observe step was skipped, so the edit acts on unread state.
- **No verifiable exit (§3).** A "done" claimed on no checked condition — no gate passed, no test went green, no read confirmed the expected state; the loop closed on an unchecked sense of completion.
- **Fixed-count stop (§3).** A loop that stops after N tries with the exit condition still false and no retreat stated — the stop was a count, not a verifiable exit, and no defined retreat bounds the unconverged loop.
- **False-sequencing (§1).** A dependency asserted between two calls that share no input/output edge — a dependency the agent cannot name is not a dependency, so the calls should have batched.

## Enforcement

Path-filtered (the eight glob patterns in this rule's `pathFilter` field — CLAUDE.md / AGENTS.md / rules / commands / skills / agents / hooks / output-styles), always-on at every seriousness level when in scope. Demand-loaded companion to `rules/tool-use-discipline.md` §Failure-tells. The parent rule carries the §1 parallel-tool-execution directive, the §2 observe → decide → act loop, and the §3 verifiable-exit directive; this companion carries the five failure tells that betray each discipline broken. Advisory under the agnostic posture, matching the parent's disposition.
