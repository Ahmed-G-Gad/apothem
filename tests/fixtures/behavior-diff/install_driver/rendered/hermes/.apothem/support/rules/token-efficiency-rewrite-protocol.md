---
name: "token-efficiency-rewrite-protocol"
description: "The full token-efficiency rewrite protocol the always-on parent rule references: the L1 prose-scaffolding elimination classes (filler / throat-clearing / restatement / hedge-padding / ceremonial-scaffolding / connective-bloat), the per-class compression heuristics, the extract-discard-re-derive-verify procedure, and worked before/after examples. Demand-loads when the assistant rewrites an authoring surface for token efficiency."
pathFilter: "**/*.md, **/*.mdx, **/rules/**, **/skills/**, **/commands/**, **/agents/**, **/docs/**"
alwaysApply: false
---

<!-- SPDX-License-Identifier: MIT -->

# Rule: Token-Efficiency Rewrite Protocol (Companion Sub-Rule)

## Purpose

Carry the operational detail the parent `rules/token-efficiency-rewrite.md` references at its §2 anchor: the L1 prose-scaffolding elimination classes, the per-class compression heuristics, the extract → discard → re-derive → verify procedure, and worked before/after examples. The parent retains the always-on directive (the two preservation tiers, the anchor-preservation invariant, the semantic-regression gate, the same-change discipline, the when-not-to-rewrite carve-out); this companion carries the protocol bodies. Path-filtered: it loads when the assistant rewrites an authoring surface (Markdown / rules / skills / commands / agents / docs) for token efficiency.

## Obligations

### 1. The Rewrite Procedure — Extract, Discard, Re-Derive, Verify

A token-efficiency rewrite proceeds in four ordered steps:

1. **Extract L2 + L3.** Enumerate the artifact's L2 substantive semantic content (every claim, contract, directive, condition, threshold, citation, observable fact) and its L3 structural anchors (headings the ecosystem cites, rule names, mandate identifiers, `(Companion Sub-Rule Anchor)` pointers, cross-reference paths, binding-block reciprocals, frontmatter, the SPDX banner). L2 + L3 is the invariant surface.
2. **Discard L1.** Everything outside L2 + L3 is L1 prose scaffolding — eligible for removal per the §2 classes.
3. **Re-derive minimal prose.** Re-author the artifact carrying L2 verbatim in meaning and L3 byte-identical, L1 removed. The re-derivation is a fresh minimal surface, not a cosmetic edit of the original, per `rules/clean-room-generation.md` §3.3.
4. **Verify regression.** Confirm every L2 directive / contract / condition / threshold / citation is preserved (the semantic-regression gate) and every L3 anchor appears byte-identical (the anchor-preservation invariant). A softened directive, a dropped condition, or a lost heading blocks the rewrite until repaired.

### 2. The L1 Elimination Classes

