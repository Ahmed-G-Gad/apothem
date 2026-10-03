---
trigger: always_on
description: "Auto memory lifecycle augmenting the harness built-in — classifies memory against PROGRESS.md / PLAN-NOTES.md / skills (stable fact/convention/preference/insight → memory; plan/task-specific → PROGRESS/PLAN-NOTES; reusable technique with detection signal → skill), bans session-specific context / incomplete info / CLAUDE.md duplicates / plan-specific decisions / ephemeral facts, and anchors topic-file hygiene to the path-filtered companion."
---

<!-- SPDX-License-Identifier: MIT -->

# Rule: Auto Memory Lifecycle

## Purpose

Augment the harness's built-in auto memory with ecosystem discipline: separate memory from other state artifacts, enforce topic organization, and prevent content misplacement. Canonical specification for CM-26 (Auto Memory Lifecycle).

## Obligations

### 1. Memory vs. Other State Files

Memory is one of four persistent-state artifacts. Place content by destination:

| Artifact | Location | Holds |
| -------- | -------- | ------- |
| **Memory** | `<harness-root>/projects/{hash}/memory/` | Stable patterns, conventions, preferences, architectural decisions, debugging insights |
| **PROGRESS.md** | Plan suite directory | Current task state, phase tracker, Resumption Contract |
| **PLAN-NOTES.md** | Plan suite directory | Decisions, Q&A audit trail, gap analysis |
| **Skills** | `skills/*/SKILL.md` | Reusable techniques with detection signals and procedures |

**Decision rule.** Plan- or task-specific → PROGRESS.md or PLAN-NOTES.md. Reusable technique with a detection signal → skill. Stable fact, convention, preference, or insight → memory.

### 2. What NOT to Write

Memory MUST NOT carry any of six classes:

- **Session-specific context** — current task details, in-progress work, temporary state (→ PROGRESS.md).
- **Incomplete information** — unverified assumptions, single-file speculative conclusions.
- **CLAUDE.md duplicates** — anything that duplicates or contradicts CLAUDE.md.
- **Plan-specific decisions** (→ PLAN-NOTES.md).
- **Reusable techniques with detection signals** (→ skills).
- **Ephemeral facts** — values stale by next session (branch names, PR numbers).

### 3. Topic-File Hygiene & Lifecycle (Companion Sub-Rule Anchor)

MEMORY.md indexing, topic-file naming / sizing / split / merge, deduplication, staleness pruning, contradiction resolution, corruption resilience, two-tier project / global layout, promotion-ledger schema, Stop-hook session-end procedure, decision tree, anti-patterns. See `rules/auto-memory-topic-files.md`.

## Seriousness Scaling

> **Invariant.** §2 bans (no session-specific context, no incomplete information, no CLAUDE.md duplicates, no plan-specific decisions, no reusable techniques in memory, no ephemeral facts) apply at every seriousness level. The table below specifies what to ADD per level on top of those bans, not what to relax.

| Level | Memory Behavior |
| ----- | --------------- |
| EXPLORING | Write only user-requested memories. If the user's request conflicts with §2 bans, explain the conflict and decline rather than silently proceed |
| PERSONAL_USE | Write confirmed patterns and user preferences |
| SHARED | Full lifecycle. Write architectural decisions, debugging insights. Prune stale entries on detection |
| PUBLIC_LAUNCH | Full lifecycle. Staleness audit mandatory at session start. Cross-project extraction candidates flagged proactively. Active pruning every session |

## Enforcement

Always-on at every seriousness level, scaling per the table above. Implements CM-26. Canonical specification for memory lifecycle, topic organization, and content placement.

## Bindings (§0.j five-direction)

- **Drives →** ● Every memory write/update/prune cycle across every project's `<harness-root>/projects/{hash}/memory/` tree. ● Session-end memory evaluation per the Stop hook's CM-26 dispatch. ● `MEMORY.md` index discipline (under-200-lines invariant). ◐ Cross-project pattern extraction at the highest seriousness tier (the promotion-ledger discipline at `rules/auto-memory-topic-files.md` §2 records every promotion event). ◐ The two-tier memory layout (project-specific `<harness-root>/projects/{hash}/memory/` vs. global `<harness-root>/memory/`).
- **Satisfies →** ● CM-26 (Auto Memory Lifecycle — rule-delegated mandate). ● the rules registry row "Auto Memory". ● the artifact directories (project vs. global memory tier declaration).
- **Established by ↑** ● CM-26. ● the artifact directories (memory paths declared there). ● `rules/context-management.md` §2.5 Externalize-On-Phase-Exit (memory evaluation is delegated here).
- **Gated by ←** ● Session-end Stop hook firing (the canonical session-boundary trigger). ● PROGRESS.md / PLAN-NOTES.md / skill artifacts taking precedence per the §1 decision rule (memory is the residual destination).
- **Cross-bound with ↔** ↔ `rules/auto-memory-topic-files.md` (path-filtered companion sub-rule carrying §1 ecosystem-specific hygiene, §2 topic-file management, §3 session-end evaluation, §4 decision tree, and §5 anti-patterns). ↔ `rules/context-management.md` (the §2.5 phase-exit protocol delegates memory evaluation here; the companion's §3 session-end evaluation pairs with that delegation). ↔ `rules/persistent-conventions-vigilance.md` (memory feeds gap-detection per §4 of the conventions rule; gap-detection writes to memory). ↔ `hooks/messages/stop.md` (the Stop hook context that operationalizes the session-end evaluation). ↔ `memory/promotion-ledger.md` (the global memory's promotion-ledger anchor declared at `rules/auto-memory-topic-files.md` §2). ↔ `rules/context-management-protocol.md` (CM-26 owns the session-end memory evaluation that §1.5 phase-exit externalization delegates). ↔ `rules/operational-mandates.md` (CM-26 memory lifecycle's full protocol lives there). ↔ `rules/persistent-conventions-vigilance-checklist.md` (memory feeds gap-detection; gap-detection writes to memory per the parent's §2 evolution cycle).
