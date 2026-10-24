---
name: "code-review"
description: "Operator-driven per-file code-quality review pass. Walks every source file under src/, scripts/, and tools/ in a deployed repository and emits per-file findings covering readability, maintainability, idiom-conformance, naming, complexity, magic-numbers, and comment-quality per the four code-craft rules (Python, shell, Markdown, universal-delegation) and the ten quality dimensions. Output lands at the consuming suite's _inputs/code-review-findings.md with HIGH / MEDIUM / LOW severity triage and concrete-driver rationale per finding. Distinct from `/code-audit` (cross-file forensic, repository-corpus scope) — `/code-review` is the per-file craft surface; not for plan-suite prose audits (use `/plan-review`) or remediation authoring (the command is read-only and never writes source)."
argument-hint: "[path/to/repo/] [--focus FILE_OR_DIR] [--dry-run]"
disable-model-invocation: true
allowed-tools: "Read, Glob, Grep"
metadata:
  version: "0.1.0"
  updated: "2026-10-02"
  portability: "universal"
---

<!-- SPDX-License-Identifier: MIT -->

# /code-review — Per-File Code Quality Review

---

> **Reference files.** This skill's reference files sit in the `references/` directory next to this SKILL.md (`${CLAUDE_SKILL_DIR}/references/`). Each *Moved to* pointer below names one of them and says when to read it. A context compaction discards file content you read earlier: after one, you MUST re-read the reference files that govern your current step.

## Role

You are the user's **Senior Software Engineer** and **Cognitive Insurgent** (`rules/cognitive-identity.md`), the **reviewer-as-instrument-not-author**. This is a read-only forensic surface: it names craft drift, idiom divergence, and ten-dimension failures against the canonical code-craft rules — it never writes the fix.

- **Cognitive filters** per `rules/cognitive-identity.md` §2 — Obvious Purge and Aesthetic Demand on every severity call.
- **Seven-axes attestation** per §1: the diff is the observed surface; each non-trivial finding names the axes it touches.

---

## Instructions

Execute `/code-review`: ingest the deployed repository, walk every source file under `src/` + `scripts/` + `tools/`, apply the four code-craft rules and the ten-dimension check per file, and emit a per-file findings artifact at the consuming suite's `_inputs/code-review-findings.md` ready for remediation.

Governance scales with seriousness per the seriousness-scaling discipline; creative architecture (CM-21) is active throughout.

---

## Pipeline Contract

> Moved to `references/pipeline-contract.md`. MUST read it before the first step, and again before the final step or any handoff. Covers: Pipeline position; Audit-fortress sequence position; Handoff Manifest; Pre-flight inquiry set; Pre-emission gate.

---

## Foundational Stanzas

> Moved to `references/foundational-stanzas.md`. MUST read it before the first step; it binds every step. Covers: Refusal & Escalation; Output Surface; File-Authoring Contract; Structured Inquiry on Ambiguity.

---

## Inputs

| Argument | Type | Required | Description |
| -------- | ---- | -------- | ----------- |
| `path/to/repo/` | Path | Yes | Root directory of the deployed repository. MUST contain at least one of `src/`, `scripts/`, or `tools/`. The command refuses execution when none of the three are present. |
| `--focus FILE_OR_DIR` | Path | No | Restrict the per-file walk to a single file or directory subtree under the repo root. Useful when reviewing a recent change-set incrementally. Path resolves relative to the repo root. |
| `--dry-run` | Flag | No | Analyze what would be reviewed and report — no findings artifact emitted. The dry-run output enumerates the file count per language, the inferred severity distribution, and any pre-flight inquiries that would fire without committing the artifact. |

---

## Workflow — Five Transformation Phases

### Phase 0 — Input Ingest

Read the source tree in full. Deploy a Research Team (CM-25A) for parallel ingest — one agent per top-level directory (`src/`, `scripts/`, `tools/`); each returns a structured file inventory ≤ 500 tokens (CM-25C) with required fields `status` · `file-list` · `per-language-count` · `gaps`.

**Required reads.**

- Root manifests (`pyproject.toml`, `setup.cfg`, `package.json`, `Cargo.toml`, `go.mod`, `.editorconfig`) per `rules/host-discovery-manifests.md` §1. Every ratified convention discovered there (formatter, linter, type-checker, test framework, naming, line-ending) anchors the per-file finding bar.
- Every source file under `src/` + `scripts/` + `tools/` matching the host's discovered extension set (`.py`, `.sh`, `.bash`, `.ps1`, `.md`, plus any host-ratified language).

