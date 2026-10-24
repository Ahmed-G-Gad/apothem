---
name: "auto-memory"
description: "Auto memory lifecycle augmenting the harness built-in — classifies memory against PROGRESS.md / PLAN-NOTES.md / skills (stable fact/convention/preference/insight → memory; plan/task-specific → PROGRESS/PLAN-NOTES; reusable technique with detection signal → skill), bans session-specific context / incomplete info / CLAUDE.md duplicates / plan-specific decisions / ephemeral facts, and anchors topic-file hygiene to the path-filtered companion."
pathFilter: "**/memory/**, **/MEMORY.md, **/projects/**/memory/**, **/promotion-ledger.md"
alwaysApply: false
paths:
  - "**/memory/**"
  - "**/MEMORY.md"
  - "**/projects/**/memory/**"
  - "**/promotion-ledger.md"
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

Applies at every seriousness level, scaling per the table above. Implements CM-26. Canonical specification for memory lifecycle, topic organization, and content placement.
