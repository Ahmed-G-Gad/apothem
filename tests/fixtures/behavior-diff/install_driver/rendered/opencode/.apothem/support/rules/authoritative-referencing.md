---
name: "authoritative-referencing"
description: "Every claim, argument, hypothesis, and asserted fact cites an authoritative, official, current source — the scattered referencing discipline (ten-dimension dim 9, sota named-exemplar, disclosure-ledger rationale, output-style citations) consolidated by reference; folklore and 'industry standard' appeals are non-conformant."
pathFilter: ""
alwaysApply: true
---

<!-- SPDX-License-Identifier: MIT -->

# Rule: Authoritative Referencing — Cite the Source, Never Folklore

## Purpose

Make the referencing bar one standing mandate, not a discipline scattered across four homes. Every claim, argument, hypothesis, or asserted fact the ecosystem emits MUST rest on an authoritative, official, current source — cited, not assumed. This rule consolidates the discipline by reference; it does not restate the per-home detail (per the de-duplication mandate).

## Obligations

### 1. Every claim carries a source

A claim, argument, hypothesis, or asserted fact of meaningful scope MUST cite its source: an official specification, vendor documentation, a primary standard (RFC / ISO / W3C), peer-reviewed work, a named currently-shipping project, or the host's own ratified source of truth at file:line. An assertion with no citable source MUST be surfaced as an open question, never stated as settled.

### 2. Authoritative, official, current

The cited source MUST be **authoritative** (the primary owner of the fact, not a downstream paraphrase), **official** (the vendor / standards body / maintainer, not an aggregator), and **current** (the in-force version, not a superseded edition). Source-trust ranking and reachability are governed by `rules/source-accessibility.md`.

### 3. Consolidate by reference, not restatement

Each per-surface referencing home keeps its single authoritative form and is cited, never duplicated. (Companion Sub-Rule Anchor) See `rules/authoritative-referencing-homes.md` §1 for the four homes — `rules/ten-dimension-check.md` dimension 9, `rules/sota-elevation.md` §2, `rules/disclosure-ledger.md`, and `output-styles/default.md` §Citations.

### 4. No folklore

Folklore, hearsay, "best practice" without a named owner, "industry standard", "everyone knows", and consensus-appeal phrasings are non-conformant. A claim is grounded in a citable source or it is reframed as an open question.

### 5. When to consult a live source

Reach for a live source when a fact may have shifted since training or its current status is unknown — a version, release, price, or API surface. Skip it for timeless or definitional facts. Obligation 2 governs *which* source; this governs *when*.

## Seriousness Scaling

(Companion Sub-Rule Anchor) See `rules/authoritative-referencing-homes.md` §2 for the four-level enforcement table (EXPLORING cite-load-bearing → PUBLIC_LAUNCH every-public-claim-cited, superseded-sources-refreshed).

## Enforcement

Always-on at every seriousness level, scaling per the table above. Referencing is checked as dimension 9 of the pre-emission gate's ten-dimension bar (`rules/ten-dimension-check.md`); this rule is its outward-projected standing mandate, not a second matcher.

## Failure tells

(Companion Sub-Rule Anchor) See `rules/authoritative-referencing-homes.md` §3 for the enumeration — no-citable-source claim, folklore authority, aggregator over primary owner, superseded edition cited as current, SOTA citation with no named exemplar.

## Bindings (§0.j five-direction)

- **Drives →** Every claim / argument / hypothesis / fact emission across every ecosystem surface; the citable-source requirement each carries before it is stated as settled.
- **Satisfies →** The standing-mandate end-state that no claim rests on folklore; the consolidation of the scattered referencing discipline into one cited home.
- **Established by ↑** The operator's standing-mandate set (the authoritative-referencing mandate — cite authoritative / official / current sources).
- **Gated by ←** `rules/source-accessibility.md` (the source-trust ranking and reachability decide WHICH source is cited); the meaningful-scope threshold (trivial edits cite only load-bearing claims).
- **Cross-bound with ↔** `rules/authoritative-referencing-homes.md` (path-filtered companion carrying the §3 per-surface referencing-home list, the §Seriousness-Scaling table, and the §Failure-tells enumeration); `rules/authoritative-referencing-quotation.md` (path-filtered companion — the quotation-ceiling / paraphrase-default reproduction form bounding *how much* of a cited source is reproduced); `rules/ten-dimension-check.md` (dimension 9 Scholarly / technical referencing — the per-artifact check this mandate outward-projects); `rules/sota-elevation.md` (§2 named-exemplar discipline — the no-"industry-standard" citation bar); `rules/disclosure-ledger.md` (M2 — the rationale-citation bar every ledger marker meets); `rules/source-accessibility.md` (the trust-outranks-accessibility ranking feeding obligation 2). ↔ `rules/source-accessibility-scaling-tells.md` (the trust-outranks-accessibility ranking decides which source the referencing mandate cites — the scaling calibrates how strictly).
