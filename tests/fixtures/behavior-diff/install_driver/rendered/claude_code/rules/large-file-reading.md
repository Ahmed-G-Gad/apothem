---
name: "large-file-reading"
description: "Large file reading via targeted segments — Grep to locate, Glob for traversal, Read with offset/limit; never load a full file when a segment suffices. Read-side analogue of large-file-generation. Demand-loaded on file-consult touches; the always-on read-side budget invariant lives in context-management.md §7."
pathFilter: "**/.apothem/plans/**, **/.plans/**, **/*.md, **/docs/**"
alwaysApply: false
paths:
  - "**/.apothem/plans/**"
  - "**/.plans/**"
  - "**/*.md"
  - "**/docs/**"
---

<!-- SPDX-License-Identifier: MIT -->

# Rule: Large File Reading via Targeted Segments

## Obligations

### 1. Pre-Read Assessment

Assess size before reading:

- **Small** (< 200): full-read MAY proceed.
- **Medium** (200–500): segment reads SHOULD be preferred for scoped tasks.
- **Large** (500–1500): locate first; read only cited ranges.
- **Massive** (> 1500): structure first; full-read forbidden unless every section is load-bearing AND recorded per §4.

### 2. Locate-Before-Read Protocol

When the task names an identifier, heading, or symbol: `Grep -n` first, `Read` the cited range with a tight buffer, re-`Grep` before any escalation. A named target MUST NOT trigger a full-read.

### 3. Structural Traversal Protocol

`Glob` for sibling discovery; `Grep` for headings, signatures, frontmatter fields. Descend into a body only when the mapped structure shows it is needed.

### 4. Segmentation Discipline

Right-size each `offset` / `limit`, track multi-segment coverage, and record every Large+ full-read exception in the disclosure ledger per `rules/disclosure-ledger.md` (path, band, driver).

## Seriousness Scaling

| Level | Large File Reading Behavior |
| ----- | --------------------------- |
| EXPLORING | Size awareness; segment-based reads encouraged on Large+ files |
| PERSONAL_USE | Pre-read assessment + locate-before-read on Medium+ files |
| SHARED+ | Segment-only on Large+ files; full-read exceptions require disclosure-ledger rationale |

## Anti-Patterns

- **DON'T** full-read when `Grep` plus a segment answers the question.
- **DON'T** skip locate-before-read for a named target.
- **DON'T** re-read overlapping ranges without tracking.

## Enforcement

Demand-loaded on file-consult touches (pathFilter above), scaling per the table above. Canonical specification for size-aware file reading; the always-on read-side context-budget invariant it operationalizes stands in `rules/context-management.md` §7.
