---
name: "sota-elevation"
description: "SOTA elevation as default posture for OSS distribution projects — every user-facing surface targets the upper bound of contemporary best-practice, calibrated against named exemplar projects (cpython, shadcn-ui, Bun, Fumadocs, vite, vitest) and audited across the eight SOTA evaluation surfaces."
pathFilter: "**/README.md, **/docs/**, **/.github/**, **/site/**"
alwaysApply: false
paths:
  - "**/README.md"
  - "**/docs/**"
  - "**/.github/**"
  - "**/site/**"
---

<!-- SPDX-License-Identifier: MIT -->

# Rule: SOTA Elevation — Default Posture for OSS Distribution Projects

## What this rule enforces

For every OSS distribution project apothem touches, the default posture is **State-Of-The-Art elevation**: every user-facing surface targets the **upper bound** of contemporary best-practice, not the median. "Good enough" is non-conformant when MAXIMAL is reachable. The operator's `MAXIMAL` descriptor in a directive signals escalation to the upper-bound interpretation; absent it, SOTA remains the floor, not a ceiling-on-request. The discipline calibrates against **named, currently-shipping OSS exemplars** — never folklore or "industry standard" appeals without a concrete source.

## Pre-conditions

Applies whenever the artifact under change belongs to an **OSS distribution project** — one that publishes to a public registry (npm, crates.io, Maven Central) or maintains a public documentation site, README, or release surface. It does not apply to internal dev-tool harnesses or private artifacts; the CM-7 codebase-vs-process-tooling distinction governs that split. Trivial-scope edits per the trivial-vs-non-trivial threshold still honor the SOTA floor on the surfaces they touch.

## Required behaviour

### 1. Eight SOTA Evaluation Surfaces (Companion Sub-Rule Anchor)

Every user-facing change MUST be audited across eight surfaces: (1) README modernization, (2) visibility surfaces, (3) supply-chain producer-pipeline, (4) CI/CD modernization, (5) test rigor, (6) packaging / type-safety, (7) observability, (8) docs SOTA. A change landing one surface without the others is partial-SOTA, not SOTA. Full per-surface specification at `rules/sota-elevation-exemplars.md` §1.

### 2. Named-Exemplar Discipline (Companion Sub-Rule Anchor)

Every SOTA citation MUST name a **currently-shipping** exemplar project as concrete-driver class 6 per `rules/interactive-questions-canonical-shapes.md` §3.2.1. Canonical exemplars: **cpython** (workflow naming, release rigor), **shadcn-ui** (README header, dark-mode aesthetic), **Bun** (performance-first landing, OG cards), **Fumadocs** (docs IA, dedicated landing), **vite** (clean IA), **vitest** (behavior-named tests). Citations like "industry standard" without naming a specific project are non-conformant per `rules/interactive-questions-canonical-shapes.md` §3.2.2. Full per-exemplar walks at `rules/sota-elevation-exemplars.md` §2.

### 3. Upper-Bound Calibration & Filter-5 Binding (Companion Sub-Rule Anchor)

A `MAXIMAL` directive (or synonyms) escalates the calibration ladder at `rules/expertise-posture-elements.md` §2 to the architectural-rework rung. Production-ready is the floor `rules/production-ready-prs.md` enforces; SOTA-elevation lifts the ceiling. SOTA is the outward projection of cognitive-identity Filter 5 (aesthetic demand) per `rules/cognitive-identity-techniques.md` §1 — passing every mechanical bar without conceptual elegance is not yet SOTA. Full bindings at `rules/sota-elevation-exemplars.md` §§3–4.

### 4. Gap-Surfacing

When the host's current state falls short of SOTA on any of the eight surfaces, the gap MUST be surfaced as a finding per `rules/authority-inquiry.md` with options annotated per `rules/option-annotation.md` — never silently entrenched. The recommended-option rationale cites a concrete exemplar from §2.

## Disclosure surface (Companion Sub-Rule Anchor)

Outcomes recorded per `rules/disclosure-ledger.md` using `[SOTA — elevated: …]`, `[SOTA — gap-surfaced: …]`, `[SOTA — floor-honored: …]` markers. Full schemas at `rules/sota-elevation-exemplars.md` §6.

## Failure tells (Companion Sub-Rule Anchor)

Partial-SOTA emissions, exemplar-less citations, `MAXIMAL` directives answered with mid-tier output, silently-entrenched gaps, aesthetic dismissal where Filter 5 has not been applied. Full enumeration at `rules/sota-elevation-exemplars.md` §7.
