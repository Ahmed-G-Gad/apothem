---
name: "multi-agent-workflow"
description: "Independent-critique, open-loop, dynamic multi-agent execution is an available, specified capability — opt-in and default-off under the agnostic posture, never imposed on a clean install; the orchestration mechanics are owned by agent-orchestration."
pathFilter: ""
alwaysApply: true
---

<!-- SPDX-License-Identifier: MIT -->

# Rule: Multi-Agent Workflow — Available Capability, Opt-In by Default

## Purpose

Declare genuinely-independent, critique-driven, open-loop, dynamically-paced multi-agent execution as a first-class capability the ecosystem ships and specifies — so it is discoverable and reachable — while binding its activation entirely to the operator's explicit opt-in. This rule names the capability and its default state; it neither turns it on nor restates the orchestration mechanics.

## Obligations

### 1. The capability is available and specified

The ecosystem ships a complete, specified path for multi-agent execution: genuinely-independent agents, adversarial / zero-trust critique, open-loop convergence dynamics, and dynamic pacing. The deployment patterns, return contracts, and isolation discipline are owned by `rules/agent-orchestration.md` and its companion; this rule does not duplicate them. (Companion Sub-Rule Anchor) See `rules/multi-agent-workflow-shape.md` §1 for the four-property capability-shape enumeration.

### 2. Default-off, opt-in — precedence to the agnostic posture

This capability ships **default-off**. A clean install **MUST NOT** auto-invoke a multi-agent workflow. It activates only on the operator's explicit in-conversation choice or an `enforcement` opt-in flag, exactly as `rules/agnostic-posture.md` §1 governs every default-off behavior. On any apparent conflict, the agnostic posture's default-off precedence controls. "Available and specified" describes the capability's shape once opted in, never an always-on imposition.

### 3. Model-agnostic and synthesis-shaped once engaged

The capability carries no model tier, effort preset, or verbosity default, and its opted-in form is genuinely-independent critique-**synthesis** with a lean main thread. (Companion Sub-Rule Anchor) See `rules/multi-agent-workflow-shape.md` §2 for the model / effort agnosticism (resolved per `rules/agnostic-posture.md` §4), §3 for the synthesis-quality form, and §Seriousness-Scaling for the level-by-level recommendation table.

## Enforcement

Opt-in at every seriousness level; never always-on. The seriousness table (companion) scales the *recommendation strength* once opted in, never the default state (off per `rules/agnostic-posture.md` §1).

## Failure tells

A multi-agent workflow auto-invoked on a clean install with no operator opt-in; this rule read as mandating agent teams (it declares availability, not obligation); a hardcoded model tier or effort preset attached to the capability; the orchestration mechanics (team patterns, launch protocol, return contracts) re-specified here instead of referenced from `rules/agent-orchestration.md`.

## Bindings (§0.j five-direction)

- **Drives →** The discoverability of the independent-critique / open-loop / dynamic multi-agent path; the recommendation strength (never the default state) the seriousness table assigns once an operator opts in.
- **Satisfies →** The standing-mandate end-state that the multi-agent capability is specified and reachable without ever being imposed on a clean install.
- **Established by ↑** The operator's standing-mandate set (the multi-agent-workflow mandate — capability available and specified, activation opt-in).
- **Gated by ←** `rules/agnostic-posture.md` §1 (default-off precedence) and §4 (end-user-invoked model / effort) — the agnostic posture controls activation and on any apparent conflict.
- **Cross-bound with ↔** `rules/multi-agent-workflow-shape.md` (path-filtered companion carrying the §1 capability-shape enumeration, the §2 model / effort agnosticism detail, the §3 synthesis-quality prose, and the §Seriousness-Scaling table; the parent §1 / §3 anchors bind this companion); `rules/agnostic-posture.md` (§1 default-off precedence governs this capability's activation; §4 end-user-invoked preference governs its model / effort agnosticism — the agnostic posture controls on any apparent conflict); `rules/agent-orchestration.md` (the team-pattern catalog, launch protocol, return contracts, and isolation discipline this capability runs through are owned there; this rule references, never duplicates, them); `rules/operational-mandates.md` (CM-1 critical evaluation governs the deploy/skip decision this capability is invoked under; CM-17/CM-25 establish the agent orchestration it runs through); `rules/tool-use-discipline.md` (§1 open-loop verifiable-exit discipline this rule declares for multi-agent waves is stated at the ordinary-tool tier there). ↔ `rules/tool-use-discipline-failure-tells.md` (§1 open-loop verifiable-exit — the no-verifiable-exit and fixed-count-stop tells are its violations below the multi-agent threshold).