L1 prose scaffolding falls into six classes. Each is removable because its removal changes neither an L2 meaning nor an L3 anchor. (Token examples below are the rule's own subject matter — quoted, not authored, per the matcher self-citation exemption.)

- **L1.1 Filler / meta-commentary.** Sentences about the document itself rather than its content (`In this section we discuss …`, `It is important to note that …`, `As mentioned earlier …`). The framed content is L2; the frame is L1.
- **L1.2 Throat-clearing.** Opening sentences that delay substance (`Before diving in …`, `Let's begin by …`, `Without further ado …`). Replace with the substantive opening.
- **L1.3 Restatement.** A sentence re-stating the prior one in different words. Compress the pair to one.
- **L1.4 Hedge-padding.** Content-free qualifiers (`very`, `quite`, `somewhat`, `fairly`, `rather`, `kind of`). Delete the qualifier; the unqualified claim is stronger and shorter. (Distinct from the M8 binding-prescription hedging that is a definitiveness defect per `rules/definitiveness.md`; this is the no-information-padding subset.)
- **L1.5 Ceremonial scaffolding.** Announcer phrases before a self-evident structure (`Here are the steps:`, `The following list enumerates …`, `Consider the following table:`). The list / table is L2; the announcement is L1.
- **L1.6 Connective bloat.** Multi-word connectives with a one-word equivalent (`in order to` → `to`, `due to the fact that` → `because`, `at this point in time` → `now`, `in the event that` → `if`). Substitute the shorter form.

### 3. Per-Class Compression Heuristics

Each class resolves on one test: **does removing or compressing the span change an L2 meaning or an L3 anchor?** If no, remove or compress; if yes, the span is L2 / L3 and MUST be preserved.

- **L1.1 / L1.2 / L1.5** — delete the span outright; the substance it framed stands alone.
- **L1.3** — keep the clause with the more specific L2 content; delete its restatement.
- **L1.4** — delete the qualifier word; leave the claim.
- **L1.6** — substitute the one-word equivalent in place.

The heuristic is conservative: when removal is uncertain (the span may carry an L2 nuance), the span is preserved. Token-efficiency never trades a directive's meaning for a shorter surface.

### 4. Worked Examples

**Example A — filler + connective bloat (L1.1 + L1.6).**

- **Before:** "It is important to note that, in order to pass the gate, the artifact must carry a header." (18 words)
- **After:** "To pass the gate, the artifact must carry a header." (10 words)
- L2 preserved: the gate requires a header. L1 removed: the `It is important to note` frame; `in order to` → `to`.

**Example B — throat-clearing + restatement (L1.2 + L1.3).**

- **Before:** "Before we get into the specifics, let's establish the baseline. The baseline is the set of tests that pass before the change. In other words, the baseline is the pre-change passing tests." (32 words)
- **After:** "The baseline is the set of tests that pass before the change." (12 words)
- L2 preserved: the baseline definition. L1 removed: the throat-clearing opener and the `in other words` restatement.

**Example C — L3 anchor preserved under compression.**

- **Before:** "## Required behavior\n\nIt should be noted that the following section, namely the required-behavior section, mandates that every option carries a recommended marker."
- **After:** "## Required behavior\n\nEvery option carries a recommended marker."
- L3 preserved byte-identical: the `## Required behavior` heading (an anchor the ecosystem cites). L2 preserved: the option-marker mandate. L1 removed: the self-referential meta-commentary.

## Enforcement

Path-filtered (the seven glob patterns in this rule's `pathFilter` field — `**/*.md`, `**/*.mdx`, `**/rules/**`, `**/skills/**`, `**/commands/**`, `**/agents/**`, `**/docs/**`), demand-loaded companion to `rules/token-efficiency-rewrite.md`. The parent carries the always-on directive (two preservation tiers, anchor-preservation invariant, semantic-regression gate, same-change discipline, when-not-to-rewrite carve-out); this companion carries the four-step procedure, the six L1 elimination classes, the per-class compression heuristics, and the worked examples. The mechanical matcher at `conformity/token_efficiency_grep.py` operationalizes the L3 anchor-diff zero-drift check.

## Bindings (§0.j five-direction)

- **Drives →** Every token-efficiency rewrite's L1-elimination pass (the six §2 classes); the per-class compression decision (§3 heuristics); the four-step extract → discard → re-derive → verify procedure (§1).
- **Driven by ←** `rules/token-efficiency-rewrite.md` §2 (the parent's anchor to this companion's full protocol).
- **Gated by ←** The frontmatter `pathFilter` (Markdown and the authoring directories): the protocol loads only when an authoring surface is rewritten for token efficiency. The when-not-to-rewrite carve-out in the parent `rules/token-efficiency-rewrite.md` (a surface the parent exempts carries no protocol obligation). `conformity/token_efficiency_grep.py` (the advisory per-write filler and qualifier heuristic).
- **Satisfies →** The token-efficiency rewrite protocol's detail tier; the parent rule's promise that the full protocol, L1 elimination classes, and per-class compression heuristics live at the path-filtered companion.
- **Established by ↑** `rules/token-efficiency-rewrite.md` (parent-rule anchor); `rules/clean-room-generation.md` §3 / §5 (the re-writing and prose disciplines this protocol specializes for token efficiency).
- **Cross-bound with ↔** `rules/token-efficiency-rewrite.md` (parent rule; §2 anchor binds this companion). `rules/token-budget-discipline.md` (the always-on body sizing cap this rewrite fits content into). `rules/clean-room-generation.md` (§3 re-writing protocol + §5 prose discipline — L1 elimination is the token-efficiency projection of §5's sentence-level justification). `rules/definitiveness.md` (M8 — L1.4 hedge-padding is the no-information subset; binding-prescription hedging is the M8 defect). `rules/bidirectional-binding.md` (§2 — L3 anchor loss is a half-edge failure on the same axis). `conformity/token_efficiency_grep.py` (the mechanical matcher).
