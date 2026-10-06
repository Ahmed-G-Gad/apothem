---
name: "plan-suite"
version: "0.1.0"
updated: "2026-06-10"
description: "Master Plan Suite template container — matched when the work is structured plan generation from authored prose, phase-by-phase decomposition of a complex multi-step engagement, plan-suite refinement, forensic plan review, closed-loop plan audit/remediation, architectural design, phase execution against quality gates, read-only progress reporting, or decision-preserving amendment; consumed by the /plan pipeline stages (spec, generate, review, design, audit, execute, status, amend). Houses master-template.md — the canonical specification defining plan-suite structure, the mandate catalog (TM-1–28), the core-principle catalog (CP-1–27), and the Technical Co-Founder Framework. Not directly user-invocable: the /plan stages resolve the template by path, cold-load it on a context-empty invocation, and refuse to regenerate it from memory if it is missing. Not a codegen tool, not a research pipeline, not a documentation generator, not a registry, and not stateful across sessions."
archetype: "workflow-template"
user-invocable: false
disable-model-invocation: true
allowed-tools: "Read"
---

<!-- SPDX-License-Identifier: MIT -->

## Purpose

> **Structural Note:** This skill is a *template container*, not a procedural skill. It deliberately omits the standard SKILL.md Procedure / Detection-Signal structure because it houses a reference template rather than encoding a reusable technique. The `/plan` pipeline stages invoke it by reading its template file directly — not by following a procedure. The deviation from standard skill structure is intentional.

Houses the Master Plan Suite Template — the canonical specification referenced by all `/plan` pipeline commands (`/plan-spec`, `/plan-generate`, `/plan-review`, `/plan-design`, `/plan-audit`, `/plan-execute`, `/plan-status`, `/plan-amend`).

## Contents

- `master-template.md` — the full template defining plan-suite structure, the mandate catalog (TM-1–28), the core-principle catalog (CP-1–27), and the Technical Co-Founder Framework.

## Auto-Load Contract

When any `/plan-<stage>` command is invoked **cold** — without its predecessor stages' context explicitly loaded into the session — the consuming stage MUST resolve this skill before executing, so the full pipeline context loads uniformly and no stage assumes manually-preloaded state.

**Cold-invocation trigger.** A `/plan-<stage>` invocation is cold when the session carries none of: a resolved `_spec/spec.md`, a loaded plan suite (PREAMBLE.md / MASTER-PLAN.md / PROGRESS.md), or a prior `/plan-<stage>` turn in the same session. On a cold invocation the stage reads this skill first; on a warm invocation (predecessor context already loaded) the read is a no-op refresh.

**Deterministic full-pipeline load order.** Resolving this skill surfaces the pipeline in one fixed order — the same cold invocation always yields the same load:

1. `/plan-spec` — prose → `_spec/spec.md` (+ Handoff Manifest)
2. `/plan-generate` — `_spec/spec.md` → Master Plan Suite
3. `/plan-review` — forensic audit + scorecards
4. `/plan-design` — architecture artifact (architecture-bearing suites only)
5. `/plan-audit` — closed-loop remediation to a zero-finding gate
6. `/plan-execute` — phase execution against quality gates
7. `/plan-status` — read-only progress report
8. `/plan-amend` — amend an existing suite, re-deriving only affected artifacts

Each stage's template anchor (its Step-0 consumption point in the Invoking Surfaces table below) resolves against this skill's `master-template.md` by path. A cold stage that cannot resolve this skill STOPs per the Resolution & Recovery clause instead of proceeding on assumed context.

## Non-Goals

This skill is a template container with a deliberately narrow surface. It is NOT:

- **Not a one-shot codegen tool.** The template defines plan structure; it does not generate code, scaffold projects, or emit codebase artifacts directly. Codebase emission is the consuming `/plan-execute` stage's responsibility, governed by the host's discovered conventions.
- **Not a research synthesis pipeline.** The template consumes authored prose at `_spec/spec.md`; it does not gather, summarize, or triangulate external sources. Prose elicitation and refinement is the upstream `/plan-spec` stage's responsibility.
- **Not a documentation generator.** Plan-suite artifacts (PREAMBLE.md, MASTER-PLAN.md, PROGRESS.md, PLAN-NOTES.md, per-phase PHASE.md / REPORT.md) are working documents driving execution; they are not user-facing documentation. User-facing docs land at `site/content/docs/`, `README.md`, and the host's documentation surfaces.
- **Not a registry.** The template path is declared in the `/plan` pipeline and resolved path-based — no auto-discovery, no fallback registry, no plug-in-style extension.
- **Not stateful across sessions.** The skill carries no runtime state; each `/plan` stage invocation re-reads the template afresh, and durable plan-suite state lives in the per-suite folder under `<project-root>/.apothem/plans/{suite}/`.

## Invoking Surfaces

The eight `/plan` pipeline stages consume this skill's template by direct path resolution:

