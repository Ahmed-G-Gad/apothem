---
name: "ten-dimension-check"
description: "Ten quality dimensions every host-project artifact passes before emission — rigor, coherence, configurability, readability, orphanism, structurality, architecture, naming, scholarly referencing, examples / tests / docs."
pathFilter: "**/CLAUDE.md, **/AGENTS.md, **/rules/**/*.md, **/commands/**/*.md, **/skills/**/*.md, **/agents/**/*.md, **/hooks/**/*.md, **/output-styles/**/*.md"
alwaysApply: false
paths:
  - "**/CLAUDE.md"
  - "**/AGENTS.md"
  - "**/rules/**/*.md"
  - "**/commands/**/*.md"
  - "**/skills/**/*.md"
  - "**/agents/**/*.md"
  - "**/hooks/**/*.md"
  - "**/output-styles/**/*.md"
---

<!-- SPDX-License-Identifier: MIT -->

# Rule: Ten Quality Dimensions

## What this rule enforces

This rule binds **M3 — The Ten Quality Dimensions Applied to Every Artifact**. Every artifact the ecosystem produces in a host project MUST be evaluated against ten quality dimensions, maximally meticulously, before emission. The check is a discrete pre-emission step (per `rules/pre-emission-gate.md`) recorded in the working trace — never implicit, never delegated downstream.

Multiple-dimension failure is **multiplicative, not additive**: an artifact that is stale AND orphan AND inconsistently named AND undocumented is a candidate for retraction, not repair.

## Pre-conditions

Applies to every host-project artifact above the trivial threshold per the trivial-vs-non-trivial threshold. Trivial work runs an abbreviated check covering dimensions 4 (readability), 5 (orphanism / staleness), and 8 (naming) only.

## Required behavior

### The Ten Dimensions (Companion Sub-Rule Anchor)

Every artifact MUST pass each dimension individually before emission. The ten dimensions, in canonical order:

1. Scientific rigor.
2. Consistency · Coherence · Integration · Validity.
3. Configurability · Irredundancy · Consolidation.
4. Readability · Intuition · Cleanness.
5. Orphanism · Staleness.
6. Structurality · Systemicity · Uniformity · Comprehensiveness.
7. Architecture.
8. Naming conventions & uniformity.
9. Scholarly / technical referencing.
10. Examples · Tests · Docstrings · Documentation.

(Companion Sub-Rule Anchor) See `rules/ten-dimension-check-dimensions.md` §The Ten Dimensions — Per-Dimension Bodies for the verbatim per-dimension bodies and per-dimension failure tells. The companion demand-loads on artifact-emission surfaces (Markdown, Python, shell, PowerShell under the rules / commands / skills / agents / docs trees and the root `CLAUDE.md`).

### Self-check at emission

Before emitting / committing / handing off, the ten-bar self-check is recorded in the working trace as part of the fifteen-bar pre-emission gate attestation per `rules/pre-emission-gate.md`. Each dimension MUST be marked `pass` or `n/a (with reason)` — never silent, never aspirational.

## Disclosure surface

A failed dimension is either fixed before emission (the standard path) or, when the failure is structural and exceeds the change's scope, surfaced via `rules/disclosure-ledger.md` as a `[Deferral — out-of-scope: dimension N — <description>; tracking: <where>]` marker. A deferred dimension MUST NOT carry a `pass` marking — it carries an explicit `defer` marking with the deferral's tracking location.

## Failure tells

Per-dimension failure tells live at the companion. Cross-cutting tells: a `pass` marking while a checked condition demonstrably fails (an **M4** self-application breach); an attestation block missing the ten-dimension entries; a dimension marked `n/a` without a reason; a `pass` recorded without corresponding evidence in the working trace; an artifact compounding multiple failed dimensions (stale + orphan + mis-named + undocumented) emitted as repaired rather than retracted.
