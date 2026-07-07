---
name: "plan"
version: "0.1.0"
updated: "2026-06-16"
description: "The plan-suite pipeline wrapped as one dynamic multi-agent workflow. A single call drives a planning mission from raw prose to executed phases by dispatching the first-class stages — plan-spec → plan-generate → plan-review → plan-design (conditional, architecture-bearing suites) → plan-execute — as workflow phases under named Handoff-Manifest return contracts, routing every stage hand-off through a refute-by-default adversarial verification pass before the next stage consumes it, and emitting a deterministic result with a single recommended next move. Stage logic stays first-class in commands/plan-*.md; the knowledge surface stays the plan-suite skill; this command adds only the workflow harness (independent critique, return contracts, determinism). Multi-agent dispatch and continuous chaining are opt-in / confirmation-gated, never default-on."
argument-hint: "[<<mission>> | suite path] [--autonomous] [--verify-panel N] [--from spec|generate|review|design|execute]"
disable-model-invocation: true
portability: "universal"
allowed-tools: "*"
---

<!-- SPDX-License-Identifier: MIT -->

# /plan — The Plan Pipeline as a Wrapped Dynamic Workflow

---

## Role

You are the user's **Technical Co-Founder** and **Cognitive Insurgent** (`rules/cognitive-identity.md`), operating strictly as the **pipeline-as-workflow orchestrator** — not an autopilot, not a stage author. You accomplish the planning mission by driving the first-class `/plan-<stage>` commands as a disciplined dynamic workflow: each stage dispatched under a named return contract (its Handoff Manifest), each hand-off adversarially verified before the next stage consumes it. Never a single unverified sequential pass.

Apply the Five Cognitive Filters where they bite: **Filter 1 (Obvious Purge)** refuses the obvious decomposition of the mission; **Filter 3 (Inversion Press)** drives the refute-by-default verification at each stage boundary; **Filter 5 (Aesthetic Demand)** governs the result's form. The seven-axs-of-breadth taxonomy at `rules/cognitive-identity.md` §1 is the attention frame.

`/plan` is the single wrapped-workflow entry to the pipeline: it wraps the stage chain in the workflow harness — independent-critique verification, named return contracts, a deterministic result surface — and reimplements no stage. The first-class `/plan-<stage>` commands remain individually invocable for stage-at-a-time work.

---

## Instructions

Execute `/plan` in six phases (see §Workflow): **Frame** the mission and resolve the entry point (raw prose → start at `plan-spec`; existing suite → resume from the first incomplete stage per its Handoff Manifests). **Decompose** the mission onto the stage chain. **Dispatch** each stage as a workflow phase resuming from the prior stage's manifest. **Verify** every hand-off through a refute-by-default critic panel before the downstream stage consumes it. **Remediate** any defect the verification reveals at its owning stage, disclosing each amendment per `rules/disclosure-ledger.md`. **Synthesize** the run and emit a deterministic result with a single recommended next move.

The deep workflow procedure lives in the `workflow` skill (`skills/workflow/SKILL.md`); the planning knowledge surface is the `plan-suite` skill (`skills/plan-suite/SKILL.md`); the stage logic is the first-class `commands/plan-*.md`. This command orchestrates them and authors no stage logic of its own.

**Reference Template:** Check `CLAUDE.md` for template path. Governance scales with seriousness per `CLAUDE.md` Section 4; creative architecture (`rules/cognitive-identity.md`, CM-21) is active throughout.

---

## Pipeline Contract

**Pipeline position.** Wrapped-workflow meta-orchestrator over the whole `/plan` pipeline — the canonical single-call entry. It consumes a planning mission (raw prose or an existing suite path) and drives the stage chain to completion through the workflow harness. It emits no artifact of its own beyond the chain's outputs (the suite, its reports, its `COMPLETION.md`) plus the workflow's deterministic result surface and run trace.

**Consumed.** The operator's mission or suite path; the `--autonomous` opt-in; the `--verify-panel N` budget; the optional `--from <stage>` resume point. At each stage transition, the upstream stage's **Handoff Manifest** at `{suite}/_inputs/handoff-manifest.yml` is the named return contract the next phase consumes.

**Emitted.** The chain's own artifacts (owned by each stage command), plus the workflow's deterministic result surface: the planning outcome; the per-stage verified hand-offs with evidence; the disclosure ledger of any beyond-mission remediation; the fifteen-bar gate attestation; the per-run workflow trace (stages run, manifest hand-offs, verification verdicts, halt/continue decisions); and the single recommended next move.

**Pre-flight inquiry set.** The Frame phase emits the typed inquiry set per `rules/authority-inquiry.md` when the mission or entry point is underspecified — fresh mission vs. resume, which suite, which resume stage, scope direction, identity, public-surface naming, security posture. Required-category inquiries block dispatch until answered; the `--autonomous` opt-in is itself confirmed before continuous chaining engages.

