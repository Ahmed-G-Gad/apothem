---
name: "visual-leverage"
description: "Structural subject matter — architecture, control flow, data flow, dependency graph, state machine, sequence, decision tree, hierarchy, precedence stack, lifecycle, permission matrix — carries a current-reality diagram alongside its prose, with provenance and a verification date. Mermaid is the recommended default for Markdown-centric ecosystems; the host's existing notation is honored per M1 host-discovery."
pathFilter: "**/*.md, **/docs/**, **/CLAUDE.md, **/rules/**, **/skills/**, **/agents/**, **/commands/**, **/adr/**, **/rfcs/**, **/architecture*, **/design*"
alwaysApply: false
paths:
  - "**/*.md"
  - "**/docs/**"
  - "**/CLAUDE.md"
  - "**/rules/**"
  - "**/skills/**"
  - "**/agents/**"
  - "**/commands/**"
  - "**/adr/**"
  - "**/rfcs/**"
  - "**/architecture*"
  - "**/design*"
---

<!-- SPDX-License-Identifier: MIT -->

# Rule: Visual Leverage — Diagrams Where Structure Is the Subject

## What this rule enforces

This rule binds **M9 — Visual Leverage**. Where the host-project artifact's subject matter is **structural** — architecture, control flow, data flow, dependency graph, state machine, sequence, decision tree, hierarchy, precedence stack, lifecycle, permission matrix — the agent MUST produce a **diagram** alongside the prose: never a substitute (the prose carries semantics the diagram cannot) but a **co-equal first-class artifact**. Prose-only structural documentation is systematic under-utilization of the medium and a structural failure, not a style choice. Every diagram MUST carry provenance (hand-authored / generated / extracted), a **verification date**, and a back-binding to the artifact it abstracts. Diagrams reflect **current reality** — never historical or aspirational state — and a patch that changes a structure updates its diagram in the same change.

## Pre-conditions

Applies whenever a host-project artifact's subject matter is structural in any sense enumerated above. Diagrams are NOT required for narrative prose, declarative configuration, prose-only how-to guides, or single-function code comments — the trigger is structural subject matter, not Markdown presence. A trivial-scope structural surface (a four-line pipeline described in one unambiguous paragraph) is exempt; the diagram becomes mandatory the moment the structure exceeds what one paragraph carries without ambiguity.

## Required behavior

### 1. Trigger Catalog — When a Diagram Is Mandatory

| Subject matter | Diagram class (recommended) | Why a diagram |
|---|---|---|
| Architecture (component layout, layering, integration boundaries) | Architecture sketch (Mermaid `graph TD` / `flowchart`) | Spatial relationships between components are illegible in linear prose |
| Control flow (decision trees, branching pipelines, retry loops) | Decision tree (`flowchart`) | Branch coverage and termination conditions are auditable visually |
| Data flow (records, tokens, sizes through stages) | Data-flow diagram (`flowchart` with edge annotations) | Stage-to-stage transformations and back-pressure points become explicit |
| State machine (lifecycle states, transition triggers) | State diagram (`stateDiagram-v2`) | Reachability and dead-end states are inspectable |
| Sequence (ordered interactions across actors) | Sequence diagram (`sequenceDiagram`) | Message ordering and concurrency are unambiguous |
| Dependency graph (modules, packages, services) | Dependency graph (`graph LR`) | Cycles and orphans are visible at a glance |
| Hierarchy (taxonomies, inheritance, organizational structure) | Tree (`graph TD`) | Depth and sibling counts are readable |
| Precedence stack (rule precedence, deny-overrides-allow, override chains) | Vertical stack (`graph TD` ordered top-down) | Override semantics need spatial ordering |
| Permission matrix (actor × resource × verdict) | Heatmap or table | Sparse / dense regions are legible in two dimensions |

Subject matter fitting one row MUST emit the corresponding diagram class (or its host-discovered equivalent per §3). Subject matter fitting two or more rows emits one diagram per row — a state machine that ALSO carries a permission matrix emits both.

### 2. Diagram Provenance — Required Metadata

