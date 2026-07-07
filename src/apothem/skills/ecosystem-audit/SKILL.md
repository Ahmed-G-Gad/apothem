---
name: "ecosystem-audit"
version: "0.1.0"
updated: "2026-06-17"
description: "Blind audit of the apothem ecosystem — matched when the user asks to 'double check', 'audit', 'verify ecosystem', 'sweep', 'validate ecosystem', 'review configuration', 'check the apothem tree', or any phrasing requesting a comprehensive validation of the apothem configuration tree as a whole. Five-phase cadence (census → parallel cross-reference audit → synthesis → report → optional --fix) detects drift, staleness, orphans, dangling references, conflicting directives, frontmatter invalidity, registry-vs-disk count mismatches, and secret exposure. Findings classify FIX / ENHANCE / CONSIDER / DEFER; only FIX auto-applies under --fix, and only after a per-file destructive-op confirmation — ENHANCE / CONSIDER / DEFER surface for operator decision via the structured-inquiry channel. User-invocable directly; also dispatchable from /plan-execute discovery contexts."
archetype: "audit-template"
userInvocable: true
argument-hint: "[--focus area] [--fix]"
disable-model-invocation: true
allowed-tools: "Read, Write, Edit, Glob, Grep, Bash, Agent, TodoWrite"
---

<!-- SPDX-License-Identifier: MIT -->

## Purpose

Execute a blind, fresh audit of the apothem ecosystem — verifying cross-references, registry accuracy, file counts, frontmatter validity, hook alignment, and content quality — and optionally apply FIX-classified findings under `--fix`. "Blind" is the discipline: each sweep anchors to the host's actual on-disk state, never to a prior sweep's conclusions, so structural gaps a prior pass anchored past are surfaced fresh.

## Detection Signal

The user requests "double check", "audit", "verify ecosystem", "sweep", "validate ecosystem", "review configuration", or "check the apothem tree" — any phrasing requesting a comprehensive validation of the apothem configuration tree as a whole.

## Non-Goals

A deliberately narrow surface — each boundary routes the out-of-scope work to its rightful owner:

- **Not a fix tool beyond the FIX classification.** Only mechanically-verifiable defects (false claims, broken cross-references, missing files, invalid frontmatter) auto-apply under `--fix`. ENHANCE / CONSIDER / DEFER NEVER auto-apply — each requires operator judgment solicited via the structured-inquiry channel.
- **Not a refactoring pipeline.** Structural reorganization (renames, moves, registry restructures, taxonomy changes) is OUT of scope. The audit reports the smell; refactoring lands as a separate, operator-driven workstream.
- **Not a content generator.** The audit generates no new rules, skills, agents, commands, or hooks. Gap detection (a missing skill / hook / rule) is reported as DEFER; authoring is the operator's decision and lands under a separate plan-suite per `rules/persistent-conventions-vigilance.md` §4.
- **Not a security scanner replacement.** Secret-exposure detection is a coarse banner-vs-real-secret heuristic surfaced for operator triage; full secret-scanning is `gitleaks` / `trufflehog` territory under `conformity/secret_leak_grep.py` and the host's CI.
- **Not a build / test runner.** The audit verifies frontmatter and cross-references; it runs no `pytest`, `ruff`, or `mypy`. Quality-gate execution is `apothem.conformity.gate` and the consuming command's responsibility.

## Invoking Surfaces

| Surface | Invocation point | What's run |
|---------|------------------|------------|
| Operator (direct) | User triggers the **ecosystem-audit** skill via a detection phrase (e.g. "verify ecosystem", "audit the apothem tree") | Full audit; `--focus` narrows; `--fix` enables FIX-class auto-apply |
| `/plan-execute` discovery context | Discovery sub-phase of an active plan-execution engagement | The audit runs as the codebase-discovery pass; findings feed the plan's audit gate |

The skill is user-invocable per `CLAUDE.md` Source Layout; the `/plan-execute` dispatch path is documented at `rules/persistent-conventions-vigilance.md` §3.

## Conformity Posture

- **Discover-don't-assume preamble (M1).** Before authoring any finding or applying any `--fix` change, walk the host's ratified source-of-truth files for the surface under audit per `rules/host-discovery.md`. Verdicts anchor to the host's *actual* state — the on-disk filesystem, the live `CLAUDE.md` registries, the actual frontmatter fields, the actual hook configuration in `settings.json` — never to assumed conventions or training-time memory. Discovered conventions are recorded with provenance (source file path, value, discovery date) per `rules/host-discovery.md` §4.
- **Authority-inquiry surface (M5).** Per the Structured Inquiry on Ambiguity stanza below; this anchor binds the M5 discipline to the seven-category inquiry catalog at `rules/authority-inquiry-categories.md` §1.