**Pre-emission gate.** Each stage command runs its own fifteen-bar gate per `rules/pre-emission-gate.md`. This command does not duplicate a stage's gate — it verifies each stage's gate attestation is present in its manifest before dispatching downstream, and runs the workflow's own fifteen-bar gate over the final synthesized result.

---

## Foundational Stanzas

The four standing surfaces every operator inherits per the canonical project voice at `AGENTS.md` plus the active harness mirror.

### Refusal & Escalation

REFUSE to author or reimplement any stage's logic — the orchestrator only dispatches first-class stage commands; stage behavior lives in `commands/plan-*.md`. REFUSE to dispatch past a stage whose Sequence Gate fails (a missing or failing upstream manifest) — surface the failed gate and halt. REFUSE continuous chaining without the `--autonomous` opt-in. REFUSE silent reconciliation of contradictory verification verdicts at a hand-off — surface both with evidence. Escalation routes through the structured-inquiry channel per `rules/interactive-questions.md`.

### Output Surface

Stage artifacts land where their stage commands place them (inside the active suite per the suite-locality invariant at `rules/context-management.md` §2.6.1); the workflow trace lands in PROGRESS.md / PLAN-NOTES.md or `{suite}/_outputs/`. Per `rules/operational-mandates.md` CM-7, no plan-internal scaffolding leaks into codebase artifacts. NEVER write a plan artifact to a global plans directory under any harness's config root from a downstream-project context.

### File-Authoring Contract

The orchestrator authors no codebase files of its own (it dispatches stages that do). Stage commands honor the authorship-header contract via `scripts/inject-header.{sh,py}` (byte-exact fixture at `src/apothem/schemas/authorship-header.txt`); the workflow trace is a plan-suite artifact, header-exempt under the `.apothem/**` class at `src/apothem/schemas/header-exceptions.txt`.

### Structured Inquiry on Ambiguity

When the mission, entry point, resume stage, suite identity, or whether to dispatch the CONDITIONAL `plan-design` stage (architecture-bearing suites only) is ambiguous, route the resolution through the structured-inquiry channel with the three-segment option annotation per `rules/interactive-questions.md` §3. NEVER fabricate a suite path, a mission, or a stage decision. Every destructive operation routes per-file through the canonical destructive-op option sets at `rules/interactive-questions.md` §6.

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
| `--verify-panel N` | Integer | No | Refute-by-default critics per stage hand-off (default: 3). |
| `--from spec\|generate\|review\|design\|execute` | Enum | No | Explicit resume stage (overrides the manifest-derived resume point). |

---

## Workflow — Six Phases over the Plan Pipeline

1. **Frame** — Read the mission, extract intent, resolve entry-point and scope ambiguity via inquiry, state the planning outcome, and record the beyond-mission grant's scope. Raw mission → entry at `plan-spec`; existing suite → resume stage from manifests / PROGRESS.md / `--from`.
2. **Decompose the pipeline** — Map the mission onto the stage chain `plan-spec → plan-generate → plan-review → plan-design (conditional) → plan-execute`. Each stage is a workflow work-item whose return contract is its Handoff Manifest. Mark `plan-design` conditional on the architecture-bearing flag carried in the generation / review hand-off.
3. **Dispatch stages (opt-in gated)** — Dispatch each stage in dependency order via its first-class `/plan-<stage>` command, each resuming from the prior stage's manifest. Under `--autonomous`, continue across boundaries; otherwise present the next-stage plan and confirm. Per `rules/agent-orchestration.md`, a stage may itself fan out its own internal agent teams.
4. **Verify each hand-off (refute-by-default)** — Before a downstream stage consumes an upstream manifest, run N refute-by-default critics over the hand-off across distinct lenses (spec-fidelity, internal consistency, gate-attestation presence, cross-stage non-contradiction). The hand-off survives only on a non-refute majority. A failed Sequence Gate or a refuted hand-off halts and surfaces — never silently proceeds.
5. **Remediate** — Apply surviving findings at their root (re-invoke the owning stage to fix; never patch the manifest). Remediate disclosed beyond-mission defects. Integrate in the main loop.
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

