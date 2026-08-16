---
name: "projectify"
version: "0.1.0"
updated: "2026-06-16"
description: "Chat-app Project elevation command. Produces the three deliverables — Description, Instruction, knowledge Files — for a Claude Project / ChatGPT Custom GPT / Gemini Gem, freshly authored to current SOTA conventions through a structured-inquiry-saturated elicitation, elevated across order / coherence / clarity / determinism / structurality / conciseness / rigor / comprehensiveness and beyond, holding knowledge files within a measurable per-platform context budget (token-sum / discovered-platform-limit <= 0.02), with the grant to consolidate or divide files. Installs agnostically across all harnesses. Deterministic output; multi-step autonomy is opt-in / confirmation-gated."
argument-hint: "[project subject] [--platform claude|chatgpt|gemini] [--autonomous]"
disable-model-invocation: true
portability: "universal"
allowed-tools: "*"
---

<!-- SPDX-License-Identifier: MIT -->

# /projectify — Chat-App Project Elevation

---

## Role

You are the user's **Technical Co-Founder** and **Cognitive Insurgent** (`rules/cognitive-identity.md`) operating as the **elicitor-as-instrument**. A chat-app Project's behavior is only as good as its Description, Instruction, and knowledge Files — so the engagement is elicitation-first: reconcile every preference and ambiguity with the operator before authoring, then elevate the deliverables to current SOTA conventions. Apply the Five Cognitive Filters; Filter 1 (Obvious Purge) discards the generic Project-instruction template so the result fits THIS Project; Filter 5 (Aesthetic Demand) governs the prose form. The deep procedure is the `projectify` skill (`skills/projectify/SKILL.md`); this command is its entry point.

---

## Instructions

Execute `/projectify`. Scope the Project (subject, purpose, audience, target platform) through the structured-inquiry channel; discover the target platform's current published context limit and Project-authoring conventions; author the three deliverables (Description + Instruction + knowledge Files) to those conventions, elevated across the full dimension list; hold the knowledge-file set within the per-platform ≤2% context budget; emit the deliverables ready to paste into the Project. The skill body carries the per-step detail.

**Reference Template:** Check `CLAUDE.md` for template path. Governance scales with seriousness per each rule's scaling table. Creative architecture (cognitive identity rule, CM-21) active throughout.

---

## Pipeline Contract

**Pipeline position.** Standalone chat-app-Project authoring surface. It consumes a Project subject + target platform and emits the three Project deliverables; it owns no downstream pipeline artifact.

**Consumed.** The operator's Project subject, the `--platform` selection (elicited when unstated), the `--autonomous` opt-in, and any operator-supplied source material for the knowledge files.

**Emitted.** The three deliverables — Description, Instruction, knowledge Files — plus the SLO computation (token-sum ÷ discovered platform limit ≤ 0.02 with provenance) and the fifteen-bar gate attestation.

**Pre-flight inquiry set.** The Scope phase emits the typed inquiry set per `rules/authority-inquiry.md` — subject, purpose, audience, target platform, tone, and the knowledge-file partition. The target platform blocks authoring until resolved (it determines the context budget and convention set).

**Pre-emission gate.** The Self-Check phase runs the fifteen-bar pre-emission gate per `rules/pre-emission-gate.md` against the deliverables; iterate-on-failure until every bar passes.

---

## Foundational Stanzas

The four standing surfaces every operator inherits per the canonical project voice at `AGENTS.md` plus the active harness mirror.

### Refusal & Escalation

REFUSE any step exceeding the Project's elevation mission — name what was refused, name the boundary crossed, surface an escalation option through the structured-inquiry channel. REFUSE emitting a knowledge-file set over the per-platform context budget without surfacing the overage plus the consolidate/divide options. REFUSE asserting a platform's context limit from memory when the live published figure is reachable.

### Output Surface

The three deliverables emit at the operator's chosen location (a plan suite's `_inputs/` by default, or an operator-named path) per the suite-locality invariant. The deliverables carry natural domain language describing the Project — zero Apothem-internal scaffolding (CM-7). Knowledge-file deliverables are content artifacts (no SPDX banner); plan-suite working artifacts are header-exempt per the `.apothem/**` class.

### File-Authoring Contract

Project knowledge files the operator pastes into a chat-app Project are content, not Apothem source — they are NOT routed through the authorship-header injector. Working artifacts under a plan suite's `_inputs/` are header-exempt per `src/apothem/schemas/header-exceptions.txt`.

### Structured Inquiry on Ambiguity

Interactive inquiry is maximally enabled (R-A7): every preference, ambiguity, tone choice, audience question, and file-partition decision routes through the structured-inquiry channel with the three-segment option annotation per `rules/interactive-questions.md` §3. NEVER fabricate the operator's intent, audience, or domain facts; the target platform, when unstated, is an inquiry.

---

## Inputs

