<!-- SPDX-License-Identifier: MIT -->

# Potency Map Template

The Potency Map is the deliverable of Discipline D2 (EXTREME Potency) inside `src/apothem/commands/plan-spec.md`. Every preserved prose element pairs with its potent operational form here; missing pairings raise a `**P1**` block at emission.

## Purpose

Realize the spec's organizing principle: **potency alone is inert archiving; potency is the ceiling, preservation is the floor**. The Forge does not merely retain the user's prose — it pairs every retained element with the operational shape that lets the spec actively drive downstream commands. The Potency Map is the audit surface where each pairing is recorded.

## Pairing dictionary (canonical)

| Preserved prose class | Paired potent operational form |
| --------------------- | ------------------------------ |
| Reliability requirement | Service Level Objective (SLO) with measurable threshold + measurement window |
| Flow / sequence | Mermaid `flowchart` (control flow) · `sequenceDiagram` (interaction) · `stateDiagram-v2` (state machine) |
| Decision / choice | Annotated structured inquiry option set with the three-segment body (rationale / recommendation / default-pointer) |
| Ordered execution | Sprint apparatus with Sprint Goal · DoR · DoD · Sprint Review · Retrospective · Velocity Log entry |
| Cross-reference | Canonical bidirectional binding (Drives → · Satisfies → · Established by ↑ · Gated by ← · Cross-bound with ↔) |
| Definitive statement | Airtight input-class coverage (closed-set enumeration with explicit-N/A attestation on residue) |
| Authoritative datum | Inquiry surfacing with `<USER-CONFIRM:kind=...>` placeholder until operator-supplied |

The dictionary is open-extensible: when a prose element does not match any of the seven canonical pair-classes above, the row records the bespoke pairing with a one-sentence rationale.

## Schema

| Column | Type | Required | Content |
| ------ | ---- | -------- | ------- |
| `pair-id` | string | Yes | Stable identifier of the form `PM-NNN`. |
| `preserved-element` | string | Yes | Verbatim prose excerpt + source reference (`path:line` or `path:lines a-b`). |
| `paired-potent-form` | string | Yes | The operational shape paired to the element. Names the class from the dictionary above (or describes the bespoke pairing) and embeds the concrete artifact (the SLO threshold, the Mermaid block name, the option-set label, etc.). |
| `pairing-anchor` | string | Yes | The section anchor in `_spec/spec.md` where the paired potent form lands (e.g., `§3.4 SLOs`, `§4.2 Sprint apparatus`). |
| `transformation-effect` | string | Yes | One sentence describing what the pairing enables downstream — what the operational form lets a downstream command (`/plan-generate`, `/plan-execute`) do that the unpaired prose alone could not. |

## Sample row

```markdown
| pair-id | preserved-element | paired-potent-form | pairing-anchor | transformation-effect |
|---------|-------------------|--------------------|----------------|----------------------|
| PM-001  | "Reliability above all" — `notes/migration.md:14` | SLO: 99.95% read availability over a 28-day rolling window; measurement via the existing latency dashboard's 5xx-rate panel | `§3.4 Service Level Objectives` | Downstream `/plan-execute` can author a quality gate that fails when the rolling 28-day 5xx rate exceeds the SLO budget. |
| PM-002  | "We probably need to retry transient failures" — `notes/migration.md:31` | Decision option set: Add retry-with-backoff (Recommended) · Add at-least-once delivery · Defer | `§4.1 Reliability options` | The annotated option set lets the operator make the retry-strategy decision via the structured-inquiry channel at G3 with the three-segment body rather than a silent default. |
| PM-008  | "Migration must be reversible" — `notes/migration.md:48` | Definitive statement: airtight closed-set enumeration of the four reversibility paths (down-migration · feature-flag rollback · blue-green swap · point-in-time-restore); residue explicitly N/A-with-rationale | `§5.1 Reversibility paths` | Downstream `/plan-review` can verify every migration step in the plan suite traces back to one of the four reversibility paths. |
```

## Gate semantics

A row missing its `paired-potent-form` raises a `**P1**` block at emission. A row whose `paired-potent-form` is the empty string, the string `none`, or the string `TODO` is treated identically. Every preserved-element from the Consideration Log (rows classified `preserved-verbatim` or `amended-with-rationale`) must have a corresponding Potency Map row; missing rows raise the `**P1**` block.

## Cross-references

- Discipline D2 EXTREME Potency definition: `src/apothem/commands/plan-spec.md` §Workflow Phase 3.
- Source consideration item: `src/apothem/templates/consideration-log.md` (row's `item-id` is the upstream join key).
- Preservation Audit's verdict for the same clause: `src/apothem/templates/preservation-audit.md`.
