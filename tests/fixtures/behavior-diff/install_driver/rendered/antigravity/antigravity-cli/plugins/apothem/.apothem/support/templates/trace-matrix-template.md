<!-- SPDX-License-Identifier: MIT -->

# TRACE-MATRIX — `[SUITE_NAME]`

> **Purpose.** Bidirectional traceability surface mapping every spec requirement to the phase(s) that satisfy it, and every phase to the requirement(s) it covers. Closes the **all-tier** drift-prevention invariant per `src/apothem/rules/canonical-layout.md` §7.2: at small tier a narrative trace table inside `PLAN-NOTES.md` substitutes for this formal file; at medium and large tier the formal matrix is materialized at the suite root.
>
> **Stable-ID convention** (medium+ tier per §7.2). Every prose directive line in `_spec/spec.md` becomes `R-NNNN` (zero-padded sequential within the suite). Every phase number becomes `P-NN` (matching `phases/NN-kebab-topic/`). Sub-phases use `P-NN.L` (matching `phases/NN-topic/NNL-subtopic/`). The matrix's row × column cells record presence / absence of mapping with the cell legend at §1.
>
> **Update cadence.** Each `/plan-generate` cycle assigns IDs to new requirements + phases and writes the initial matrix. Each `/plan-review` cycle re-audits the matrix and flags `✗` cells (uncovered requirements) or orphan rows (requirements with no phase coverage). Each `/plan-execute` cycle does NOT modify the matrix — execution consumes IDs but does not assign them.

---

## 1. Cell Legend