Every diagram MUST carry a metadata header (Mermaid `%%` comments, or the host's diagram-notation comment syntax) with all three fields:

- **`provenance: <hand-authored | generated-from <source> | extracted-from <source>>`** — how the diagram was produced. Generated diagrams cite the generator (script path, command, tool); extracted diagrams cite the source artifact (file path, line range).
- **`verified: <ISO-8601 date>`** — when the diagram was last verified against current reality. Updated **in the same change** that touches the abstracted structure (per §4).
- **`cross-reference: <peer artifact>`** — the artifact the diagram binds back to (prose section, code module, spec). This is the M10 reciprocal-binding surface (`rules/bidirectional-binding.md`).

A diagram missing any field is non-conformant. A diagram whose `verified` date precedes the structure it abstracts is **stale** (per §4).

### 3. Notation Discipline — Mermaid Default, Host Override

**Mermaid is the recommended default** for Markdown-centric ecosystems (concrete drivers per `rules/interactive-questions-canonical-shapes.md` §3.2.1):

- **Class 5 rule citation** — the hooks pipeline uses Mermaid decision-tree diagrams; sibling `rules/` use Mermaid for decision-trees and sequence diagrams.
- **Class 6 observed-state** — Mermaid renders inline in GitHub, GitLab, Bitbucket, Markdown editors (VS Code, Obsidian), and most doc generators (Fumadocs, Docusaurus, Sphinx via `myst-parser`); it diffs cleanly in version control and covers the full §1 diagram family.

**Host override (M1 discipline).** Where the host has ratified a different notation — PlantUML, draw.io, Graphviz dot, ASCII-art, mermaid-py, or vendor-specific (Lucidchart, Miro, Excalidraw) — honor it per `rules/host-discovery.md`: walk the host's structural-artifact corpus (`docs/`, `architecture/`, `adr/`, `rfcs/`), count notation occurrences, adopt the dominant one. Where the host is silent, surface the choice as an inquiry per `rules/authority-inquiry.md` with Mermaid as the **Recommended** option per `rules/option-annotation.md`.

### 4. Fidelity & Staleness — Current Reality Only

Every diagram reflects **current reality**, never historical or aspirational state. Three fidelity invariants:

1. **Same-change update.** A patch changing a structure (add a component, rename a state, reorder a precedence stack, add a permission row) updates the corresponding diagram in the same change. Splitting structure-change and diagram-update across two commits / PRs leaves the diagram stale at the boundary — non-conformant even when transient.
2. **Staleness check.** Compare the `verified:` date against the modification date of the abstracted structure; when the structure is newer, the diagram is **stale**. The `diagram-staleness-grep` mechanical matcher flags stale diagrams at the pre-emission gate.
3. **Aspirational-state declaration.** A diagram describing what the system *will* or *should* do (a target architecture, a future state) MUST carry the literal label `[Aspirational — target: <name>; date: <ISO-8601>]` in its metadata header AND as visible prose adjacent to it. An unlabelled aspirational diagram is non-conformant.

### 5. Surface Imposition — Where Diagrams Land

| Surface | Diagram obligation |
|---|---|
| `CLAUDE.md` | Carries the standing directive that structural subject matter draws (M9 row in §8 fifteen-mandate registry). |
| `rules/*.md` | Decision-tree-bearing rules emit Mermaid `flowchart TD` per §1 row "Control flow". Architectural-discipline rules emit Mermaid `graph TD` per §1 row "Architecture". |
| `skills/*/SKILL.md` | Multi-step procedures whose subject matter is structural emit a sequence diagram or flowchart in the procedure body. |
| `agents/*.md` | Architectural-remit agents emit diagrams in their return format per `rules/canonical-layout.md`. |
| `commands/*.md` | Pipeline-shaped commands emit a flowchart of the pipeline's decision-tree (every `commands/plan-*.md` carries a Mermaid `flowchart TD` of its workflow). |
| `output-styles/*.md` | Preserve diagram blocks rather than flattening them — a concise output style does not collapse a Mermaid `flowchart` to a bulleted list. |
| `hooks/messages/*.md` | Carry diagrams when the hook's subject matter is structural (the dispatcher's flow, the precedence stack of overlapping matchers). |
| `conformity/*-grep.py` headers | Carry no diagrams (single-purpose scripts; structural surface is the dispatch tree at `conformity/gate.py`). |

### 6. Failure Recovery — When a Diagram Is Missing or Stale

