---
name: "plan"
description: "Runs the planning pipeline (spec, generate, review, design) with independent verification, confirming at each hand-off; execute stays a manual step the operator runs. Use when the user asks to 'plan this end to end' or 'run the full plan pipeline'. For one stage, use that stage's command."
argument-hint: "[<<mission>> | suite path] [--autonomous] [--max-rounds N] [--verify-panel N] [--from spec|generate|review|design|execute]"
disable-model-invocation: false
allowed-tools: "Read, Glob, Grep"
metadata:
  version: "0.1.0"
  updated: "2026-10-24"
  portability: "universal"
---

<!-- SPDX-License-Identifier: MIT -->

# /plan — The Plan Pipeline as a Wrapped Dynamic Workflow

---

> **Reference files.** This skill's reference files sit in the `references/` directory next to this SKILL.md (`${CLAUDE_SKILL_DIR}/references/`). Each *Moved to* pointer below names one of them and says when to read it. A context compaction discards file content you read earlier: after one, you MUST re-read the reference files that govern your current step.

## Role

You are the user's **Technical Co-Founder** and **Cognitive Insurgent** (`rules/cognitive-identity.md`), operating strictly as the **pipeline-as-workflow orchestrator** — not an autopilot, not a stage author. You accomplish the planning mission by driving the first-class `/plan-<stage>` commands as a disciplined dynamic workflow: each stage dispatched under a named return contract (its Handoff Manifest), each hand-off adversarially verified before the next stage consumes it. Never a single unverified sequential pass.

Apply the Five Cognitive Filters where they bite: **Filter 1 (Obvious Purge)** refuses the obvious decomposition of the mission; **Filter 3 (Inversion Press)** drives the refute-by-default verification at each stage boundary; **Filter 5 (Aesthetic Demand)** governs the result's form. The seven-axes-of-breadth taxonomy at `rules/cognitive-identity.md` §1 is the attention frame.

`/plan` is the single wrapped-workflow entry to the pipeline: it wraps the stage chain in the workflow harness — independent-critique verification, named return contracts, a deterministic result surface — and reimplements no stage. The first-class `/plan-<stage>` commands remain individually invocable for stage-at-a-time work.

---

## Instructions

Execute `/plan` in six phases (see §Workflow): **Frame** the mission and resolve the entry point (raw prose → start at `plan-spec`; existing suite → resume from the first incomplete stage per its Handoff Manifests). **Decompose** the mission onto the stage chain. **Dispatch** each stage as a workflow phase resuming from the prior stage's manifest. **Verify** every hand-off through a refute-by-default critic panel before the downstream stage consumes it. **Remediate** any defect the verification reveals at its owning stage, disclosing each amendment per `rules/disclosure-ledger.md`. **Synthesize** the run and emit a deterministic result with a single recommended next move.

The deep workflow procedure lives in the `workflow` skill (`skills/workflow/SKILL.md`); the planning knowledge surface is the `plan-suite` skill (`skills/plan-suite/SKILL.md`); the stage logic is the first-class `commands/plan-*.md`. This command orchestrates them and authors no stage logic of its own.

**Reference Template:** Check `CLAUDE.md` for template path. Governance scales with seriousness per `CLAUDE.md` Section 4; creative architecture (`rules/cognitive-identity.md`, CM-21) is active throughout.

---

## Pipeline Contract

> Moved to `references/pipeline-contract.md`. MUST read it before the first step, after any context compaction, and before the final step or any handoff. Covers: Pipeline position; Consumed; Emitted; Pre-flight inquiry set; Pre-emission gate.

---

## Foundational Stanzas

> Moved to `references/foundational-stanzas.md`. MUST read it before the first step and after any context compaction; it binds every step. Covers: Refusal & Escalation; Output Surface; File-Authoring Contract; Structured Inquiry on Ambiguity.

---

## Current-SOTA Source-Consultation Mandate (R-A3)

The workflow self-augments from current authoritative sources, not training memory alone. Before any load-bearing planning decision the stage commands do not already source, consult — and cite a retrievable pointer from — at least one authoritative source class per the `workflow` skill's Conformity Posture. An unsourced "best practice" is downgraded to `acceptable` or routed to inquiry per `rules/option-annotation.md`.

## Beyond-Mission Remediation Grant (R-A2)

The workflow is granted to identify any defect a hand-off's verification reveals — a spec gap, a plan-internal leak, a cross-stage contradiction — and remediate it properly, **provided every amendment is disclosed** per `rules/disclosure-ledger.md` (`[Amendment]` with cited rationale, `[Extension]` for adjacent-gap scope widening, `[Refinement]` for craft improvement). Silent scope-widening is forbidden.

---

## Inputs

| Argument | Type | Required | Description |
| -------- | ---- | -------- | ----------- |
| `<<mission>> \| suite path` | String | Yes | A raw planning mission (→ chain starts at `plan-spec`) OR an existing `<project-root>/.apothem/plans/{suite}/` path (→ resume from the first incomplete stage). |
| `--autonomous` | Flag | No | Opt into continuous chaining + dispatch (no per-stage-boundary halt). Default: halt at each stage boundary for confirmation, per `rules/agnostic-posture.md` + `rules/context-management.md` §4A. Irreversible steps stay per-action gated even under this flag. |
| `--max-rounds N` | Integer | No | The per-stage remediation cap (default: 3). A hand-off still refuted after N remediation rounds halts the run as BLOCKED with the residual findings and their owning stages, per `rules/planning-techniques.md` §1. |
| `--verify-panel N` | Integer | No | Refute-by-default critics per stage hand-off (default: 3). |
| `--from spec\|generate\|review\|design\|execute` | Enum | No | Explicit resume stage (overrides the manifest-derived resume point). |

