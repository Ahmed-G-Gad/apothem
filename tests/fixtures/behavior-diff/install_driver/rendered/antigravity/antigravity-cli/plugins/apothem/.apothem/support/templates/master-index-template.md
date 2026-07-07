<!-- SPDX-License-Identifier: MIT -->

# MASTER-INDEX — `[SUITE_NAME]`

> **Purpose.** Suite-root index for **medium+ tier** plan suites (≥50 phases or ≥100 spec sections / constraints per `src/apothem/rules/canonical-layout.md` §7 Three-Tier Scalability). The index is the queryable surface a fresh session, a `/plan-review` cycle, or a sub-suite-federation parent reads to navigate the suite without scanning every PHASE.md or spec section linearly.
>
> **When required.** Mandatory at medium and large tier; absent at small tier (in-line refs in `PLAN-NOTES.md` substitute). A small-tier suite that grows past the 50-phase or 100-spec boundary materializes this index in the same change-set per the §7.5 tier-transition rule.
>
> **Authoring cadence.** Initial authorship at the medium-tier transition; per-phase write-back appends a row to §2 on phase completion; spec-section evolution edits §1; decision ratification appends a row to §4. The index is always current with the suite — staleness is a structural failure on the orphan-output axis.

---

## 1. Spec-Section Anchor Table

> **Schema.** Every section of `_spec/spec.md` (and any sibling specifications under `_spec/supporting/`) emits one row. The `Stable ID` column carries the `R-NNNN` zero-padded sequential per the §7.2 stable-ID convention (cross-references survive section renames). The `Phase coverage` column lists every `P-NN` mapped to the requirement.

| Stable ID | Spec section | Title / one-line summary | Phase coverage | Notes |
|---|---|---|---|---|
| `R-0001` | `_spec/spec.md §1` | Mission statement | `P-01`, `P-20` | — |
| `R-0002` | `_spec/spec.md §2.1` | Token-usage optimization directive | `P-04` | Ratified at Q-014 |
| `R-NNNN` | `_spec/spec.md §M.N` | `[one-line summary]` | `P-NN`, `P-NN` | `[notes]` |

---

## 2. Phase Anchor Table

> **Schema.** Every phase folder under `phases/` emits one row. Sub-phases (`phases/NN-topic/NNL-subtopic/`) emit additional rows nested via the `Stable ID` (`P-NN.L`). The `Spec coverage` column lists every `R-NNNN` the phase satisfies.

| Stable ID | Phase folder | Title / scope | Spec coverage | Status |
|---|---|---|---|---|
| `P-01` | `phases/01-kebab-topic/` | `[scope summary]` | `R-0001`, `R-0007` | ✅ Complete |
| `P-02` | `phases/02-kebab-topic/` | `[scope summary]` | `R-0003` | ⏳ Pending |
| `P-NN` | `phases/NN-kebab-topic/` | `[scope summary]` | `R-NNNN`, `R-NNNN` | `[status]` |
| `P-NN.A` | `phases/NN-topic/NNA-subtopic/` | `[sub-phase scope]` | `R-NNNN` | `[status]` |

---

## 3. Constraint Anchor Table

> **Schema.** Every named constraint (architectural invariant, security floor, regulatory boundary, performance budget, compliance clause) emits one row. Constraints sit alongside requirements; the table separates them so binding analysis can audit each class independently.

| Stable ID | Constraint name | Source citation | Affected phases | Notes |
|---|---|---|---|---|
| `C-01` | `[constraint name]` | `_spec/spec.md §M.N` or `src/apothem/rules/<rule>.md §X` | `P-NN`, `P-NN` | `[mitigation / verification surface]` |

---

## 4. Decision Anchor Table

> **Schema.** Every numbered decision (D-1, D-2, …) the suite ratifies emits one row. Decisions are the resolved-structured inquiry surface plus any agent-driven architectural decisions recorded with operator approval. Cross-references in PLAN-NOTES.md and PHASE.md files cite the `Stable ID` so renames preserve the link.

