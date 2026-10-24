---
name: "authoritative-referencing-quotation"
description: "Quotation-ceiling / paraphrase-default companion to authoritative-referencing — paraphrase a cited source by default with attribution; quote sparingly and briefly (a short excerpt, never a full third-party work); attribute the source without offering a legal or fair-use opinion. Path-filtered to prose surfaces where source material is reproduced."
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

# Rule: Authoritative Referencing — Quotation Ceiling & Paraphrase Default (Companion Sub-Rule)

## Purpose

Govern *how much* of a cited source is reproduced once `rules/authoritative-referencing.md` has decided the source is authoritative and worth citing. The parent rule binds *which* source a claim rests on and *when* to reach for a live one; this companion binds the reproduction form: paraphrase by default, quote sparingly, never copy a whole third-party work, and attribute without judging the legality of the reproduction. Path-filtered: it loads on prose surfaces — docs / site / README / research manuscripts — where source material is most likely reproduced.

## Obligations

### 1. Paraphrase by default, with attribution

The default reproduction form is a **paraphrase** of the source's content in apothem's own words, carrying an attribution to the source (a link, footnote, or inline citation per `rules/code-craft-markdown.md` §6). A paraphrase preserves the source's meaning; it does not preserve the source's wording. Reproducing a source's exact phrasing where a paraphrase would carry the same meaning is non-conformant.

### 2. Quote sparingly and briefly

A direct quotation is reserved for the case where the source's exact wording is itself load-bearing — a definition under audit, a contract clause, a phrase whose precise form is the subject. A further named case makes the short quotation **required, not optional**: a policy, security-advisory, or deprecation claim whose exact wording a remediation is **acted on or gated by** (a fix applied, a version pinned, a gate held open or closed on the strength of the source's own text) MUST carry a short exact quotation with attribution at the point the claim is relied on, so the acted-on wording is inspectable rather than laundered through a paraphrase. When a quotation is used:

- it is a **short excerpt** — the smallest span that carries the load-bearing wording, not a paragraph where a sentence suffices;
- it is **clearly marked as a quotation** (block quote, inline quotation marks, or fenced span) and visually distinct from apothem's own prose;
- it carries its **attribution** at the quotation site, never deferred.

A quotation longer than the load-bearing span, or used where a paraphrase would have carried the meaning, is non-conformant.

### 3. Never reproduce a full third-party work

A full third-party work — an entire article, page, chapter, file, specification section run end to end, or any reproduction that substitutes for accessing the source itself — MUST NOT be reproduced. When a reader needs the whole source, the citation links to the source so the reader reaches the original; apothem reproduces only the load-bearing excerpt and points to the rest.

### 4. Attribute without a legal opinion

Attribution names the source so the reader can reach it and credits its author or owner. Attribution does **not** assert that the reproduction is lawful, fair use, permitted, or licensed — apothem is not the arbiter of that question. A reproduction is kept within the §1–§3 ceiling (paraphrase-default, brief-quotation, no-full-work) so the question rarely arises; where a reproduction's scope is genuinely in doubt, the doubt is surfaced as an open question per `rules/authority-inquiry.md`, never resolved with a self-issued legal conclusion.

## Failure tells

A source's exact phrasing reproduced where a paraphrase would carry the same meaning (default-paraphrase skipped). A multi-paragraph block quote where a one-sentence excerpt is load-bearing (over-quotation). A quotation with no attribution at its site (uncredited reproduction). A full article, page, or file reproduced inline instead of linked (whole-work reproduction). A reproduction defended with a self-issued "this is fair use" / "this is permitted" claim (legal opinion offered where attribution was the obligation). A paraphrase that drops the source attribution (uncredited paraphrase — the parent rule's no-folklore failure tell).
