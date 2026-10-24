---
name: "agent-orchestration"
description: "Agent and agent team orchestration — the six canonical team patterns (Research, Audit, Implementation, Generation, Quality, Documentation), the deploy-when threshold (3+ independent parallel operations, multi-path exploration, heavy reads, multi-dimension verification, multi-file generation), the single-message parallel-launch invariant, explicit return contracts, and context isolation. Canonical specification for CM-17 / CM-25."
pathFilter: "**/agents/**/*.md, **/commands/plan-*.md, **/skills/**/SKILL.md, **/rules/agent-orchestration*.md"
alwaysApply: false
paths:
  - "**/agents/**/*.md"
  - "**/commands/plan-*.md"
  - "**/skills/**/SKILL.md"
  - "**/rules/agent-orchestration*.md"
---

<!-- SPDX-License-Identifier: MIT -->

# Rule: Agent Orchestration

## Purpose

Govern agent deployment: maximize parallelism, enforce return contracts, isolate context, prevent duplication and contradiction. Canonical specification for CM-17 (Worker Teams) and CM-25 (Worker Orchestration).

## Obligations

### 1. Standing Directive

Deploy agent teams to maximize parallelism, enforce return contracts, isolate context, and prevent duplication and contradiction. Six canonical team patterns — **Research**, **Audit**, **Implementation**, **Generation**, **Quality**, **Documentation** — each binding an agent type, a parallelism shape, and a return-contract template. (Companion Sub-Rule Anchor) See `rules/agent-orchestration-patterns.md` §1 for the full team-pattern catalog.

### 2. Deployment Heuristic

**Deploy** when ANY holds: 3+ independent parallel operations, multi-path exploration, heavy reads that bloat the main context, multi-dimension verification, or multi-file generation. **Skip** when ANY holds: <3 operations, tightly-coupled sequential steps, coordination overhead exceeds the parallelism benefit, or the main context already holds the needed information.

**Standing delegation default (lean-context posture).** Where the host exposes agent / subagent dispatch, broad reads, large-corpus consumption, and heavy workloads SHOULD route to a spawned agent **by default** — keeping the main context lean is the standing posture, not only the explicit opt-in path. This is advisory SHOULD-guidance about *where* delegable work runs when dispatch is available; it never makes the heavy multi-agent apparatus a clean-install obligation. The apparatus itself stays default-off per `rules/agnostic-posture.md` §1; this default governs only routing once delegation is reachable. Where the host exposes no dispatch surface, the work runs in the main context. (Companion Sub-Rule Anchor) See `rules/agent-orchestration-patterns.md` §2 for agent-type selection (`Explore` / `general-purpose` / `Plan`) and model-tier selection (lightweight / balanced / deep-reasoning).

### 3. Launch Protocol

Every agent prompt MUST carry six elements: Mission + Deliverable + Constraints + Context + Return contract + File scope (Implementation Teams). Independent agents MUST launch in a SINGLE message with multiple Agent tool calls; dependent agents are grouped into waves (Wave 1 independent → collect → Wave 2 dependent). Foreground is the default; `run_in_background: true` is for genuinely-independent long-running work — never poll or sleep. (Companion Sub-Rule Anchor) See `rules/agent-orchestration-patterns.md` §3 for the full prompt-engineering, parallel-launch, and background/foreground specification.

### 4. Return Contract Invariant

Every agent launch MUST specify an explicit return contract: format, maximum size, required fields, and fallback shape. Results are processed in a single pass, verified against the contract, synthesized into a compact summary, and the raw output is released — never held in context beyond the turn it is processed. (Companion Sub-Rule Anchor) See `rules/agent-orchestration-patterns.md` §4 for contract-specification, result-processing, and context-integration detail.

### 5. Isolation, Non-Duplication, Error Handling

Each agent operates on a non-overlapping scope; agents touching the same file MUST be sequenced or use `isolation: "worktree"`. The main context MUST NOT duplicate work an agent is performing. Parallel outputs are checked for consistency before integration. Timeouts continue; failures retry once; 2+ team failures degrade the team result; contradictions escalate to the main context. (Companion Sub-Rule Anchor) See `rules/agent-orchestration-patterns.md` §5–§6 for isolation, non-duplication, coherence-verification, and error-handling detail.

### 6. Decision Tree and Anti-Patterns

The orchestration decision tree (deploy / skip → agent type → parallel / solo → isolation → return contract → synthesize) and the six canonical anti-patterns (single-agent-for-direct-tool-task, sequential-when-parallel, main-context-duplicating-agent-work, raw-results-held-in-context, no-return-contract, deep-reasoning-on-trivial-task). (Companion Sub-Rule Anchor) See `rules/agent-orchestration-patterns.md` Decision Tree + Anti-Patterns sections.

## Seriousness Scaling

> **Two-axis scaling note.** Unlike most rules (single column), this scaling table tracks two orthogonal dimensions: **deployment requirement** (when to use agents at all) and **agent sophistication** (which model tier to prefer). They scale at different rates with seriousness — e.g., a SHARED project may demand parallel teams (axis 1) while still using balanced-tier models for routine work (axis 2). Read the columns independently.

| Level | Agent Team Requirement | Agent Sophistication |
| ----- | ---------------------- | -------------------- |
| EXPLORING | Optional | Lightweight tier for cost efficiency |
| PERSONAL_USE | Encouraged for parallelizable work | Balanced tier for standard tasks |
| SHARED | Required for 3+ independent parallel operations — strict return contracts enforced | Deep-reasoning tier for critical decisions, balanced tier for standard |
| PUBLIC_LAUNCH | Required for 2+ independent operations. Isolation verification after parallel completion | Deep-reasoning tier for all agents touching shared/public artifacts |

## Enforcement

Applies at every seriousness level, scaling per the table above. Implements CM-17/CM-25. Canonical specification for agent and agent team orchestration.