## Procedure

A fixed five-phase cadence — **Census → Cross-Reference Audit (parallel
three-agent team) → Synthesis → Report → Apply (under `--fix`)**, sequential at
the phase level and parallelizable at the dimensional level when an audit team
is deployed, closing with a Phase-6 fifteen-bar pre-emission self-check.
Improvement findings classify **FIX / ENHANCE / CONSIDER / DEFER** (only FIX
auto-applies under `--fix`). The full per-phase procedure, the
improvement-classification taxonomy, the failure-recovery table, the cadence
guidance, and the phase-thread diagram are at
[`references/procedure.md`](references/procedure.md).

## Arguments

- `--focus [area]` — Narrow to a specific area: `rules`, `commands`, `hooks`, `memory`, `agents`, `skills`.
- `--fix` — Apply discovered FIX-class fixes (default: report only).

## Audit-Fortress Phase Skeleton

The decision-tree skeleton shared by the eleven audit-fortress commands (`/code-review`, `/code-audit`, `/security-audit`, `/perf-audit`, `/architecture-review`, `/ux-review`, `/a11y-audit`, `/docs-review`, `/dependency-audit`, `/supply-chain-audit`, `/threat-model-audit`) is the canonical flowchart plus the per-command parameter table at [`references/audit-fortress.md`](references/audit-fortress.md). Each command's `## Decision Tree` section cites that skeleton and supplies its row (`tools-probed`, `borderline-classes`, `focus-semantics`, `pipeline-tail-handoff`). The reference loads selectively beside this entry point so it consumes context only when a fortress command resolves it.

## Foundational Stanzas

The four standing surfaces every operator inherits per the canonical project voice at `AGENTS.md` plus the active harness mirror — adapted to this skill's user-invocable audit role with optional `--fix`, so the operator's destructive-op floor is preserved across the audit surface.

### Refusal & Escalation

REFUSE any request that asks the audit to act outside its stated mission — refactoring, content generation, taxonomy redesign, structural reorganization, full secret-scanning, build / test execution, ENHANCE / CONSIDER / DEFER auto-application. Refusal is explicit: name what was refused, name the mission boundary crossed, and surface an escalation option through the structured-inquiry channel per `rules/interactive-questions.md` (canonical channel; three-segment option annotation; never free-form prose as primary input). When `--fix` is set and the FIX-classified set is empty, REFUSE the no-op auto-apply and surface the empty-set finding instead — `--fix` against zero defects is a misuse signal worth flagging. When two parallel Step-2 agents produce contradictory findings on the same dimension, REFUSE silent reconciliation and surface BOTH findings to the operator with evidence per the Failure Recovery result-conflict clause.

### Output Surface

The primary output is the structured audit report (markdown; max 2000 tokens without `--fix`, unlimited with `--fix` per the Return Contract). The report writes to STDOUT for direct invocation; when dispatched from `/plan-execute`, it lands at the phase's working-evidence directory `.audit/AUDIT.md` per the suite-locality invariant. Under `--fix`, the audit applies FIX-class edits to live files at their canonical locations under the active harness's config root — these land at the host's ratified paths per `rules/host-discovery.md`, and per `rules/operational-mandates.md` CM-7 every edit preserves natural domain language (zero plan-internal references in protected codebase artifacts). Audit-internal working state (intermediate JSON dumps, scratch tables) lands under `.audit/` (gitignored-class per the canonical `.gitignore` snippet). NEVER write audit working state outside the harness's config root, and NEVER write to a downstream project's `.apothem/plans/` from the audit context.

### File-Authoring Contract

