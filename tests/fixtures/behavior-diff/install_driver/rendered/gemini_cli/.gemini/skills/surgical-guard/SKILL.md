---
name: "surgical-guard"
version: "0.1.0"
updated: "2026-06-14"
description: "Surgical-edit + reactive-guard skill — matched when the operator asks to 'edit surgically', 'make a minimal diff', 'guard this change', 'review the diff for quality', 'don't rewrite the whole file', or otherwise needs a precise, anchor-bounded mutation plus a post-edit quality pass before it lands. Stage 1 is a minimal-diff editing discipline: mutate through a managed-block or anchor-bounded edit (e.g. swap only the sentinel-delimited region, preserving the surrounding bytes and the authorship banner) — never a blunt whole-file overwrite where a scoped edit suffices. Stage 2 is a reactive, diff-based quality guard that reviews only the change's diff and loads only the rule references the diff's context matches (progressive disclosure), catching the systematic failure modes of generated changes: clean-code (swallowed errors, hardcoded success returns, hallucinated APIs, premature abstraction, silent contract changes), test (mock-boundary violations, duplicate bodies, hollow assertions, missing coverage of the changed behavior), docs (hallucinated symbols, broken samples, docs-vs-code drift). Not for: green-field file creation with no existing content to preserve (below the surgical threshold — routes to ordinary authoring); domain-framework linting with vendor-specific rule packs (out of scope — only the generalized clean-code/test/docs guard pattern is carried); producing the change's content via debugging or TDD (routes to dev-toolkit — this skill governs how the change lands and whether it passes). Harness-agnostic; deterministic output. Feeds the harness-directive surgical-manipulation mandate."
archetype: "guard-template"
userInvocable: true
argument-hint: "[change target] [--guard clean-code|test|docs|all]"
disable-model-invocation: true
allowed-tools: "Read, Write, Edit, Glob, Grep, Bash, TodoWrite"
---

<!-- SPDX-License-Identifier: MIT -->

## Purpose

Land a change as a **precise, minimal, scoped mutation**, then **guard it reactively** before it is accepted. Two stages, one contract:

1. **Surgical edit** — mutate through a managed block (sentinel-delimited region swapped, boundaries preserved) or an anchor-bounded edit, touching only the lines the change requires. Everything outside the anchor stays byte-for-byte identical, including the authorship banner. A blunt whole-file overwrite where a scoped edit suffices is refused.
2. **Reactive guard** — a diff-based post-edit review that loads only the rule references the change's context matches (progressive disclosure) and catches the systematic failure modes of generated changes — swallowed errors, hollow tests, docs-vs-code drift — before the change is accepted.

The pairing is the skill's robustness: the change is **both** surgically minimal **and** quality-attested. This skill supplies the surgical-manipulation discipline the harness directives mandate.

## Detection Signal

The operator asks to edit surgically, make a minimal diff, or not rewrite a whole file; asks to guard or review a change for quality; or hands off a mutation that should land scoped and attested rather than sweeping.

**Falsifiable counter-signal.** A green-field file creation with no existing content to preserve is below the surgical threshold — it routes to ordinary authoring, not this skill.

## Non-Goals

A deliberately narrow surface. The skill is NOT:

- **A whole-file rewriter.** Where a scoped, anchor-bounded edit satisfies the change, a blunt whole-file overwrite is refused — minimality is the contract.
- **A domain-framework linter.** The source guard set carried framework-specific rule packs (a particular CMS / e-commerce platform); apothem generalizes the *guard pattern* (clean-code / test / docs) and does **not** carry those domain-specific packs — they are out of scope.
- **A writing-time constraint engine.** The guard is a **reactive** post-edit diff pass, not a constraint that bloats every edit as it is written — the change is made, then guarded.
- **The engineering-loop owner.** Producing the change's *content* (debugging, TDD, slicing) routes to `skills/dev-toolkit/SKILL.md`; this skill governs *how the change lands* (minimal diff) and *whether it passes* (the guard).

## Foundational Stanzas

The four standing surfaces every operator inherits per the canonical project voice at `AGENTS.md` plus the active harness mirror.

### Refusal & Escalation

REFUSE a whole-file overwrite where an anchor-bounded edit suffices — name the minimal alternative and apply it. REFUSE accepting a change the guard flags (swallowed error, hollow assertion, docs drift) without surfacing the finding — name it, never silently pass. REFUSE any request beyond surgical editing + reactive guarding; surface an escalation option through the structured-inquiry channel per `rules/interactive-questions.md`.

### Output Surface

Changes land at their domain-natural host locations per `rules/host-discovery.md` as minimal diffs; the guard report lands beside the change or in the working trace. Per `rules/operational-mandates.md` CM-7, the change and its commit carry natural domain language — zero process-internal scaffolding.

### File-Authoring Contract

Edits preserve any existing authorship banner — the surgical discipline never strips a header (corner case B of the header-inject-guard hook at `hooks/messages/pretooluse-{write,edit}-header-guard.md`). New files route through `scripts/inject-header.{sh,py}`; exempt classes at `src/apothem/schemas/header-exceptions.txt`.

### Structured Inquiry on Ambiguity

