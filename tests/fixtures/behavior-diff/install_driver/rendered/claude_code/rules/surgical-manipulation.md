---
name: "surgical-manipulation"
description: "Every mutation of an existing artifact is surgical — a precise, minimal, anchor-bounded or managed-block edit that touches only the span the change requires, never a blunt whole-file overwrite where a scoped edit suffices, and never a strip of a surrounding banner or unrelated content. The mutation produces a minimal diff attested against the host's green conformity baseline (the golden-corpus invariant). The surgical-edit + reactive-guard mechanism is the surgical-guard skill."
pathFilter: "**/*.py, **/*.md, **/*.mdx, **/*.json, **/*.yaml, **/*.yml, **/*.toml, **/*.sh, **/*.ps1, **/*.ts, **/*.js, **/*.mjs, **/*.css, **/*.mdc"
alwaysApply: false
paths:
  - "**/*.py"
  - "**/*.md"
  - "**/*.mdx"
  - "**/*.json"
  - "**/*.yaml"
  - "**/*.yml"
  - "**/*.toml"
  - "**/*.sh"
  - "**/*.ps1"
  - "**/*.ts"
  - "**/*.js"
  - "**/*.mjs"
  - "**/*.css"
  - "**/*.mdc"
---

<!-- SPDX-License-Identifier: MIT -->

# Rule: Surgical Manipulation — Minimal, Anchor-Bounded Mutation

## What this rule enforces

Every mutation of an **existing** artifact MUST be **surgical**: a precise, minimal edit scoped to an anchor — a managed-block sentinel region, a contiguous span, or the smallest range the change requires. It MUST NOT be a blunt whole-file overwrite where a scoped edit suffices, and MUST NOT strip a surrounding authorship banner or unrelated content. The diff is minimal — only the lines the change requires move — and is attested against the host's green conformity baseline: the **minimal-diff golden-corpus invariant** (a surgical edit that leaves every gate green). The cohort mandates this discipline; its operating mechanism — surgical edit plus a reactive post-edit quality guard — is the `surgical-guard` skill.

## Pre-conditions

Applies whenever an existing artifact is mutated (an Edit, an in-place rewrite, a managed-block refresh). It does NOT apply to green-field file creation (no existing content to preserve) — that is authoring, governed by `rules/clean-room-generation.md`. Trivial-scope single-line edits inherit the discipline at the touch site (preserve surroundings) without further ceremony.

## Required behavior

### 1. Anchor before mutate

Locate the precise mutation site first (locate-before-read): a sentinel-delimited managed block, an anchor-bounded span, or the smallest contiguous range the change needs. Read only that range plus a tight buffer. The anchor is the scope contract — the edit touches it and nothing outside it.

### 2. Minimal diff

Apply the change as the smallest diff that satisfies it. Everything outside the anchor MUST stay byte-for-byte unchanged — including the SPDX authorship banner, surrounding comments, and unrelated declarations. A whole-file overwrite where an anchor-bounded edit suffices is non-conformant; a managed-block refresh replaces only the sentinel-delimited content, never the boundaries.

### 3. Golden-corpus attestation

After the mutation, the host's conformity gate MUST be green and the diff minimal — the golden-corpus invariant. A mutation that turns a gate red, or sweeps far beyond its stated scope, fails the invariant and is reduced to its surgical minimum before acceptance.

### 4. Reactive guard

Non-trivial mutations MUST be reviewed reactively (a diff pass) for the systematic failure modes of generated changes — swallowed errors, hollow tests, docs-vs-code drift — via the `surgical-guard` skill before the change is accepted.

## Failure tells

A whole-file overwrite where a three-line anchor-bounded edit would suffice. A diff that strips or relocates the SPDX banner during an unrelated change. A managed-block edit that rewrites the sentinel boundaries instead of the enclosed content. A mutation that sweeps unrelated lines into its diff. A change accepted while a conformity gate it touched is red (golden-corpus breach).

## Bindings (§0.j five-direction)

- **Drives →** Every mutation of an existing artifact across the host (anchor-bounded minimal diff). The minimal-diff golden-corpus attestation on every non-trivial change. The reactive post-edit guard pass.
- **Driven by ←** The WS-E surgical-manipulation mandate; the harness installation discipline's managed-block (`sentinel_merge`) convention.
- **Gated by ←** The Pre-conditions scope test: an existing artifact is mutated; green-field creation is governed by `rules/clean-room-generation.md` instead. The frontmatter `pathFilter` (source, docs, and configuration file types). The managed-block sentinels (`sentinel_merge`) that bound an installer's writes inside a shared file.
- **Satisfies →** The MAXIMAL golden-corpus end-state (internally consistent, minimally-diffed, gate-conformant).
- **Established by ↑** `skills/surgical-guard/SKILL.md` (the surgical-edit + reactive-guard mechanism this rule mandates); the harness-installation managed-block discipline.
- **Cross-bound with ↔** `skills/surgical-guard/SKILL.md` (the mechanism). `rules/code-craft-python.md` + sibling code-craft rules (scoped, atomic refactoring is the per-language form of surgical mutation). `rules/interactive-questions.md` (§6 — destructive mutations route per-file through the canonical destructive-op floor). `rules/clean-room-generation.md` (governs green-field authoring; this rule governs mutation of existing artifacts). `rules/pre-emission-gate.md` (the golden-corpus attestation is verified at the gate). `rules/refactoring-discipline.md` (a refactor's edits are surgical, anchor-bounded mutations).
