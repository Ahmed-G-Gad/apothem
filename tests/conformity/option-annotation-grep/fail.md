<!-- SPDX-License-Identifier: MIT -->

# Sample Artifact — Per-Option Recommended Bind (FAIL)

This fixture is the FAIL case for `option-annotation-grep`. Two bind violations
are present: the first option's body is `recommended` but its label uses the
banned lowercase `(recommended)` variant rather than the canonical capital
`(Recommended)`; the second option carries the canonical postfix on its label
while its body recommendation is not `recommended` (a spurious postfix). The
per-option bind flags both directions.

structured inquiry: question `Which migration approach should run?`

- `Patch (recommended)`:
  rationale: Applies the minimal diff to the schema; preserves every existing row.
  recommendation: recommended — observed-state shows the migration target is one additive column with no type change.
  default-pointer: Patch — safe because the change is reversible via a down-migration.
- `Full rewrite (Recommended)`:
  rationale: Reconstructs the schema from scratch.
  recommendation: discouraged — observed-state shows scope is one additive column, far below the rewrite threshold.
  default-pointer: Patch — the rewrite path is documented as inferior here.

multiSelect: false
