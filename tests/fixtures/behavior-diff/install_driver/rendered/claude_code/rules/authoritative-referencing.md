---
name: "authoritative-referencing"
description: "Every claim, argument, hypothesis, and asserted fact cites an authoritative, official, current source — the scattered referencing discipline (ten-dimension dim 9, sota named-exemplar, disclosure-ledger rationale, output-style citations) consolidated by reference; folklore and 'industry standard' appeals are non-conformant."
pathFilter: "**/docs/**, **/site/**, **/README.md, **/research/**, **/manuscript/**, **/paper/**, **/literature/**, **/*.bib, **/*.tex"
alwaysApply: false
paths:
  - "**/docs/**"
  - "**/site/**"
  - "**/README.md"
  - "**/research/**"
  - "**/manuscript/**"
  - "**/paper/**"
  - "**/literature/**"
  - "**/*.bib"
  - "**/*.tex"
---

<!-- SPDX-License-Identifier: MIT -->

# Rule: Authoritative Referencing — Cite the Source, Never Folklore

## Purpose

Make the referencing bar one standing mandate, not a discipline scattered across four homes. Every claim, argument, hypothesis, or asserted fact the ecosystem emits MUST rest on an authoritative, official, current source — cited, not assumed. This rule consolidates the discipline by reference; it does not restate the per-home detail (per the de-duplication mandate).

## Obligations

### 1. Every claim carries a source

A claim, argument, hypothesis, or asserted fact of meaningful scope MUST cite its source: an official specification, vendor documentation, a primary standard (RFC / ISO / W3C), peer-reviewed work, a named currently-shipping project, or the host's own ratified source of truth at file:line. An assertion with no citable source MUST be surfaced as an open question, never stated as settled.

(Companion Sub-Rule Anchor) See `rules/authoritative-referencing-quotation.md` for how much of a cited source may be reproduced — paraphrase by default with attribution, quote sparingly and briefly, and give no legal or fair-use opinion.

### 2. Authoritative, official, current

The cited source MUST be **authoritative** (the primary owner of the fact, not a downstream paraphrase), **official** (the vendor / standards body / maintainer, not an aggregator), and **current** (the in-force version, not a superseded edition). Source-trust ranking and reachability are governed by `rules/source-accessibility.md`.

### 3. Consolidate by reference, not restatement

Each per-surface referencing home keeps its single authoritative form and is cited, never duplicated. (Companion Sub-Rule Anchor) See `rules/authoritative-referencing-homes.md` §1 for the four homes — `rules/ten-dimension-check.md` dimension 9, `rules/sota-elevation.md` §2, `rules/disclosure-ledger.md`, and `output-styles/default.md` §Citations.

### 4. No folklore

Folklore, hearsay, "best practice" without a named owner, "industry standard", "everyone knows", and consensus-appeal phrasings are non-conformant. A claim is grounded in a citable source or it is reframed as an open question.

### 5. When to consult a live source

Reach for a live source when a fact may have shifted since training or its current status is unknown — a version, release, price, or API surface. Skip it for timeless or definitional facts. Obligation 2 governs *which* source; this governs *when*.

### 6. Evidence provenance

(Companion Sub-Rule Anchor) See `rules/authoritative-referencing-provenance.md` §1–§6 for the access and status labels, the literature search record, the empty-search limit on novelty claims, the conditions check on cited results, the discriminating-check bar, and the model-written-reading limit.

(Companion Sub-Rule Anchor) See `rules/authoritative-referencing-assurance.md` §1–§6 for the checks a research claim needs beyond its source — a proof's assumptions and weakest step, the meaning of each status label, a number's binding to its run, the closest prior work behind a novelty claim, the tool-and-model use statement, and a gate fixed before results are seen.

## Seriousness Scaling

(Companion Sub-Rule Anchor) See `rules/authoritative-referencing-homes.md` §2 for the four-level enforcement table (EXPLORING cite-load-bearing → PUBLIC_LAUNCH every-public-claim-cited, superseded-sources-refreshed).

## Enforcement

Applies at every seriousness level, scaling per the table above. Referencing is checked as dimension 9 of the pre-emission gate's ten-dimension bar (`rules/ten-dimension-check.md`); this rule is its outward-projected standing mandate, not a second matcher.

## Failure tells

(Companion Sub-Rule Anchor) See `rules/authoritative-referencing-homes.md` §3 for the enumeration — no-citable-source claim, folklore authority, aggregator over primary owner, superseded edition cited as current, SOTA citation with no named exemplar.
