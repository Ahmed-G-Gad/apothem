---
name: "refactor-extract"
version: "0.1.0"
updated: "2026-10-02"
description: "Scoped behavior-preserving extraction refactor — matched when the user asks to 'extract this', 'extract this function', 'pull this out into its own module', 'clean up this module', 'refactor this', 'split this function', 'break this apart', or any phrasing that asks for a structural extraction of an existing symbol or file while preserving observable behavior. Performs behavioral extraction of what the code DOES, clean-room re-derivation from the extracted specification, quality elevation against a named deficiency, and regression verification that behavior is preserved. NOT for behavior changes (changed inputs / outputs / side effects / error behavior route back as a feature-change finding), whole-file rewrites (the clean-room barrier binds the named target only), or building a test suite as the deliverable. User-invocable directly with an optional target symbol or file — the interactive skill counterpart to the dispatched `refactor-surgeon` agent."
archetype: "refactor-template"
userInvocable: true
argument-hint: "[--target SYMBOL_OR_FILE]"
disable-model-invocation: true
allowed-tools: "Read, Glob, Grep"
---

<!-- SPDX-License-Identifier: MIT -->

## Purpose

Perform a scoped, behavior-preserving extraction refactor on an existing symbol or file. The skill extracts what the code observably DOES into a specification, re-derives the implementation **clean-room** from that specification, elevates quality against a **named deficiency**, and verifies the original behavioral contracts hold. Scope matches the change: extract and re-derive the named target, never the surrounding unchanged code.

The invariant that makes this an extraction and not a rewrite: the original's observable behavior — its inputs, outputs, side effects, error behavior, edge cases — is the contract the new code MUST honor byte-for-byte at the boundary. Quality rises; behavior does not move.

## Detection Signal

The user asks for a structural extraction of an existing symbol or file while preserving observable behavior. Trigger phrases: "extract this", "extract this function", "pull this out into its own module", "clean up this module", "refactor this", "split this function", "break this apart". The `--target` argument names the symbol or file when supplied; absent it, the skill resolves the target from the active selection or the user's prose and **confirms the resolved target before proceeding** — an extraction against the wrong target is worse than no extraction.

## Non-Goals

The skill carries a deliberately narrow surface. It is NOT:

- **Not a behavior-changing refactor.** The extraction preserves every observable contract. A request that changes inputs, outputs, side effects, or error behavior is OUT of scope and routes back to the user as a finding — that is a feature change, not an extraction.
- **Not a whole-file rewrite.** The clean-room barrier applies to the named target only. Unchanged code in the same artifact is preserved verbatim; the skill never re-derives code it was not asked to touch.
- **Not a test author.** The skill verifies existing behavioral contracts. Where no tests exist, the skill writes behavioral assertions to capture the contract before re-derivation, but it does not build a test suite as a deliverable.
- **Not a formatter pass.** Pure formatting normalization is a carve-out auto-decision, not an extraction refactor. The skill applies the host's ratified formatter to its own output but does not present formatting as the refactor.

## Workflow

Five ordered steps, each operationalizing a clause of the Re-Writing Protocol at `rules/clean-room-generation.md` §3. Step N's criterion gates step N+1.

1. **Resolve and bound the target.** Confirm the named symbol or file. Use `Grep` to locate **every** call site and `Glob` to map siblings of the target's kind (so the extracted unit lands where its peers live). Bound the extraction to the named target and enumerate the unchanged code that stays verbatim. **Criterion:** the target is confirmed, the call-site set is complete, and the verbatim-unchanged boundary is explicit.

2. **Extract behavioral specification (§3.1).** Read the target and record what it observably DOES — inputs, outputs, contracts, invariants, side effects, edge cases, error behavior. This extracted behavior **IS** the specification for re-derivation. Where no tests exist, write the behavioral assertions (input → output contracts) that pin the specification before any code moves. **Criterion:** every observable behavior is captured; nothing the original does is left undescribed.

3. **Re-derive clean-room from the specification (§3.3).** Treat the extracted specification as the **sole** input and re-derive the unit fresh — never edit the original implementation in place. The re-derivation is a fresh creation that happens to preserve behavior, not a cosmetic transformation of the original text. **Criterion:** the new unit is derived from the specification, not transcribed from the original; the clean-room barrier held.

4. **Elevate quality against a named deficiency (§3.4).** Name the **specific** deficiency in the original — a leaky abstraction, a god function, primitive obsession, a missing domain type, a tangled dependency — and state how the re-derivation addresses it. A re-derivation that only rephrases the original (rename, reorder, reformat) is non-conformant: the extraction must improve at least one named dimension. **Criterion:** the deficiency is named and the improvement is demonstrable.

