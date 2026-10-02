---
name: "workflow"
version: "0.1.0"
updated: "2026-10-02"
description: "General-purpose workflow-harnessing skill — matched when the operator states a mission via '/workflow <<mission>>', asks to 'harness a workflow', 'run a multi-agent workflow', 'orchestrate agents', 'fan out and verify', 'critique and remediate', 'maximally elevate' a target, or otherwise hands off a non-trivial multi-step mission whose accomplishment benefits from genuinely-independent parallel work plus adversarial verification. Decomposes the mission, dispatches independent agents under named return contracts (non-overlapping scope, isolation where parallel writes collide, single-message parallel launch), subjects every load-bearing finding to an EXTREMELY-CRITIQUE refute-by-default verification pass (N independent critics per finding, default 3, distinct lenses — correctness/security/reproducibility/regression — survival only on non-refute majority) before it survives, is granted to identify and remediate defects beyond the literal mission (each disclosed per rules/disclosure-ledger.md), self-augments from current authoritative SOTA sources rather than memory alone, and emits a deterministic, byte-stable result. Multi-agent dispatch and continuous auto-execution are opt-in / confirmation-gated, never default-on — the canonical home for the '/workflow <<mission>>' entry pattern. A single-step request that one direct tool call resolves is below this skill's threshold."
archetype: "orchestration-template"
userInvocable: true
argument-hint: "[<<mission>>] [--autonomous] [--verify-panel N]"
disable-model-invocation: true
allowed-tools: "Read, Glob, Grep, Agent, WebSearch, TodoWrite"
---

<!-- SPDX-License-Identifier: MIT -->

## Purpose

Harness a non-trivial mission into a disciplined multi-agent workflow: decompose it, dispatch genuinely-independent agents under named return contracts, subject every finding to an adversarial refute-by-default verification pass, remediate the mission plus any defect expertise reveals along the way (disclosing each amendment), and emit a deterministic result with a single recommended next move. The skill is the operator's general-purpose orchestration surface — the canonical home for the `/workflow <<mission>>` entry pattern — and it honors apothem's agnostic posture: the heavy machinery engages only when the operator opts in.

## Detection Signal

The operator states a mission through `/workflow <<mission>>`, or asks to "harness a workflow", "run a multi-agent workflow", "orchestrate agents", "fan out and verify", "critique and remediate", or "maximally elevate" a target — any non-trivial, multi-step mission whose accomplishment benefits from independent parallel work plus adversarial verification.

**Falsifiable counter-signal.** A single-step request that one direct tool call resolves is below this skill's threshold — it routes to the direct tool, not the harness.

## Non-Goals

The skill is NOT:

- **A default-on autonomy switch.** Multi-agent dispatch and continuous auto-execution engage only under `--autonomous` (or an explicit in-conversation opt-in / the profile's `enforcement` flag), per `rules/agnostic-posture.md`. A clean invocation plans the workflow and confirms before committing irreversible or outward-facing steps.
- **A replacement for the specialized pipelines.** Plan-suite work routes to the `/plan-<stage>` cohort and the `/plan` orchestrator; audit work routes to the audit-fortress commands; research routes to `/research`. This skill harnesses general missions and dispatches those surfaces where they fit — it does not reimplement them.
- **A memory-only operator.** Every load-bearing technical decision consults current authoritative sources (Conformity Posture below); the skill never asserts a SOTA convention from training memory alone when the live source is reachable.
- **A silent-scope-widener.** Remediation beyond the literal mission is granted but never silent — every beyond-mission amendment is disclosed per `rules/disclosure-ledger.md`.

## Foundational Stanzas

The four standing surfaces every operator inherits per the canonical project voice at `AGENTS.md` plus the active harness mirror.

### Refusal & Escalation

REFUSE any step that exceeds the operator's stated mission AND its disclosed beyond-mission remediation grant — name what was refused, name the boundary crossed, and surface an escalation option through the structured-inquiry channel per `rules/interactive-questions.md` (canonical channel; three-segment option annotation; never free-form prose as primary input). REFUSE engaging autonomous multi-agent dispatch when the operator has not opted in. REFUSE an irreversible or outward-facing step (deletion, publish, force-push, machine-state mutation) without per-action confirmation per the destructive-op floor. When two verification agents return contradictory verdicts on the same finding, REFUSE silent reconciliation — surface both with evidence.

### Output Surface

Workflow outputs land at their domain-natural locations under the host project per `rules/host-discovery.md` (code at source paths; plan artifacts inside the active suite per the suite-locality invariant at `rules/context-management.md` §2.6.1). Per `rules/operational-mandates.md` CM-7, codebase artifacts carry natural domain language — zero workflow-internal or plan-internal scaffolding. NEVER write a plan artifact to a global plans directory under any harness's config root from a downstream-project context, and NEVER write to any other global-ecosystem location.

### File-Authoring Contract

Every NEW codebase file the workflow creates routes through `scripts/inject-header.{sh,py}` so the canonical `SPDX-License-Identifier` `MIT` banner is injected at the head in the comment family matching the filetype; the injector is idempotent and detects the variant from the byte-exact fixture at `src/apothem/schemas/authorship-header.txt`. Exempt classes are enumerated at `src/apothem/schemas/header-exceptions.txt`. Edits to existing files preserve any existing banner; the header-inject-guard hook enforces the contract at every Write / Edit.

### Structured Inquiry on Ambiguity

When uncertain about any of the seven authoritative-data categories per `rules/authority-inquiry.md` — identity, scope direction, preference, security, naming of public surfaces, infrastructure, version pins — and the host is silent, route the resolution through the structured-inquiry channel with the three-segment option annotation per `rules/interactive-questions.md` §3 (rationale / recommendation / default-pointer). NEVER fabricate authoritative data. Every destructive operation routes per-file through the canonical destructive-op option sets at `rules/interactive-questions.md` §6 — one invocation per file, `default-pointer: no-default: user decision required`.

## Conformity Posture

**Discover-don't-assume preamble (M1).** Before any substantive decision, walk the host's ratified source-of-truth files for the surface under work per `rules/host-discovery.md`; anchor verdicts to the host's actual state, never to assumed conventions.

**Current-SOTA source-consultation mandate (M5).** The workflow self-augments from current authoritative sources, not memory alone, per `rules/sota-elevation.md`. The enumerated source classes — extend comprehensively beyond this list as the mission warrants:

- **Official vendor documentation** for any tool, framework, platform, or harness in scope (the authoritative current API / convention / limit).
- **Standards and specifications** — RFCs, W3C / WHATWG, language standards, ECMA, IEEE, the relevant normative spec.
- **Peer-reviewed and authoritative references** — primary literature, official reference works, canonical texts.
- **Current SOTA tool documentation** — the live docs of the present best-in-class tool for the task, version-pinned where behavior shifts.

A SOTA claim cites at least one source class with a retrievable pointer; an unsourced "best practice" is downgraded or routed to inquiry per `rules/option-annotation.md`.

**Authority inquiry surface (M5).** Per the Structured Inquiry on Ambiguity stanza; binds the seven-category catalog at `rules/authority-inquiry.md`.

## Procedure

Six numbered steps. Steps 3–5 engage the heavy machinery only under opt-in; step 1, 2, and 6 run on every invocation.

### 1. Frame the Mission

Read the mission in full. Extract intent — not literal text alone — per `rules/expertise-posture.md`. Resolve scope ambiguity through the structured-inquiry channel before dispatch. State the mission as an outcome (testable at close), and record the beyond-mission remediation grant's scope. Apply the Obvious Purge (Filter 1 per `rules/cognitive-identity.md`): discard the first approach; find the structurally superior decomposition.

### 2. Decompose & Plan the Dispatch

Decompose the mission into independent work-items per `rules/agent-orchestration.md`. Choose the team pattern (Research / Audit / Implementation / Generation / Quality / Documentation) and the agent type per `rules/agent-orchestration-patterns.md` §2. Assign each agent a non-overlapping scope, a named return contract (format + max size + required fields + fallback shape), and isolation where parallel writes would collide. Deploy when 3+ independent operations, multi-path exploration, heavy reads, or multi-dimension verification justify it; skip for tightly-coupled or sub-threshold work.

### 3. Dispatch (opt-in gated)

Under opt-in (`--autonomous` / in-conversation opt-in / profile flag), launch independent agents in waves sized to the host's reliable concurrency (size the wave to avoid throttle; cap and sequence, never burst). Without opt-in, present the dispatch plan and confirm. Honor the single-message parallel-launch invariant for genuinely independent agents; group dependent agents into waves. The main loop never duplicates work an agent is performing.

### 4. EXTREMELY-CRITIQUE Adversarial Verification

Every load-bearing finding faces an independent refute-by-default verification pass before it survives (the judge-panel + adversarial-verify pattern, `rules/agent-orchestration-patterns.md` §Quality patterns):

- Spawn N independent critics per finding (default 3; `--verify-panel N`), each prompted to **refute** the finding and to default to "refuted" under uncertainty.
- A finding survives only on a non-refute majority; a majority-refute kills it.
- Where a finding can fail in more than one way, give each critic a distinct lens (correctness / security / reproducibility / regression), not N identical refuters.
- Contradictory verdicts surface to the operator with evidence — never silently reconciled.

### 5. Remediate (mission + disclosed beyond-mission)

Apply the surviving findings. Remediate root causes, not symptoms. Where expertise reveals a defect beyond the literal mission, remediate it and disclose the amendment per `rules/disclosure-ledger.md` (`[Amendment]` / `[Extension]` / `[Refinement]` with cited rationale). Integrating, correctness-critical edits stay in the main loop; independent fan-out stays in the agents.

### 6. Synthesize & Self-Check

Collect agent results in one pass, verify mutual consistency, synthesize a compact result, and release raw agent output from active context. The procedure keeps the main thread lean: raw agent output is released after this single-pass synthesis, so only the synthesized verified findings persist in the conversation per `rules/multi-agent-workflow.md` §4. Run the fifteen-bar pre-emission gate per `rules/pre-emission-gate.md` against every emitted artifact; iterate on any failing bar until it passes within the three-round cap of `rules/pre-emission-gate-bars.md` §3 (then BLOCKED). Record the attestation.

## Autonomy Posture

| Mode | Trigger | Behavior |
|------|---------|----------|
| **Planned (default)** | clean invocation | Decompose + plan + present; confirm before committing irreversible or outward-facing steps. |
| **Autonomous** | `--autonomous`, explicit in-conversation opt-in, or the profile `enforcement` flag | Dispatch + verify + remediate + advance continuously; every irreversible / outward-facing step still per-action confirmation-gated. |

Autonomy is opt-in, never the shipped default, per `rules/agnostic-posture.md`. De-enforced machinery is preserved, not removed: the opt-in path restores it intact.

## Arguments

- `<<mission>>` — the mission / task / requirement in natural language (the `/workflow <<mission>>` entry form).
- `--autonomous` — opt into continuous multi-agent dispatch + advancement (default: planned, confirm-before-commit).
- `--verify-panel N` — critics per finding in the adversarial-verify pass (default: 3).

## Return Contract

A deterministic result surface:

- The **mission outcome** (testable against the framing at step 1).
- The **surviving (verified) findings** with evidence.
- The **disclosure ledger** of every beyond-mission amendment.
- The **fifteen-bar gate attestation** per `rules/pre-emission-gate.md`.
- A single `## Recommended Next Step`.

Output shape is byte-stable for identical inputs per `rules/determinism.md`; any non-determinism is declared with its source named. When an agent wave fails or returns partial coverage, the orchestrator records the coverage gap, never silently dropping the dimension.

## Recommended Next Step

**State your mission as `/workflow <<mission>>`** (add `--autonomous` to opt into continuous multi-agent dispatch); the harness frames it, decomposes the dispatch, runs the adversarial-verify pass, and returns the verified result with a single forward move. Begin in planned mode and opt into autonomy only once the dispatch plan reads correctly.

## Bindings (§0.j five-direction)

- **Drives →** ● Every operator mission handed off via `/workflow <<mission>>` (the skill is user-invocable; the orchestration surface for general missions). ● Every adversarial-verify pass that gates a finding before it survives. ● Every beyond-mission amendment disclosed through the ledger. ◐ The opt-in autonomy path that restores continuous multi-agent dispatch.
- **Satisfies →** ● `CLAUDE.md` Source Layout row "workflow" (skills/ class). ● The multi-agent independent-critique / synthesis / lean-thread capability declared at `rules/multi-agent-workflow.md`. ● The deterministic-output contract at `rules/determinism.md`. ● The agnostic default-off posture at `rules/agnostic-posture.md`.
- **Established by ↑** ● `rules/agent-orchestration.md` (the team patterns + dispatch discipline this skill orchestrates). ● `rules/agent-orchestration-patterns.md` §Quality patterns (the judge-panel + adversarial-verify pattern). ● `rules/agnostic-posture.md` (the opt-in default-off frame). ● `rules/multi-agent-workflow.md` (the rule that declares this independent-critique / synthesis / lean-thread capability available and opt-in; this skill is the procedure that realizes it).
- **Gated by ←** ● The harness's Agent + structured-inquiry + Edit + Write + WebSearch + WebFetch tool surface. ● The operator's opt-in for autonomous dispatch. ● The destructive-op floor for irreversible / outward-facing steps.
- **Cross-bound with ↔** ↔ `commands/workflow.md` (the `/workflow` command entry point that drives this skill). ↔ `rules/multi-agent-workflow.md` (the rule declares the independent-critique / synthesis / lean-thread capability; this skill is the procedure that realizes it — the rule names it, the skill runs it). ↔ `rules/agent-orchestration.md` + `rules/agent-orchestration-patterns.md` (the orchestration discipline). ↔ `rules/determinism.md` (the deterministic-output contract). ↔ `rules/disclosure-ledger.md` (every beyond-mission amendment recorded). ↔ `rules/agnostic-posture.md` (opt-in autonomy). ↔ `rules/interactive-questions.md` (the structured-inquiry channel + destructive-op floor). ↔ `rules/authority-inquiry.md` (the SOTA-source + seven-category inquiry catalog). ↔ `skills/projectify/SKILL.md` (sibling deterministic-SOTA elicitation skill).
