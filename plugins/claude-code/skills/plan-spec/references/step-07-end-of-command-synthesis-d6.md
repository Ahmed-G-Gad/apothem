<!-- SPDX-License-Identifier: MIT -->

### End-of-Command Synthesis (D6)

Just before G5 Handoff Manifest emission, fire ONE structured inquiry per D6 (Q-022) with the spec §7.4 form. The invocation MUST satisfy `rules/interactive-questions.md` §2 (canonical schema) + §3 (three-segment body) + §4.1 (closed recommendation taxonomy) + the H4/H6 invariants from `rules/interactive-questions-sweep-matchers.md` (every option carries all three body segments; the `(Recommended)` label postfix bidirectionally binds the body `recommendation: recommended` value):

- `question:` `Spec phase complete. Are there any suggested improvements, ambiguities, contradictions to surface before handoff?`
- `header:` `End synthesis`
- `multiSelect:` `false`
- Option `All clear (Recommended)`:
  - `rationale:` No deferred concerns; the spec command's outputs are ready for handoff to /plan-generate.
  - `recommendation:` recommended — cites class 6 observed-state: the command's crystallization summary shows zero open unknowns and zero contradictions at the synthesis boundary.
  - `default-pointer:` no-default: user decision required (operator's final ratification surface; silent default would bypass the operator's judgment on long-lived spec content).
- Option `Surface findings`:
  - `rationale:` Operator has substantive concerns to raise before handoff; agent captures them inline in the synthesis record and routes to /plan-generate as input rather than as authoritative spec.
  - `recommendation:` acceptable
  - `default-pointer:` no-default: user decision required.
- Option `Defer findings`:
  - `rationale:` Operator notes findings but defers resolution to a later cycle; agent appends `[Deferral — out-of-scope: <description>; tracking: <PLAN-NOTES.md or follow-up issue>]` per `rules/disclosure-ledger.md`.
  - `recommendation:` acceptable
  - `default-pointer:` no-default: user decision required.

The selection routes the post-synthesis flow: `All clear` proceeds to G5 Manifest emission unchanged; `Surface findings` captures the findings inline at the synthesis record in PLAN-NOTES.md and re-runs Phases 4–6 on affected loci; `Defer findings` appends the deferral marker to the disclosure ledger and emits G5 with the deferral routed via the Manifest's `deferrals` field per `rules/disclosure-ledger.md`.
