---
name: "systemic-participation"
description: "Every artifact apothem introduces into a host project joins the host as a systemic participant — declares its upstream / downstream / peers / enforcers; honors sibling conventions; lands at the host's canonical layout; updates the host's index registries in the same change. Silos (self-contained artifacts diverging from sibling conventions) and orphans (artifacts with no consumer / no index entry / no producer attribution) are structural failures, not aesthetic preferences."
pathFilter: "**/CLAUDE.md, **/AGENTS.md, **/rules/**/*.md, **/commands/**/*.md, **/skills/**/*.md, **/agents/**/*.md, **/hooks/**/*.md, **/output-styles/**/*.md, **/__init__.py, **/CONTRIBUTING.md, **/CODEOWNERS, **/migrations/**, **/.github/**"
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
  - "**/__init__.py"
  - "**/CONTRIBUTING.md"
  - "**/CODEOWNERS"
  - "**/migrations/**"
  - "**/.github/**"
---

<!-- SPDX-License-Identifier: MIT -->

# Rule: Ecosystem Systemicity in the Host Project — No Orphans, No Silos

## What this rule enforces

This rule binds **M14 — Ecosystem Systemicity in the Host Project**. Every artifact the agent produces in a host project — module, test fixture, CI workflow, documentation page, script, manifest, configuration entry, schema, migration, deployment artifact — MUST **join the host as a systemic participant**: it declares its **upstream** (what triggers it), **downstream** (what consumes it), **peers** (siblings of the same kind), and **enforcers** (the host quality gates that govern it). Introduction is **complete in the same change-set** — host registries / indexes / TOCs / linkbacks update, the sibling convention is honored, no parallel-but-divergent function is left for the reader to find. A **silo** (self-contained artifact diverging from sibling conventions or duplicating existing function) and an **orphan** (no consumer, no index entry, no place in the reference graph) are structural failures, not aesthetic preferences.

## Pre-conditions

Applies in a host project that maintains a reference graph (a software project with imports, indexes, and registries) whenever apothem introduces a new component, modifies an existing component's systemic relations (rename, relocation, scope change), or removes one (retirement is the symmetric inverse); a plain chat, cowork, research, or writing session with no such graph is outside its scope. Trivial-scope edits per the trivial-vs-non-trivial threshold (≤ 5 lines AND no public-API change AND no behavioral shift) are exempt; the moment a change introduces a component or alters its place in the host's reference graph, the rule applies.

## Required behavior

### 1. The Four Systemic Relations

Every new component declares four relations — **upstream** (what triggers it), **downstream** (what consumes it), **peers** (siblings of its kind), **enforcers** (host gates governing it) — both inline in the artifact AND in the host's adjacent registry. (Companion Sub-Rule Anchor) See `rules/systemic-participation-relations.md` §1 for the full relations table.

### 2. Sibling-Convention Convergence

Every new component converges with its peers on naming, layout, frontmatter / header shape, and internal idioms. At three or more peers, the dominant observable convention is ratified; below that, the adopted choice is recorded in the disclosure ledger. (Companion Sub-Rule Anchor) See `rules/systemic-participation-relations.md` §2 for the convergence detail and threshold rule.

### 3. Index / Registry Update — Same-Change Discipline

Every new component updates the host's adjacent registries in the same change-set; a deferred index update leaves a transient orphan. (Companion Sub-Rule Anchor) See `rules/systemic-participation-relations.md` §3 for the per-class registry-update table (test file, documentation page, CI workflow, source module, configuration entry, schema / migration).

### 4. Orphan Prevention — The Three Orphan Classes

An orphan has no consumer, no index entry, or no producer attribution. This extends `rules/canonical-layout.md` §3 from multi-step work outputs to every new component. (Companion Sub-Rule Anchor) See `rules/systemic-participation-relations.md` §4 for the three-class catalog and the canonical-layout extension clause.

### 5. Silo Prevention — The Three Silo Classes

A silo exhibits convention divergence, functional duplication, or scope drift relative to host peers. Recovery (merge / refactor / split) lands in the same change-set as the introduction. (Companion Sub-Rule Anchor) See `rules/systemic-participation-relations.md` §5 for the three-class catalog and the recovery protocol.

### 6. Retirement Discipline — Symmetric to Introduction

When a component is removed, its upstream / downstream / peer / enforcer references are unwound in the same change-set; a persistent downstream reference is a broken-reference orphan. (Companion Sub-Rule Anchor) See `rules/systemic-participation-relations.md` §6 for the per-relation unwinding detail.

### 7. Cross-Component Reference Graph

The host's reference graph — the union of every component's four relations — carries connectivity, acyclicity-where-applicable, and density invariants. Every change preserves them or surfaces the change as a finding. (Companion Sub-Rule Anchor) See `rules/systemic-participation-relations.md` §7 for the three-invariant detail.

## Disclosure surface

Every systemic-participation declaration is recorded in the disclosure ledger per `rules/disclosure-ledger.md`:

- `[Systemic — introduced: <component-path>; class: <test | doc | workflow | module | config | schema>; upstream: <list>; downstream: <list>; peers: <list>; enforcers: <list>; index-entry: added at <registry-path>]` for every new-component introduction.
- `[Systemic — convergence: <component-path>; sibling-convention adopted: <convention>; sibling-source: <peer-files>]` for every sibling-convergence outcome.
- `[Systemic — silo-recovery: <component-path>; resolution: <merge | refactor | split>; original-divergence: <description>]` for every silo recovery.
- `[Systemic — orphan-recovery: <component-path>; resolution: <consumer-added | index-added | provenance-added | retired>]` for every orphan recovery.
- `[Systemic — retired: <component-path>; class: <test | doc | workflow | module | config | schema>; downstream-cleanup: <list-of-updated-references>]` for every component retirement.

## Failure tells

Sibling-convention drift; orphan introduction (no consumer / no index entry / no producer attribution); functional-duplication and scope-drift silos; broken-reference orphans from incomplete retirement; unjustified convention divergence in the ledger. (Companion Sub-Rule Anchor) See `rules/systemic-participation-relations.md` §§4–6 for the per-class diagnostic catalog.
