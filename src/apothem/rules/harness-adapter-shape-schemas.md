---
name: "harness-adapter-shape-schemas"
description: "Path-filtered companion to `rules/harness-adapter-shape.md` — carries the per-harness schema catalog, convergence-vs-divergence table, per-harness pre-emission gate adaptation, the 7-column adapter-test matrix template, the cross-harness redundancy hoist heuristic, and the per-harness STANDARD CONVENTION PIN templates for the 17-harness cohort."
pathFilter: "**/src/apothem/harnesses/**, **/_inputs/harness-*"
alwaysApply: false
---

<!-- SPDX-License-Identifier: MIT -->

# Rule: Harness Adapter Shape — Schemas & PIN Templates (Companion Sub-Rule)

## Purpose

Specify the operational depth of the per-harness adapter discipline declared at the parent rule `rules/harness-adapter-shape.md`. Path-filtered: loads when the assistant edits any adapter sub-package under `src/apothem/harnesses/` or any per-harness scratch under `_inputs/harness-*`, keeping the parent rule's always-on payload lean while preserving full per-harness fidelity at the demand-load surface.

## Obligations

### 1. Per-Harness Discovery Walk — Schema Catalog

Each adapter sub-package walks its harness's ratified config schema. The 17-harness cohort:

| Harness | Canonical config filename(s) | Schema form | Adapter sub-package |
|---|---|---|---|
| antigravity | `~/.gemini/GEMINI.md` plus `~/.gemini/antigravity-cli/plugins/apothem/plugin.json` | Markdown global context plus JSON plugin metadata | `src/apothem/harnesses/antigravity/` |
| claude_code | `settings.json` (+ `CLAUDE.md` operator-owned) | JSON; Claude Code settings schema | `src/apothem/harnesses/claude_code/` |
| codebuddy | `<project>/.codebuddy/rules/apothem-rules.md` | Markdown rules-directory file; CodeBuddy rules schema | `src/apothem/harnesses/codebuddy/` |
| codex | `~/.codex/AGENTS.md`, `~/.codex/hooks.json`, `~/.codex/hooks/`, `~/.codex/agents/*.toml`, `~/.agents/skills/` | Markdown, JSON hooks, TOML custom agents, shared skills; OpenAI Codex schema | `src/apothem/harnesses/codex/` |
| cursor | `<project>/.cursor/rules/apothem-rules.mdc` | Markdown + YAML frontmatter; Cursor rules schema | `src/apothem/harnesses/cursor/` |
| gemini_cli | `<project>/GEMINI.md` plus `<project>/.gemini/{commands,skills,agents}/` | Markdown context plus TOML commands and Markdown skills/agents | `src/apothem/harnesses/gemini_cli/` |
| github_copilot | `.github/copilot-instructions.md` | Markdown prose; Copilot instructions schema | `src/apothem/harnesses/github_copilot/` |
| hermes | `~/.hermes/config.yaml` plus `~/.hermes/.apothem/support/` | YAML native config plus support cohorts | `src/apothem/harnesses/hermes/` |
| kimi_code | `<project>/AGENTS.md` plus `<project>/.kimi-code/.apothem/support/` | Markdown project instruction surface plus support cohorts | `src/apothem/harnesses/kimi_code/` |
| kiro | `<project>/.kiro/steering/apothem-rules.md` | Markdown steering-directory file; Kiro steering schema | `src/apothem/harnesses/kiro/` |
| open_claw | `~/.openclaw/openclaw.json` plus `~/.openclaw/.apothem/support/` | JSON native config plus support cohorts | `src/apothem/harnesses/open_claw/` |
| opencode | `~/.config/opencode/opencode.json` plus native commands, skills, and agents | JSON native config plus Markdown cohorts | `src/apothem/harnesses/opencode/` |
| qwen_code | `~/.qwen/settings.json`, `~/.qwen/QWEN.md`, native commands, skills, and agents | JSON settings plus Markdown context/cohorts | `src/apothem/harnesses/qwen_code/` |
| trae | `<project>/.trae/rules/apothem-rules.md` | Markdown rules-directory file; Trae workspace rules schema | `src/apothem/harnesses/trae/` |
| windsurf | `<project>/.devin/rules/apothem-rules.md` | Markdown; Devin Desktop / Windsurf rules schema | `src/apothem/harnesses/windsurf/` |
| zed | `<project>/.rules` | Markdown rules file (`.rules`); Zed rules schema | `src/apothem/harnesses/zed/` |
| glm | `<project>/.apothem/providers/glm.toml` | TOML provider config; GLM (Z.ai) Anthropic/OpenAI-compatible backend schema | `src/apothem/harnesses/glm/` |

Discovery walks read the harness's vendor-pinned schema (per the STANDARD CONVENTION PIN at §6), the per-harness adapter paths, and the per-harness convention surfaces (rules-directory shape, hook-event taxonomy, output-style placement). Every discovered value is recorded with provenance per `rules/host-discovery.md` §4.

### 2. Sibling-Convention Convergence vs. Divergence

**Shared semantics (cross-harness convergence floor).** Every adapter sub-package:

- exposes a `<Name>Adapter` class implementing the `HarnessAdapter` protocol (`name`, `output_path`, `install`, `uninstall`, `is_installed`, `verify`);
- ships sibling action modules `install.py` / `uninstall.py` / `update.py` / `verify.py`;
- ships `materializer.py` exposing `materialize_native_config(profile) -> str` only when the harness renders a single-file native config surface; raw-propagation adapters document the missing materializer as an intentional divergence;
- registers via the `[project.entry-points."apothem.harnesses"]` table in `pyproject.toml`;
- co-resides with `STANDARD-CONVENTION-PIN.md` per §6.

**Declared divergences.** Per-harness schema differences are declared explicitly in the adapter's docstring AND in a `[Divergence — …]` ledger entry:

| Harness | Declared divergence |
|---|---|
| antigravity | No materializer; installs global `GEMINI.md` plus an Antigravity CLI plugin under `~/.gemini/antigravity-cli/plugins/apothem/`; hook support material is not active hook wiring |
| claude_code | No materializer; propagates raw templates plus convention dirs; does not manage `CLAUDE.md` |
| codex | No materializer; propagates AGENTS.md, hooks.json, converted TOML agents, and shared skills; does not overwrite `config.toml` |
| gemini_cli | No materializer; project-scope adapter writes `<project>/GEMINI.md` and converts commands into Gemini TOML files |
| github_copilot | Materializes Markdown prose rather than structured config; no JSON schema |
| cursor | No materializer; project-scope rules-only adapter writes a single `<project>/.cursor/rules/apothem-rules.mdc` via one `sentinel_merge` and authors no other cohorts |
| hermes | Materializes `config.yaml` and keeps unsupported cohorts under `~/.hermes/.apothem/support/` |
| kimi_code | No materializer; project-scope adapter writes the governance surface into `<project>/AGENTS.md` as a `sentinel_merge` managed block and keeps the non-native cohorts under `<project>/.kimi-code/.apothem/support/`; does not author `<project>/.kimi-code/mcp.json` |
| open_claw | Materializes `openclaw.json` and keeps unsupported cohorts under `~/.openclaw/.apothem/support/` |
| opencode | Materializes `opencode.json` while also writing native commands, skills, and agents under `~/.config/opencode/` |
| qwen_code | Materializes `settings.json` plus `QWEN.md` and writes native command, skill, and agent cohorts under `~/.qwen/` |
| windsurf | No materializer; project-scope rules-only adapter writes a single `<project>/.devin/rules/apothem-rules.md` (the preferred Devin Desktop surface; `.windsurf/rules/` is the backward-compat fallback) via one `sentinel_merge` and authors no other cohorts |
| codebuddy | No materializer; project-scope rules-only adapter writes `<project>/.codebuddy/rules/apothem-rules.md` and authors no other cohorts |
| kiro | No materializer; project-scope rules-only adapter writes `<project>/.kiro/steering/apothem-rules.md` and authors no other cohorts |
| trae | No materializer; project-scope rules-only adapter writes `<project>/.trae/rules/apothem-rules.md` alongside the vendor `project_rules.md` / `user_rules.md` anchors without clobbering them |
| zed | No materializer; project-scope rules-only adapter writes the project-root `<project>/.rules` file and authors no other cohorts |
| glm | No rules/skills/commands cohort; backend-provider adapter writes a single `<project>/.apothem/providers/glm.toml` configuring GLM (Z.ai) as an Anthropic/OpenAI-compatible model backend, and authors no governance surface |

Undeclared divergences are silo-class findings per `rules/systemic-participation.md` M14.

### 3. Per-Harness Pre-Emission Gate Adaptation

Every adapter passes the fifteen-bar gate per `rules/pre-emission-gate.md`. Per-harness adaptation:

| Bar | Per-harness adaptation |
|---|---|
| M1 host agnosticism | Adapter idioms match peer adapters', not a single ecosystem default; the per-harness config schema is the M1 host |
| M13 code craft | Python code-craft per `rules/code-craft-python.md`; the per-harness materializer's output passes the harness's vendor schema validator |
| M14 systemic participation | Convergence per §2; divergences declared; the cross-adapter shared module (§5) honored |
| M15 production-ready | The per-harness test matrix per §4 ships in the same change-set as the adapter touch |

### 4. Adapter-Test Matrix — 7-Column Template

Every adapter ships a test matrix covering load, conformance, standard-conformance, agent-capability coverage, gate pass, divergences, and attestation. Tests live under `tests/unit/harnesses/<name>/` (unit-scoped) and `tests/integration/harnesses/<name>/` (round-trip-scoped). The 7 columns:

| Column | Covers | Test surface |
|---|---|---|
| **Load** | Adapter sub-package importable; entry-point resolves to the `<Name>Adapter` class | `test_load_<name>.py::test_entry_point_resolves` |
| **Conform** | Adapter passes `python -m apothem.conformity.gate --all` on its own sub-package | `tests/conformity/test_<name>_conformity.py` |
| **Standard-Conformance** | Materialized output conforms to the vendor schema pinned at §6 | `test_materializer_<name>.py::test_output_matches_schema` |
| **Agent-Capability Coverage** | Every advertised capability (install / uninstall / update / verify) has a covering test | `test_<action>_<name>.py` (one per action) |
| **Gate-PASS** | Every gate bar attests pass or reasoned n/a in the adapter's working trace | `test_<name>_gate_attestation.py` |
| **Divergences** | Every per-harness divergence from §2 is enumerated AND tested | `test_<name>_divergences.py` |
| **Attestation** | Gate attestation block present + verifiable in the adapter's working trace | `test_<name>_attestation_present.py` |

A test matrix missing one or more columns is a cross-harness coverage finding.

### 5. Cross-Harness Redundancy Elimination — Hoist Heuristic

Logic recurring across **three or more** adapter sub-packages is hoisted to `src/apothem/harnesses/_shared/`. Hoist candidates:

- path-resolution helpers (XDG / `~/.config/<harness>/` resolution);
- schema-validation wrappers (JSON Schema / TOML / YAML validators);
- backup-on-install helpers (timestamped rename of existing config);
- verify-walks (config-file-present + parseable + minimum-schema-version).

**Keep-per-adapter heuristic.** Genuinely per-harness logic — vendor-specific schema quirks, harness-specific hook taxonomies, harness-specific output paths — stays in the adapter sub-package. The threshold is **structural similarity across three or more adapters**, not mere topical overlap. Cross-harness redundancy findings enumerate every duplicate meeting the three-adapter threshold that has not been hoisted.

### 6. Per-Harness STANDARD CONVENTION PIN — Template

Every adapter sub-package carries `src/apothem/harnesses/<name>/STANDARD-CONVENTION-PIN.md`. The canonical template:

```markdown
<!-- canonical single-line SPDX license header per scripts/inject-header.py -->

# STANDARD CONVENTION PIN — <harness-name>

vendor-doc-url: <commit-permalinked vendor documentation URL>
commit-sha: <vendor-repository commit SHA or archival snapshot ID>
snapshot-date: <YYYY-MM-DD ISO 8601>
canonical-filename: <e.g., settings.json>
canonical-schema: <JSON Schema URL | TypeScript type definition path | inline schema body>

## Verification

The vendor schema at the pinned commit-sha above was verified against
vendor reality on snapshot-date. Adapter materializer output MUST
produce content conforming to canonical-schema; deviations are
findings per `rules/harness-adapter-shape.md` §4 Standard-Conformance.

## Refresh cadence

Re-verify against vendor reality every 90 days. On refresh, update
commit-sha + snapshot-date in the same change-set and emit a
`[Pin — refreshed: <harness>; …]` ledger entry per
`rules/disclosure-ledger.md`.

## Bindings

- Established by ↑ `rules/harness-adapter-shape.md` §6.
- Cross-bound with ↔ `src/apothem/harnesses/<name>/__init__.py` (the
  adapter whose discovery walk this pin anchors).
```

Per-harness pins differ on `vendor-doc-url`, `commit-sha`, `snapshot-date`, `canonical-filename`, and `canonical-schema` only; the template shape is invariant across the cohort.

**Stale-pin findings.** A pin whose `snapshot-date` is older than 90 days against current vendor reality surfaces as a finding at the next adapter-touch boundary. The finding routes to a pin-refresh change-set per the §6 refresh cadence.

## Bindings (§0.j five-direction)

- **Drives →** Every per-harness discovery walk; every adapter sub-package's convergence-vs-divergence declaration; every per-harness pre-emission gate adaptation; every 7-column test matrix; every cross-harness hoist decision; every per-harness STANDARD CONVENTION PIN authoring + refresh.
- **Satisfies →** `rules/harness-adapter-shape.md` §§1–6 Companion Sub-Rule Anchors; per-harness adapter discipline; adapter-test matrix discipline; STANDARD CONVENTION PIN freshness; capability-coverage test matrix shape.
- **Established by ↑** `rules/harness-adapter-shape.md` (parent-rule anchor) and the adapter cohort's standard pin discipline.
- **Gated by ←** The path-filter (`**/src/apothem/harnesses/**`, `**/_inputs/harness-*`) — this companion demand-loads only on adapter sub-package or per-harness scratch touches. `rules/harness-adapter-shape.md` always-on baseline.
- **Cross-bound with ↔** `rules/harness-adapter-shape.md` (parent rule; §§1–6 anchors bind this companion). `rules/host-discovery.md` (M1 — per-harness discovery walks). `rules/host-discovery-manifests.md` (M1 detail — discovery-record provenance schema underwrites the §6 PIN). `rules/systemic-participation.md` + `rules/systemic-participation-relations.md` (M14 — convergence-vs-divergence at §2). `rules/canonical-layout.md` (M12 — adapter sub-packages + PIN files at the canonical layout). `rules/disclosure-ledger.md` (M2 — every discovery, pin refresh, declared divergence recorded). `rules/agent-capability-discipline.md` (co-resident PIN discipline mirror).