When the audit emits a NEW file (rare; the FIX path edits existing files in place), it routes through `scripts/inject-header.{sh,py}` so the canonical authorship-header banner is injected at the head; the injector is idempotent and detects the filetype variant automatically from the byte-exact fixture at `src/apothem/schemas/authorship-header.txt` (the project's canonical authorship-header source of truth per `CLAUDE.md` §File Headers). Exempt classes (LICENSE, JSON configuration files, lockfiles, generated assets, vendored trees, `.audit/` ephemera, `<project-root>/.apothem/plans/` ephemera, `.keep` / `.gitkeep` markers, binary files) are enumerated at `src/apothem/schemas/header-exceptions.txt`; audit reports emitted to STDOUT or `.audit/` are header-exempt under the `.audit/**` exception class. Edits to existing files (the typical FIX path) preserve any existing banner; the header-inject-guard hook at `hooks/messages/pretooluse-{write,edit}-header-guard.md` enforces the contract at every Write / Edit invocation.

### Structured Inquiry on Ambiguity

When the audit reaches a decision in any of the seven authoritative-data categories per `rules/authority-inquiry.md` — identity, scope direction, preference (formatter / linter / test framework / CI provider), security (deny rules, secret rotation), naming of public surfaces, infrastructure endpoints, version pins — and the host is silent, route the resolution through the structured-inquiry channel with the three-segment option annotation per `rules/interactive-questions.md` §3 (rationale / recommendation / default-pointer). Free-form prose questions as primary input are forbidden. NEVER fabricate authoritative data. Every ENHANCE / CONSIDER classification surfaces as a structured-inquiry invocation per the Improvement Classification section; the audit never silently applies an ENHANCE finding.

**Per-file destructive-op floor.** Every delete / rename / move / overwrite-without-retention operation the audit performs under `--fix` against an existing file routes through the structured-inquiry channel on a per-file basis per `rules/interactive-questions.md` §6 — one invocation per file, every time, no `multiSelect` batching across files, every option's `default-pointer:` carrying the verbatim `no-default: user decision required` marker. The §6.4 Delete / §6.5 Rename / §6.6 Move canonical option sets are the floor. Confirmation fatigue is an accepted cost; silent destruction is not. In-place edits via Edit (no path change, no deletion) follow the standard FIX-class flow without per-file destructive-op invocations.

## Return Contract

Structured markdown report. Maximum 2000 tokens without `--fix`; unlimited with `--fix` (includes edit confirmations).

**Required fields.** The report carries pass / fail per check with evidence (the `## Report` step at Procedure §4), the improvement classification per finding (`## Improvement Classification`), and — under `--fix` — per-edit confirmation. A check without locatable evidence is downgraded to a watch item, never asserted.

**Failure behavior.** When a sub-agent fails or returns partial coverage, the orchestrator records the coverage gap and never silently drops the dimension, and resolves contradictory findings per the result-conflict clause (`## Failure Recovery`) by surfacing BOTH findings to the operator with evidence — never silently picking one. A `--fix` run against a zero-defect FIX set surfaces the empty-set finding instead of a no-op auto-apply.

## Recommended Next Step

**Re-trigger the ecosystem-audit skill with `--fix`** to auto-apply the FIX-classified findings the report surfaced, then route each ENHANCE / CONSIDER / DEFER finding through the structured-inquiry channel per `rules/interactive-questions.md` for operator decision. The report-only pass leaves FIX defects unremediated; `--fix` closes the mechanically-verifiable set before the next sweep.

## Bindings (§0.j five-direction)

- **Drives →** ● Every operator-invoked blind audit of the apothem ecosystem (the skill is user-invocable). ● Every `--fix` run that materializes FIX-class edit-confirmations into the live ecosystem. ● Every `/plan-execute` discovery context that consumes the audit as its codebase-discovery pass. ◐ The ecosystem-coherence enforcement loop alongside `rules/persistent-conventions-vigilance.md`.
- **Satisfies →** ● `CLAUDE.md` Source Layout row "ecosystem-audit". ● `rules/persistent-conventions-vigilance.md` §3 Ecosystem Coherence (the audit-template archetype materializes the coherence-verification surface).
- **Established by ↑** ● `CLAUDE.md` Source Layout. ● `CLAUDE.md` Source Layout (skills/ class declaration with the folder-with-`SKILL.md` convention).
- **Gated by ←** ● The harness's Skill tool surface and the operator's explicit invocation. ● The ecosystem's mandatory-file presence (rules/, commands/, skills/, agents/, hooks/, CLAUDE.md, settings*.json).
- **Cross-bound with ↔** ↔ `skills/ecosystem-audit/references/audit-fortress.md` (the bundled reference surface housing the Audit-Fortress Phase Skeleton this skill points to). ↔ `skills/ecosystem-audit/references/procedure.md` (the bundled reference surface housing the five-phase procedure, classification, recovery, cadence, and phase-thread diagram this skill points to). ↔ `rules/persistent-conventions-vigilance.md` (the convention-coherence specification this audit consumes). ↔ `scripts/dev/validate_ecosystem.py` (the verifier suite the audit cross-references). ↔ `agents/convention-auditor.md` + `agents/memory-auditor.md` (sibling audit-class artifacts that may dispatch within this skill's protocol). ↔ `skills/plan-suite/SKILL.md` (sibling skill under the same registry section). ↔ `commands/code-review.md` + `commands/code-audit.md` + `commands/security-audit.md` + `commands/perf-audit.md` + `commands/architecture-review.md` + `commands/ux-review.md` + `commands/a11y-audit.md` + `commands/docs-review.md` + `commands/dependency-audit.md` + `commands/supply-chain-audit.md` + `commands/threat-model-audit.md` (the 11 audit-fortress commands whose Decision Tree sections cite the `references/audit-fortress.md` Audit-Fortress Phase Skeleton + per-command parameter-table row).
