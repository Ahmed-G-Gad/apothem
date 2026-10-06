---
trigger: glob
description: "Path-filtered companion sub-rule to multi-agent-workflow.md — carries the four-property capability-shape enumeration (independent agents, adversarial critique, open-loop dynamics, dynamic pacing), the model- and effort-agnostic detail, the synthesis-quality-and-lean-main-thread form, and the seriousness-scaling recommendation table declared at the parent rule's §1, §3, and §Seriousness-Scaling anchors; demand-loaded on agent / workflow-command / workflow-skill and multi-agent authoring surfaces."
globs: "**/agents/**, **/commands/workflow*.md, **/skills/workflow/**, **/*workflow*.md, **/*multi-agent*.md"
---

<!-- SPDX-License-Identifier: MIT -->

# Rule: Multi-Agent Workflow — Capability Shape, Agnosticism, Synthesis & Scaling (Companion Sub-Rule)

## Purpose

Carry the situational depth of the multi-agent-workflow capability the parent rule `rules/multi-agent-workflow.md` anchors. Path-filtered: it demand-loads when the assistant authors an agent definition, a workflow command, a workflow skill, or any multi-agent surface — the surfaces where multi-agent work is actually engaged. The parent retains the always-on directive core (the §2 default-off / opt-in precedence and the capability declaration a clean install reads every session); this companion carries the §1 four-property capability-shape enumeration, the §3 model- and effort-agnostic detail, the synthesis-quality-and-lean-main-thread form, and the seriousness-scaling recommendation table. It neither turns the capability on nor restates the orchestration mechanics — those are owned by `rules/agent-orchestration.md`.

## Obligations

### 1. The Capability Shape (Parent §1 Detail)

The ecosystem ships a complete, specified path for multi-agent execution along four properties:

- **Genuinely-independent agents** — non-shared context, independent reasoning; each agent reaches its finding without inheriting another's conclusions.
- **Adversarial / zero-trust critique** — each finding is verified by an agent prompted to refute it, so a claim earns its place against its strongest counter-evidence rather than by assertion.
- **Open-loop dynamics** — waves continue until a convergence or exhaustion criterion is met, never a fixed count; the loop's exit is a verifiable state, not a pre-set number of rounds.
- **Dynamic pacing** — depth scales to the work and the operator's stated budget; a shallow question earns a shallow sweep, a deep mission a deep one.

The deployment patterns, return contracts, and isolation discipline for these four properties are owned by `rules/agent-orchestration.md` and its companion; this rule enumerates the shape, it does not duplicate the mechanics.

### 2. Model- and Effort-Agnostic (Parent §3 Detail)

The capability carries no model tier, effort preset, or verbosity default. Which model runs an agent, and at what effort, resolve only from the operator's explicit choice per `rules/agnostic-posture.md` §4; the workflow specification is agnostic to both. A hardcoded model tier or effort preset attached to the capability is the failure tell the parent names.

### 3. Synthesis Quality and a Lean Main Thread (Parent §3 Detail)

Once opted in, the preferred shape is genuinely-independent critique-**synthesis**: every load-bearing finding earns its place against its strongest counter-evidence, and the main conversation stays **lean** — raw agent output is released after a single-pass synthesis. Load-bearing decisions ground in current authoritative sources, not memory; a disclosed grant covers beyond-mission remediation. This is the form once engaged, never a clean-install imposition.

## Seriousness Scaling (Parent §Seriousness-Scaling Detail)

| Level | Multi-agent capability |
| ----- | ---------------------- |
| EXPLORING | Available; opt-in; rarely warranted. |
| PERSONAL_USE | Available; opt-in; encouraged for parallelizable critique work once chosen. |
| SHARED | Available; opt-in; the specified path for independent multi-dimension verification when the operator invokes it. |
| PUBLIC_LAUNCH | Available; opt-in; the recommended path for adversarial verification of public-surface artifacts when the operator invokes it — still never auto-applied. |

The table scales the *recommendation strength* once opted in, never the default state (off per `rules/agnostic-posture.md` §1).

## Enforcement

Path-filtered (the five glob patterns in this rule's `pathFilter` field — `**/agents/**`, `**/commands/workflow*.md`, `**/skills/workflow/**`, `**/*workflow*.md`, `**/*multi-agent*.md`), demand-loaded companion to `rules/multi-agent-workflow.md` §1 / §3 / §Seriousness-Scaling. The parent carries the always-on directive core (the default-off / opt-in precedence and the capability declaration); this companion carries the capability-shape enumeration, the model / effort agnosticism detail, the synthesis-quality form, and the seriousness-scaling table. Together the parent and companion constitute the canonical specification for the multi-agent-workflow capability. Opt-in at every seriousness level; never always-on.

## Bindings (§0.j five-direction)

- **Drives →** ● The discoverability of the four-property multi-agent capability shape on agent / workflow authoring surfaces. ● The model / effort agnosticism every agent dispatch resolves from the operator's explicit choice. ● The critique-synthesis form and lean-main-thread discipline once the capability is opted in. ● The recommendation-strength calibration the seriousness table assigns per level.
- **Satisfies →** ● the rules registry row "Multi-Agent Workflow Shape". ● `rules/multi-agent-workflow.md` §1 / §3 / §Seriousness-Scaling anchors (the parent rule's pointers to this companion's enumeration, agnosticism detail, synthesis prose, and scaling table).
- **Established by ↑** ● `rules/multi-agent-workflow.md` (parent-rule anchor — the capability declaration and default-off / opt-in precedence this companion details). ● the operator's standing-mandate set (the multi-agent-workflow mandate — capability available and specified, activation opt-in).
- **Gated by ←** ● The path-filter (the five glob patterns) — this rule demand-loads only on agent / workflow-command / workflow-skill / multi-agent authoring touches. ● `rules/multi-agent-workflow.md` always-on baseline (the parent's capability declaration and default-off precedence must be live for the shape / agnosticism / synthesis / scaling detail to apply coherently). ● `rules/agnostic-posture.md` §1 (default-off precedence controls activation) and §4 (end-user-invoked model / effort controls the agnosticism).
- **Cross-bound with ↔** ↔ `rules/multi-agent-workflow.md` (parent rule; §1 / §3 / §Seriousness-Scaling anchors bind this companion). ↔ `rules/agnostic-posture.md` (§1 default-off precedence governs the capability's activation; §4 end-user-invoked preference governs its model / effort agnosticism — the agnostic posture controls on any apparent conflict). ↔ `rules/agent-orchestration.md` (the team-pattern catalog, launch protocol, return contracts, and isolation discipline the four-property shape runs through are owned there; this companion enumerates the shape, never duplicates the mechanics). ↔ `rules/tool-use-discipline.md` (§1 open-loop verifiable-exit discipline — the open-loop-dynamics property of the capability shape is the agent-tier expression of the ordinary-tool-tier loop stated there).
