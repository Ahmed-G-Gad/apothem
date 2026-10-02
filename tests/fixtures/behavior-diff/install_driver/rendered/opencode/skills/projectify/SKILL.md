---
name: "projectify"
version: "0.1.0"
updated: "2026-10-02"
description: "Chat-app Project elevation skill — matched when the operator asks to 'projectify', 'build a Project', 'set up a Custom GPT / Gem', 'write Project instructions', 'rewrite my Project', or otherwise hands off a chat-app Project (Claude Project / ChatGPT Custom GPT / Gemini Gem) to be freshly authored or elevated to current SOTA conventions. Emits the three deliverables a Project carries — Description, Instruction, knowledge Files — through an inquiry-saturated elicitation that reconciles every preference and ambiguity with the operator before committing, elevated across order / coherence / clarity / determinism / structurality / conciseness / rigor / comprehensiveness and beyond. Holds the knowledge-file set within a measurable per-platform context budget (token-sum / platform-limit <= 0.02, the limit discovered live and never inlined), with the grant to consolidate or divide files through the inquiry channel. Installs agnostically across all harnesses; the deliverables target the chat-app Project. Deterministic output; multi-step autonomy is opt-in / confirmation-gated. NOT for authoring coding-harness rules / skills / commands / hooks (route to the ecosystem authoring paths), and NOT a hardcoded-limit calculator (the per-platform limit is discovered live, never inlined)."
archetype: "elicitation-template"
userInvocable: true
argument-hint: "[project subject] [--platform claude|chatgpt|gemini] [--autonomous]"
disable-model-invocation: true
allowed-tools: "Read, Glob, Grep, WebSearch, TodoWrite"
---

<!-- SPDX-License-Identifier: MIT -->

## Purpose

Freshly author or elevate a chat-app Project to current SOTA conventions, emitting the three deliverables a Project carries — its **Description**, its **Instruction**, and its **knowledge Files** — through an inquiry-saturated elicitation that reconciles every preference and ambiguity with the operator before it commits.

The skill installs agnostically across apothem's harnesses; the artifact it produces targets the operator's chat-app Project (Claude Project, ChatGPT Custom GPT / Project, Gemini Gem, or the platform the operator names). Knowledge files are held within a measurable per-platform context budget, and the operator may have files consolidated or divided as the material warrants.

## Detection Signal

Triggers when the operator asks to "projectify", "build a Project", "set up a Custom GPT" / "make a Gem", "write Project instructions", "rewrite / elevate my Project", or otherwise hands off a chat-app Project's Description / Instruction / knowledge-file surface to be authored or elevated. A request to author a coding-harness rule, skill, or command is a different surface — that routes to the ecosystem's authoring paths, not here.

## Non-Goals

- **Not a harness config author.** It produces chat-app Project deliverables, not apothem rules / skills / commands / hooks. The two surfaces are distinct — a Project's Instruction is consumed by a chat assistant, not a harness's config surface.
- **Not a hardcoded-limit calculator.** The per-platform context limit is **discovered** from the platform's current published documentation at runtime per `rules/dynamism.md`, never inlined as a static number that rots when the platform changes its limit.
- **Not a silent file-restructurer.** Consolidating or dividing knowledge files is granted but routes through the structured-inquiry channel — the operator ratifies the file partition.
- **Not a default-on autonomy switch.** Multi-step elaboration engages under opt-in per `rules/agnostic-posture.md`; a clean invocation elicits and confirms.

## Foundational Stanzas

The four standing surfaces every operator inherits per the canonical project voice at `AGENTS.md` plus the active harness mirror.

### Refusal & Escalation

REFUSE any step exceeding the stated Project's elevation mission — name what was refused, name the boundary crossed, surface an escalation option through the structured-inquiry channel per `rules/interactive-questions.md`. REFUSE emitting a knowledge-file set that exceeds the per-platform context budget without surfacing the overage and the consolidate / divide options. REFUSE asserting a platform's context limit from memory when the live published figure is reachable.

### Output Surface

The three deliverables emit at the operator's chosen location (the consuming suite's `_inputs/` working surface by default, or an operator-named path) per the suite-locality invariant at `rules/context-management.md` §2.6.1. The Description and Instruction are prose deliverables; the knowledge Files are the operator's curated corpus. Per `rules/operational-mandates.md` CM-7, the deliverables carry natural domain language — they describe the Project's purpose, never apothem's internal scaffolding.

### File-Authoring Contract

Knowledge-file deliverables the operator pastes into a chat-app Project are content artifacts, not apothem source files — they are NOT routed through the authorship-header injector (a Project knowledge file carries no SPDX banner). When the skill emits a working artifact into a plan suite's `_inputs/`, that path is header-exempt per the `.apothem/plans/**` class at `src/apothem/schemas/header-exceptions.txt`.

### Structured Inquiry on Ambiguity

Interactive inquiry is **maximally enabled**: the elicitation surfaces every preference, ambiguity, scope question, tone choice, audience question, and file-partition decision through the structured-inquiry channel with the three-segment option annotation per `rules/interactive-questions.md` §3 (rationale / recommendation / default-pointer). NEVER fabricate the operator's intent, audience, or domain facts. The target platform, when unstated, is an inquiry — not a guess.

## Conformity Posture

**Discover-don't-assume preamble (M1).** The target platform's current published context limit, its Project-surface conventions (Description length norms, Instruction structure, knowledge-file format + count limits), and its current SOTA authoring guidance are **discovered** from the platform's live documentation per `rules/host-discovery.md`, recorded with provenance — never assumed from memory.

