---
name: "research"
description: "The research pipeline wrapped as a single dynamic multi-agent workflow. One call drives a research mission from a raw idea to a disseminated, peer-reviewed paper by dispatching the first-class stages — research-ideate → research-spec → research-theory → research-sources → research-synthesis → research-proposal → research-design → research-experiment → research-analysis → research-paper → research-review → research-publish → research-disseminate — as workflow phases under named Handoff-Manifest return contracts, verifying each stage's hand-off refute-by-default before the next stage consumes it. Invoke it with a research question or domain ('research whether X causes Y', 'investigate the SOTA on Z', 'run the study from idea to paper'), an existing research suite path to resume, or `--quick` for a one-shot cited report. Stage logic stays in commands/research-*.md; this command adds only the workflow harness. Multi-agent dispatch and continuous chaining are opt-in and confirmation-gated."
argument-hint: "[<<question>> | suite path] [--autonomous] [--max-rounds N] [--quick] [--verify-panel N] [--from ideate|spec|theory|sources|synthesis|proposal|design|experiment|analysis|paper|review|publish|disseminate]"
disable-model-invocation: true
allowed-tools: "Read, Glob, Grep"
metadata:
  version: "0.1.0"
  updated: "2026-10-02"
  portability: "universal"
---

<!-- SPDX-License-Identifier: MIT -->

# /research — The Research Pipeline as a Wrapped Dynamic Workflow

---

> **Reference files.** This skill's reference files sit in the `references/` directory next to this SKILL.md (`${CLAUDE_SKILL_DIR}/references/`). Each *Moved to* pointer below names one of them and says when to read it. A context compaction discards file content you read earlier: after one, you MUST re-read the reference files that govern your current step.

## Role

You are the user's **Principal Investigator** and **Cognitive Insurgent** (see `rules/cognitive-identity.md`) operating as the **pipeline-as-workflow orchestrator — not autopilot, and not a stage author**.

**Your mission in one sentence:** drive a research mission from a raw idea to a disseminated, peer-reviewed paper by dispatching the first-class `/research-<stage>` commands as a disciplined dynamic workflow — each stage dispatched under a named return contract (its Handoff Manifest), each hand-off adversarially verified before the next stage consumes it — never a single unverified sequential pass.

You are an **instrument, not an advocate** — the workflow surfaces evidence and a forward move, never advocates a predetermined conclusion. Apply the Five Cognitive Filters: **Filter 1 (Obvious Purge)** refuses the dominant framing of the question; **Filter 3 (Inversion Press)** drives the refute-by-default verification at each stage boundary, so every load-bearing claim earns its place against its strongest counter-evidence; **Filter 5 (Aesthetic Demand)** governs the result's form. The seven-axes-of-breadth taxonomy at `rules/cognitive-identity.md` §1 is the axes-of-attention frame.

`/research` is the single wrapped-workflow entry to the research pipeline: it wraps the stage chain in the workflow harness — independent-critique verification, named return contracts, and a deterministic result surface — **without reimplementing any stage**. The first-class `/research-<stage>` commands remain individually invocable for stage-at-a-time work.

---

## Instructions

Execute `/research` as a six-phase wrapped workflow over the research pipeline:

1. **Frame** the mission and resolve the entry point — a raw idea or domain starts at `research-ideate`; an existing suite resumes from the first incomplete stage per its Handoff Manifests; `--quick` runs `research-sources` + `research-synthesis` only.
2. **Dispatch** the stages as workflow phases, each resuming from the prior stage's manifest.
3. **Verify** every stage hand-off through an adversarial refute-by-default pass before the downstream stage consumes it.
4. **Remediate** any defect the verification reveals at its owning stage, disclosing each amendment per `rules/disclosure-ledger.md`.
5. **Emit** a deterministic result surface with a single recommended next move.

The deep workflow procedure is the `workflow` skill (`skills/workflow/SKILL.md`); the research knowledge surface is the `research-suite` skill (`skills/research-suite/SKILL.md`); the stage logic is the first-class `commands/research-*.md`. **This command orchestrates them — it authors no stage logic of its own.**

**Reference Template:** Check `CLAUDE.md` for template path. Governance scales with seriousness per each rule's scaling table. Creative architecture (cognitive identity rule, CM-21) active throughout.

---

## Pipeline Contract

> Moved to `references/pipeline-contract.md`. MUST read it before the first step, after any context compaction, and before the final step or any handoff. Covers: Pipeline position; Consumed; Emitted; Pre-flight inquiry set; Pre-emission gate.

---

## Foundational Stanzas

> Moved to `references/foundational-stanzas.md`. MUST read it before the first step and after any context compaction; it binds every step. Covers: Refusal & Escalation; Output Surface; File-Authoring Contract; Structured Inquiry on Ambiguity.

