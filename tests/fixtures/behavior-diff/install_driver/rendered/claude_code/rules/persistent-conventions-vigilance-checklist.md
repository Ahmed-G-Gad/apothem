---
name: "persistent-conventions-vigilance-checklist"
description: "Path-filtered companion sub-rule carrying the Convention Awareness checklist (§1) and the Ecosystem Gap Detection artifact-class triggers (§4) for the parent `persistent-conventions-vigilance.md` rule; demand-loaded on touches of governed-core surfaces."
pathFilter: "**/CLAUDE.md, **/rules/**, **/skills/**, **/commands/**, **/agents/**, **/hooks/**, **/settings.json"
alwaysApply: false
paths:
  - "**/CLAUDE.md"
  - "**/rules/**"
  - "**/skills/**"
  - "**/commands/**"
  - "**/agents/**"
  - "**/hooks/**"
  - "**/settings.json"
---

<!-- SPDX-License-Identifier: MIT -->

# Rule: Persistent Conventions Vigilance — Checklist (Companion Sub-Rule)

## Purpose

Carry the full Convention Awareness checklist and the full Ecosystem Gap Detection artifact-class trigger catalog that the parent rule `rules/persistent-conventions-vigilance.md` declares at its §1 and §4 anchors. This companion is path-filtered: it loads when the assistant edits any governed-core surface (CLAUDE.md, rules/, skills/, commands/, agents/, hooks/, settings.json) so the parent rule's always-on payload stays lean while preserving full checklist fidelity at the demand-load surface. The parent remains the canonical home for the standing directives, Proactive Evolution, Ecosystem Coherence, Anti-Patterns, and Seriousness Scaling; this companion carries the §1 checklist and the §4 trigger catalog.

## Obligations

### 1. Convention Awareness — Full Checklist

Before any non-trivial action, verify alignment with the current harness ecosystem on each artifact class:

- **File/folder naming:** kebab-case for rules, skills, commands, plan artifacts. PascalCase or UPPER_SNAKE_CASE only where harness convention requires (e.g., `CLAUDE.md`, `SKILL.md`, `PROGRESS.md`).
- **Directory structure:** `rules/`, `commands/`, `skills/`, `.apothem/plans/`, `projects/` — each carries a defined purpose; never conflate them.
- **Skill:** one folder per skill in `skills/`; entry point is always `SKILL.md` with YAML frontmatter.
- **Rule:** flat `.md` file in `rules/`; self-contained with Purpose, Obligations, Seriousness Scaling, Anti-Patterns, Enforcement.
- **Command:** flat `.md` file in `commands/`; each defines one slash command (`/command-name`).
- **Hook:** defined in `settings.json`, triggers prompts on tool events. Timeout values (seconds) bound execution — a hook exceeding its timeout is silently skipped. Per-event timeouts live in the canonical hook-events table at the hooks pipeline; new events take their timeout from that same column.
- **Agent:** prompts carry mission, deliverable, constraints, context, return contract; deployment patterns per CM-25.
- **Plan:** suites at `<project-root>/.apothem/plans/[REPO]-[CONTEXT]-[MISSION]/` with preamble, master plan, progress, notes, and a `phases/` directory of per-phase folders (each holding `PHASE.md` and `REPORT.md`).
- **Other:** `CLAUDE.md` (root config, always-loaded), `settings.json` (hooks, permissions, MCP), memory (per CM-26), MCP tools (`mcp__server__tool` naming), narration (GFM; no emojis unless requested).

### 2. Ecosystem Gap Detection — Artifact-Class Triggers

Beyond refining existing artifacts (parent §2 Proactive Evolution), identify when the ecosystem is MISSING an artifact that would add value. **Common trigger:** a pattern recurs 2+ times in-session with similar structure, or is noted in memory as recurring. Route the gap to the matching artifact class:

- **Agent:** recurring agent pattern → persistent `agents/{name}.md` with tool restrictions + system prompt.
- **Hook:** repeatedly violated/forgotten mandate → enforcement hook in `settings.json`.
- **Rule:** repeatedly corrected behavior uncovered by existing rules → new `.md` rule.
- **Plugin:** repeatedly referenced missing tool/MCP server → install or create.
- **Config freshness:** `CLAUDE.md` or `settings.json` references that no longer match ecosystem state → update the stale references.
- **Skill:** reusable detectable technique (actionable, falsifiable) with no existing skill → `skills/{name}/SKILL.md`. See also `rules/persistent-conventions-vigilance.md`.
- **Command:** recurring multi-step workflow → `commands/{name}.md` with proper frontmatter.

## Enforcement

Path-filtered (the eight glob patterns in this rule's `pathFilter` field), always-on at every seriousness level when in scope. Demand-loaded companion to `rules/persistent-conventions-vigilance.md` §1 and §4. The parent rule carries the standing directive, Proactive Evolution (§2), Ecosystem Coherence (§3), Anti-Patterns, and Seriousness Scaling; this companion carries the §1 Convention Awareness checklist and the §4 Ecosystem Gap Detection trigger catalog.

## Bindings (§0.j five-direction)

- **Drives →** ● Every governed-core surface touch's pre-flight convention check (§1 checklist applied per artifact class). ● Every gap-detection sweep's artifact-class routing (§2 trigger catalog maps recurrence patterns to agent / hook / rule / plugin / config / skill / command classes).
- **Satisfies →** ● CM-22 (rule-delegated companion sub-rule). ● `rules/persistent-conventions-vigilance.md` §1 + §4 anchors (the parent rule's pointers to this companion's full checklist and trigger catalog).
- **Established by ↑** ● `rules/persistent-conventions-vigilance.md` §1 + §4 (parent-rule anchors). ● CM-22.
- **Gated by ←** ● The path-filter (the eight glob patterns) — this rule demand-loads only on governed-core surface touches. ● `rules/persistent-conventions-vigilance.md` always-on baseline (parent rule's §1 + §4 anchors must be live for the companion to demand-load coherently).
- **Cross-bound with ↔** ↔ `rules/persistent-conventions-vigilance.md` (parent rule; §1 + §4 anchors bind this companion). ↔ `rules/auto-memory.md` (memory feeds gap-detection; gap-detection writes to memory per the parent's §2 evolution cycle). ↔ `rules/operational-mandates.md` (CM-6 self-improvement triggers gap-detection routing through §2 here).
