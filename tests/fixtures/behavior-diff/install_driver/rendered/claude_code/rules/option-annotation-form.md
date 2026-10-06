---
name: "option-annotation-form"
description: "Path-filtered companion rule carrying the prose-and-document annotation form, rationale-specificity citations, cross-channel consistency invariant, cardinality bounds, and failure-tells enumeration declared at the parent `option-annotation.md` rule's anchor lines; demand-loaded on prose-and-document artifact touches."
pathFilter: "**/*.md, **/CLAUDE.md, **/rules/**, **/commands/**, **/skills/**, **/agents/**, **/docs/**, **/ADR/**, **/rfcs/**"
alwaysApply: false
paths:
  - "**/*.md"
  - "**/CLAUDE.md"
  - "**/rules/**"
  - "**/commands/**"
  - "**/skills/**"
  - "**/agents/**"
  - "**/docs/**"
  - "**/ADR/**"
  - "**/rfcs/**"
---

<!-- SPDX-License-Identifier: MIT -->

# Rule: Option Annotation Form (Companion Sub-Rule)

## Purpose

Specify the executable details of the prose-and-document option-annotation discipline declared at the parent `rules/option-annotation.md`. This companion is path-filtered: it loads when the assistant edits any prose-and-document artifact (Markdown files, rules, commands, skills, agents, docs, ADRs, RFCs), keeping the parent's always-on payload lean while preserving full form fidelity at the demand-load surface. The parent rule remains the canonical home for the M7 standing directive and channel-routing summary; this companion carries the prose-and-document form, rationale specificity, cross-channel consistency, cardinality bounds, and failure tells.

## Obligations

### 1. The Prose-and-Document Annotation Form

Every option set in a prose-and-document artifact carries the following structure:

```text
Option A — <name>
  <one-paragraph statement of what the option means and its direct, observable consequence>
Option B — <name> — **Recommended**
  <one-paragraph statement of what the option means>
  Rationale: <specific, principle-linked rationale citing a concrete driver — host-project sibling-file precedent, observed-state fact, named risk, named constraint, RFC or vendor documentation, or a rule citation with anchor>
Option C — <name>
  <one-paragraph statement of what the option means and why the rationale's pressure does not weigh as heavily>
```

A mutually exclusive option set carries at most one `**Recommended**` label, mirroring the single-select cardinality at `rules/interactive-questions.md` §3.1. A non-exclusive set MAY mark multiple options only when the prose states they can be selected together AND each recommended option carries its own concrete-driver rationale. A zero-recommended set is conformant only when no option dominates on the cited driver — the rationale section then names the underdetermined dimensions and routes the choice to the user via an inquiry per `rules/authority-inquiry.md`.

### 2. Rationale Specificity

The rationale meets the scholarly / technical bar declared at `rules/ten-dimension-check.md` dimension 9. Specifically, the rationale cites at least one concrete driver class — host-project sibling-file precedent, observed-state fact (measured metric, file contents, gate result, log entry, dependency-graph analysis with a reproducible evidence pointer), named risk, named constraint, RFC or vendor documentation, or a rule citation with anchor. Phrases on the vague-rationale forbid list at `rules/interactive-questions-canonical-shapes.md` §3.2.2 — "this is widely adopted" without a named source, "best practice", "industry standard", "more scalable", "cleaner", "more elegant", "generally speaking" — are non-conformant when they stand as the sole justification.

### 3. Cross-Channel Consistency

When the same decision is surfaced in both channels — e.g., a commit-message body documents the option set the structured-inquiry invocation resolved — the two surfaces carry consistent option labels, consistent recommended markers, and consistent rationales. The structured-inquiry record is the source of truth on shape and label set; the prose surface tracks it without divergence.

### 4. Cardinality Bounds

Floor: two options (a single option is a notification, not a question). Ceiling: four options (more than four degrades operator judgment per the choice-overload literature at `rules/interactive-questions.md` §9). A set exceeding four entries MUST be split into a hierarchical surface — a primary three-or-four-option choice on the dominant dimension, then a follow-up choice on the secondary dimension once the primary resolves.

### 5. Failure Tells

"Here are some options, let me know which" — annotation absent (un-annotated form). "I went with Black" — silent pick (no option set surfaced). "Recommended: X. (No rationale)" — annotation hollow (marker without principle-linked driver). Two options carry the `**Recommended**` label in the same option set (cardinality violation). The rationale is `"this is widely adopted"` with no named source (vague-rationale forbid list). The recommended option's body lacks the `Rationale:` line (annotation incomplete). An option set of five or more entries presented flat (cardinality-bound violation; the choice-overload threshold is exceeded). A commit-message body documents an option set with a different recommended option than the structured-inquiry record resolved (cross-channel divergence).

## Enforcement

Path-filtered (the nine glob patterns in this rule's `pathFilter` field), always-on at every seriousness level when in scope. Demand-loaded companion to `rules/option-annotation.md`. The parent rule carries the M7 standing directive and channel-routing summary; this companion carries the prose-and-document form, rationale specificity, cross-channel consistency, cardinality bounds, and failure tells.

## Bindings (§0.j five-direction)

- **Drives →** ● Every prose-and-document option set's annotation shape (the §1 form is the floor). ● The rationale-specificity check at every `Rationale:` line (§2 cites the concrete-driver taxonomy and the vague-rationale forbid list). ● The cardinality check at every option set (§4 floor of 2 / ceiling of 4). ◐ The cross-channel consistency check between structured-inquiry records and prose surfaces (§3).
- **Satisfies →** ● the fifteen-mandate registry row **M7 — Option Annotation** (the prose-and-document subset). ● `rules/option-annotation.md` companion-anchor lines (the parent rule's pointers to this companion's full specification).
- **Established by ↑** ● `rules/option-annotation.md` (parent-rule anchor). ● the fifteen-mandate registry row M7.
- **Gated by ←** ● The path-filter (the nine glob patterns) — this rule demand-loads only on prose-and-document artifact touches. ● `rules/option-annotation.md` always-on baseline (parent rule's anchor must be live for the companion to demand-load coherently).
- **Cross-bound with ↔** ↔ `rules/option-annotation.md` (parent rule; companion-anchor lines bind this companion). ↔ `rules/interactive-questions-canonical-shapes.md` (§2.1 per-invocation cardinality, §3.2.2 vague-rationale forbid list). ↔ `rules/interactive-questions-detail.md` (choice-overload bound, authoring discipline). ↔ `rules/ten-dimension-check.md` (M3 dimension 9 scholarly / technical referencing — rationale specificity meets it). ↔ `rules/authority-inquiry.md` (M5 — zero-recommended option sets route through the inquiry surface). ↔ `rules/disclosure-ledger.md` (M2 — annotation outcomes recorded in the ledger).
