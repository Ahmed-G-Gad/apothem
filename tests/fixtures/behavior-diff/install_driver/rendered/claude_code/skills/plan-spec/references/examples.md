<!-- SPDX-License-Identifier: MIT -->

## Examples

### Example 1 — Greenfield Forge run

```text
$ /plan-spec ~/notes/migration-plan-draft.md --suite-name database-migration-v2

[Phase 1] Reading 12K-token prose source. Suite folder created at <project-root>/.apothem/plans/database-migration-v2/.
[Phase 1] Forge file initialized at <project-root>/.apothem/plans/database-migration-v2/_inputs/forge.md.
[Phase 2] Consideration pass — 38 items captured; G0 ◇ Consideration-Log-Complete satisfied.
[Phase 2] Tension surfaced (rollback-strategy ambiguity); structured inquiry fired at G3.
[Phase 3] Potency Map — 47 element/potent-form pairings; 0 unpaired.
[Phase 4] Preservation Audit — L1 PASS (124 distinctive phrases all grep-matched); L2 PASS (47 requirements operationally enforced); L3 PASS (12 ALL-CAPS / repeated-intensifier loci preserved).
[Phase 5] Expertise — 5 of 7 axes applied; 2 explicitly N/A-with-rationale.
[Phase 6] Question-Resolution Sweep — 6 questions across 4 gates; 0 P0-unresolved; 0 P1-unresolved.
[G4] Four-Discipline Invariant — PASS on all 6 conditions; promotion authorized.
[G4] Promoting forge.md → _spec/spec.md.
[G5] Handoff Manifest emitted at <project-root>/.apothem/plans/database-migration-v2/_inputs/handoff-manifest.yml; downstream: /plan-generate.
```

### Example 2 — Iterative refinement (`--refine-existing`)

```text
$ /plan-spec --refine-existing <project-root>/.apothem/plans/database-migration-v2

[Phase 1] Existing spec.md detected (1,247 lines). Treating as starting point.
[Phase 2] Re-consideration pass — 4 new items captured (delta against the prior Consideration Log).
[Phase 3] Re-pairing pass — 2 new potent-form pairings added.
[Phase 4] Preservation Audit re-run — L1 PASS preserved; L2 PASS preserved; L3 PASS preserved.
[Phase 5] Expertise delta — 1 newly-applicable axis surfaced.
[Phase 6] Question-Resolution Sweep — 2 new questions surfaced; 0 unresolved.
[G4] Invariant PASS; spec.md updated in place; forge.md not used (refinement mode).
[G5] Handoff Manifest re-emitted with incremented invocation_sequence.
```