| Stable ID | Decision title | Resolution | Source | Affected phases |
|---|---|---|---|---|
| `D-1` | `[decision name]` | `[one-sentence resolution]` | Q-NNN in `PLAN-NOTES.md` Wave N | `P-NN`, `P-NN` |

---

## 5. Cross-Suite Federation (Large Tier Only)

> **Schema.** Large-tier suites decompose into multiple child suites with parent-child relationship per `src/apothem/rules/canonical-layout.md` §7.1 Decomposition. The parent's MASTER-INDEX.md carries this section listing every child suite plus its own MASTER-INDEX.md path. Child suites omit this section (they are small or medium per §7.1).

| Child suite | Path | Tier | Phase count | Spec count | MASTER-INDEX path | Last rollup |
|---|---|---|---|---|---|---|
| `[child-suite-name]` | `<project-root>/.apothem/plans/[child-suite]/` | `medium` | NN | NNN | `[child-suite]/MASTER-INDEX.md` | `[ISO-8601 date]` |

**Federation invariants:**

- Every `R-NNNN` requirement in the parent index resolves to at least one child suite's phase coverage.
- Every cross-child reference uses the parent's stable ID space (no child-local IDs leak into parent navigation).
- Child suite tier transitions (small ↔ medium) propagate to this section in the same change-set.

---

## 6. Validation Cadence

> **Schema.** The medium and large tiers run `/plan-review` incrementally rather than full-suite-each-pass. This section records the rolling validation state — which phase groups have been audited in the current cycle, which spec sections have been re-validated, when the next sampled-rollup is due.

| Audit class | Last cycle | Coverage this cycle | Next due |
|---|---|---|---|
| Per-phase verification | `[ISO-8601 date]` | `P-NN..P-NN` | `[ISO-8601 date]` |
| Phase-rollup verification (groups of 5-20) | `[ISO-8601 date]` | `[group ID]` | `[ISO-8601 date]` |
| Spec-section sampled audit | `[ISO-8601 date]` | `R-NNNN..R-NNNN` | `[ISO-8601 date]` |
| Suite-rollup (large only) | `[ISO-8601 date]` | full | `[ISO-8601 date]` |

---

## 7. Bindings (§0.j five-direction)

- **Drives →** Every fresh-session navigation of this suite (the index is the first read after PROGRESS.md per `src/apothem/rules/context-management.md` §6 Blind Bootstrap at medium+ tier); every `/plan-review` cycle's audit-coverage decision (the §6 cadence table records what was last audited and what is due); every cross-suite federation parent's child-suite enumeration at large tier.
- **Satisfies →** `src/apothem/rules/canonical-layout.md` §7 Three-Tier Scalability (medium+ tier indexing requirement); the §7.2 drift-prevention `MASTER-INDEX.md` mechanism; the §7.5 tier-transition emission contract.
- **Established by ↑** `_spec/spec.md` §8 (D7 source — Q-011 three-tier ratification); the medium-tier transition decision recorded in PLAN-NOTES.md when the suite crosses the 50-phase or 100-spec boundary.
- **Gated by ←** Tier classification (small-tier suites omit this index); operator's borderline-tier structured inquiry resolution per §7.3 of the canonical-layout companion when phase count sits within ±10% of a boundary.
- **Cross-bound with ↔** `src/apothem/templates/trace-matrix-template.md` (sibling drift-prevention surface; the trace matrix's row × column shape and this index's anchor tables together close the bidirectional traceability invariant); `PROGRESS.md` (per-phase status mirrors the §2 Phase Anchor Table's Status column); `_spec/spec.md` (every §1 row maps back to a spec section); `PLAN-NOTES.md` (every §4 row maps back to a Q-NNN resolution); every `phases/NN-kebab-topic/PHASE.md` (every §2 row resolves to a PHASE.md file).
