---
trigger: glob
description: "Path-filtered companion to tool-use-discipline carrying the failure-tells enumeration for the three tool-loop disciplines — sequential-where-parallel, act-without-observe, no-verifiable-exit, fixed-count-stop, and false-sequencing — declared at the parent rule's §Failure-tells anchor; demand-loaded on rule, command, skill, agent, and hook authoring surfaces where tool-loop cadence is exercised."
globs: "**/rules/**, **/commands/**, **/skills/**, **/agents/**, **/hooks/**"
---

<!-- SPDX-License-Identifier: MIT -->

# Rule: Tool-Use Discipline — Failure Tells (Companion Sub-Rule)

## Purpose

Carry the failure-tells enumeration for the three tool-loop disciplines that `rules/tool-use-discipline.md` §1 (parallel calls), §2 (observe → decide → act), and §3 (verifiable exit) bind. The parent rule keeps the three standing directives; this companion carries the catalog of failure shapes that betray each discipline broken, so the always-on parent stays lean while the diagnostic detail loads on the authoring surfaces where the tool-loop cadence is exercised. Path-filtered: it demand-loads when the assistant authors or edits a rule, command, skill, agent, or hook — the surfaces that specify or drive tool-loop behavior.

## Failure tells

Each tell names one broken discipline and the shape it takes in practice:

- **Sequential where parallel was correct (§1).** Three `Read` calls across three turns to answer one question — the calls share no input/output edge, so the correct form was one batch, not three turns.
- **Act without observe (§2).** An `Edit` to a file the agent has not read in the current loop — the observe step was skipped, so the edit acts on unread state.
- **No verifiable exit (§3).** A "done" claimed on no checked condition — no gate passed, no test went green, no read confirmed the expected state; the loop closed on an unchecked sense of completion.
- **Fixed-count stop (§3).** A loop that stops after N tries with the exit condition still false and no retreat stated — the stop was a count, not a verifiable exit, and no defined retreat bounds the unconverged loop.
- **False-sequencing (§1).** A dependency asserted between two calls that share no input/output edge — a dependency the agent cannot name is not a dependency, so the calls should have batched.

## Enforcement

Path-filtered (the five glob patterns in this rule's `pathFilter` field — rules / commands / skills / agents / hooks), always-on at every seriousness level when in scope. Demand-loaded companion to `rules/tool-use-discipline.md` §Failure-tells. The parent rule carries the §1 parallel-tool-execution directive, the §2 observe → decide → act loop, and the §3 verifiable-exit directive; this companion carries the five failure tells that betray each discipline broken. Advisory under the agnostic posture, matching the parent's disposition.

## Bindings (§0.j five-direction)

- **Drives →** ● The self-check every tool-loop cadence applies before claiming a step done (the five failure-shape diagnostics). ● The reviewer's read of a landed tool-loop for the sequential-where-parallel, act-without-observe, and unchecked-exit tells.
- **Satisfies →** ● the rules registry row "Tool-Use Discipline Failure Tells". ● `rules/tool-use-discipline.md` §Failure-tells anchor (the parent rule's pointer to this companion's enumeration).
- **Established by ↑** ● `rules/tool-use-discipline.md` §1 / §2 / §3 (the three disciplines whose broken shapes this companion enumerates). ● `rules/agnostic-posture.md` §2 (advisory disposition inherited from the parent).
- **Gated by ←** ● The path-filter (the five glob patterns) — this rule demand-loads only on rule / command / skill / agent / hook authoring surfaces. ● `rules/tool-use-discipline.md` always-on baseline (the parent's three directives must be live for the failure tells to diagnose coherently).
- **Cross-bound with ↔** ↔ `rules/tool-use-discipline.md` (parent rule; §1 / §2 / §3 / §Failure-tells anchors bind this companion). ↔ `rules/agent-orchestration.md` (§3 single-message parallel-launch — the sequential-where-parallel tell is its violation at the ordinary-tool tier). ↔ `rules/large-file-reading.md` (locate-before-read is the observe-step discipline the act-without-observe tell violates). ↔ `rules/multi-agent-workflow.md` (§1 open-loop verifiable-exit — the no-verifiable-exit and fixed-count-stop tells are its violations below the multi-agent threshold).
