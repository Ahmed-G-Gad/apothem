---
name: "bidirectional-binding"
description: "Every substantive structural element carries reciprocal bindings to its peers in canonical five-direction notation — Drives → / Driven by ← / Satisfies → / Established by ↑ / Cross-bound with ↔. Every binding declared in one direction has a reciprocal back-pointer at the other end; half-edges are structural failures. A Bidirectional Binding Matrix appendix summarizes the graph where structure permits."
pathFilter: "**/*.md, **/docs/**, **/CLAUDE.md, **/rules/**, **/skills/**, **/agents/**, **/commands/**, **/adr/**, **/rfcs/**, **/architecture*, **/design*"
alwaysApply: false
---

<!-- SPDX-License-Identifier: MIT -->

# Rule: Bidirectional Binding & Phase-Execution Threading

## What this rule enforces

This rule binds **M10 — Bidirectional Binding & Phase-Execution Threading**. Every substantive structural element in a host-project artifact — section, sub-section, contract, requirement, test, dependency declaration, citation, cross-reference, phase, sprint, milestone — MUST carry **explicit, reciprocal, persistently-maintained bindings** to its peers in the canonical **five-direction notation** below. Every binding declared in one direction MUST have a **reciprocal back-pointer** at the other end. A binding without its reciprocal is a **half-edge** — a structural failure, never an aesthetic preference or a deferral candidate. Where structure permits, a **Bidirectional Binding Matrix** MUST be appended summarizing the graph.

**Phase-execution threading.** Where the artifact describes ordered execution (a pipeline, a migration, a release process, a deployment, a research procedure), the order MUST be **named, numbered, anchor-bearing, and fully cited at both ends** — every phase declares what it invokes, what it advances, what gates it, and what it gates. Standing gates (mandates active throughout) MUST be explicitly marked.

## Pre-conditions

The rule applies whenever a host-project artifact carries substantive structural elements — sections depending on sections, contracts satisfying or establishing contracts, phases driving or gating phases, peers mutually reinforcing. Trivial-scope artifacts per the trivial-vs-non-trivial threshold (single-file edits ≤ 5 lines AND no public-API change AND no behavioral shift) are exempt; the trigger is structural surface, not Markdown presence. A linear narrative with no structural dependencies (a top-to-bottom how-to with no cross-references) is exempt — but the moment the artifact carries a cross-reference, a satisfies-relation, a gate, or mutual reinforcement, the bindings requirement applies.

## Required behavior

### 1. The Five Directions — Canonical Notation

The bindings notation reproduces the five canonical symbols **verbatim**. Variants, abbreviations, translations, or substitutions (Unicode-emoji arrows, ASCII-only `->`, alternative wording like "Causes" or "Contributes-to") are non-conformant.

| Direction | Symbol | Semantic | Reciprocal direction |
|---|---|---|---|
| **Drives →** | `→` (forward arrow) | What this element causes, produces, advances downstream | **Driven by ←** |
| **Driven by ←** | `←` (backward arrow) | What introduces / gates / triggers this element | **Drives →** |
| **Satisfies →** | `→` (forward arrow) | What end-state / criterion / acceptance test this element establishes | **Established by ↑** |
| **Established by ↑** | `↑` (upward arrow) | What element(s) produce this outcome (anchors, ratifications, design sources) | **Satisfies →** |
| **Cross-bound with ↔** | `↔` (bidirectional arrow) | Sibling elements that mutually reinforce; symmetric reciprocal | **Cross-bound with ↔** (self-reciprocal) |

**Reading discipline.** The arrow reads in the natural direction of the prose: "Drives → A" reads "drives A"; "Driven by ← B" reads "driven by B". The arrow belongs to the section header, not as a separator inside a sentence — `**Drives →** A, B, C` is canonical, never `**Drives** → A, B, C` or `Drives -> A, B, C`.

**Section-header form.** Every artifact carrying bindings emits a `## Bindings (§0.j five-direction)` section with one bullet per direction:

```markdown
## Bindings (§0.j five-direction)

- **Drives →** <enumeration of downstream targets, comma-separated or sub-bulleted>
- **Driven by ←** <enumeration of upstream triggers / gates>
- **Satisfies →** <enumeration of end-states / criteria>
- **Established by ↑** <enumeration of anchors / ratifications>
- **Cross-bound with ↔** <enumeration of sibling reinforcements> `rules/propagation.md` (propagation's reciprocity surface is operationalised through this rule's five-direction notation).
```

