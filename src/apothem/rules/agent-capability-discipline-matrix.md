---
name: "agent-capability-discipline-matrix"
description: "Path-filtered companion to `agent-capability-discipline.md` — carries the per-harness agentic-capability matrix (§1), the per-harness MCP-surface catalog (§3), and the per-harness agent-memory-convention catalog (§7) the parent rule's anchors delegate to. Demand-loaded when the assistant edits any adapter sub-package, cross-harness capability-matrix input, or per-harness MCP-config artifact."
pathFilter: "**/src/apothem/harnesses/**, **/_inputs/cross-harness-agent-capability-matrix.md, **/.mcp.json, **/mcp.json"
alwaysApply: false
---

<!-- SPDX-License-Identifier: MIT -->

# Rule: Agent Capability Discipline — Per-Harness Matrix (Companion Sub-Rule)

## Purpose

Carry the per-harness agentic-capability matrix, the per-harness MCP-surface catalog, and the per-harness agent-memory-convention catalog that the parent `rules/agent-capability-discipline.md` rule's §1 / §3 / §7 anchors delegate to. Path-filtered: loads when the assistant edits adapter sub-packages under `src/apothem/harnesses/<name>/`, the cross-harness capability-matrix scratch input under `_inputs/cross-harness-agent-capability-matrix.md`, or per-harness MCP-config artifacts (`.mcp.json`, `mcp.json`). The parent rule retains the standing directive, the plain-language boundary, the disclosure surface, the failure tells, and the bindings; this companion carries the per-harness operational catalogs.

## Obligations

### 1. Per-Harness Agentic-Capability Matrix

