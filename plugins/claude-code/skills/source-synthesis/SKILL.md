---
name: "source-synthesis"
version: "0.1.0"
updated: "2026-06-22"
description: "Reconcile a fixed set of provided sources into one cited synthesis — matched when the user says 'synthesize these sources', 'combine these documents', 'reconcile these', 'what do these say together', 'merge these notes into one', or any phrasing that hands over N specific documents and asks for a single consolidated reading. Extracts the claim set per source with citation anchors, reconciles agreements and contradictions across sources, and produces a cited synthesis that separates consensus from contested ground while flagging coverage gaps. User-invocable directly via `--sources`; never gathers or discovers sources of its own (that is the `multi-source-research` surface), never adjudicates which source is correct against ground truth (a contradiction is reported as contested, not resolved by fiat), and never synthesizes fewer than two sources (a lone source is summarized, not synthesized)."
archetype: "research-template"
userInvocable: true
argument-hint: "[--sources GLOB_OR_PATHS]"
disable-model-invocation: true
allowed-tools: "Read, Write, Edit, Glob, Grep"
---

<!-- SPDX-License-Identifier: MIT -->

## Purpose

Reconcile a **fixed set of operator-provided sources** into one cited synthesis. The skill reads each named source, extracts its claim set with per-claim citation anchors, cross-references the claims to surface agreement and contradiction, and emits a single synthesis that separates what the sources **agree on** from what they **contest** — with every synthesized claim attributed to the source(s) that assert it.

The discipline that distinguishes synthesis from summary: synthesis is **relational**. It does not merely report what each source says; it places each claim in relation to the others — consensus, contradiction, or solitary assertion — so the reader sees not just the content but its evidentiary weight. Per-claim attribution is non-negotiable: an unattributed synthesized claim is indistinguishable from a fabrication.

## Detection Signal

The user provides specific documents and asks for a consolidated reading. Trigger phrases: "synthesize these sources", "combine these documents", "reconcile these", "what do these say together", "merge these notes into one". The defining marker: the source set is **given, not requested** — the user names the inputs and asks for the union, never for new material.

## Non-Goals

The skill carries a deliberately narrow surface. It is NOT:

- **Not source discovery.** The skill consumes the sources the operator provides via `--sources`. It does NOT search for additional documents, follow citations to new material, or fetch external references. Discovery of sources to synthesize is the `multi-source-research` surface; this skill begins where the source set is already fixed.
- **Not a fact-checker.** The skill reconciles what the sources say against each other; it does NOT adjudicate which source is correct against ground truth. A contradiction is reported as contested, not resolved by fiat. External verification is out of scope.
- **Not a summarizer of a single document.** Synthesis requires two or more sources to reconcile. A lone source is summarized, not synthesized; that request routes elsewhere.
- **Not a content generator.** Every synthesized claim traces to a source claim. The skill introduces no assertion the sources do not support; unsupported ground is flagged as a gap, never filled.

## Workflow

Five ordered steps. Each step's output exists and is checkable before the next runs — the **Criterion** gates the advance.

1. **Resolve the source set.** Expand `--sources` (glob or explicit paths) to a concrete file list and read each source. **Criterion:** the resolved list holds **two or more** sources and every path read successfully. A missing or unreadable source STOPs the workflow and surfaces the gap; a resolved set of fewer than two routes to single-source summary, not synthesis (per Non-Goals).

2. **Extract the claim set per source.** For each source, enumerate its distinct claims and attach a **citation anchor** to each — source path plus the locating heading, line range, or quoted span — so a reader can verify the claim at its origin. **Criterion:** every source has a claim list, and every claim carries an anchor that resolves back to its source.

3. **Reconcile across sources.** Cross-reference the per-source claim sets. Cluster claims by **subject**; within each cluster, assign exactly one relation:
   - **Agreement** — two or more sources assert the same claim.
   - **Contradiction** — sources assert mutually incompatible claims about the same subject.
   - **Singleton** — one source only asserts the claim.

   **Criterion:** every claim lands in exactly one subject cluster with exactly one assigned relation — no claim is unclassified, none double-counted.