| Command | Consumption point | What the command reads |
|---------|-------------------|------------------------|
| `/plan-spec` | Step 0 (template anchor) | TM-1 / TM-7 / TM-10 / TM-11 mandates governing prose elicitation |
| `/plan-generate` | Step 0 (template anchor) | Full TM-N / CP-N catalog + plan-suite skeleton (PREAMBLE / MASTER-PLAN / PROGRESS / PLAN-NOTES / per-phase PHASE.md) |
| `/plan-review` | Step 0 (template anchor) | TM-N / CP-N IDs for forensic-audit cross-references; scorecard rubric |
| `/plan-design` | Step 0 (template anchor) | Architecture-bearing TM-N / CP-N mandates governing the six-phase architectural-design transformation (sits between `/plan-review` and `/plan-execute`) |
| `/plan-audit` | Step 0 (template anchor) | TM-19 orchestration, zero-finding gate, `_outputs/`, and `*-maintenance` routing |
| `/plan-execute` | Step 0 (template anchor) | Verification-section + Phase Output Registry + Resumption Contract conventions |
| `/plan-status` | Step 0 (template anchor) | Phase Tracker + Phase Output Registry shape (read-only) |
| `/plan-amend` | Step 0 (template anchor) | TM-N / CP-N IDs governing decision-preserving amendment + the plan-suite artifact set it re-derives |

No agent invokes the skill directly; the `/plan` pipeline commands are the canonical consumption surface.

## Foundational Stanzas

The four standing surfaces per the canonical project voice at `AGENTS.md` plus the active harness mirror, adapted to this skill's passive template-container role so consuming `/plan` pipeline stages inherit a coherent posture on template resolution.

### Refusal & Escalation

REFUSE any consumer request that asks the skill to act outside its template-container mission — generation, edits, research, codegen, fixes. Refusal is explicit: name what was refused, name the mission boundary crossed, and route the consumer back to the appropriate `/plan` stage via the structured-inquiry channel per `rules/interactive-questions.md` (canonical channel; three-segment option annotation; free-form prose as primary input is forbidden). When the template file is missing, malformed, or unreachable, the skill STOPs and surfaces the recovery options in the Resolution & Recovery section below — it does NOT regenerate the template from training-time memory or scaffold a partial replacement.

### Output Surface

The skill emits **no artifacts of its own**; it is a passive template read by consuming commands. Plan-suite artifacts that the consumers emit while resolving this template land at `<project-root>/.apothem/plans/{suite}/` per the suite-locality invariant at `rules/context-management.md` §2.6.1 — gitignored per the canonical `.gitignore` snippet, lifecycle draft → in-progress → converged → abandoned / superseded. NEVER write a plan-suite artifact outside the suite folder, NEVER write to `<project-root>/.apothem/plans/` from a downstream-project context, and NEVER write to any global-ecosystem location. The downstream-project lightweight plan-write surface is `/plan-spec --quick` per D3 — a single `<YYYY-MM-DD>--<kebab-slug>.md` file at the resolved project's `.apothem/plans/` directory. Codebase artifacts that consuming commands emit during plan execution go to their domain-natural locations under the host project per `rules/host-discovery.md`; per `rules/operational-mandates.md` CM-7, codebase artifacts contain ZERO plan-internal references — natural domain language only.

### File-Authoring Contract

The skill is `allowed-tools: "Read"` — it authors no files directly. The contract applies to consuming `/plan` pipeline stages: every NEW codebase file the consumer creates routes through `scripts/inject-header.{sh,py}` so the canonical authorship-header banner is injected at the head; the injector is idempotent and detects the filetype variant automatically from the byte-exact fixture at `src/apothem/schemas/authorship-header.txt`. The exempt classes — LICENSE, JSON configuration files, lockfiles, generated assets, vendored trees, `.audit/` ephemera, `<project-root>/.apothem/plans/` ephemera, `.keep` / `.gitkeep` markers, binary files — are enumerated at `src/apothem/schemas/header-exceptions.txt`. Plan-suite artifacts (PREAMBLE.md, MASTER-PLAN.md, PROGRESS.md, PLAN-NOTES.md, per-phase PHASE.md / REPORT.md) are header-exempt under the `.apothem/plans/**` exception class. The header-inject-guard hook at `hooks/messages/pretooluse-{write,edit}-header-guard.md` enforces the contract at every Write / Edit invocation made by the consuming command.

### Structured Inquiry on Ambiguity

When a consuming `/plan` stage reaches a decision in any of the seven authoritative-data categories per `rules/authority-inquiry.md` — identity (suite owner, contributors), scope direction (which subtree, which target), preference (CI provider, branch strategy, formatter, linter, test framework), security (deny rules, secret rotation, allowed shells, allowed network egress), naming of public surfaces (suite name, phase identifiers), infrastructure endpoints, version pins (template version, downstream-tooling pins) — and the host is silent, the consumer routes the resolution through the structured-inquiry channel with the three-segment option annotation per `rules/interactive-questions.md` §3 (rationale / recommendation / default-pointer). Free-form prose questions as primary input are forbidden. NEVER fabricate authoritative data. Required-category inquiries (identity, scope direction, security posture, naming of public surfaces) block emission until answered; optional inquiries fall back to the recommended option and record the fallback in PLAN-NOTES.md as a finding. **Per-file destructive-op floor.** Every delete / rename / move / overwrite-without-retention / revert-uncommitted operation the consumer performs against an existing plan-suite artifact routes through the structured-inquiry channel on a per-file basis per `rules/interactive-questions.md` §6 — one invocation per file, every time, no `multiSelect` batching across files, every option's `default-pointer:` carrying the verbatim `no-default: user decision required` marker.