| Cell | Meaning |
|---|---|
| `✓` | Covered — the phase satisfies the requirement (verified by the phase's own verification section). |
| `◐` | Partially covered — the phase satisfies part of the requirement; the remainder maps to another phase row. |
| `✗` | Uncovered — the phase claims to address the requirement but verification has not yet confirmed it. Findings flagged at `/plan-review`. |
| `N/A` | Not applicable — the phase is intentionally outside this requirement's scope; the row × column intersection is empty by design. |
| `—` | Vacuous — no relationship; the phase neither addresses nor excludes the requirement. (The default cell value when the matrix is initialized; cells transition to `✓` / `◐` / `✗` / `N/A` as coverage is declared.) |

---

## 2. Matrix — Requirements × Phases

> **Schema.** Rows are requirements (`R-NNNN`); columns are phases (`P-NN` and `P-NN.L`). The `Source` column anchors the row to a spec section. The `Verification surface` column names where the row's coverage is verified (a phase REPORT.md, a CI gate, an external audit).

| `R-ID` | Source | `P-01` | `P-02` | `P-03` | … | `P-NN` | Verification surface |
|---|---|---|---|---|---|---|---|
| `R-0001` | `_spec/spec.md §1` | `✓` | `—` | `—` | … | `✓` | `phases/01-.../REPORT.md` + `phases/NN-.../REPORT.md` |
| `R-0002` | `_spec/spec.md §2.1` | `—` | `—` | `—` | … | `—` | `phases/04-.../REPORT.md` (verification cell pending Phase 04 execution) |
| `R-NNNN` | `_spec/spec.md §M.N` | `[cell]` | `[cell]` | `[cell]` | … | `[cell]` | `[verification surface]` |

> **Wide-matrix tactic.** When phase count exceeds ~30, render the matrix as a flat list rather than a wide table — each `R-NNNN` row collapses to one line (`R-NNNN: covered by P-NN, P-NN; partial at P-NN; uncovered at P-NN`). Wide tables become unreadable past ~30 columns. The flat-list form preserves every cell value but trades two-dimensional readability for vertical scrollability.

---

## 3. Phase Coverage Summary (Inverse)

> **Schema.** The inverse projection — every phase enumerates the requirements it covers. This table is derived from §2 (no new information) but accelerates phase-side audit ("what does Phase NN actually deliver?"). Both projections must agree; disagreement is a structural failure on the bidirectional-binding axis.

| `P-ID` | Phase folder | Requirements covered | Partial coverage | Uncovered claims |
|---|---|---|---|---|
| `P-01` | `phases/01-kebab-topic/` | `R-0001`, `R-0007` | — | — |
| `P-NN` | `phases/NN-kebab-topic/` | `R-NNNN`, `R-NNNN` | `R-NNNN` | `R-NNNN` |

---

## 4. Orphan & Drift Audit

> **Schema.** Two classes of drift the matrix surfaces:
>
> 1. **Orphan requirement** — an `R-NNNN` row whose every cell is `—` or `N/A` (no phase claims coverage). The requirement is unaddressed; either (a) a new phase must be authored, (b) the requirement must be retired with explicit deferral logged in `PLAN-NOTES.md`, or (c) the requirement maps to an existing phase and the matrix is stale.
> 2. **Orphan phase** — a `P-NN` column whose every cell is `—` or `N/A` (the phase covers no requirement). The phase has no spec source; either (a) the spec is missing a requirement the phase implicitly addresses (author it and add the row), or (b) the phase's scope is unjustified and should be re-scoped.

| Drift class | ID | Description | Action |
|---|---|---|---|
| Orphan requirement | `R-NNNN` | `[one-sentence summary of what is unaddressed]` | `[author phase / retire with deferral / amend matrix]` |
| Orphan phase | `P-NN` | `[one-sentence summary of unsourced scope]` | `[author requirement / re-scope / retire]` |
| Stale partial coverage | `R-NNNN × P-NN` | `[one-sentence summary of why the cell stayed `◐` past its expected resolution]` | `[upgrade to ✓ via verification, downgrade to ✗ pending re-audit, or mark `N/A` with rationale]` |

---

## 5. Small-Tier Substitution

At small tier (per `src/apothem/rules/canonical-layout.md` §7.1), the formal matrix file is replaced by a narrative trace table inside the plan suite's notes file. The narrative form preserves the bidirectional invariant — every requirement names the phase(s) that satisfy it; every phase names the requirement(s) it covers — without the per-cell two-dimensional grid. A small-tier suite that grows past the 50-phase or 100-spec boundary materializes this formal matrix in the same change-set as the medium-tier transition (per §7.5 of the canonical-layout companion).

---

## 6. Bindings (§0.j five-direction)

- **Drives →** Every `/plan-review` cycle's drift audit (the §4 orphan tables produce review findings); every medium-to-large tier transition's matrix-decomposition step (the matrix splits along the sub-suite federation seam at large tier per `MASTER-INDEX.md` §5); every fresh-session understanding of "what spec coverage looks like" without re-reading every PHASE.md.
- **Satisfies →** `src/apothem/rules/canonical-layout.md` §7.2 drift-prevention trace-matrix mechanism (all-tier obligation); the §7.5 tier-transition emission contract for the small→medium boundary.
- **Established by ↑** `_spec/spec.md` §8 (D7 source — Q-011 three-tier ratification); `_spec/spec.md` §8.4 drift-prevention table (the trace-matrix row of which this template is the materialization).
- **Gated by ←** Tier classification (small-tier suites substitute the §5 narrative form); the assignment of stable IDs (`R-NNNN`, `P-NN`) at `/plan-generate` time gates this template's authorability — without IDs the matrix has no row / column keys.
- **Cross-bound with ↔** `src/apothem/templates/master-index-template.md` (sibling drift-prevention surface — its §1 spec-section anchor table and §2 phase anchor table together provide the row / column legends this matrix consumes); `PLAN-NOTES.md` (small-tier substitute lives there per §5; deferred-orphan rationales recorded there); every `phases/NN-kebab-topic/REPORT.md` (the verification-surface column resolves to a REPORT.md path); `_spec/spec.md` (the Source column anchors every row to a spec section).