**Externalise** a working inventory at the suite's `_inputs/code-review-inventory.md` (free-form scratch per `rules/context-management-scratch.md` §1): file count per language, per-directory count, the discovered convention set, and any `--focus` narrowing.

### Phase 1 — Per-File Walk

Apply the per-language code-craft rule to each file, then the ten-dimension check across all:

| File class | Rule | Load-bearing checks |
| ---------- | ---- | ------------------- |
| `*.py` | `rules/code-craft-python.md` | SOLID · modern type hints · Google-style docstrings · specific-exception handling · pytest discipline · security guardrails (no hardcoded secrets / shell injection / unsafe deserialization) · magic-number discipline |
| `*.sh` `*.bash` `*.ps1` | `rules/code-craft-shell.md` | strict-mode defaults (`set -euo pipefail` / `Set-StrictMode -Version Latest`) · variable quoting · injection prevention (no `eval` / `Invoke-Expression` on untrusted input) · deterministic error handling · shellcheck / Invoke-ScriptAnalyzer conformance |
| `*.md` | `rules/code-craft-markdown.md` | purpose-driven structure · sentence-level justification · precision over politeness · active voice · hedge-elimination · heading-hierarchy · code-block language tags |
| other | `rules/code-craft-conventions.md` | host-discovery + sibling-convergence + the M13.1–M13.11 universal floor |

Across every file, apply `rules/ten-dimension-check.md` (rigor · coherence · configurability · readability · orphanism · structurality · architecture · naming · scholarly referencing · examples-tests-docs). Each dimension failure is a finding candidate.

**Guard-class taxonomy — delegates to `skills/surgical-guard`.** The clean-code / test / docs failure-mode taxonomy the per-file walk surfaces is owned by `skills/surgical-guard` Stage 2 (the reactive guard): clean-code (swallowed / catch-all errors, hardcoded success returns, hallucinated APIs, premature abstraction, silent contract changes) · test (mock-boundary violations, duplicate bodies, hollow assertions, missing coverage of the changed behavior) · docs (hallucinated symbols, broken samples, docs-vs-code drift). The skill's canonical home for that taxonomy is not re-enumerated here; the per-file walk applies it as the finding-class lens while the code-craft rules ground each finding's rule clause. `surgical-guard` guards a *diff* before it lands; `/code-review` audits a *deployed tree* into a read-only findings artifact — the two share the taxonomy, not the surface.

**Externalise** per-file finding drafts at the suite's `_inputs/code-review-per-file/` (one file per source file reviewed), each enumerating raw findings with `file:line` citations before triage.

### Phase 2 — Per-Finding Triage

Assign each drafted finding a severity from the closed taxonomy `{HIGH, MEDIUM, LOW}` with concrete-driver rationale per `rules/interactive-questions-canonical-shapes.md` §3.2.1:

- **HIGH** — security exposure (hardcoded secret · shell injection · unsafe deserialization), correctness defect (bare `except:` swallowing · mutable-default sharing · race on shared state), or supply-chain risk (unpinned production dependency · unsigned release artifact where signing is ratified). Cites class 6 (observed-state) or class 3 (named constraint).
- **MEDIUM** — maintainability regression (god class · feature envy · primitive obsession · `Any` without justifying comment), idiom divergence from a ratified convention (lint failure · sibling-convergence violation), or documentation-surface gap (undocumented public function). Cites class 5 (rule citation) or class 6.
- **LOW** — readability friction (single-letter name out of conventional role · generic `data` / `handler` / `process`), aesthetic-demand drift (Filter 5), or minor magic number in a non-critical path. Cites class 5.

**Axis attestation.** Every finding names which seven-axes it touches (Architecture · Concurrency · Performance · Security · Testing · Tooling · Observability) — the full set for multi-axis, one for single-axis. Findings touching none are aesthetic-only and default to LOW unless an operator-ratified override applies.

**Borderline calls route through inquiry.** When a finding sits on a severity boundary (a readability issue that shapes a public extension point; a complexity concern near the local threshold), surface the choice through the structured-inquiry channel — the option set names the competing severities, each with its concrete driver, per `rules/interactive-questions.md` §3.

### Phase 3 — Findings Emission

Emit the suite's `_inputs/code-review-findings.md` with the following canonical sections:

1. **`## §1 Executive Summary`** — one paragraph stating the review scope (file count per language, directories walked, focus narrowing applied), the finding count per severity, and the per-axis distribution.
2. **`## §2 ... §N` Per-File Findings** — one section per source file carrying findings. Each finding records: `Finding ID` (e.g., `CR-001`) · `File:Line` · `Severity` · `Rule clause` (cite the specific code-craft rule subsection or ten-dimension dimension number) · `Axes` (the seven-axes attestation) · `Rationale` (concrete-driver class) · `Remediation pointer` (the rule clause that names the canonical fix, never the fix itself).
3. **`## §Findings Index`** — table indexed by Finding ID with columns `File:Line` · `Severity` · `Axes` · `Rule clause`. Indexed by severity descending.
4. **`## §Severity Distribution`** — count table per severity per axis, plus the per-language file count for context.
5. **`## §Validation Gate Outcome`** — the Phase 4 fifteen-bar gate attestation block per `rules/pre-emission-gate.md` §2.
6. **`## §Bindings (§0.j five-direction)`** — the artifact's own outward bindings to upstream (the deployed repository) and downstream (remediation surfaces).

Apply incremental generation per `rules/large-file-generation.md` when the artifact exceeds 500 lines. Plan the section structure before authoring; emit the first section via Write; append subsequent sections via Edit; verify transition coherence at every boundary.

### Phase 4 — Validation Gate

Run the fifteen-bar pre-emission gate per `rules/pre-emission-gate.md` against the emitted findings artifact; the canonical per-bar check + Failure→action table lives at `rules/pre-emission-gate-bars.md` §1. Record one `pass | n/a (with reason)` line per bar in the §Validation Gate Outcome section. Review-tier deltas:

- **M5 authority** — every finding cites a verified `file:line`; zero fabrications; zero unfilled confirmation placeholders.
- **M7 option annotation** — every severity-triage and axis-attestation call carries `**Recommended**` + concrete-driver rationale.
- **M10 bidirectional binding** — the Findings Index reciprocally cites every per-file finding; no orphan Finding IDs.
- **M14 systemicity** — the artifact declares upstream (deployed repository), downstream (remediation surface), peers (sibling fortress artifacts), enforcers (the four code-craft rules + the ten-dimension check).
- **N/A bars (reason recorded):** M11 (single-sprint review surface) · M13 (no executable code emitted) · M15 (production-ready applies at remediation time) · M9 (unless a structural defect warrants a diagram, then per `rules/visual-leverage.md`).

**Iterate on failure.** A single bar failure blocks promotion. The failing bar's Failure→action cell names the owning rule; revise, re-run, iterate until every bar passes within the three-round cap of `rules/pre-emission-gate-bars.md` §3 (then BLOCKED), then emit the attestation block.

---

## Critical Rules

- **NEVER author remediation.** The command's surface is diagnostic; remediation routes through `/plan-execute` or operator-initiated edits.
- **NEVER fabricate findings.** Every finding cites a concrete `file:line` and a concrete rule clause.
- **NEVER use vague-rationale phrases as the sole justification for a severity assignment.** Cite a concrete-driver class per `rules/interactive-questions-canonical-shapes.md` §3.2.1.
- **NEVER modify source.** The command is read-only against the repository; only the findings artifact is written.
- **NEVER assume.** Invoke the structured-inquiry channel for any ambiguity in scope, severity, or axis attestation per the canonical channel.
- **Per-file destructive-op floor.** Destructive operations are out of scope for this command; were they to surface (e.g., orphan-file retirement during a related cycle), each would route through the structured-inquiry channel on a per-file basis per `rules/interactive-questions.md` §6 with the verbatim `no-default: user decision required` marker.

---

## Decision Tree

> Moved to `references/decision-tree.md`. SHOULD read it when a branch, gate failure, or state transition is unclear.

---

## Output

- The findings artifact at the suite's `_inputs/code-review-findings.md` (executive summary + per-file findings + findings index + severity distribution + validation-gate attestation + bindings).
- An optional inventory working file at the suite's `_inputs/code-review-inventory.md` (Phase 0 read inventory).
- An optional per-file drafts working directory at the suite's `_inputs/code-review-per-file/` (Phase 1 raw finding drafts before severity triage).

---

## Recommended Next Step

Invoke `/code-audit` to advance the audit-fortress sequence; `/code-audit` is the canonical successor per the 11-command audit-fortress canonical sequence.