## Conformity Posture

The three-element conformity discipline applies to **consumers** of this template — every `/plan` stage invocation that resolves the template inherits the obligations below — and is reproduced here so consumers reach the discipline at the same surface they reach the template.

**Discover-don't-assume preamble (M1).** Before any `/plan` stage invocation populates a plan-suite artifact from this template, the consuming command walks the host's ratified source-of-truth files for the host's planning conventions per `rules/host-discovery.md` — phase-folder naming, sub-phase-folder naming, report-filename convention, frontmatter requirements on per-phase artifacts, host-discovered TM-N / CP-N analogs. Honor discoveries; never silently install a planning convention where the host has its own.

**Authority inquiry surface (M5).** Per the Structured Inquiry on Ambiguity stanza above; this anchor binds the M5 discipline to the seven-category inquiry catalog at `rules/authority-inquiry-categories.md` §1.

**Pre-emission self-check (M4).** Every plan-suite artifact emitted from this template — `PREAMBLE.md`, `MASTER-PLAN.md`, `PROGRESS.md`, `PLAN-NOTES.md`, every `phases/NN-topic/PHASE.md`, every `phases/NN-topic/REPORT.md` — passes the fifteen-bar pre-emission gate per `rules/pre-emission-gate.md` before the consuming `/plan` stage considers the artifact complete. The gate's attestation lands in the artifact's working trace (specifically, the corresponding REPORT.md's "Pre-Emission Gate Attestation" section per the established reporting convention). Mechanical-fraction bars run via the per-bar matchers at `conformity/*-grep.py`; reasoned bars are evaluated inline by the consuming command.

## Resolution & Recovery

Not directly invocable. The `/plan` pipeline stages resolve this template via the path declared in `CLAUDE.md` Source Layout (currently `skills/plan-suite/master-template.md`). Resolution is path-based, not registry-based — there is no fallback registry and no auto-discovery; the path must match exactly.

**Fallback handling.** If the template file is missing, malformed (corrupted YAML/markdown that prevents parsing of the TM-N / CP-N sections), or unreachable: STOP and inform the user. Do NOT regenerate the template from training-time memory or scaffold a partial replacement — `/plan` pipeline stages depend on the canonical TM-N / CP-N IDs, and any divergence silently corrupts every cross-reference downstream. Recovery options surfaced via the structured-inquiry channel: (a) re-clone or re-install the apothem ecosystem from version control (Recommended); (b) restore the template file from a backup; (c) point commands at a known-good template via an explicit override path.

**Version compatibility.** Commands declare `Requires template v0.1.0+`. Bump the template's version field when changes alter TM-N / CP-N semantics; consumers refuse to operate against an older major version than they expect.

## Recommended Next Step

Invoke `/plan-generate` to consume this skill's `master-template.md` and materialize a plan suite from the authored prose at `_spec/spec.md`. `/plan-generate` is the canonical downstream consumer that reads the full TM-N / CP-N catalog and the plan-suite skeleton from this template.

## Bindings (§0.j five-direction)

- **Drives →** ● Every `/plan` stage's resolution of the master template at `skills/plan-suite/master-template.md`. ● Every TM-N / CP-N cross-reference resolution across the eight `/plan` pipeline stages. ● Every plan-suite emission's structural conformity (the template is the canonical schema). ◐ The version-compatibility gate (`Requires template v0.1.0+`).
- **Satisfies →** ● `CLAUDE.md` Source Layout row "plan-suite". ● `CLAUDE.md` Project Purpose (the eight `/plan` pipeline stages consume this skill's template).
- **Established by ↑** ● `CLAUDE.md` Source Layout. ● `CLAUDE.md` Project Purpose (the path declaration `skills/plan-suite/master-template.md`). ● `CLAUDE.md` Source Layout (skills/ class declaration with the folder-with-`SKILL.md` convention).
- **Gated by ←** ● The harness's Read tool surface (commands resolve the template by reading the canonical path). ● The presence of the template file at the canonical path (path-based resolution per the Resolution & Recovery clause).
- **Cross-bound with ↔** ↔ `commands/plan-spec.md` + `commands/plan-generate.md` + `commands/plan-review.md` + `commands/plan-audit.md` + `commands/plan-design.md` + `commands/plan-execute.md` + `commands/plan-status.md` + `commands/plan-amend.md` (the eight consumer commands). ↔ `skills/ecosystem-audit/SKILL.md` (sibling skill under the same registry section).
