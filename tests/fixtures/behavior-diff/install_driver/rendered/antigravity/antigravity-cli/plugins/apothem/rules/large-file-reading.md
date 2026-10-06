---
trigger: glob
description: "Large file reading via targeted segments — Grep to locate, Glob for traversal, Read with offset/limit; never load a full file when a segment suffices. Read-side analogue of large-file-generation. Demand-loaded on file-consult touches; the always-on read-side budget invariant lives in context-management.md §7."
globs: "**/.apothem/plans/**, **/.plans/**, **/*.md, **/docs/**"
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

## Bindings (§0.j five-direction)

- **Drives →** Every file-consultation surface across the ecosystem (every `Read` invocation against a non-trivial-size file routes through the pre-read assessment at §1 and the locate-before-read protocol at §2). The `Grep` / `Glob` first-pass discipline at every search-before-implement step per CM-4. The segmentation discipline at §4 on every multi-segment file consult.
- **Satisfies →** Project `CLAUDE.md` reading-discipline obligations; the read-side half of the context-budget invariant declared at `rules/context-management.md` §7.
- **Established by ↑** `rules/large-file-generation.md` (sibling write-side rule — same essence, applied to writing). `rules/context-management.md` §7 Context Budget Discipline (this rule operationalizes the read-side of §7.2 Demand Loading).
- **Gated by ←** The size-band thresholds at §1 (small files bypass the protocol). The trivial-vs-non-trivial threshold inherited from the project's CLAUDE.md scope.
- **Cross-bound with ↔** ↔ `rules/large-file-generation.md` (sibling; write-side analogue with matching size-bands and segmentation logic). ↔ `rules/context-management.md` (CM-12 lean-context discipline; this rule's segmentation is one of the primary read-side levers preserving context budget). ↔ `rules/token-budget-discipline.md` (read-side analogue of the always-on body-size ceiling; both rules optimize the same gradient on different surfaces). ↔ `rules/clean-room-generation.md` (CM-4 Search Before Implement uses `Grep` / `Glob` first; this rule canonicalizes the locate-before-read shape that CM-4 search relies on). ↔ `rules/tool-use-discipline.md` (locate-before-read is the observe-step discipline at the file tier of that rule's observe → decide → act loop). ↔ `rules/tool-use-discipline-failure-tells.md` (locate-before-read is the observe-step discipline the act-without-observe tell violates).
