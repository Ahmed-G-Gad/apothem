<!-- SPDX-License-Identifier: MIT -->

# Consideration Log Template

The Consideration Log is the deliverable of Discipline D1 (Meticulous Consideration) inside `src/apothem/commands/plan-spec.md`. Every transformation choice the Forge makes traces back to one row in this log; an empty / skeletal / sham log fires the D1 ◇ Gate at P0 severity and blocks emission.

## Purpose

Capture every consideration item surfaced during the prose-to-spec transformation — the directives, intentions, rationales, adjacent-domain scans, second-order consequences, and contradictions that the double-read + triple-extract pass produced. The log is the primary evidence that Discipline D1 (double-read · triple-extract · adjacent-domain scan · second-order-consequence enumeration · contradiction surfacing · persona/register/voice inference) executed in full.

## Schema

| Column | Type | Required | Content |
| ------ | ---- | -------- | ------- |
| `item-id` | string | Yes | Stable identifier of the form `CL-NNN` (zero-padded three-digit ordinal). Used as the join key from the Potency Map (paired potent form), the Preservation Audit (preservation verdict per level), and any inline `[Expertise amendment — axis: X — rationale: ...]` markers in the emitted spec. |
| `source` | string | Yes | The verbatim prose excerpt that produced this consideration. Includes the source-file reference (`path:line` or `path:lines a-b`). Verbatim-quoted; no paraphrase. |
| `classification` | enum | Yes | One of `preserved-verbatim` (clause woven into the spec at an analogous locus without rewriting) · `amended-with-rationale` (clause woven with a documented amendment) · `added-with-rationale` (no source clause; the consideration extends the prose with a rationale traceable to an adjacent-domain scan or second-order-consequence enumeration). |
| `disposition` | string | Yes | The transformation choice: where the consideration lands in the spec (section anchor) and how it manifests (e.g., as a requirement, a constraint, a Sprint Goal element, an annotation marker). |

## Sample row

```markdown
| item-id | source | classification | disposition |
|---------|--------|----------------|-------------|
| CL-001  | "Reliability above all" — `notes/migration.md:14` | preserved-verbatim | Becomes the Sprint Goal's load-bearing clause at `_spec/spec.md` §2.1; paired in Potency Map row PM-001 with the SLO `99.95% read availability over a 28-day rolling window`. |
| CL-014  | "Probably should think about caching" — `notes/migration.md:62` | amended-with-rationale | Tension surfaced via the structured-inquiry channel at G3; operator selected `Add caching as a deferred capability` over `Add caching as a sprint commitment`; lands at `_spec/spec.md` §3.4 with the deferral rationale captured. |
| CL-027  | (no source — adjacent-domain scan) | added-with-rationale | Adjacent-domain scan on `database` surfaced the connection-pool-exhaustion failure mode the prose did not name; lands at `_spec/spec.md` §5.2 Failure Modes; rationale points to the Postgres `max_connections` operational pattern. |
```

## Gate semantics

The D1 ◇ Gate fires at G0 (Consideration-Log-Complete standing). An empty log, a log carrying fewer rows than there are distinctive prose phrases, or a log whose `classification` is uniformly `preserved-verbatim` (signal that no thought was applied beyond mechanical transcription) all fail the gate. P0 severity; blocks emission.

## Cross-references

- Discipline D1 Meticulous Consideration definition: `src/apothem/commands/plan-spec.md` §Workflow Phase 2.
- Pairing into the Potency Map: `src/apothem/templates/potency-map.md`.
- Preservation Audit's verdict per row: `src/apothem/templates/preservation-audit.md` (the Preservation Audit's `clause-id` shares the namespace with this log's `item-id` for traceability).
- Question-Resolution Audit's row when a consideration surfaced via the structured-inquiry channel: `src/apothem/templates/question-resolution-audit.md`.