5. **Verify behavior preserved (§3.5).** Run the host's tests (or the step-2 behavioral assertions) via `Bash` and confirm every contract from step 2 holds. Update every call site found in step 1 to the extracted unit and re-run. **A contract that no longer holds BLOCKS the refactor until repaired** — a passing extraction with one broken contract is a regression, not a refactor. **Criterion:** the full test surface is green AND every step-2 contract is confirmed preserved.

## Return Contract

Maximum response: 500 tokens unless the invoker requests a higher budget. Structure:

- **Summary:** one sentence naming the target extracted and the deficiency addressed.
- **Extraction:** the new file or symbol path, the call sites updated, and the unchanged code left verbatim.
- **Verification:** the test command run and its result; the behavioral contracts confirmed preserved.
- **Surfaced gaps:** adjacent gaps surfaced during extraction (M6); empty when none.

## Foundational Stanzas

### Refusal & Escalation

REFUSE any request that asks the skill to act outside its extraction mission — behavior changes, whole-file rewrites, test-suite authoring, feature additions. Refusal is explicit: name what was refused, name the mission boundary the request crossed, and route the user back through the structured-inquiry channel per `rules/interactive-questions.md` (canonical channel; three-segment option annotation; never free-form prose as primary input). When step 5 verification cannot confirm behavior preservation, STOP — do not present an unverified extraction as complete.

### Output Surface

The skill edits codebase artifacts at their domain-natural locations under the host project per `rules/host-discovery.md`. The extracted unit lands at the host's sibling-convention location for its kind. Per `rules/operational-mandates.md` CM-7, the extracted code carries natural domain language and zero plan-internal references. NEVER write a plan-suite artifact from this skill; planning state is out of this skill's surface.

### File-Authoring Contract

Every NEW codebase file the extraction creates routes through `scripts/inject-header.py` so the canonical authorship-header banner is injected at the head; the injector is idempotent and detects the filetype variant automatically from the byte-exact fixture at `src/apothem/schemas/authorship-header.txt`. Exempt classes (LICENSE, JSON configuration files, lockfiles, generated assets, vendored trees, `.audit/` ephemera, `.apothem/plans/` ephemera, `.keep` / `.gitkeep` markers, binary files) are enumerated at `src/apothem/schemas/header-exceptions.txt`. Edits to existing files preserve any existing banner.

### Structured Inquiry on Ambiguity

When the extraction reaches a decision in any authoritative-data category per `rules/authority-inquiry.md` — naming of the extracted public surface, target scope direction, the host's preferred module boundary — and the host is silent, route the resolution through the structured-inquiry channel with the three-segment option annotation per `rules/interactive-questions.md` §3 (rationale / recommendation / default-pointer). Free-form prose questions as primary input are forbidden. NEVER fabricate authoritative data. Every delete / rename / move of an existing file during extraction routes through the structured-inquiry channel on a per-file basis per `rules/interactive-questions.md` §6 — one invocation per file, no batching, every option's `default-pointer:` carries the verbatim `no-default: user decision required` marker.

## Recommended Next Step

**Run the host's full test suite against the extracted unit and its updated call sites** to confirm the behavioral contracts from step 2 hold before the change leaves the working tree.

## Bindings (§0.j five-direction)

- **Drives →** ● Every extraction refactor's clean-room re-derivation of the named target. ● Every call-site update for the extracted unit. ● The behavioral-contract verification at step 5.
- **Satisfies →** ● `CLAUDE.md` Source Layout row "refactor-extract" (skills/ class). ● The behavior-preserving extraction mission for the developer cohort.
- **Established by ↑** ● `CLAUDE.md` Source Layout (skills/ folder-with-`SKILL.md` convention). ● `CLAUDE.md` Ambiguity Handling (structured inquiry over fabrication). ● `rules/clean-room-generation.md` §3 (the re-writing protocol this skill operationalizes).
- **Gated by ←** ● The harness's Read / Write / Edit / Glob / Grep / Bash tool surface. ● The presence of a resolvable target symbol or file (the skill confirms the target before proceeding).
- **Cross-bound with ↔** ↔ `rules/clean-room-generation.md` (§3 Re-Writing Protocol — behavioral extraction, clean-room barrier, quality elevation, regression gate). ↔ `rules/interactive-questions.md` (structured-inquiry channel for target naming and per-file destructive ops). ↔ `rules/host-discovery.md` (M1 — sibling-convention location for the extracted unit). ↔ `rules/operational-mandates.md` (CM-7 — natural domain language in extracted code). ↔ `skills/plan-suite/SKILL.md` + `skills/ecosystem-audit/SKILL.md` (sibling skills under the same registry section). ↔ `agents/refactor-surgeon.md` (the dispatched agent counterpart of this interactive skill; same extract, re-derive, verify contract on one named target).