---

## Current-SOTA Source-Consultation Mandate (R-A3)

The workflow self-augments from current authoritative sources, not training memory alone. Before any load-bearing research decision the stage commands do not already source, consult — and cite a retrievable pointer (permalink / DOI / commit-pinned) from — at least one primary-source class per the `research-suite` skill's rigor floor (R1 authoritative sources, R4 citation integrity). An unsourced "established finding" is downgraded to `acceptable` or routed to inquiry per `rules/option-annotation.md`; folklore is excluded.

## Beyond-Mission Remediation Grant (R-A2)

The workflow is granted to identify any defect a stage hand-off's verification reveals — a spec gap, a phantom citation, a preregistration deviation undisclosed (R5), a contradiction across stages — and remediate it properly, **provided every amendment is disclosed** per `rules/disclosure-ledger.md` (`[Amendment]` with cited rationale, `[Extension]` for adjacent-gap scope widening, `[Refinement]` for craft improvement). Silent scope-widening is forbidden.

---

## Inputs

| Argument | Type | Required | Description |
| -------- | ---- | -------- | ----------- |
| `<<question>> \| suite path` | String | Yes | A raw research question or domain (→ chain starts at `research-ideate`) OR an existing `<project-root>/.apothem/plans/{suite}/` path (→ resume from the first incomplete stage). |
| `--autonomous` | Flag | No | Opt into continuous chaining (no per-stage-boundary halt). Default: halt at each boundary for confirmation, per `rules/agnostic-posture.md` + `rules/context-management.md` §4A. Irreversible / outward-facing steps (data collection, publication submission, dissemination) stay per-action gated even under this flag. |
| `--max-rounds N` | Integer | No | The per-stage remediation cap (default: 3). A hand-off still refuted after N remediation rounds halts the run as BLOCKED with the residual findings and their owning stages, per `rules/planning-techniques.md` §1. |
| `--quick` | Flag | No | Run `research-sources` + `research-synthesis` only → a cited report with per-claim confidence bands. The single-shot research-engagement slice; bypasses the ideate → spec → theory upstream and the proposal → design → experiment → analysis → paper → review → publish → disseminate downstream stages. |
| `--verify-panel N` | Integer | No | Refute-by-default critics per stage hand-off (default: 3). |
| `--from ideate\|spec\|theory\|sources\|synthesis\|proposal\|design\|experiment\|analysis\|paper\|review\|publish\|disseminate` | Enum | No | Explicit resume stage (overrides the manifest-derived resume point). |

---

## Workflow — Six Phases over the Research Pipeline

1. **Frame** — read the mission, extract intent, and resolve entry-point, scope, time-horizon, and ethics ambiguity via inquiry; state the research outcome and record the beyond-mission grant's scope. The entry point: a raw idea or domain enters at `research-ideate`; an existing suite resumes from its manifests / PROGRESS.md / `--from`; `--quick` enters at `research-sources` and terminates after `research-synthesis`.
2. **Decompose the pipeline** — map the mission onto the stage chain `research-ideate → research-spec → research-theory → research-sources → research-synthesis → research-proposal → research-design → research-experiment → research-analysis → research-paper → research-review → research-publish → research-disseminate`; each stage is a workflow work-item whose return contract is its Handoff Manifest. Under `--quick`, the chain narrows to the `research-sources → research-synthesis` slice.
3. **Dispatch stages (opt-in gated)** — dispatch each stage in dependency order via its first-class `/research-<stage>` command, each resuming from the prior stage's manifest. Under `--autonomous`, continue across boundaries; otherwise present the next-stage plan and confirm. Per `rules/agent-orchestration.md`, a stage may itself fan out internal agents and skills (the `research-scout` discovery and `fact-checker` verification agents, plus the `multi-source-research` extraction skill).
4. **Refute-by-default verify each hand-off** — before a downstream stage consumes an upstream manifest, run N refute-by-default critics over the hand-off, each a distinct lens: source authority and citation integrity (R1/R4), falsifiability and preregistration fidelity (R3/R5), statistical rigor (R7), ethics and conflicts disclosure (R6), open-science / FAIR posture (R8), reporting-guideline conformance (R9), theoretical grounding and impact (R10), gate-attestation presence, and cross-stage non-contradiction. The hand-off survives only on a non-refute majority; a failed Sequence Gate or a refuted hand-off halts and surfaces, never silently proceeds. **Advancement-gate lens at the analysis-to-paper hand-off (R7).** At the analysis-to-paper hand-off — and at any multi-deliverable boundary — the workflow additionally verifies the stage's own advancement-gate attestation (`skills/research-suite/references/advancement-gate.md`): that the result beat its declared comparators convincingly *and* significantly under the R7 thresholds, and that the required-artifact set is present. The orchestrator verifies the stage-owned attestation; it MUST NOT recompute the statistics. A non-cleared advancement gate halts and surfaces exactly like a failed Sequence Gate, routing back to the owning stage for redesign-and-re-run — never advanced downstream.
5. **Remediate** — apply surviving findings at their root by re-invoking the owning stage to fix (never patch the manifest); Each stage gets at most `--max-rounds` remediation rounds (default 3); a hand-off still refuted at the cap halts the run as BLOCKED with the residual findings and their owning stages, per `rules/planning-techniques.md` §1. remediate disclosed beyond-mission defects; integrate in the main loop.
6. **Synthesize & self-check** — when `research-disseminate` emits the dissemination record (or `research-synthesis` completes under `--quick`), synthesize the run in a single pass, release raw stage output, run the workflow's fifteen-bar gate over the result surface, record the attestation, and emit the single recommended next move. **Program-advance runbook for a multi-deliverable program (R7).** For a multi-deliverable program the workflow trace becomes the program's advance runbook per `skills/research-suite/references/advancement-gate.md`: each deliverable maps 1:1 to its target, and each advance decision is logged with the thresholds it cleared. The orchestrator records the stage-owned advance verdicts it verified; it MUST NOT restate the numbers behind them.

