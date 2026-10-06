---
trigger: glob
description: "Rewrite protocol for token-efficient content — re-derives prose to a minimal surface while preserving L2 substantive semantics and L3 structural / load-bearing anchors; pairs with token-budget-discipline (sizing) and clean-room-generation §3 (re-writing protocol)."
globs: "**/rules/**, **/commands/**, **/skills/**, **/agents/**, **/docs/**"
---

<!-- SPDX-License-Identifier: MIT -->

# Rule: Token-Efficiency Rewrite Protocol

## Purpose

Token-efficiency is a rewrite discipline, not a one-shot compression. Where prose carries surplus tokens — filler, restatement, throat-clearing, paraphrase of the literal — the rewrite re-derives it to a minimal surface that preserves what matters and discards what does not. Operationalises the operator-ratified token-efficiency mandate alongside `rules/token-budget-discipline.md` (sizes the always-on tier) and `rules/clean-room-generation.md` §3 (the canonical re-writing protocol).

## Obligations

### 1. The Two Preservation Tiers

Every rewrite preserves two tiers:

- **L2 — Substantive semantic content.** Every claim, contract, directive, condition, threshold, citation, and observable fact the prose asserts. L2 is carried forward verbatim in **meaning**; expression MAY differ.
- **L3 — Structural / load-bearing anchors.** Section headings the ecosystem cites; rule names; mandate identifiers (M-N / CM-N); `(Companion Sub-Rule Anchor)` pointer lines; cross-reference paths; binding-block reciprocal pointers; frontmatter; header.

L2 + L3 are the invariant surface. Anything outside them is **L1 prose scaffolding** — eligible for compression.

### 2. The Rewrite Discipline (Companion Sub-Rule Anchor)

The rewrite proceeds: extract L2 + L3 → discard L1 → re-derive minimal prose carrying L2 verbatim and L3 byte-identical → verify regression. Full protocol with worked examples, L1 elimination classes, and per-class compression heuristics lives at the path-filtered companion. (Companion Sub-Rule Anchor) See `rules/token-efficiency-rewrite-protocol.md`.

### 3. Anchor-Preservation Invariant

Every L3 anchor in the pre-rewrite artifact MUST appear byte-identical in the post-rewrite artifact. A renamed heading, a deleted section anchor, a dropped `(Companion Sub-Rule Anchor)` pointer, a removed mandate-identifier — each is a structural failure on the same axis as a half-edge per `rules/bidirectional-binding.md` §2. The matcher `conformity/token_efficiency_grep.py` diffs L3 anchors pre / post and FAILs on any drift.

### 4. Semantic-Regression Gate

Every directive, contract, condition, and threshold from the pre-rewrite artifact MUST survive into the post-rewrite artifact. The rewrite MUST NOT soften a directive (`must` → `should`), remove a condition, drop a threshold, or elide a citation. The regression gate at `rules/clean-room-generation.md` §3.5 applies in full; this rule extends it to the token-efficiency class with explicit L2 enumeration.

### 5. Same-Change Discipline

A rewrite ships in one change-set: the rewritten prose AND the L3-anchor diff (mechanical zero-drift) AND the L2-preservation attestation (per `rules/pre-emission-gate.md`). Splitting rewrite from regression-verification across commits leaves the artifact in a non-conformant transient state.

### 6. When Not to Rewrite

The rewrite is **inapplicable** (a no-op; the artifact passes the gate as-is) to:

- prose already minimal under the token-budget ceiling;
- L1-rich prose authored for didactic purposes (tutorials, worked examples whose teaching value depends on the scaffold);
- aspirational or quoted material whose source-fidelity invariant forbids re-derivation.

## Seriousness Scaling

| Level | Enforcement |
|-------|-------------|
| EXPLORING | Advisory; rewrites authored on explicit operator request |
| PERSONAL_USE | Rewrite mandatory on over-budget always-on rules; L3 anchor-diff zero-drift verified |
| SHARED | Full discipline; semantic-regression gate runs on every rewrite |
| PUBLIC_LAUNCH | Full enforcement; matcher exit-non-zero blocks emission |

## Anti-Patterns

- **DON'T** drop a section heading the ecosystem cites — **BECAUSE** L3 anchors are reciprocal-binding surfaces; their loss orphans every back-pointer.
- **DON'T** soften a `must` to a `should` to save a token — **BECAUSE** L2 directive strength is invariant under rewrite.
- **DON'T** collapse a closed enumeration to "etc." — **BECAUSE** exhaustiveness is L2 per `rules/definitiveness.md` §2; the closure is the contract.
- **DON'T** rewrite a tutorial's worked example to its bullet-form summary — **BECAUSE** the scaffold is the teaching surface, not L1 noise.

## Enforcement

Always-on at every seriousness level, scaling per the table above. Canonical specification for the token-efficiency rewrite protocol; pairs with `rules/token-budget-discipline.md` (sizing) and `rules/clean-room-generation.md` §3 (re-writing).

## Bindings (§0.j five-direction)

- **Drives →** Every token-efficiency rewrite across `rules/`, `commands/`, `skills/`, `agents/`, `docs/`; the mechanical matcher at `conformity/token_efficiency_grep.py`; the L3 anchor-diff zero-drift verification at every rewrite emission; the L2-preservation attestation at every rewrite's gate row.
- **Satisfies →** The token-efficiency rewrite directive; `CLAUDE.md` rules-registry row "Token-Efficiency Rewrite"; the ecosystem's always-on token-efficiency posture.
- **Established by ↑** The operator-ratified token-efficiency mandate and the precedent re-writing protocol at `rules/clean-room-generation.md` §3.
- **Gated by ←** The `pathFilter` authored-content globs (demand-loaded on rules / commands / skills / agents / docs edits); the PreToolUse Write/Edit hook entries that wire `conformity/token_efficiency_grep.py`.
- **Cross-bound with ↔** `rules/clean-room-generation.md` §3 (re-writing protocol; this rule is the token-efficiency specialisation of §3 with L2 / L3 tiers made explicit); `rules/token-budget-discipline.md` (sizing pair — that rule caps; this rule rewrites to fit the cap); `rules/large-file-generation.md` (CM-23 write-side incremental-append budget protocol; this rule complements at the read-side / always-on rewrite tier); `rules/pre-emission-gate.md` (bar inspection of L3 anchor-diff zero-drift and L2-preservation attestation); `rules/bidirectional-binding.md` §2 (L3 anchor loss is a half-edge failure on the same axis); `rules/definitiveness.md` (M8 — closed-enumeration exhaustiveness is L2 invariant); `rules/token-efficiency-rewrite-protocol.md` (path-filtered companion carrying the full protocol, L1 elimination classes, worked examples); `conformity/token_efficiency_grep.py` (the mechanical matcher).
