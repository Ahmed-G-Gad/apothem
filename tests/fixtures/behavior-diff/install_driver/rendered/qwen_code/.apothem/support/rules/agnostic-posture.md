---
name: "agnostic-posture"
description: "Default-off, opt-in posture for every shipped behavior; correctness gates stay advisory; every surface is harness-neutral; model, effort, and workflow preference resolve only from an explicit in-conversation choice."
pathFilter: ""
alwaysApply: true
---

<!-- SPDX-License-Identifier: MIT -->

# Rule: Agnostic Posture — Default-Off, Opt-In, Harness-Neutral

## Purpose

Govern the shipped posture so a clean install imposes nothing — no workflow ceremony, no model or effort preset, no harness bias auto-applied. Every behavior is reachable, but only the end user turns it on. This rule is the standing frame every other shipped rule and command reads its enforcement defaults through.

## Obligations

### 1. Default-off behaviors

Workflow behaviors — the sprint apparatus, agent-team dispatch, parallel multitasking, continuous multi-step advancement, and continuous-learning capture — ship **default-off**. A clean install MUST run a request with none of them engaged. Each is opt-in through the shared profile's `enforcement` flags (every flag defaults `false`); set a flag `true` to invoke that behavior. Where a sibling rule marks one of these behaviors "always-on", "mandatory", or "required at" a tier, that marking describes the behavior's shape **once the operator opts in** — never an imposition on a clean install.

### 2. Advisory correctness gates

Correctness and quality gates — lint, format, type-check, test, security scan, conformance, the pre-emission gate — stay active but **advisory**. Each MUST emit its findings plus a definitive next step and then yield; none blocks, aborts, or silently mutates the end user's action. The end user decides what to do with a finding.

### 3. Harness neutrality

No shipped surface carries tailoring for one harness. Every rule, command, output-style, statusline, and template MUST render identically across every registered harness. A harness name appears only as one catalog entry among many — never as a tailored default, a privileged path, or an assumed runtime.

### 4. End-user-invoked preference

Model, effort, and workflow preference resolve only from an explicit in-conversation choice. No shipped config pre-determines them; the default state is unset, and the agent asks or waits rather than guessing.

### 5. Machinery preserved

De-enforced behavior MUST NOT be deleted. Each behavior keeps a working invocation path — an opt-in flag, a documented command, a named procedure — so opting in restores it intact. Preservation, not removal, is the discipline.

### 6. Verification

The per-invariant verification checklist for this posture — each of the five obligations restated as a checkable invariant with a concrete verification step — lives at the path-filtered companion `agnostic-posture-checklist.md`. Every phase that changes a shipped surface runs the checklist as its agnosticism definition-of-done gate.

## Bindings (§0.j five-direction)

- **Drives →** the default-off shape of every shipped rule and command; the shared profile's `enforcement` opt-in flags; the advisory framing every correctness gate honors; the harness-neutral rendering of every shipped surface.
- **Driven by ←** the operator directive that the agent impose no workflow, model, or effort and delegate every such preference to the end user.
- **Gated by ←** `alwaysApply: true` with an empty `pathFilter`: the posture loads in every session. The shared profile's `enforcement` flags (each defaults `false`; only an end-user opt-in turns a behavior on). `conformity/agnosticism_grep.py` (the mechanical §3 harness-neutrality and §1 default-off sweep under `gate --all`).
- **Satisfies →** the agnostic, zero-enforcement posture across the whole shipped surface; the harness-neutrality floor.
- **Established by ↑** `operational-mandates.md` (CM-1 critical evaluation gates whether any behavior is imposed); the shared-profile `enforcement` schema (the opt-in surface this rule references).
- **Cross-bound with ↔** `agnostic-posture-checklist.md` (the path-filtered companion carrying this posture's per-invariant verification checklist); `agile-sprints.md` (sprint apparatus is opt-in here); `agent-orchestration.md` (agent-team dispatch is opt-in here); `context-management.md` (continuous advancement is opt-in here); `interactive-questions.md` (preference selection routes through the end user); `pre-emission-gate.md` (its bars surface as advisories, not blocks); `own-voice-reimplementation.md` (reimplementations derive conventions from each harness's own documentation under this host-agnostic posture, not from a single reference); `multi-agent-workflow.md` (the independent-critique / open-loop / dynamic multi-agent capability is opt-in and default-off under this posture's §1; §4 governs its model and effort agnosticism — this posture controls on any apparent conflict); `agents-md-convention.md` (the per-folder folder-guidance surface that inherits the agnostic posture — every folder README's agent-facing guidance and any standalone companion privileges no harness, model, or effort). ↔ `rules/agent-orchestration.md` (agent-team dispatch is opt-in under the host-agnostic posture, not a default-on obligation). ↔ `rules/agile-sprints.md` (the sprint apparatus is opt-in under the host-agnostic posture, not a default-on obligation). ↔ `rules/context-management.md` (continuous single-session advancement is opt-in under the host-agnostic posture, not a default-on obligation). ↔ `rules/interactive-questions.md` (preference selection routes through the end user under the host-agnostic posture rather than being silently picked). ↔ `rules/multi-agent-workflow.md` (§1 default-off precedence governs this capability's activation; §4 end-user-invoked preference governs its model / effort agnosticism — the agnostic posture controls on any apparent conflict). ↔ `rules/multi-agent-workflow-shape.md` (§1 default-off precedence governs the capability's activation; §4 end-user-invoked preference governs its model / effort agnosticism — the agnostic posture controls on any apparent conflict). ↔ `rules/operational-mandates.md` (↔ reciprocal of the peer's Cross-bound citation). ↔ `rules/own-voice-reimplementation.md` (host-agnostic posture; reimplementations derive conventions from each harness's own documentation, not from a single reference). ↔ `rules/pre-emission-gate.md` (under the host-agnostic posture the gate's bars surface as advisories, not blocks).