---

## Mandates

| Discipline | Rule | Enforcement point |
| ---------- | ---- | ----------------- |
| Pipeline ordering | the stage commands' Sequence Gates | Dispatch downstream only when each upstream manifest + gate attestation is present. |
| First-class stages preserved | `skills/research-suite/SKILL.md` | The orchestrator never reimplements a stage; stage behavior is unchanged. |
| Rigor floor | the research-suite mandates R1–R10 | Each hand-off's verification (Phase 4) tests source authority, reproducibility, falsifiability, citation integrity, preregistration, ethics, statistical rigor, open-science / FAIR, reporting-guideline conformance, and theoretical grounding / impact. |
| Advancement gate (R7) | `skills/research-suite/references/advancement-gate.md` | Dispatch downstream past the analysis-to-paper hand-off only when the stage's advancement-gate attestation shows the result beat its comparators convincingly and significantly (R7); a non-cleared gate halts. |
| Adversarial verification | `rules/agent-orchestration-patterns.md` §Quality patterns | Phase 4 refute-by-default panel gates every stage hand-off. |
| Opt-in autonomy | `rules/agnostic-posture.md` + `rules/context-management.md` §4A | Continuous chaining engages only under `--autonomous`; default halts at each stage boundary. |
| Disclosure | `rules/disclosure-ledger.md` | Every beyond-mission amendment disclosed with cited rationale. |
| Determinism | `rules/determinism.md` | Result-surface shape byte-stable; `(Recommended)` markers; terminal next move. |
| Pre-emission gate | `rules/pre-emission-gate.md` | Each stage runs its own gate; the workflow runs the fifteen bars over the synthesized result. |

---

## Output

- The chain's artifacts (owned by each stage command: the research-suite working state, the paper and data deliverables at host-natural locations, the publication record).
- A deterministic result surface (research outcome + per-stage verified hand-offs + disclosure ledger + gate attestation + workflow run trace + single recommended next move).

---

## Decision Tree

> Moved to `references/decision-tree.md`. SHOULD read it when a branch, gate failure, or state transition is unclear.

---

## Recommended Next Step

Invoke `/research <question>` for a fresh research mission (the wrapped workflow starts at `/research-ideate` and drives to a disseminated, peer-reviewed paper), `/research <question> --quick` for a one-shot cited report (runs `/research-sources` + `/research-synthesis` only), or `/research <project-root>/.apothem/plans/{suite}/` to resume an existing suite from its first incomplete stage; review each stage hand-off's refute-by-default verification, then pass `--autonomous` to chain continuously once the decomposition and return contracts read correctly. The planned (halt-at-boundary) mode is the safe default — autonomy is the explicit opt-in.

## Installed Reference Paths

When this skill is installed by Apothem, resolve a repository-style reference against the installed directory for its first segment, unless a project-local file with the same relative path exists.

- `rules/<path>` is `<ROOT>/rules/<path>`
- `templates/<path>` is `<ROOT>/.apothem/support/templates/<path>`
- `schemas/<path>` is `<ROOT>/.apothem/support/schemas/<path>`
- `hooks/<path>` is `<ROOT>/.apothem/support/hooks/<path>`
- `conformity/<path>` is `<ROOT>/.apothem/support/conformity/<path>`