A direction with **no bindings** is omitted — a section with three populated and two absent directions is conformant (the absent ones read as "this element neither drives nor is gated beyond its own scope"). Placeholder entries (`- **Drives →** TBD`) are non-conformant per `rules/definitiveness.md`.

**Shipped-corpus floor.** Apothem's own rules, commands, agents, skills, and their folder READMEs hold a stricter floor than a host-project artifact: each closes with the section and carries **Drives →**, **Satisfies →**, **Established by ↑**, **Gated by ←** (the activation condition or enforcer that gates it), and **Cross-bound with ↔**; each hook-message context carries the **Drives →**, **Established by ↑**, **Cross-bound with ↔** subset. The corpus-walking `binding-five-direction-grep` matcher at `conformity/binding_five_direction_grep.py` enforces the floor and is **blocking**: a missing section or direction fails `gate --all --strict`.

### 2. Reciprocity — The Half-Edge Failure Pattern

**Every binding is reciprocal.** When A declares `Drives → B`, B declares `Driven by ← A`. When A declares `Satisfies → criterion C`, C declares `Established by ↑ A`. The reciprocal back-pointer lives **at the other end of the edge**, not in the artifact that emitted the forward declaration.

**Half-edge failure pattern.** A binding declared in one direction without its reciprocal at the other end is a **half-edge**:

- `A: Drives → B` declared, but B has no `Driven by ← A` — half-edge.
- `A: Satisfies → C` declared, but C has no `Established by ↑ A` — half-edge.
- `A: Cross-bound with ↔ B` declared, but B has no `Cross-bound with ↔ A` — half-edge (the self-reciprocal direction is the only one that requires identical wording on both ends).

Half-edges are **structural failures**. Two mechanical matchers enforce this rule across complementary scopes. The per-file `binding-reciprocity-grep` matcher at `conformity/binding_reciprocity_grep.py` enforces the **arrow notation** within each artifact's Bindings section (ASCII substitutes like `->` are notation drift). The corpus-walking `binding-reciprocity-corpus-grep` matcher at `conformity/binding_reciprocity_corpus_grep.py` enforces **cross-file `↔` reciprocity** across the `rules/*.md` corpus: for every `rules/A.md` that cites `rules/B.md` under `Cross-bound with ↔`, it verifies `rules/B.md` cites `rules/A.md` back under `Cross-bound with ↔`, reporting each ↔ half-edge with both file paths. Its scope is the self-reciprocal `↔` direction between rule peers and rule-to-rule edges only — `↔` citations to non-rule surfaces (`conformity/*.py`, `skills/*/SKILL.md`) carry no Bindings section and are not subject to reciprocity; the directional relations (`Drives →` / `Driven by ←`, `Satisfies →` / `Established by ↑`) are specified in prose here but are not mechanically walked, because a rule's directional targets are typically artifacts and gate rows rather than reciprocating sibling rules. The corpus matcher is **blocking**: the corpus ships with every ↔ edge closed, so a new half-edge fails the sweep (and `gate --all --strict` exits non-zero on it). Half-edges are reported at the pre-emission gate per `rules/pre-emission-gate.md` row 10.

**Closure protocol.** A forward declaration lacking its reciprocal MUST gain the reciprocal in the **same change-set**. A patch adding `A: Drives → B` while B is unmodified is non-conformant — the patch updates B's `Driven by ←` line in the same change. Where the cited target is outside modifiable scope (a cross-repository reference, a vendor-controlled artifact), the citation declares the asymmetry: `Drives → <target> (one-way: target outside our control)` — the explicit one-way label is the documented escape hatch, never a default.

### 3. Phase-Execution Threading — Ordered Work Surfaces

Where the artifact describes ordered execution — a pipeline, a migration, a release process, a deployment, a research procedure, a sprint sequence — the bindings carry phase-execution threading:

- **Named.** Every phase has a stable identifier (`Phase 01`, `Sprint 3`, `Step 5`). Identifiers are anchor-bearing (Markdown headings the rest of the artifact can link to).
- **Numbered.** Order is explicit through the identifier's numeric component. Zero-padding (`01`, `02`, …, `10`, `11`) is conformant where the host's discovered convention is zero-padded; otherwise honor the host's pattern.
- **Anchor-bearing.** Every phase emits a heading the rest of the artifact references (`## Phase 01 — Discovery`). Internal cross-references use the heading's anchor, not free-text mentions.
- **Fully cited at both ends.** Every phase declares what it invokes (`Drives →` next phase, downstream consumers), what it advances (`Satisfies →` end-states), what gates it (`Driven by ←` prerequisite phases, standing gates), what it gates (the reciprocal `Driven by ←` declaration in the next phase). Both ends are populated; one-sided declarations are half-edges.
- **Standing gates marked.** Mandates active throughout the entire ordered execution (e.g., a CM-N or M-N rule that gates every phase, not just the first) are marked **explicitly** as standing — `Driven by ← (standing) <rule-citation>`. Standing gates are inherited by every phase by default; the explicit marking lets the reader distinguish phase-specific gates from ecosystem-wide ones.