- **Missing diagram on structural subject matter.** Author the diagram in the same change as the prose; never emit the prose-only artifact and defer the diagram — it is non-conformant at emission. Where the diagram needs data the agent lacks (e.g., a permission matrix depending on host-discovered scope), surface the gap as an inquiry per `rules/authority-inquiry.md` and mark the missing diagram a `<USER-CONFIRM:diagram-needs-data>` placeholder — which blocks emission per the pre-emission gate.
- **Stale diagram detected.** Update the diagram and its `verified:` date in the same change that touched the structure. On a substantial rewrite, update `provenance:` to reflect it (`generated-from <source>` → `hand-authored` for a manual rewrite).
- **Notation drift.** Convert a diagram in a non-ratified notation (e.g., Mermaid in a PlantUML-host project) at next touch. Mixed-notation corpora are a finding per M14 systemic participation.

## Disclosure surface

Every diagram emission, update, or staleness recovery is recorded in the disclosure ledger per `rules/disclosure-ledger.md`:

- `[Diagram — emitted: <path>; class: <architecture | flowchart | sequence | state | dependency | hierarchy | precedence | matrix>; provenance: <provenance-form>; verified: <ISO-8601>]` for new diagrams.
- `[Diagram — refreshed: <path>; reason: <staleness | structure-change | notation-conversion>; verified: <ISO-8601>]` for updates.
- `[Diagram — deferred: subject matter is structural but the diagram requires <missing-data>; tracking: <USER-CONFIRM:id> | inquiry-id]` for cases where the diagram cannot be authored without further input.

## Failure tells

A 2,000-word architectural description with no diagram. An ADR that says "the new flow is …" in prose for ten paragraphs without an accompanying state diagram. A permission rule documented as a bulleted list of `(tool, scope, verdict)` triples instead of a matrix. A migration guide that lists steps in prose but draws no state machine of the migration's lifecycle. A diagram with no `verified:` date. A diagram whose `verified:` date precedes the latest modification of the structure it abstracts. A diagram in PlantUML in a host project where every other diagram is Mermaid (notation drift). An aspirational diagram presented as current reality without the `[Aspirational — …]` label. A "before / after" architecture comparison where only the "before" sketch is current and the "after" is undated. Multiple diagrams of the same subject matter scattered across the artifact corpus with conflicting depictions (no single source of truth).

## Bindings (§0.j five-direction)

- **Drives →** ● Every structural-artifact emission across the ecosystem (every rule decision-tree, every command flowchart, every skill sequence diagram). ● The `diagram-staleness-grep` mechanical matcher at `conformity/diagram_staleness_grep.py` — operationalizes the §4 staleness check. ● Every Mermaid `%%` comment header carrying `provenance: …` + `verified: …` + `cross-reference: …`. ● The `verified:` date discipline at every `rules/*.md` Mermaid block. ◐ The aspirational-state declaration at every target-architecture diagram.
- **Satisfies →** ● the fifteen-mandate registry row **M9 — Visual Leverage**. ● the Pre-Emission Gate row 9 (M9 visual leverage check).
- **Established by ↑** ● the fifteen-mandate registry (ratifies M9). ● the Pre-Emission Gate row 9.
- **Gated by ←** ● The trivial-vs-non-trivial threshold (trivial structural surfaces with unambiguous prose are exempt). ● `CLAUDE.md` always-loaded preamble. ● The path-filter declared in this rule's frontmatter (Markdown / docs / structural-artifact directories).
- **Cross-bound with ↔** ↔ `rules/host-discovery.md` (M1 — host's existing notation overrides Mermaid default). ↔ `rules/authority-inquiry.md` (M5 — silent host on notation routes through inquiry surface). ↔ `rules/option-annotation.md` (M7 — every notation choice carries the Recommended marker plus concrete-driver rationale). ↔ `rules/bidirectional-binding.md` (M10 — diagram `cross-reference:` metadata is the M10 reciprocal-binding surface). ↔ `rules/pre-emission-gate.md` (M4 — bar 9 of the gate enforces this rule's diagram-presence check on structural subject matter). ↔ `rules/disclosure-ledger.md` (M2 — diagram emissions / refreshes / deferrals are recorded in the ledger). ↔ `rules/canonical-layout.md` (M9 — diagrams of phase / sub-phase structure live at the canonical layout per §2). ↔ `rules/code-craft-markdown.md` (M9 — diagram + prose pairing inside Markdown structural artifacts). ↔ `rules/pre-emission-gate-bars.md` (this rule is among the M-rules named in the gate's "Failure → action" column; the bar-level catalog cross-binds each).
