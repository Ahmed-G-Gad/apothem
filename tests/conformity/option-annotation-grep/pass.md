<!-- SPDX-License-Identifier: MIT -->

# Sample Artifact — Per-Option Recommended Bind (PASS)

This fixture is the PASS case for `option-annotation-grep`. The single-select
question surfaces two annotated options. The recommended option carries the
canonical capital `(Recommended)` postfix on its own label; the non-recommended
option carries no postfix. The bidirectional bind holds in both directions and
the single-select cardinality (at most one recommended option) is satisfied.

structured inquiry: question `Which migration approach should run?`

- `Patch (Recommended)`:
  rationale: Applies the minimal diff to the schema; preserves every existing row.
  recommendation: recommended — observed-state shows the migration target is one additive column with no type change.
  default-pointer: Patch — safe because the change is reversible via a down-migration.
- `Full rewrite`:
  rationale: Reconstructs the schema from scratch.
  recommendation: discouraged — observed-state shows scope is one additive column, far below the rewrite threshold.
  default-pointer: Patch — the rewrite path is documented as inferior here.

multiSelect: false