### 4. The Bidirectional Binding Matrix — Appendix Discipline

Where the artifact's structure permits — multi-section specs, multi-phase plans, multi-element architectural documents, multi-rule rule sets — a **Bidirectional Binding Matrix** is appended summarizing the graph. The matrix surfaces drift the inline bindings cannot reveal at a glance.

**Matrix shape.** The matrix is a square table indexed by element identifier on both axs. Each cell records the binding direction from the row element to the column element, using the canonical symbols:

| | A | B | C | D |
|---|---|---|---|---|
| A | — | → | ↔ | ↑ |
| B | ← | — | → | — |
| C | ↔ | ← | — | → |
| D | ↓ | — | ← | — |

Reading the row: "A drives B; A is cross-bound with C; A is established by D." Reading the column: "B is driven by A; B drives C; B has no relation to D." The matrix's reciprocity invariant is mechanical — when row R, column C carries `→`, then row C, column R MUST carry `←`. When row R, column C carries `↔`, then row C, column R MUST carry `↔`. The diagonal is `—` (an element does not bind to itself; self-citation is not a binding).

**When the matrix is mandatory.** The matrix is mandatory when the artifact carries five or more bound elements AND at least one element binds to three or more peers. Below this threshold, inline bindings sections suffice (a sparse matrix adds no clarity). At or above it, the matrix is the canonical reciprocity-audit surface.

**Matrix placement.** The matrix lives in an `## Appendix — Bidirectional Binding Matrix` section near the artifact's tail, after the last substantive section but before the closing bindings citation (the artifact's own outward bindings live at the artifact's `## Bindings (§0.j five-direction)` section, separate from the inter-element matrix).

### 5. Maintenance Discipline — Bindings Are Persistent

Bindings are **persistently maintained**, not authored once and frozen:

- **Element rename.** When an element's identifier changes, every reciprocal back-pointer is updated in the same change. For rule-file `↔` peers, the `binding-reciprocity-corpus-grep` matcher catches the resulting stale citation (the renamed rule no longer cites back under `Cross-bound with ↔`).
- **Element removal.** When an element is removed, every reciprocal back-pointer pointing AT the removed element is removed in the same change. Dangling back-pointers (`Driven by ← <removed-element>`) are non-conformant.
- **Element split / merge.** When an element splits (one element becomes two), the original's bindings distribute to the new elements based on which new element inherits each binding's semantic. When elements merge, the union of their bindings becomes the merged element's bindings (deduplication required — two `Driven by ← X` declarations from the pre-merge elements collapse to one).
- **Cross-rule citations.** When a rule cites another rule (`Cross-bound with ↔ rules/<peer>.md`), the cited rule's `Cross-bound with ↔` section MUST cite this rule. The `binding-reciprocity-corpus-grep` matcher walks the whole `rules/*.md` corpus and reports each `↔` half-edge as part of the pre-emission gate (blocking; the corpus ships with every ↔ edge closed).

## Disclosure surface

Every binding emission, update, or reciprocal closure is recorded in the disclosure ledger per `rules/disclosure-ledger.md`:

- `[Binding — emitted: <element>; direction: <Drives → | Driven by ← | Satisfies → | Established by ↑ | Cross-bound with ↔>; target: <peer>]` for new bindings.
- `[Binding — closed: half-edge between <element-A> and <element-B>; reciprocal added at <element-B> in the same change-set]` for half-edge closures.
- `[Binding — removed: <element>; reason: <element-removed | binding-no-longer-applies>; reciprocals updated at <peer-list>]` for binding removals.
- `[Binding — Matrix appended: <appendix-path>; element-count: <N>]` for matrix emissions.

## Failure tells

