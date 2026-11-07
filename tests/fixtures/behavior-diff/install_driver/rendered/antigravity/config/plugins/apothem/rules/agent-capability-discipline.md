---
trigger: glob
description: "Cross-harness agentic discipline — the 17-harness adapter cohort is recognized as sophisticated AI agent systems; core and supplemental agentic capabilities converge via M14, anchor to per-adapter STANDARD CONVENTION PIN, validate at materializer time, and attest through adapter capability coverage. Demand-loaded on adapter / capability / MCP-config touches, co-triggering with its matrix companion."
globs: "**/src/apothem/harnesses/**, **/_inputs/cross-harness-agent-capability-matrix.md, **/.mcp.json, **/mcp.json"
---

<!-- SPDX-License-Identifier: MIT -->

# Rule: Agent Capability Discipline

## What this rule enforces

Binds cross-harness agentic discipline across the 17-harness adapter cohort (**antigravity, claude_code, codebuddy, codex, cursor, gemini_cli, github_copilot, hermes, kimi_code, kiro, open_claw, opencode, qwen_code, trae, windsurf, zed, glm**). Each adapter targets a sophisticated AI agent system. Core and supplemental capabilities MUST discover per vendor doc + commit-SHA-pinned snapshot (or adapter-local convention pin) co-resident with the adapter's STANDARD CONVENTION PIN per `rules/harness-adapter-shape.md` §6, project via M14, validate at materializer time, and attest through capability-coverage. No capability is assumed: every cell is evidence-backed or discovery-pending.

## Pre-conditions

Applies on adapter, capability, and convergence touches.

## Required behavior

### 1. Per-harness agentic-capability matrix (Companion Sub-Rule Anchor)

Core dimensions per adapter: MCP server · sub-agent dispatch · tool-surface restriction · system-prompt template · agent-memory · output-style · custom-command · hooks-pipeline · skills-directory. Supplemental dimensions include recommended-postfix rendering and long-context/compaction continuity. See `rules/agent-capability-discipline-matrix.md` §1.

### 2. Cross-harness sibling-convergence

Operator workflows project per-harness via `rules/systemic-participation.md` M14. A capability present in one adapter MUST project into every cohort sibling whose vendor supports it; divergences MUST be declared — silent omission is a silo finding.

### 3. MCP registry / discovery / sharing (Companion Sub-Rule Anchor)

Profile carries canonical MCP inventory; per-harness materializers project into native surfaces. See `rules/agent-capability-discipline-matrix.md` §3.

### 4. Sub-agent dispatch

Kebab-case names; per-harness ratified file shape. A sub-agent's tool-restriction boundary MUST equal its parent's allow-list intersected with its own restrictions — never widening the parent's. Return-contract per `rules/agent-orchestration.md` §3; converge across the cohort.

### 5. Tool-surface restriction

The universal-deny floor binds regardless of any per-harness allow-list: secrets paths (`.env*`, `~/.ssh/**`, credentials), destructive shell ops (`rm -rf:*`, `sudo:*`, `git push --force*`), network-write to unsigned endpoints. No override silently widens it.

### 6. System-prompt template

Profile system-prompt content projects into each harness's native template; overrides MUST cite a concrete driver per `rules/interactive-questions-canonical-shapes.md` §3.2.1.

### 7. Agent-memory convention (Companion Sub-Rule Anchor)

Per-harness memory semantics: persists / does-not-persist / migrates. See `rules/agent-capability-discipline-matrix.md` §7.

### 8. Materializer detection + post-install validation

Materializers MUST probe vendor support before emission. When a profile declares a capability the pinned snapshot lacks, the materializer refuses unless the operator overrides via `rules/interactive-questions.md` §6. Post-install re-probe surfaces drift as a finding.

### 9. Agent-Capability Coverage attestation

The adapter matrix per `rules/harness-adapter-shape.md` §4 carries a capability-coverage column: every §1 capability MUST have a covering test, attested in the adapter's gate block per `rules/pre-emission-gate.md`.

## Plain-language boundary

Agentic vocabulary (AI / agent / sub-agent / MCP / tool-surface / harness names) is in-scope process-artifact vocabulary for adapter sub-packages, materializers, dev tech-spec, rule-tier. User-facing landing prose remains under `rules/plain-language.md`; this rule does not relax that boundary.

## Disclosure surface

- `[Discovery — source: <harness>/STANDARD-CONVENTION-PIN.md; capability: <name>; vendor-support: <yes | no | partial>; honored]`
- `[Divergence — harness: <name>; capability: <name>; rationale: <concrete-driver>]`
- `[Refusal — materializer: <harness>; capability: <name>; reason: vendor-snapshot lacks support; operator-override: <yes | no>]`

## Failure tells

Profile declares unsupported capability without §8 refusal. Sub-agent widens universal-deny without divergence record. Skill projected into one harness, silently omitted from another despite vendor support. Capability-coverage column blank. User-facing surface leaks agentic vocabulary outside in-scope boundary.

## Bindings (§0.j five-direction)

- **Drives →** Adapter capability declarations co-resident with STANDARD CONVENTION PIN; materializer vendor-support probes; adapter capability-coverage attestation; the matcher `conformity/agent_capability_grep.py`.
- **Satisfies →** The cross-harness agentic-discipline baseline; `rules/harness-adapter-shape.md` §4 capability-coverage matrix; `rules/harness-adapter-shape.md` §6 STANDARD CONVENTION PIN discipline.
- **Established by ↑** `rules/harness-adapter-shape.md` §4 and §6; `CLAUDE.md` Harness Adapter Pattern section.
- **Gated by ←** This rule's own pathFilter (`**/src/apothem/harnesses/**, **/_inputs/cross-harness-agent-capability-matrix.md, **/.mcp.json, **/mcp.json`) gates its demand-load, co-triggering with the matrix companion; `rules/plain-language.md` boundary.
- **Cross-bound with ↔** `rules/agent-capability-discipline-matrix.md` (companion §1 / §3 / §7); `rules/harness-adapter-shape.md` (PIN §6); `rules/plain-language.md`; `rules/systemic-participation.md` (M14); `rules/agent-orchestration.md` (CM-17 / CM-25); `rules/interactive-questions.md` (§6); `conformity/agent_capability_grep.py`. ↔ `rules/harness-adapter-shape-schemas.md` (co-resident PIN discipline mirror).
