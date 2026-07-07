---
name: "persistent-conventions-vigilance"
description: "Adhere to the harness ecosystem's conventions and proactively evolve its artifacts — per-artifact-class convention awareness (naming, layout, frontmatter shape), the five-step proactive-evolution cycle (detect → search → act → validate → retire), bidirectional cross-reference coherence, and ecosystem gap detection that surfaces a missing rule / skill / command / hook before it is needed. Implements CM-22."
pathFilter: ""
alwaysApply: true
---

<!-- SPDX-License-Identifier: MIT -->

# Rule: Persistent Conventions Vigilance

## Purpose

Adhere to the harness ecosystem's conventions and proactively evolve artifacts as projects change.

## Obligations

### 1. Convention Awareness (Companion Sub-Rule Anchor)

Before any non-trivial action, the agent MUST verify alignment with ecosystem conventions covering naming, directory structure, and per-artifact-class shape (skill, rule, command, hook, agent, plan, root config, settings, memory, MCP, narration). Full per-class checklist at `rules/persistent-conventions-vigilance-checklist.md` §1.

### 2. Proactive Evolution

The agent MUST continuously evaluate whether existing artifacts remain sufficient, running a five-step cycle: **Detect** recurrence (2+ instances or noted in memory) → **Search** skills / rules / commands / hooks / memory / MCP for overlap → **Act** (evolve in place when overlap exists; author new only when genuinely orthogonal) → **Validate** that cross-references resolve → **Retire** superseded artifacts with reference updates. Refinement is preferred over creation.

### 3. Ecosystem Coherence

Cross-references between CM-N / TM-N / rules / skills / commands MUST be bidirectional and accurate; naming MUST be identical across surfaces; every rule / skill / command MUST be registered in `CLAUDE.md` (no orphans). New artifacts MUST be verified against existing mandates, with resolution order documented when tension exists.

### 4. Ecosystem Gap Detection (Companion Sub-Rule Anchor)

Beyond refining existing artifacts (§2), the agent MUST identify when the ecosystem is MISSING an artifact that would add value. Common trigger: a pattern recurs 2+ times in the session or is noted in memory as recurring. Full artifact-class trigger catalog (agent / hook / rule / plugin / config-freshness / skill / command) at `rules/persistent-conventions-vigilance-checklist.md` §2.

## Seriousness Scaling

| Level | Conventions Behavior |
| ----- | -------------------- |
| EXPLORING | Naming + structure checks only — verify kebab-case and directory placement |
| PERSONAL_USE | Full convention awareness; cross-references verified on create/modify; gap detection on request |
| SHARED | Mandatory ecosystem coherence; proactive evolution + gap detection; cross-references enforced every change |
| PUBLIC_LAUNCH | Full enforcement + proactive index maintenance + session-end gap sweep; violations block completion; cross-project audit |

## Anti-Patterns

- **DON'T** create a new artifact when an existing one covers the same concern — **BECAUSE** duplicates produce conflicting directives and fragment knowledge.
- **DON'T** ignore naming conventions for "quick" one-off files — **BECAUSE** inconsistency compounds and makes discovery unreliable.
- **DON'T** leave a new artifact unregistered in `CLAUDE.md` — **BECAUSE** orphans become invisible and unmaintained.
- **DON'T** mix concerns across artifact types (e.g., skill content inside a rule) — **BECAUSE** it breaks the separation that keeps each type discoverable.
- **DON'T** skip cross-reference verification after modifying an artifact — **BECAUSE** broken references propagate confusion and erode trust.

## Enforcement

Always-on at every seriousness level, scaling per the table above. Implements CM-22. Canonical specification for ecosystem conventions and artifact lifecycle.

## Bindings (§0.j five-direction)

- **Drives →** ● Every non-trivial ecosystem action's pre-flight convention check (§1 Convention Awareness). ● Every artifact-evolution decision (§2 Proactive Evolution — refine vs. create heuristic). ● Every gap-detection sweep (§4 Ecosystem Gap Detection — agent / hook / rule / plugin / config / skill / command classes). ● Every CHANGELOG / CLAUDE.md registry update on artifact lifecycle events. ◐ Cross-reference accuracy enforcement on every artifact change at SHARED+.
- **Satisfies →** ● CM-22 (Conventions Vigilance — rule-delegated mandate). ● the rules registry row "Conventions Vigilance". ● `rules/persistent-conventions-vigilance.md` (the five-step Detect / Search / Act / Validate / Retire cycle).
- **Established by ↑** ● CM-22. ● `rules/persistent-conventions-vigilance.md`. ● the hooks pipeline timeout-value canonical block (this rule's §1 cites the canonical column for hook-timeout values).
- **Gated by ←** ● `CLAUDE.md` always-loaded preamble. ● `rules/operational-mandates.md` (CM-6 self-improvement gates artifact-evolution triggers).
- **Cross-bound with ↔** ↔ `rules/persistent-conventions-vigilance-checklist.md` (path-filtered companion sub-rule carrying the §1 Convention Awareness checklist and the §4 Ecosystem Gap Detection artifact-class triggers). ↔ `rules/operational-mandates.md` (CM-6 self-improvement triggers artifact evolution; CM-22 specifies the lifecycle here). ↔ `rules/auto-memory.md` (memory feeds gap-detection per §4; gap-detection writes to memory per the §2 evolution cycle). ↔ `rules/context-management.md` (§2.5 phase-exit delegates artifact-evolution evaluation to this rule's §2 + §4). ↔ the artifact registries Registries (the canonical registry surface this rule maintains). ↔ `rules/dynamism.md` (sibling discipline; dynamism is a ratified ecosystem convention whose new surfaces feed §4 Ecosystem Gap Detection). ↔ `rules/sota-elevation.md` (sibling discipline; SOTA-gap detection feeds §4 ecosystem-gap-detection). ↔ `rules/auto-memory-topic-files.md` (memory feeds gap-detection per §4 of the conventions rule; gap-detection writes to memory). ↔ `rules/clean-room-generation.md` (clean-room generation produces ecosystem-coherent artifacts; convention vigilance maintains ecosystem coherence). ↔ `rules/code-craft-conventions.md` (CM-22 §4 — recurrence-driven gap detection signals new per-language-sibling-rule candidates). ↔ `rules/context-management-protocol.md` (CM-22 owns the artifact-evolution evaluation that §1.5 delegates). ↔ `rules/sota-elevation-exemplars.md` (gap-detection surface). ↔ `rules/systemic-participation.md` (CM-22 — the inward-axis analog M14 cross-maps to per `CLAUDE.md` PLAN-NOTES.md D1 cross-mapping table; CM-22 governs internal artifact lifecycle, M14 governs external systemic participation; both apply where both apply). ↔ `rules/token-budget-discipline.md` (the demand-load companion-sub-rule pattern is itself a gap-closure).
