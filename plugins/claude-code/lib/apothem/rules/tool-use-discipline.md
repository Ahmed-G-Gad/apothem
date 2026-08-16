---
name: "tool-use-discipline"
description: "Ordinary tool use runs as a disciplined loop: independent tool calls go in one turn, never sequentially; the agent works an observe → decide → act cadence; the loop iterates until a verifiable exit condition is met, never a fixed count. Generalizes the agent-tier single-message parallel-launch discipline down to every tool call. Harness-agnostic; advisory under the agnostic posture."
pathFilter: ""
alwaysApply: true
---

<!-- SPDX-License-Identifier: MIT -->

# Rule: Tool-Use Discipline — Parallel Calls, the Observe → Decide → Act Loop

## Purpose

Every tool an agent reaches for is a step in a loop, not an isolated act. This rule names that loop and binds two disciplines on it: independent calls run together in one turn, and the loop runs until a verifiable condition closes it. The agent-orchestration rules carry the same discipline at the agent-team tier; this rule states it for ordinary tool use, below the team threshold.

## Obligations

### 1. Parallel Tool Execution

Independent tool calls — calls whose inputs do not depend on each other's outputs — MUST be issued together in a single turn, never one-per-turn in sequence. Reading three files, grepping two patterns, and listing a directory to answer one question is one batch, not five turns. This generalizes the single-message parallel-launch invariant `rules/agent-orchestration.md` §3 binds at the agent-dispatch tier down to the ordinary-tool tier: the same latency and context gain applies whether the parallel unit is an agent or a `Read`.

Sequence only on a genuine dependency — when call B's input is call A's output, A precedes B. A dependency the agent cannot name is not a dependency; batch the calls.

### 2. The Observe → Decide → Act Loop

The agent's canonical working cadence is **observe → decide → act**: observe the current state (read context, run a tool, inspect a result), decide the next move from what was observed, act, then observe again. Naming the loop makes the cadence explicit. The lineage is loop-engineering; the vocabulary is apothem's own.

A turn that acts without first observing — edits a file it has not read this loop, asserts a result it has not checked — has skipped the observe step. Read-before-edit, locate-before-read per `rules/large-file-reading.md`, and check-before-claim are the same discipline at the tool tier.

### 3. Iterate to a Verifiable Exit, Never a Fixed Count

The loop continues until a **verifiable exit condition** is true — a gate passes, a test goes green, a build succeeds, a read confirms the expected state — never until a fixed iteration count elapses, never on the agent's unchecked sense that it is "probably done." When no machine-checkable exit exists, the loop closes on an explicit stated criterion the operator can audit, not a silent stop. This is the tool-tier form of the open-loop discipline `rules/multi-agent-workflow.md` §1 declares for multi-agent waves; a bounded retry with a defined retreat per `rules/context-management.md` §8 bounds the loop when the exit resists convergence.

## Failure tells

(Companion Sub-Rule Anchor) See `rules/tool-use-discipline-failure-tells.md` §Failure-tells for the five failure-shape diagnostics — sequential-where-parallel (§1), act-without-observe (§2), no-verifiable-exit (§3), fixed-count-stop (§3), and false-sequencing (§1).

## Bindings (§0.j five-direction)

- **Drives →** ● Every ordinary tool-call batch (independent calls issued together per §1). ● Every agent working cadence (the observe → decide → act loop per §2). ● Every loop's exit decision (verifiable condition, never fixed count, per §3).
- **Satisfies →** ● The tool-tier generalization of the single-message parallel-launch discipline. ● The named canonical agent-loop vocabulary the ecosystem references.
- **Established by ↑** ● `rules/agent-orchestration.md` §3 (the agent-tier single-message parallel-launch invariant this rule generalizes down to ordinary tool calls). ● `rules/multi-agent-workflow.md` §1 (the open-loop verifiable-exit discipline this rule states at the tool tier).
- **Gated by ←** ● `CLAUDE.md` always-loaded preamble. ● `rules/agnostic-posture.md` §2 (this rule is advisory, not a blocking gate).
- **Cross-bound with ↔** ↔ `rules/tool-use-discipline-failure-tells.md` (path-filtered companion carrying the §Failure-tells enumeration — the five failure-shape diagnostics for §1 / §2 / §3). ↔ `rules/agent-orchestration.md` (§3 single-message parallel-launch — this rule is its ordinary-tool-tier generalization; the team-tier mechanics are owned there). ↔ `rules/context-management.md` (§7.2 demand-loading and §8 bounded-retry-with-retreat — the observe step preserves context budget and the loop's retreat path is owned there). ↔ `rules/large-file-reading.md` (locate-before-read is the observe-step discipline at the file tier). ↔ `rules/multi-agent-workflow.md` (§1 open-loop verifiable-exit — this rule states the same exit discipline at the tool tier, below the multi-agent threshold). ↔ `rules/multi-agent-workflow-shape.md` (§1 open-loop verifiable-exit discipline — the open-loop-dynamics property of the capability shape is the agent-tier expression of the ordinary-tool-tier loop stated there).

## Recommended Next Step

**Batch the next set of independent tool calls into one turn** and name the loop's verifiable exit condition before acting, per §1 and §3 of this rule.