4. **Produce the cited synthesis.** Emit the consolidated reading with consensus and contested ground **visibly separated**: a **Consensus** section (agreed claims, citing every asserting source) and a **Contested** section (each contradiction, citing each side's source and conflicting anchors). **Criterion:** no synthesized claim lacks attribution; consensus and contested ground are structurally distinct, never blended into a single narrative that hides which ground is settled.

5. **Flag gaps.** Name the subjects the source set leaves uncovered, the singleton claims (unconfirmed by a second source), and the contradictions left unresolved. **Criterion:** a Gaps section exists — even when its content is the single word "none" — so the reader always knows the boundary of what the sources can settle.

## Return Contract

A cited synthesis with four labeled sections, in order:

- **Consensus** — claims asserted by two or more sources, each citing every agreeing source.
- **Contested** — contradictions across sources, each side attributed to its source with the conflicting anchors.
- **Singletons** — claims a single source asserts, marked **unconfirmed**.
- **Gaps** — subjects the source set leaves uncovered plus contradictions left unresolved (`none` when empty).

**Per-claim source attribution is mandatory.** A synthesized claim with no source anchor is a contract failure — it is the failure mode this skill exists to prevent, because an unattributed claim cannot be distinguished from invented material.

## Foundational Stanzas

### Refusal & Escalation

REFUSE any request that pushes the skill past its mission — discovering new sources, fact-checking against external ground truth, summarizing a single document, or generating claims the sources do not support. Refusal is explicit: name what was refused, name the mission boundary the request crossed, and route the operator to the correct surface via the structured-inquiry channel per `rules/interactive-questions.md` (canonical channel; three-segment option annotation; never free-form prose as primary input). When `--sources` resolves to fewer than two sources, REFUSE the synthesis and surface the single-source-summary boundary instead.

### Output Surface

The synthesis writes to STDOUT for direct invocation. When the operator requests a durable artifact, it lands at the operator-named path under the host project per `rules/host-discovery.md`; per `rules/operational-mandates.md` CM-7, the artifact carries natural domain language with zero plan-internal references. NEVER write to a global-ecosystem location and NEVER fabricate a source path the operator did not provide.

### File-Authoring Contract

When the skill emits a NEW file, it routes through `scripts/inject-header.py` so the canonical authorship header is injected at the head; the injector is idempotent and detects the filetype variant from the byte-exact fixture at `src/apothem/schemas/authorship-header.txt`. Exempt classes are enumerated at `src/apothem/schemas/header-exceptions.txt`. Edits to existing files preserve any present header.

### Structured Inquiry on Ambiguity

When the skill reaches a decision in any of the seven authoritative-data categories per `rules/authority-inquiry.md` — identity, scope direction, preference, security, naming of public surfaces, infrastructure endpoints, version pins — and the input is silent, route the resolution through the structured-inquiry channel with the three-segment option annotation per `rules/interactive-questions.md` §3 (rationale / recommendation / default-pointer). Free-form prose questions as primary input are forbidden. NEVER fabricate authoritative data. Clean-room discipline per `rules/clean-room-generation.md` governs the synthesis prose: it is re-derived from the extracted claim sets, never paraphrased from a single source's framing.

## Recommended Next Step

**Run the skill against the resolved source set** with `--sources` naming the documents to reconcile; review the Contested and Gaps sections first, since they name the claims the source set cannot settle on its own.

## Bindings (§0.j five-direction)

- **Drives →** ● Every per-source claim extraction with citation anchors. ● Every cross-source reconciliation pass separating consensus from contested ground. ● The Gaps surface naming uncovered subjects and unresolved contradictions.
- **Satisfies →** ● `CLAUDE.md` Source Layout row "source-synthesis" (skills/ class). ● The research cohort's provided-source reconciliation surface.
- **Established by ↑** ● `CLAUDE.md` Source Layout (skills/ class declaration with the folder-with-`SKILL.md` convention). ● `CLAUDE.md` Ambiguity Handling (structured inquiry over fabrication).
- **Gated by ←** ● The harness's Read tool surface. ● The presence of two or more resolvable sources in `--sources` (a single source routes to summary, not synthesis).
- **Cross-bound with ↔** ↔ `rules/clean-room-generation.md` (the synthesis is re-derived, not paraphrased). ↔ `rules/interactive-questions.md` (the structured-inquiry channel on ambiguity). ↔ `skills/plan-suite/SKILL.md` + `skills/ecosystem-audit/SKILL.md` (sibling skills under the same registry section).