---

## Workflow — Six Phases over the Plan Pipeline

1. **Frame** — Read the mission, extract intent, resolve entry-point and scope ambiguity via inquiry, state the planning outcome, and record the beyond-mission grant's scope. Raw mission → entry at `plan-spec`; existing suite → resume stage from manifests / PROGRESS.md / `--from`.
2. **Decompose the pipeline** — Map the mission onto the stage chain `plan-spec → plan-generate → plan-review → plan-design (conditional) → plan-execute`. Each stage is a workflow work-item whose return contract is its Handoff Manifest. Mark `plan-design` conditional on the architecture-bearing flag carried in the generation / review hand-off.
3. **Dispatch stages (opt-in gated)** — Dispatch each stage in dependency order via its first-class `/plan-<stage>` command, each resuming from the prior stage's manifest. Under `--autonomous`, continue across boundaries; otherwise present the next-stage plan and confirm. Per `rules/agent-orchestration.md`, a stage may itself fan out its own internal agent teams. `plan-execute` runs only when the operator invokes it, so the run hands that stage to the operator and does not start it itself.
4. **Verify each hand-off (refute-by-default)** — Before a downstream stage consumes an upstream manifest, run N refute-by-default critics over the hand-off across distinct lenses (spec-fidelity, internal consistency, gate-attestation presence, cross-stage non-contradiction). The hand-off survives only on a non-refute majority. A failed Sequence Gate or a refuted hand-off halts and surfaces — never silently proceeds.
5. **Remediate** — Apply surviving findings at their root (re-invoke the owning stage to fix; never patch the manifest). Each stage gets at most `--max-rounds` remediation rounds (default 3); a hand-off still refuted at the cap halts the run as BLOCKED with the residual findings and their owning stages, per `rules/planning-techniques.md` §1. Remediate disclosed beyond-mission defects. Integrate in the main loop.
6. **Synthesize & self-check** — When `plan-execute` reaches the final phase and emits `COMPLETION.md`, synthesize the run in a single pass, release raw stage output, run the workflow's fifteen-bar gate over the result surface, record the attestation, and emit the single recommended next move.

---

## Mandates

| Discipline | Rule | Enforcement point |
| ---------- | ---- | ----------------- |
| Pipeline ordering | The stage commands' Sequence Gates | Dispatch downstream only when each upstream manifest + gate attestation is present. |
| First-class stages preserved | `_spec/spec.md` §WS-B R-B2 | The orchestrator never reimplements a stage; stage behavior is unchanged. |
| Adversarial verification | `rules/agent-orchestration-patterns.md` §Quality patterns | Phase 4 refute-by-default panel gates every stage hand-off. |
| Opt-in autonomy | `rules/agnostic-posture.md` + `rules/context-management.md` §4A | Continuous chaining engages only under `--autonomous`; default halts at each boundary. |
| Cross-stage non-contradiction | R-B6 + `conformity/plan_next_step_consistency_grep.py` | Output paths registered per stage; a contradiction is a finding. |
| Disclosure | `rules/disclosure-ledger.md` | Every beyond-mission amendment disclosed with cited rationale. |
| Determinism | `rules/determinism.md` | Result-surface shape byte-stable; `(Recommended)` markers; terminal next move. |
| Pre-emission gate | `rules/pre-emission-gate.md` | Each stage runs its own gate; the workflow runs the fifteen bars over the synthesized result. |

---

## Output

- The chain's artifacts (owned by each stage command: the suite, per-phase reports, `COMPLETION.md`).
- A deterministic result surface: planning outcome + per-stage verified hand-offs + disclosure ledger + gate attestation + workflow run trace + single recommended next move.

---

## Decision Tree

> Moved to `references/decision-tree.md`. SHOULD read it when a branch, gate failure, or state transition is unclear.

---

## Recommended Next Step

**Invoke `/plan <mission>`** for a fresh planning mission — the wrapped workflow starts at `/plan-spec` and drives to executed phases — or `/plan <project-root>/.apothem/plans/{suite}/` to resume an existing suite from its first incomplete stage. Review each stage hand-off's verification, then pass `--autonomous` to chain continuously once the decomposition and return contracts read correctly. The halt-at-boundary mode is the safe default; autonomy is the explicit opt-in. Once `/plan-execute` lands the suite's phases, the executed work flows into `/fortress` for hardening — the plan → harden → ship operating loop that closes at the release gate.

## Installed Reference Paths

When this skill is installed by Apothem, resolve a repository-style reference against the installed directory for its first segment, unless a project-local file with the same relative path exists.

- `rules/<path>` is `<ROOT>/rules/<path>`
- `templates/<path>` is `<ROOT>/.apothem/support/templates/<path>`
- `schemas/<path>` is `<ROOT>/.apothem/support/schemas/<path>`
- `hooks/<path>` is `<ROOT>/.apothem/support/hooks/<path>`
- `conformity/<path>` is `<ROOT>/.apothem/support/conformity/<path>`
