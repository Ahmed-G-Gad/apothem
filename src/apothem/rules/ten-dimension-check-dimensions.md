---
name: "ten-dimension-check-dimensions"
description: "Path-filtered companion sub-rule carrying the verbatim per-dimension bodies (rigor / coherence / configurability / readability / orphanism / structurality / architecture / naming / scholarly referencing / examples-tests-docs) and per-dimension failure tells declared at the parent `ten-dimension-check.md` rule's anchor; demand-loaded on artifact-emission surfaces."
pathFilter: "**/*.md, **/*.py, **/*.sh, **/*.ps1, **/CLAUDE.md, **/rules/**, **/commands/**, **/skills/**, **/agents/**, **/docs/**"
alwaysApply: false
---

<!-- SPDX-License-Identifier: MIT -->

# Rule: Ten-Dimension Check — Per-Dimension Bodies (Companion Sub-Rule)

## Purpose

Carry the verbatim per-dimension bodies and per-dimension failure tells the parent rule `rules/ten-dimension-check.md` anchors. Path-filtered: loads on any artifact-emission surface (Markdown, Python, shell, PowerShell under the rules / commands / skills / agents / docs trees and the root `CLAUDE.md`). The parent owns the M3 standing directive, the multiplicative-failure clause, the trivial-work abbreviated check, the self-check-at-emission paragraph, the cross-cutting failure tells, and the disclosure surface; this companion owns the ten per-dimension bodies below.

## Obligations

### The Ten Dimensions — Per-Dimension Bodies

Every artifact MUST pass each of the ten dimensions individually before emission. The order is canonical; each carries one diagnostic failure tell.

1. **Scientific rigor.** Claims are evidence-based; cause-effect statements are reproducible by inspection or experiment; folklore is excluded; falsifiability is stated where applicable. **Tell:** "this is faster" with no benchmark cited.

2. **Consistency · Coherence · Integration · Validity.** No contradiction within the artifact or against its neighbors; every part belongs to one mental model; references resolve, data shapes align, schemas match, names exist, the artifact parses. **Tell:** a README that disagrees with the code it documents.

3. **Configurability · Irredundancy · Consolidation.** Varying behavior is parameterized; values, rules, and patterns are not duplicated; downstream artifacts reference rather than copy; fragmentation is healed. **Tell:** the constant `60` repeated across three files.

4. **Readability · Intuition · Cleanness.** Readable on first pass by a competent engineer new to the artifact; names telegraph purpose; surprising behavior is documented or removed; no trailing whitespace, mixed line endings, dead TODOs, or commented-out blocks. **Tell:** a function named `process_data` (intent-invisible).

5. **Orphanism · Staleness.** No reference to a removed API, renamed identifier, deprecated tool, dead URL, or non-existent file; the artifact is itself reachable in the host's reference graph; verification dates are stamped where content is volatile. **Tell:** a reference to a file moved last sprint.

6. **Structurality · Systemicity · Uniformity · Comprehensiveness.** The artifact has clear structure, behaves as part of a system rather than a heap, follows its peers' shape, and fully covers the surface it claims. **Tell:** a partial enumeration listing 3 of 5 cases without naming the omission.

7. **Architecture.** Where the artifact is structural, layering is articulated, data and control flow are traceable, layer boundaries are respected, and violations are flagged. **Tell:** a domain function that imports an infrastructure adapter.

8. **Naming conventions & uniformity.** One convention per scope, applied identically; identifier shapes match the host's idioms; names never lie about behavior; specificity is not baked into the names of generic things. **Tell:** mixed `camelCase` and `snake_case` in one Python module.

9. **Scholarly / technical referencing.** Every reference — internal, external, symbolic, quoted — meets a scholarly bar: canonical permalinked form, access date where volatile, author or organization attribution, commit-pinned over branch-pointed, primary over secondary source, no phantom citation. **Tell:** "RFC 7234 says X" with no link, no section, no quote — and X is not in RFC 7234.

10. **Examples · Tests · Docstrings · Documentation.** The artifact carries the minimum viable documentation surface for its kind: examples for invocables, tests or verification recipes for non-trivial logic, docstrings or header comments for scripts, README-equivalent coverage where the artifact is a directory or module. **Tell:** a public function with no docstring and no example.

## Enforcement

Path-filtered (the glob list in this rule's `pathFilter` field), always-on at every seriousness level when in scope. Demand-loaded companion to `rules/ten-dimension-check.md`: the parent owns the M3 standing directive, multiplicative-failure clause, trivial-work abbreviated check, self-check-at-emission paragraph, cross-cutting failure tells, and disclosure surface; this companion owns the ten per-dimension bodies and their failure tells.

## Bindings (§0.j five-direction)

- **Drives →** ● Every artifact-emission surface's per-dimension self-check (the ten verbatim per-dimension bodies enumerated above are the dimension-by-dimension specification the gate's bar 3 inspects). ● Every per-dimension failure-tell match at the pre-emission gate. ◐ The dimension-by-dimension marking on the gate attestation.
- **Satisfies →** ● the fifteen-mandate registry row **M3 — Ten Quality Dimensions** (per-dimension specification surface). ● `rules/ten-dimension-check.md` anchor (parent rule's pointer to this companion's full per-dimension fidelity).
- **Established by ↑** ● `rules/ten-dimension-check.md` (parent-rule anchor). ● the fifteen-mandate registry (ratifies M3). ● the Pre-Emission Gate row 3.
- **Gated by ←** ● The path-filter (the glob list in this rule's frontmatter) — this rule demand-loads only on artifact-emission-surface touches. ● `rules/ten-dimension-check.md` always-on baseline (parent rule's anchor must be live for the companion to demand-load coherently).
- **Cross-bound with ↔** ↔ `rules/ten-dimension-check.md` (parent rule; anchor binds this companion). ↔ `rules/pre-emission-gate.md` (M4 — bar 3 of the fifteen-bar gate inspects each of the ten verbatim per-dimension bodies enumerated here). ↔ `rules/code-craft-python.md` + `rules/code-craft-shell.md` + `rules/code-craft-markdown.md` + `rules/code-craft-conventions.md` (per-language code-craft rules apply dimensions 4, 7, 8, 10 with language-specific failure tells). ↔ `rules/disclosure-ledger.md` (M2 — deferred dimensions surface as deferrals per the parent rule's disclosure surface).
