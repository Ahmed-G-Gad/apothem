---
trigger: glob
description: "Path-filtered companion to `agnostic-posture.md`: the default-off and opt-in invariant checklist, each with a concrete verification step, that every phase's definition of done satisfies and the planning-pipeline commands and learning loop consult."
globs: "**/commands/**, **/rules/**, **/output-styles/**, **/statuslines/**, **/.apothem/plans/**, **/.plans/**"
---

<!-- SPDX-License-Identifier: MIT -->

# Rule: Agnostic Posture — Checklist (Companion Sub-Rule)

## Purpose

Carry the verification checklist for the parent rule `agnostic-posture.md`. The parent declares the posture — default-off behaviors, advisory correctness gates, harness neutrality, end-user-invoked preference, preserved machinery. This companion makes that posture **checkable**: it restates each invariant with a concrete verification step so a phase, a planning pass, or a learning-loop iteration can confirm a clean install still imposes nothing. Path-filtered: loads when the agent touches a shipped surface, a command, or a plan — where the posture is produced and verified.

## Obligations

### 1. The Invariant Checklist

Every phase that changes a shipped surface MUST satisfy all six invariants before its work is done. Each invariant carries a verification step that produces evidence; a phase records the outcome of each step it touches.

| # | Invariant | Verification step (evidence) |
|---|-----------|------------------------------|
| 1 | **Workflow behaviors ship default-off.** The sprint apparatus, agent-team dispatch, parallel multitasking, continuous multi-step advancement, and continuous-learning capture are each off until the end user opts in. | Load the default shared profile and assert every `enforcement` flag (`sprints`, `agent_teams`, `multitasking`, `continuous_execution`, `learning_loop`) is `False`. A flag defaulting `true` in the shipped schema or example profile fails the invariant. |
| 2 | **A clean install imposes no workflow.** A request runs with no sprint ceremony, no forced agent dispatch, and no parallel-task imposition unless a flag was set. | Trace a representative request against a default profile; confirm none of the five behaviors auto-applies. Where a sibling rule marks a behavior "mandatory" or "always-on", confirm that marking describes the opted-in shape, not a clean-install imposition. |
| 3 | **Correctness gates are advisory.** Lint, format, type-check, test, security scan, conformance, and the pre-emission gate emit findings plus a definitive next step and then yield — none blocks the end user's action by default. | Run the conformity gate without the strict opt-in; confirm it surfaces findings and a next step and exits zero. Confirm the strict flag and the strict environment variable restore blocking for the pipelines that opt in. |
| 4 | **No shipped surface tailors to one harness.** Every rule, command, output-style, statusline, and template renders identically across every registered harness; a harness name appears only by its slug as one catalog entry among many. | Run the agnosticism sweep over the shipped rules, commands, output-styles, and statuslines; confirm zero findings. A privileging brand reference outside a fenced example or a catalog row fails the invariant. |
| 5 | **Preference is end-user-invoked.** No shipped config pre-determines a model, effort, or workflow preference; the default state is unset until an in-conversation choice resolves it. | Inspect shipped commands and templates for an `effort:` or `model:` frontmatter preset; confirm none is present. The agnosticism sweep flags any re-introduced preset in a command. |
| 6 | **De-enforced machinery is preserved, not deleted.** Each default-off behavior keeps a working invocation path — an opt-in flag, a documented command, or a named procedure — so opting in restores it intact. | Confirm each behavior's invocation path exists, then exercise the preserve-machinery smoke test that opts each behavior in and asserts it activates. A behavior reachable by no path fails the invariant: removal, not preservation, is the defect. |

### 2. Per-Surface Use

- **A phase's definition of done.** A phase touching a shipped surface MUST run every invariant whose surface it changed and record the verification outcome. The checklist is the phase-level agnosticism gate; an unverified invariant on a touched surface is an open finding, not a pass.
- **The planning-pipeline commands.** Each `/plan-<stage>` command consults this checklist when shaping a phase, so each phase inherits the default-off and opt-in invariants as acceptance criteria rather than re-deriving them.
- **The learning loop.** When the learning loop captures a correction, it checks the correction against this checklist so a learned behavior is never wired in as a clean-install imposition.

### 3. Failure Tells

A shipped profile with an `enforcement` flag defaulting `true`. A correctness gate that aborts the end user's action on a clean install. A rule or command naming one harness as the assumed runtime or privileged path. A command frontmatter carrying an `effort:` or `model:` preset. A de-enforced behavior with no surviving invocation path. A phase that changed a shipped surface and recorded no verification outcome for the invariants it touched.

## Bindings (§0.j five-direction)

- **Drives →** every phase's agnosticism definition-of-done check; the planning-pipeline commands' per-phase acceptance criteria; the learning loop's clean-install-imposition guard; the agnosticism sweep's two detection classes (the mechanical arm of invariants 4 and 5).
- **Driven by ←** the parent rule `agnostic-posture.md` (the posture this checklist verifies); the operator directive that the agent impose no workflow, model, or effort.
- **Gated by ←** The frontmatter `pathFilter` (commands, rules, output-styles, statuslines, and the plans trees): the checklist loads when a shipped surface or a plan suite is touched. A phase that changes a shipped surface (the §1 trigger; an unchanged surface carries no checklist obligation). `conformity/agnosticism_grep.py` (the mechanical harness-neutrality and default-off sweep under `gate --all`).
- **Satisfies →** the default-off and opt-in invariant enumeration with per-invariant verification; the phase-level agnosticism gate.
- **Established by ↑** `agnostic-posture.md` (the posture the checklist operationalizes); the shared-profile `enforcement` schema (the opt-in surface invariant 1 inspects).
- **Cross-bound with ↔** `agnostic-posture.md` (parent rule; this companion carries its verification checklist); `agile-sprints.md`, `agent-orchestration.md`, `context-management.md` (the opted-in behaviors invariants 1–2 hold default-off); `pre-emission-gate.md` (its bars surface as advisories per invariant 3).
