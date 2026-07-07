<!-- SPDX-License-Identifier: MIT -->

# Sample Artifact — Narrative Marker Leak (FAIL)

This fixture is the FAIL case for the `narrative-marker-leak` sub-check of
`option-annotation-grep`. The recommended option correctly carries the
canonical `(Recommended)` postfix on its label, but it ALSO repeats the marker
inside the `recommendation:` body segment — the marker lives solely in the
label, never in the narrative, so the body repetition is a leak. The body must
carry verifiable concrete-driver evidence instead of the marker string.

structured inquiry: question `Which migration approach should run?`

- `Patch (Recommended)`:
  rationale: Applies the minimal diff to the schema; preserves every existing row.
  recommendation: recommended (Recommended) — observed-state shows the migration target is one additive column with no type change.
  default-pointer: Patch — safe because the change is reversible via a down-migration.
- `Full rewrite`:
  rationale: Reconstructs the schema from scratch.
  recommendation: discouraged — observed-state shows scope is one additive column, far below the rewrite threshold.
  default-pointer: Patch — the rewrite path is documented as inferior here.

multiSelect: false