Every cell is one of: **yes** (vendor-supported per the adapter's pinned snapshot), **no** (vendor does not support), **partial** (vendor supports a subset; the adapter's STANDARD CONVENTION PIN names the subset boundary), **discovery-pending** (the capability has not yet been discovered against the harness's pinned snapshot; surfaces as a finding per the disclosure ledger).

The matrix axes:

- **Rows (17 harnesses):** antigravity, claude_code, codebuddy, codex, cursor, gemini_cli, github_copilot, hermes, kimi_code, kiro, open_claw, opencode, qwen_code, trae, windsurf, zed, glm.
- **Core columns (9 capabilities):** MCP server support · sub-agent dispatch · tool-surface restrictions · system-prompt template surface · agent-memory convention · output-style support · custom-command support · hooks-pipeline support · skills-directory support.
- **Supplemental operational columns:** recommended-postfix rendering · long-context/compaction continuity · context-ignore surface · layered-context surface · LSP/symbol-navigation surface · hook-learning capture surface · standard-convention pin pointer · web-fetch / browser-retrieval surface (the `web_fetch` projection backing `rules/source-accessibility.md` step 1's "retrieve through the host's browser / fetch capability" escalation).

Each row's authoritative cell values live co-resident with the adapter's STANDARD CONVENTION PIN at `src/apothem/harnesses/<name>/STANDARD-CONVENTION-PIN.md` per `rules/harness-adapter-shape.md` §6. Until every adapter pin carries the full evidence chain, `src/apothem/harnesses/<name>/capabilities.yml` is the interim machine-readable projection for installed checks; it carries the legacy five required fields plus `custom_command_support`, `recommended_postfix_rendering`, `long_context_compaction`, `context_ignore_surface`, `layered_context_surface`, `lsp_symbol_navigation`, `hook_learning_capture`, `standard_convention_pin`, and `web_fetch` (the web-fetch / browser-retrieval surface per §1A). The aggregate cross-harness matrix is materialized at `_inputs/cross-harness-agent-capability-matrix.md` during the cross-harness convergence walks.

Per-cell evidence requirement: every **yes** / **partial** cell MUST cite the vendor-doc-url + commit-sha + snapshot-date triple from the adapter's pin. Every **no** cell cites the same triple plus a one-sentence rationale naming the vendor surface that lacks the capability. Every **discovery-pending** cell carries an inquiry-id per `rules/authority-inquiry.md` so the gap is tracked.

Per-row attestation surface: the adapter's gate-attestation block per `rules/pre-emission-gate.md` carries an `agent-capability-coverage: <yes | partial | no | discovery-pending>` field per column, mirrored from the matrix row.

Matrix-staleness check: a cell whose snapshot-date is older than 90 days against current vendor reality surfaces as a finding per `rules/harness-adapter-shape.md` §6 stale-pin discipline. The companion's evidence chain is the parent rule's STANDARD CONVENTION PIN evidence chain — never duplicated, always referenced.

### 1A. Web-Fetch / Browser-Retrieval Surface — the M2 Source-Accessibility Backing Dimension

The `web_fetch` supplemental column is the per-harness declaration of whether the harness exposes a vendor-native web-fetch / URL-retrieval / web-search / browser tool. It is the real backing dimension for `rules/source-accessibility.md` step 1's escalation — "retrieve it directly through the host's browser / fetch capability" — so the escalation reads a declared cell instead of assuming a capability. Each harness's `capabilities.yml` carries the `web_fetch` field as one of: **yes** / **no** / **partial** / **discovery-pending**, with the same per-cell evidence requirement as §1: a **yes** / **partial** cell cites the vendor-doc-url + commit-sha + snapshot-date triple from the adapter's pin; a **no** cell cites the triple plus a rationale; a **discovery-pending** cell carries the tracked-gap note. When a harness's `web_fetch` cell is **no** or **discovery-pending**, `rules/source-accessibility.md` step 2 (operator-interview escalation per `rules/authority-inquiry.md`) is the live path — the absence of a fetch capability does not abandon the trusted source, it routes the retrieval to the operator.

Current sweep state (web-fetch evidence pass, snapshot-date 2026-06-21): eight harnesses are vendor-confirmed and now carry an inline evidence triple (vendor-doc-url + snapshot-id + snapshot-date) in their `capabilities.yml` `web_fetch` comment block — **yes**: `claude_code` (built-in WebFetch + WebSearch), `gemini_cli` (built-in `web_fetch` + `google_web_search`, commit-pinned to the adapter's own immutable snapshot), `codex` (first-party web search tool, default-on for local tasks), `github_copilot` (Copilot CLI `web_fetch` tool, URL-permission-gated), `windsurf` (Cascade Web Search + URL Read, admin-toggle-gated); **partial**: `qwen_code` (built-in `web_fetch` yes, `web_search` removed → MCP-only), `opencode` (`webfetch` unconditional, `websearch` provider/env-gated), `cursor` (`@Web` user-invoked context search, no documented autonomous fetch tool). The remaining seven — `antigravity`, `codebuddy`, `hermes`, `kiro`, `open_claw`, `trae`, `zed` — stay **discovery-pending**: no authoritative vendor source was located in this sweep, and the §1 definition forbids asserting `no` (vendor lacks it) or `yes` (without the triple) absent evidence. The eight populated cells' canonical evidence home remains the STANDARD CONVENTION PIN per §1's per-cell requirement; the inline `capabilities.yml` triple is the interim machine-readable carrier until a pin refresh folds each triple into the adapter's pin "Native Surfaces" block (the open follow-up). The 15 STANDARD CONVENTION PINs were last pinned (2026-05-31) cataloging config-materialization surfaces (rules files, MCP registration surfaces, hooks, skills, commands, memory), not the vendor runtime tool catalog — the pin-refresh follow-up adds the web-fetch tool row to each populated harness's pin. The 2026-10-03 pin refresh adds `kimi_code` as **yes** (built-in `FetchURL` + `WebSearch`, evidence in its pin).

### 1B. Per-Harness "(Recommended)"-Annotation Enforcement Gap (M5)

The `(Recommended)` option-label postfix is specified behaviorally at `rules/determinism.md` §1, `rules/option-annotation.md` / `rules/option-annotation-form.md`, and `rules/interactive-questions-canonical-shapes.md` §2.1. The **runtime well-formedness guard** for that postfix is `hooks/askuserquestion_validator.py`, which fires on the `AskUserQuestion` tool event and checks the rendered option set's recommended-marker placement and bidirectional bind at call time. That guard is wired into exactly **one** harness:

- **claude_code** — the validator is registered in the generated `templates/settings.json` (matcher `AskUserQuestion` → the `pretooluse-askuserquestion-recommended` hook message). claude_code is the **only** harness whose operators get a call-time guard on the `(Recommended)` rendering.
- **The other 14 harnesses** (antigravity, codebuddy, codex, cursor, gemini_cli, github_copilot, hermes, kiro, open_claw, opencode, qwen_code, trae, windsurf, zed) receive the `(Recommended)` discipline as **behavioral rules text only** — the rule prose is materialized into each harness's instruction surface, but no call-time validator inspects the rendered option set. The enforcement floor for these 14 is the pre-emission conformity sweep on authored artifacts (`conformity/option_annotation_grep.py`, `conformity/determinism_grep.py`), not a runtime call-time guard.

**Wiring candidates.** Among the 14 text-only harnesses, **codex** (`~/.codex/hooks.json` hook surface) and **qwen_code** (`settings.json` hooks namespace) are the hook-capable candidates for wiring the same `AskUserQuestion`-equivalent validator, since both ratify a hooks-pipeline surface in their pins (codex `hooks.json`; qwen_code `hook_learning_capture: settings.json-hooks`). gemini_cli also documents a native settings.json hooks surface but the adapter keeps hook prose as support material and registers no native hooks (see its `capabilities.yml`), so it is a secondary candidate behind codex and qwen_code. Wiring those two would close the runtime-enforcement gap for the harnesses that can host a call-time guard; the remaining rules-only harnesses stay on the authored-artifact conformity floor. This is a tracked divergence, not a defect — the `(Recommended)` discipline is materialized everywhere; only the call-time guard is claude_code-exclusive today.

### 3. Per-Harness MCP-Surface Catalog

Per-harness MCP server registration surfaces, projected from the shared profile's canonical MCP inventory:

- **claude_code** — `mcpServers` block inside `~/.claude/settings.json` (user-scope) plus project-level `.mcp.json` (project-scope). The adapter's materializer renders both surfaces from the profile's MCP inventory.
- **cursor** — `~/.cursor/mcp.json` (user-scope) plus project-level `.cursor/mcp.json` analogue where the vendor supports per-project MCP scoping.
- **codex / opencode / open_claw / qwen_code / antigravity / hermes / gemini_cli / windsurf / github_copilot** — per-harness MCP surface declared at the adapter's STANDARD CONVENTION PIN under `canonical-filename:` and `canonical-schema:` fields per `rules/harness-adapter-shape.md` §6. Where the harness does not yet expose an MCP surface (matrix column 1 cell is **no** or **discovery-pending**), the adapter declares the absence and the profile's MCP inventory is materialized into a sibling fallback surface (e.g., a system-prompt-embedded MCP descriptor) where the vendor surface permits, or omitted with an explicit `[Refusal — …]` ledger row per the parent rule's disclosure surface.

Sharing discipline: the profile's MCP inventory is the single source of truth; a per-harness surface MUST NOT silently diverge from the inventory. Operator-authored per-harness override rows (a harness-specific MCP server the operator declares for one harness only) are recorded explicitly in the profile's `mcp.overrides.<harness>` block and carry a concrete-driver rationale per `rules/interactive-questions-canonical-shapes.md` §3.2.1.

Project-vs-user scoping: the profile's MCP entries declare scope (`user` / `project` / `both`) and the per-harness materializer projects the scope into the harness's ratified surface (claude_code's project-level `.mcp.json` vs. user-level `mcpServers` block; cursor's project-level `.cursor/mcp.json` vs. user-level `~/.cursor/mcp.json`; per-harness analogues).

Discovery-pending MCP surfaces: when a harness's pinned snapshot does not yet document an MCP surface, the adapter carries a `mcp-surface: discovery-pending` field in its STANDARD CONVENTION PIN until the vendor surface ratifies; the materializer refuses MCP materialization for that harness per the parent rule's §8 refusal-and-override flow.

### 7. Per-Harness Agent-Memory-Convention Catalog

Per-harness agent-memory persistence semantics:

- **persists-across-sessions** — the harness's memory surface survives session boundaries (vendor-ratified durable memory; e.g., a `memory/` directory or a memory-store file the harness reads at session start). The adapter's materializer emits the cohort's shared memory content into the harness's ratified durable surface.
- **does-not-persist** — the harness has no durable memory surface; agent memory is session-local. The adapter declares the absence and the profile's memory content is projected into the harness's system-prompt template surface (parent rule §6) as a read-only memory snapshot at session start where the vendor surface permits, or omitted with an explicit ledger row.
- **migrates** — the harness's memory surface admits import from an adjacent harness's memory format (vendor-ratified memory portability). The adapter declares the migration source-and-target pair, the migration script (under `src/apothem/harnesses/<name>/memory_migration.py` or equivalent), and the migration's idempotency guarantees.

The per-harness memory-convention cell maps to matrix column 5 (agent-memory convention) of §1. The adapter's STANDARD CONVENTION PIN carries the memory-convention field under `agent-memory: persists-across-sessions | does-not-persist | migrates` with per-harness specifics (the durable surface's path, the migration source-and-target pair, the read-only-snapshot projection surface).

Cross-harness memory portability table: the aggregate per-harness memory-convention map lives at `_inputs/cross-harness-agent-capability-matrix.md` alongside the §1 matrix, with the `migrates` rows pointing to the migration scripts and the `does-not-persist` rows pointing to their fallback projection surface. The table is the canonical reference for cross-harness skill authorship that depends on durable memory.

Stale memory-convention detection: a memory-convention cell whose snapshot-date diverges from current vendor reality (e.g., the vendor introduced a memory surface after the pin's snapshot date) surfaces as a finding per the stale-pin discipline.

## Enforcement

Path-filtered (the four glob patterns in this rule's `pathFilter` field — `**/src/apothem/harnesses/**`, `**/_inputs/cross-harness-agent-capability-matrix.md`, `**/.mcp.json`, `**/mcp.json`), demand-loaded companion to `rules/agent-capability-discipline.md` §1 / §3 / §7. The parent rule retains the standing directive, the plain-language boundary, the disclosure surface, the failure tells, and the bindings; this companion carries the per-harness capability matrix, the MCP-surface catalog, and the agent-memory-convention catalog.

## Bindings (§0.j five-direction)

- **Drives →** ● Every adapter sub-package's per-capability cell value declaration co-resident with its STANDARD CONVENTION PIN. ● The aggregate cross-harness matrix materialization at `_inputs/cross-harness-agent-capability-matrix.md`. ● Every per-harness MCP-surface projection from the profile's MCP inventory. ● Every per-harness agent-memory-convention declaration and its cross-harness portability mapping.
- **Satisfies →** ● `rules/agent-capability-discipline.md` §1 / §3 / §7 Companion Sub-Rule Anchor pointers. ● The cross-harness adapter capability convergence baseline.
- **Established by ↑** ● `rules/agent-capability-discipline.md` (parent-rule anchors at §1 / §3 / §7). ● `rules/harness-adapter-shape.md` §4 adapter capability-coverage matrix. ● `rules/harness-adapter-shape.md` §6 STANDARD CONVENTION PIN (the co-resident discipline this companion's evidence chain references).
- **Gated by ←** ● The path-filter (the four glob patterns) — this rule demand-loads only on adapter / matrix / MCP-config artifact touches. ● `rules/agent-capability-discipline.md` always-on baseline (parent rule's §1 / §3 / §7 anchors must be live for the companion to demand-load coherently).
- **Cross-bound with ↔** ↔ `rules/agent-capability-discipline.md` (parent rule; §1 / §3 / §7 anchors bind this companion). ↔ `rules/harness-adapter-shape.md` (co-resident STANDARD CONVENTION PIN discipline at §6; per-cell evidence chain anchors to the same pin). ↔ `rules/host-discovery.md` (M1 — per-cell discovery walks the vendor surface per the discovery-record provenance schema). ↔ `rules/disclosure-ledger.md` (M2 — discovery-pending cells and stale-snapshot findings recorded). ↔ `conformity/agent_capability_grep.py` (the mechanical matcher operationalizes the per-cell evidence-chain check). ↔ `rules/source-accessibility.md` (the §1A `web_fetch` column is the backing dimension for that rule's step-1 browser/fetch escalation; reciprocal of its `Gated by ←` web-fetch citation). ↔ `rules/determinism.md` + `rules/option-annotation.md` (the §1B `(Recommended)`-rendering discipline whose per-harness runtime-enforcement wiring this companion catalogs).