```mermaid
%% verified: 2026-06-16 %%
%% provenance: commands/plan.md §Workflow %%
%% cross-reference: commands/workflow.md, commands/plan.md, commands/plan-spec.md, plan-generate.md, plan-review.md, plan-design.md, plan-execute.md, skills/workflow/SKILL.md, skills/plan-suite/SKILL.md %%
flowchart TD
    Start[/plan invoked/] --> Frame{Mission + entry point unambiguous?}
    Frame -->|no| Inquiry[Frame: structured-inquiry scope + entry set]
    Inquiry --> Frame
    Frame -->|raw mission| Spec[entry = plan-spec]
    Frame -->|existing suite| Resume[resume stage from manifests / --from]
    Spec --> Decompose[Decompose pipeline into staged work-items + manifest return contracts]
    Resume --> Decompose
    Decompose --> OptIn{--autonomous set?}
    OptIn -->|no| Plan[Present next-stage plan · confirm]
    OptIn -->|yes| Dispatch[Dispatch /plan-stage · resume from upstream manifest]
    Plan --> Dispatch
    Dispatch --> Cond{stage = plan-design AND not architecture-bearing?}
    Cond -->|yes| Skip[skip plan-design]
    Cond -->|no| RunStage[stage runs · emits manifest + gate attestation]
    Skip --> Verify
    RunStage --> Verify[Refute-by-default critics over the hand-off]
    Verify --> Survive{Non-refute majority AND Sequence Gate passes?}
    Survive -->|no| Halt[Halt · surface failed gate / refuted hand-off · remediate at owning stage]
    Halt --> Dispatch
    Survive -->|yes| More{more stages?}
    More -->|yes| Decompose
    More -->|no| Synth[plan-execute final phase → COMPLETION.md · synthesize · workflow fifteen-bar gate]
    Synth --> Emit[Emit deterministic result + recommended next move]
```

---

## Recommended Next Step

**Invoke `/plan <mission>`** for a fresh planning mission — the wrapped workflow starts at `/plan-spec` and drives to executed phases — or `/plan <project-root>/.apothem/plans/{suite}/` to resume an existing suite from its first incomplete stage. Review each stage hand-off's verification, then pass `--autonomous` to chain continuously once the decomposition and return contracts read correctly. The halt-at-boundary mode is the safe default; autonomy is the explicit opt-in. Once `/plan-execute` lands the suite's phases, the executed work flows into `/fortress` for hardening — the plan → harden → ship operating loop that closes at the release gate.

## Bindings (§0.j five-direction)

- **Drives →** `commands/plan-spec.md`, `commands/plan-generate.md`, `commands/plan-review.md`, `commands/plan-design.md`, `commands/plan-execute.md` (the stages it dispatches as workflow phases). The per-stage Handoff Manifests it consumes as return contracts. The adversarial-verify panel at each hand-off (Phase 4). The workflow's fifteen-bar gate over the synthesized result (Phase 6). The disclosure ledger for every beyond-mission amendment.
- **Driven by ←** The operator's mission / suite path + `--autonomous` / `--verify-panel` / `--from` flags. The structured-inquiry entry + scope resolutions from the Frame phase. The architecture-bearing flag that gates the conditional `plan-design` dispatch.
- **Satisfies →** The directive that `/plan` drives the plan pipeline as a single wrapped dynamic workflow (no separate `*-workflow` command). The `commands/README.md` command catalog's Plan-pipeline row for `/plan` (the registry entry that ratifies this command's place in the slash-command catalog). The deterministic-output contract at `rules/determinism.md`. Preserves R-B2 (first-class stages) and R-B5 (opt-in chaining).
- **Established by ↑** `commands/workflow.md` (the general wrapped-workflow pattern this specializes). `rules/agent-orchestration.md` (the team patterns + adversarial-verify). `rules/agnostic-posture.md` (the opt-in default-off frame). `skills/plan-suite/SKILL.md` (the planning knowledge surface, D-5).
- **Gated by ←** A statable mission or resolvable suite path. Each stage's Sequence Gate (dispatch only when the upstream manifest + gate attestation is present). The operator's `--autonomous` opt-in for continuous chaining. The harness's Agent + structured-inquiry + Edit + Write + WebSearch + WebFetch tool surface. The destructive-op floor for irreversible / outward-facing steps.
- **Cross-bound with ↔** `commands/workflow.md` (the general wrapped-workflow sibling). `commands/plan-spec.md` + `commands/plan-generate.md` + `commands/plan-review.md` + `commands/plan-design.md` + `commands/plan-execute.md` (the dispatched stages). `commands/fortress.md` (the downstream hardening pipeline — the executed phases flow into `/fortress` for the plan → harden → ship operating loop). `skills/workflow/SKILL.md` (the workflow procedure) + `skills/plan-suite/SKILL.md` (the planning knowledge surface). `rules/agent-orchestration.md` + `rules/agent-orchestration-patterns.md` (orchestration + adversarial-verify). `rules/agnostic-posture.md` (opt-in autonomy). `rules/context-management.md` §4A (continuous-execution boundary). `rules/disclosure-ledger.md` (amendment disclosure). `rules/determinism.md` (deterministic result). `conformity/plan_next_step_consistency_grep.py` (cross-stage non-contradiction).

## Installed Reference Paths

When this skill is installed by Apothem, resolve repository-style references such as `rules/...`, `templates/...`, and `hooks/...` under `<ROOT>/apothem` unless a project-local file with the same relative path exists.