`See Section 3` with no reciprocal back-pointer in Section 3 (half-edge — Section 3 does not declare it is being seen-from). A migration step that depends on a prior step without declaring the dependency in its `Driven by ←` (half-edge in the prerequisite direction). A test that satisfies an unstated requirement (the test's `Satisfies →` cites a requirement that has no `Established by ↑` declaration). A bindings section using ASCII-only arrows (`->` instead of `→`) — notation drift. A bindings section listing only `Drives →` and `Cross-bound with ↔`, omitting `Driven by ←` and `Satisfies →` and `Established by ↑` despite the artifact clearly being gated, satisfying criteria, and established by upstream anchors (incomplete population). A `Cross-bound with ↔` citation where the cited peer's section omits the reciprocal `Cross-bound with ↔` (asymmetric self-reciprocal). A multi-phase plan where Phase 03's `Drives → Phase 04` is declared but Phase 04 has no `Driven by ← Phase 03` (phase-execution threading half-edge). An artifact with five elements, dense bindings (each element binds to three or more peers), and no Bidirectional Binding Matrix appendix (mandatory matrix omitted). A renamed element whose old identifier still appears as a citation target in another element's binding line (stale citation). An element removed from the artifact whose reciprocal back-pointers in peer elements were not removed (dangling back-pointer).

## Bindings (§0.j five-direction)

- **Drives →** ● Every substantive structural element across every emitted host-project artifact (the five-direction notation is the binding floor for every section, sub-section, contract, phase). ● The `## Bindings (§0.j five-direction)` section at every `rules/*.md` body. ● The phase-execution threading at every `<project-root>/.apothem/plans/*/MASTER-PLAN.md` and `phases/NN-topic/PHASE.md`. ● The Bidirectional Binding Matrix appendix at every spec / multi-element design document. ● The `binding-reciprocity-grep` mechanical matcher at `conformity/binding_reciprocity_grep.py` — operationalizes the §2 reciprocity invariant's per-file notation discipline. ● The `binding-reciprocity-corpus-grep` corpus matcher at `conformity/binding_reciprocity_corpus_grep.py` — operationalizes the §2 cross-file `↔` reciprocity walk across the `rules/*.md` corpus. ● The `binding-five-direction-grep` corpus matcher at `conformity/binding_five_direction_grep.py` — operationalizes the §1 shipped-corpus floor (the section and its required directions on every rule, command, agent, skill, and hook message).
- **Satisfies →** ● the fifteen-mandate registry row **M10 — Bidirectional Binding**. ● the Pre-Emission Gate row 10 (M10 bidirectional-binding check).
- **Established by ↑** ● the fifteen-mandate registry (ratifies M10). ● the Pre-Emission Gate row 10. ● The ecosystem's existing practice — every `rules/*.md` already carries a `Bindings (§0.j five-direction)` section; this rule canonicalizes that practice rather than introducing it.
- **Gated by ←** ● The trivial-vs-non-trivial threshold (trivial linear artifacts without cross-references are exempt). ● `CLAUDE.md` always-loaded preamble. ● The path-filter declared in this rule's frontmatter (Markdown / docs / structural-artifact directories).
- **Cross-bound with ↔** ↔ `rules/visual-leverage.md` (M9 — diagram `cross-reference:` metadata is the diagram-side projection of the M10 reciprocal-binding surface). ↔ `rules/canonical-layout.md` (M12 — phase / sub-phase reporting binds producer / consumer / cross-references through M10 notation). ↔ `rules/disclosure-ledger.md` (M2 — binding emissions / closures / removals are recorded in the ledger). ↔ `rules/pre-emission-gate.md` (M4 — bar 10 of the gate enforces this rule's reciprocity invariant via the mechanical matcher). ↔ `rules/definitiveness.md` (M8 — placeholder bindings like `Drives → TBD` violate both this rule's reciprocity discipline and M8's closure-of-open-markers discipline). ↔ `rules/token-efficiency-rewrite.md` (L3 anchor loss is a half-edge failure on the same axis as §2 reciprocity). ↔ `rules/canonical-layout-reporting-tiers.md` (M10 — §4 reciprocal producer / consumer cross-references operationalize M10 reciprocity at the artifact layer). ↔ `rules/pre-emission-gate-bars.md` (this rule is among the M-rules named in the gate's "Failure → action" column; the bar-level catalog cross-binds each). ↔ `rules/propagation.md` (binding reciprocity). ↔ `rules/systemic-participation.md` (M10 — the four systemic relations populate the M10 five-direction binding section). ↔ `rules/systemic-participation-relations.md` (M10 — the four systemic relations populate the M10 five-direction binding section). ↔ `rules/token-efficiency-rewrite-protocol.md` (§2 — L3 anchor loss is a half-edge failure on the same axis).