When the change's anchor / scope, the managed-block boundary, or a guard finding's disposition is ambiguous, route the resolution through the structured-inquiry channel with the three-segment option annotation per `rules/interactive-questions.md` §3 (rationale / recommendation / default-pointer). Every destructive operation (deletion, move, non-retaining overwrite) routes per-file through the §6 canonical destructive-op option sets — one invocation per file, every option's `default-pointer:` carrying the verbatim `no-default: user decision required`.

## Conformity Posture

**Discover-don't-assume preamble (M1).** Discover the host's managed-block / anchor convention (sentinel markers, comment-delimited regions) and its diff + review tooling per `rules/host-discovery.md`. The surgical anchor scheme is the host's, discovered — never imposed.

**Minimal-diff attestation.** The change's diff is attested against the golden corpus (the host's green-gate baseline): a surgical edit that leaves the gates green is the minimal-diff golden-corpus contract this skill establishes and that the surgical-manipulation harness directive depends on.

## Procedure

Four numbered, independently-verifiable steps. The change's *content* is supplied upstream; this procedure governs *how it lands and whether it passes*.

### 1. Locate the Anchor

Locate the precise mutation site — a managed-block sentinel region, an anchor-bounded span, or the smallest contiguous range the change requires. Read only that range plus a tight buffer (locate-before-read per `rules/large-file-reading.md`). The anchor is the scope contract: the edit touches it and nothing else.

### 2. Mutate Surgically

Apply the change as a minimal diff at the anchor — a managed-block replacement (sentinel-delimited content swapped, boundaries preserved) or an anchor-bounded edit. Preserve everything outside the anchor byte-for-byte, including the authorship banner. No whole-file overwrite where a scoped edit suffices.

### 3. Reactive Guard (diff-based, progressive-disclosure)

Review the change's **diff** — not the whole file — against the guard set selected by `--guard` (default `all`), loading only the rule references the diff's context matches:

- **clean-code guard** — swallowed / catch-all errors, hardcoded success returns, hallucinated APIs, premature abstraction, silent contract changes.
- **test guard** — mock-boundary violations, duplicate test bodies, hollow assertions, missing coverage of the changed behavior.
- **docs guard** — hallucinated symbols, broken samples, docs-vs-code drift introduced by the change.

Each finding is surfaced with its offending diff locus. An accepted change carries no surviving guard finding — or each finding is explicitly dispositioned by the operator through the structured-inquiry channel.

### 4. Attest & Self-Check

Attest the minimal-diff golden-corpus contract: the change is scoped, the gates are green, the guard is clear. Run the fifteen-bar pre-emission gate per `rules/pre-emission-gate.md`. Emit the change, the guard report, and the single recommended next move.

## Arguments

- `[change target]` — the change to land, in natural language (the behavior to mutate, the anchor it touches).
- `--guard clean-code|test|docs|all` — the reactive guard set (default: `all`).

## Return Contract

The skill returns:

- **Minimal diff** — scoped to the anchor; everything outside it byte-identical.
- **Guard report** — per-guard findings with diff loci, or a clean attestation.
- **Minimal-diff golden-corpus attestation** — scope + green gates.
- **Fifteen-bar gate attestation** per `rules/pre-emission-gate.md`.
- A single `## Recommended Next Step`.

Deterministic per `rules/determinism.md`: the same change target + anchor yields the same minimal diff.

## Recommended Next Step

**Invoke the `surgical-guard` skill via the Skill tool** with `<change> --guard all` — apply the change as a managed-block / anchor-bounded minimal diff, then review the guard report and disposition any finding before accepting. Route the change's *content* (the debugging / TDD that produced it) through the `dev-toolkit` skill, and keep this skill for *how the change lands and whether it passes*.

## Bindings (§0.j five-direction)

- **Drives →** ● Every surgical (minimal-diff, anchor-bounded) mutation across the host. ● The reactive diff-based quality guard on every guarded change. ● **The surgical-manipulation discipline the harness directives weave in** (this skill is its mechanism).
- **Satisfies →** ● `CLAUDE.md` Source Layout row "surgical-guard" (skills/ class). ● The elevation dimension **robustness** (minimal-diff editing + reactive diff-based guard with progressive-disclosure rule loading).
- **Established by ↑** ● `CLAUDE.md` Source Layout (skills/ folder-with-`SKILL.md` class). ● `CLAUDE.md` Ambiguity Handling (structured inquiry over fabrication). ● `rules/own-voice-reimplementation.md` (zero-verbatim; `reference-token-grep` = 0). ● `rules/agnostic-posture.md` (17-harness agnostic floor).
- **Gated by ←** ● The host's discovered managed-block / anchor convention + diff tooling. ● The minimal-diff contract (no whole-file overwrite where a scoped edit suffices). ● The host's structured-inquiry + Edit + Write + Bash tool surface; the per-file destructive-op floor.
- **Cross-bound with ↔** ↔ `skills/dev-toolkit/SKILL.md` (produces the change's content; this skill governs how it lands + whether it passes). ↔ `rules/own-voice-reimplementation.md` + `rules/agnostic-posture.md` (own-voice + agnostic floors). ↔ `rules/interactive-questions.md` (§6 destructive-op floor). ↔ `skills/diagram-authoring/SKILL.md` + `skills/document-authoring/SKILL.md` (sibling own-voice authoring skills).
