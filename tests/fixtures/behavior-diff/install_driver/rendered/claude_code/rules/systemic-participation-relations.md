---
name: "systemic-participation-relations"
description: "Path-filtered companion rule carrying the operational detail of M14 systemic participation — the four systemic relations table, sibling-convention convergence detail, index/registry update table, the three orphan classes, the three silo classes, retirement discipline, and the cross-component reference graph invariant. Demand-loaded when the parent `systemic-participation.md` rule's anchors surface on host-project component touches."
pathFilter: "**/src/**, **/lib/**, **/tests/**, **/docs/**, **/.github/**, **/migrations/**, **/__init__.py, **/CONTRIBUTING.md, **/CODEOWNERS"
alwaysApply: false
paths:
  - "**/src/**"
  - "**/lib/**"
  - "**/tests/**"
  - "**/docs/**"
  - "**/.github/**"
  - "**/migrations/**"
  - "**/__init__.py"
  - "**/CONTRIBUTING.md"
  - "**/CODEOWNERS"
---

<!-- SPDX-License-Identifier: MIT -->

# Rule: Systemic-Participation Relations (Companion Sub-Rule)

## Purpose

Carry the operational detail of M14 systemic participation that the parent rule `rules/systemic-participation.md` anchors. The companion is path-filtered: it loads when the assistant edits any host-project component class (source modules, libraries, tests, documentation, CI workflows under `.github/`, migrations, package `__init__.py`, contribution surfaces). The parent rule retains the canonical directive paragraph, the pre-conditions, the disclosure surface, and the failure-tells catalog; this companion carries the seven sub-section bodies that operationalize the directive at the component-touch surface.

## Obligations

### 1. The Four Systemic Relations

Every newly-introduced component declares four relations:

| Relation | What it names | Why |
|---|---|---|
| **Upstream** | What triggers, depends on, or invokes this component | The reader can answer "what causes this to run / be loaded / be referenced?" |
| **Downstream** | What consumes this component's output / behavior / surface | The reader can answer "what would break if this were removed?" |
| **Peers** | Sibling components of the same kind (other tests, other docs, other workflows, other modules) | The reader can answer "what convention does this follow, and what conventions does it bind?" |
| **Enforcers** | Host quality gates that govern this component (CI workflows, linters, type-checkers, security scans, code review owners) | The reader can answer "what gates pass / fail when this changes?" |

The four relations MUST be declared in two places: inline in the artifact (header comment, frontmatter, or a dedicated `## Bindings` section per `rules/bidirectional-binding.md`) AND in the host's adjacent registry (the index file the host maintains for components of this kind).

### 2. Sibling-Convention Convergence

Every newly-introduced component **converges with its peers** on every observable convention:

- **Naming.** The component's filename, identifier, header, ID, slug match the peers' naming convention (kebab-case / snake_case / PascalCase / camelCase / etc.).
- **Layout.** The component's directory placement matches where the peers live. A new test under the host's tests directory; a new doc page under the host's docs directory; a new CI workflow under `.github/workflows/`.
- **Frontmatter / header / preamble.** When peers carry a frontmatter contract or a header-comment shape, the new component carries the same contract / shape with the same field set (host-discovered required fields per `rules/host-discovery.md`).
- **Internal idioms.** The component's body uses the same idioms its peers use — same fixture pattern in tests, same heading hierarchy in docs, same action-pinning policy in CI workflows, same import order in source files, same logging surface in scripts.

**Sibling-convergence threshold.** When the host has at least three peer components of the same kind, the dominant observable convention is the ratified convention; new components honor it. When the host has fewer than three peers, the observable conventions are advisory; the new component adopts one and the choice is recorded in the disclosure ledger so future siblings converge on the same.

### 3. Index / Registry Update — Same-Change Discipline

Every newly-introduced component updates the host's adjacent registries **in the same change-set**:

| Component class | Registry update |
|---|---|
| **Test file** | Picked up by the host's existing test discovery without configuration changes; if the host maintains an explicit test index (e.g., `tests/__init__.py`, `tests/index.json`, a `tox.ini` envlist), the new test is added |
| **Documentation page** | Listed in the host's TOC / nav / sidebar / index page; cross-linked from contextually-related pages with reciprocal links per `rules/bidirectional-binding.md` |
| **CI workflow** | If the host's `CONTRIBUTING.md` documents the CI section, the new workflow is mentioned; if the host has a workflow-index file, the new workflow is added |
| **Source module** | Added to the host's `__init__.py` / module index / package manifest so it is importable through the public API surface |
| **Configuration entry** | Documented in the configuration's reference page; default value declared; environment-variable mapping (where applicable) noted |
| **Schema / migration** | Indexed in the host's migration directory; numbered or timestamped per the host's convention; downstream-consumer code that depends on the new schema updated in the same change-set |

The same-change discipline forbids "I'll add the index entry in a follow-up": the follow-up never lands, the artifact persists as an orphan in the meantime, and orphans are structural failures.

### 4. Orphan Prevention — The Three Orphan Classes

An orphan is an artifact satisfying any one of the three conditions enumerated at `rules/canonical-layout.md` §3:

- **No consumer.** Nothing in the host's reference graph reads / imports / executes / links / references the artifact.
- **No index entry.** The artifact is not listed in the enclosing directory's index where the host maintains one.
- **No producer attribution.** The artifact carries no provenance — no frontmatter `provenance:` field, no header comment naming the producer, no record in the producer's report.

This rule extends the orphan-prevention discipline from `rules/canonical-layout.md` (which governs orphans within multi-step work session outputs) to **every** newly-introduced component in the host project (regardless of whether the component originated from multi-step work or a single-step touch).

### 5. Silo Prevention — The Three Silo Classes

A silo is a newly-introduced component satisfying any one of:

- **Convention divergence.** The component's observable conventions (naming, layout, frontmatter, internal idioms) diverge from peer components of the same kind without explicit justification.
- **Functional duplication.** The component performs a function the host already provides through an existing component, without explicit justification (e.g., a new utility function alongside an equivalent existing helper; a new test fixture alongside an equivalent existing fixture; a new doc page alongside an equivalent existing page).
- **Scope drift.** The component bundles concerns that belong to multiple existing components, blurring the host's existing scope boundaries (e.g., a new module mixing domain logic and infrastructure concerns; a new doc page combining tutorial and reference material).

Silo recovery: the silo is either (a) merged into the existing component it duplicates, (b) refactored to converge with peer conventions, or (c) split along the host's existing scope boundaries. Recovery happens in the same change-set as the silo's introduction; deferred recovery leaves the host's reference graph in a divergent state.

### 6. Retirement Discipline — Symmetric to Introduction

When apothem removes a component, the four relations are unwound:

- **Upstream.** Triggers / dependencies that point at the removed component are updated or removed in the same change-set. A CI workflow's `runs-on` reference to a removed runner; a configuration entry's reference to a removed environment variable.
- **Downstream.** Consumers that depend on the removed component are updated or removed in the same change-set. Code that imports the removed module; documentation pages that link to the removed page.
- **Peers.** Sibling components that share registry entries with the removed component update their entries (e.g., a `__init__.py` that exported the removed module).
- **Enforcers.** CI workflows / linters that referenced the removed component's path-filter or surface are updated. Removed-component-related warnings are deleted from the warning suppression list.

The retirement is **complete** at the change-set boundary. A removed component whose downstream references persist is itself a finding (broken-reference orphan).

### 7. Cross-Component Reference Graph

The host's reference graph is the union of every component's four relations:

- **Connectivity.** Every component is reachable from at least one entry point (the host's main entry, the host's documentation root, the host's CI configuration). Unreachable components are orphans.
- **Acyclicity (where applicable).** Module dependency graphs that the host's language requires acyclic (Python, ES modules, Rust, Go) honor the constraint. Documentation cross-references may form cycles (forward + back-reference is a feature, not a violation).
- **Density.** Sparse references (a component referenced from only one site) are inspected for whether the component is over-isolated or under-developed; dense references (a component referenced from many sites) are inspected for whether the component has become a god-object peer.

The reference-graph state is the host's **systemic invariant**. Every change preserves the invariant or surfaces the invariant change as a finding.

## Enforcement

Path-filtered (the nine glob patterns in this rule's `pathFilter` field), always-on at every seriousness level when in scope. Demand-loaded companion to `rules/systemic-participation.md`. The parent rule carries the canonical M14 directive, pre-conditions, disclosure surface, and failure-tells catalog; this companion carries the seven operational sub-sections (four relations, sibling convergence, index/registry update, orphan classes, silo classes, retirement, reference graph).

## Bindings (§0.j five-direction)

- **Drives →** ● The four-relations declaration at every newly-introduced host-project component (the §1 table is the operational floor). ● The sibling-convergence walk at §2. ● The index / registry update at §3 across every component class. ● The orphan-recovery and silo-recovery actions at §4 and §5. ● The retirement-discipline unwinding at §6. ● The reference-graph invariant preservation at §7.
- **Satisfies →** ● the fifteen-mandate registry row **M14 — Ecosystem Systemicity** (operational detail tier). ● `rules/systemic-participation.md` companion-sub-rule anchors.
- **Established by ↑** ● `rules/systemic-participation.md` (parent-rule anchor). ● the fifteen-mandate registry (ratifies M14). ● the Pre-Emission Gate row 14.
- **Gated by ←** ● The path-filter (nine glob patterns covering host-project component classes) — this rule demand-loads only on component touches. ● `rules/systemic-participation.md` always-on baseline (parent rule must be live for the anchors to surface).
- **Cross-bound with ↔** ↔ `rules/systemic-participation.md` (parent rule; companion-sub-rule anchors bind this companion). ↔ `rules/canonical-layout.md` (M12 — orphan-prevention discipline at §3 of that rule extends through this companion's §4 to all newly-introduced components). ↔ `rules/bidirectional-binding.md` (M10 — the four systemic relations populate the M10 five-direction binding section). ↔ `rules/host-discovery.md` (M1 — sibling-convergence walks the host-discovery surface). ↔ `rules/code-craft-conventions.md` (universal-delegation stub's sibling-convergence enforcement at §2 binds here for code-language artifacts). ↔ `rules/disclosure-ledger.md` (M2 — systemic-participation outcomes recorded in the ledger). ↔ `rules/harness-adapter-shape-schemas.md` (M14 — convergence-vs-divergence at §2).