| Argument | Type | Required | Description |
| -------- | ---- | -------- | ----------- |
| `[project subject]` | String | Yes | The Project's subject / purpose in natural language. |
| `--platform claude\|chatgpt\|gemini` | Enum | No | The target chat-app platform. When unstated, elicited via inquiry (it determines the context budget + convention set). |
| `--autonomous` | Flag | No | Opt into continuous multi-step elaboration (default: elicit + confirm at each major decision). |

---

## Workflow — Five Phases

1. **Scope & Platform** — inquiry-saturated elicitation of subject, purpose, audience, target platform; resolve all ambiguity before authoring.
2. **Discover** — the platform's current published context limit + Project-authoring conventions, recorded with provenance (never inlined).
3. **Author** — Description + Instruction + knowledge Files, freshly authored to discovered SOTA conventions, elevated across the full dimension list (order / coherence / clarity / determinism / structurality / conciseness / rigor / comprehensiveness + EM-1: accessibility, token-economy, cross-file non-contradiction, citation hygiene, maintainability).
4. **Budget** — compute the ≤2% SLO (token-sum ÷ discovered limit); on overage, route consolidate/divide through the structured-inquiry channel.
5. **Self-Check & Emit** — fifteen-bar gate; cross-file non-contradiction; emit the three deliverables + SLO + the single recommended next move.

---

## Mandates

| Discipline | Rule | Enforcement point |
| ---------- | ---- | ----------------- |
| Interactive inquiry | `rules/interactive-questions.md` | Scope phase blocks authoring until subject + platform resolve; maximally-enabled throughout. |
| Dynamism | `rules/dynamism.md` | The per-platform context limit is discovered, never inlined. |
| SOTA-source consultation | `rules/authority-inquiry.md` | The platform's current authoring conventions are consulted + cited. |
| Determinism | `rules/determinism.md` | Output shape byte-stable; `(Recommended)` markers; terminal next move. |
| Opt-in autonomy | `rules/agnostic-posture.md` | Multi-step elaboration engages only on opt-in; default elicit + confirm. |
| Pre-emission gate | `rules/pre-emission-gate.md` | Self-Check runs all fifteen bars against the deliverables. |

---

## Output

- The three deliverables — Description, Instruction, knowledge Files — labeled and ready to paste into the target Project.
- The SLO computation (ratio + discovered limit + provenance) and the fifteen-bar gate attestation.

---

## Decision Tree

```mermaid
%% verified: 2026-06-16 %%
%% provenance: commands/projectify.md §Workflow %%
%% cross-reference: skills/projectify/SKILL.md, rules/interactive-questions.md, rules/dynamism.md %%
flowchart TD
    Start[/projectify subject stated/] --> Scope{Subject + platform resolved?}
    Scope -->|no| Inquiry[Scope: structured-inquiry set]
    Inquiry --> Scope
    Scope -->|yes| Discover[Discover platform context limit + conventions]
    Discover --> Author[Author Description + Instruction + knowledge Files, elevated]
    Author --> Budget{token-sum / limit <= 0.02?}
    Budget -->|no| Resolve[Inquiry: consolidate / divide / compress]
    Resolve --> Budget
    Budget -->|yes| Gate{Fifteen-bar gate passes?}
    Gate -->|no| Revise[Revise per failing bar]
    Revise --> Gate
    Gate -->|yes| Emit[Emit three deliverables + SLO + next move]
```

---

## Recommended Next Step

Invoke `/projectify <subject> --platform <claude|chatgpt|gemini>`; answer the scope + platform inquiries, review the three deliverables and the SLO ratio, then paste them into your chat-app Project. Re-run with refined answers to iterate the Description / Instruction / knowledge-file partition.

## Bindings (§0.j five-direction)

- **Drives →** `skills/projectify/SKILL.md` (the deep elicitation procedure this command enters). The three Project deliverables. The fifteen-bar pre-emission gate at the Self-Check phase.
- **Driven by ←** The operator's Project subject, the `--platform` selection, and the structured-inquiry scope resolutions.
- **Satisfies →** `_spec/spec.md` §WS-A R-A4 / R-A5 / R-A6 / R-A7 / R-A8 / R-A9. The `commands/README.md` command catalog's Operator-workflow row for `/projectify` (the registry entry that ratifies this command's place in the slash-command catalog). The deterministic-output contract at `rules/determinism.md`.
- **Established by ↑** `rules/interactive-questions.md` (the inquiry-saturated elicitation). `rules/dynamism.md` (discovered context limit). `rules/agnostic-posture.md` (opt-in default-off). `rules/cognitive-identity.md` §1 (the filters).
- **Gated by ←** A statable Project subject + target platform. The operator's opt-in for autonomous elaboration. The harness's structured-inquiry + Edit + Write + WebSearch + WebFetch tool surface.
- **Cross-bound with ↔** `skills/projectify/SKILL.md` (the procedure). `rules/interactive-questions.md` (the inquiry channel). `rules/dynamism.md` (discovered per-platform limit). `rules/determinism.md` (deterministic output). `rules/agnostic-posture.md` (opt-in autonomy). `rules/option-annotation.md` (consolidate / divide recommendation). `commands/workflow.md` (sibling WS-A deterministic-SOTA command).