**Current-SOTA source-consultation mandate (M5).** Before authoring, consult the target platform's current official Project/GPT/Gem authoring documentation plus current SOTA prompt-and-instruction conventions per `rules/sota-elevation.md`; cite a retrievable pointer. An unsourced convention claim is downgraded or routed to inquiry per `rules/option-annotation.md`.

## Procedure

### 1. Scope & Platform (inquiry-saturated)

Elicit the Project's subject, purpose, audience, and target platform through the structured-inquiry channel. Resolve every ambiguity before authoring. When the platform is unstated, inquire (`--platform` or the channel) — it determines the context budget and the convention set. Record the scoped intent.

### 2. Discover the Platform Convention Set & Context Limit

Discover, from the platform's live documentation: the current published **context limit** (the denominator for the SLO), the Description and Instruction conventions, and the knowledge-file format / count / size limits. Record each with provenance. The limit is never inlined as a static number.

### 3. Author the Three Deliverables (elevated)

Author — freshly, to the discovered SOTA conventions — across the full elevation-dimension list:

- **order · structurality / organization · systemicity · flow · consolidation · conciseness** — the deliverables read as one coherently-ordered, non-redundant whole.
- **clarity · readability · understanding · ambient-induction · accessibility of instruction prose** — a first-time reader grasps the Project's behavior without re-reading.
- **certainty · determinism · rigor · solidity · integrity · cross-file non-contradiction** — the Instruction prescribes definitively; no two knowledge files contradict.
- **interoperability · suitability · professionalism · elaboration · comprehensiveness · in-depth · style · proofreading · SOTA-conventions adherence · citation hygiene · maintainability across edits** — the trailing dimensions are realized, not elided; the list extends comprehensively beyond these as the Project warrants.

Emit: **Description** (the Project's one-surface summary), **Instruction** (the behavioral contract), and the **knowledge Files** (the curated corpus).

### 4. Knowledge-File Context Budget (the ≤2% SLO)

Compute, per platform, the measurable SLO:

```
knowledge_file_token_sum / platform_context_limit  <=  0.02
```

The numerator is the token sum across every emitted knowledge file; the denominator is the platform's **discovered current published context limit** (Step 2), never a hardcoded constant. When the ratio exceeds 0.02, surface the overage and route the **consolidate / divide** decision through the structured-inquiry channel — compress, split, or drop low-value files per the operator's ratification. The SLO is a hard budget, not a soft expectation; the emitted set satisfies it, or the overage is an explicit operator decision.

### 5. Self-Check & Emit

Run the fifteen-bar pre-emission gate per `rules/pre-emission-gate.md` against the deliverables. Verify cross-file non-contradiction, the SLO, citation hygiene, and the elevation-dimension coverage. Emit the three deliverables ready for the operator to paste into the Project, with the single recommended next move.

## Autonomy Posture

Multi-step elaboration (e.g., authoring a large knowledge corpus across many files in one pass) engages under `--autonomous`, an explicit in-conversation opt-in, or the profile `enforcement` flag; the clean default elicits + confirms at each major decision. Opt-in, never default-on, per `rules/agnostic-posture.md`.

## Arguments

- `[project subject]` — the Project's subject / purpose in natural language.
- `--platform claude|chatgpt|gemini` — the target chat-app platform (when unstated, elicited via inquiry).
- `--autonomous` — opt into continuous multi-step elaboration (default: elicit + confirm).

## Return Contract

The three deliverables — **Description**, **Instruction**, **knowledge Files** — each labeled and ready to paste into the target Project, plus the SLO computation (ratio + discovered limit + provenance), the fifteen-bar gate attestation, and a single `## Recommended Next Step`. Output shape is byte-stable for identical inputs per `rules/determinism.md`; the discovered context limit (a date-sensitive external figure) is the declared non-deterministic element, stamped with its source and access date.

## Recommended Next Step

Invoke `/projectify <subject> --platform <claude|chatgpt|gemini>`; answer the scope + platform inquiries, then review the three deliverables and the SLO ratio before pasting them into your chat-app Project. Re-run with refined answers to iterate the Description / Instruction / knowledge-file partition.

## Bindings (§0.j five-direction)

- **Drives →** ● Every operator chat-app Project authored or elevated via `/projectify` (the skill is user-invocable). ● Every knowledge-file set held within the per-platform ≤2% context budget. ● Every file consolidate / divide decision routed through the structured-inquiry channel. ◐ The opt-in autonomy path for large-corpus elaboration.
- **Satisfies →** ● `CLAUDE.md` Source Layout row "projectify" (skills/ class). ● The deterministic-output contract at `rules/determinism.md`. ● The agnostic default-off posture at `rules/agnostic-posture.md`.
- **Established by ↑** ● `rules/interactive-questions.md` (the inquiry-saturated elicitation discipline). ● `rules/determinism.md` (the deterministic-output contract). ● `rules/dynamism.md` (the discovered, never-inlined context limit). ● `rules/agnostic-posture.md` (the opt-in default-off frame).
- **Gated by ←** ● The harness's structured-inquiry + Edit + Write + WebSearch + WebFetch tool surface. ● A statable Project subject + target platform. ● The operator's opt-in for autonomous elaboration.
- **Cross-bound with ↔** ↔ `commands/projectify.md` (the `/projectify` command entry point). ↔ `rules/interactive-questions.md` (the maximally-enabled inquiry channel). ↔ `rules/determinism.md` (deterministic output). ↔ `rules/dynamism.md` (discovered per-platform context limit). ↔ `rules/agnostic-posture.md` (opt-in autonomy). ↔ `rules/option-annotation.md` (consolidate / divide recommendation). ↔ `skills/workflow/SKILL.md` (sibling deterministic-SOTA orchestration skill).
