<!-- SPDX-License-Identifier: MIT -->

# Expertise-Gap Log Template

The Expertise-Gap Log is the deliverable of Discipline D4 (Extensive Expertise) inside `src/apothem/commands/plan-spec.md`. Every transformation in the prose-to-spec run records which of the seven axs of breadth applied, which were not applicable (with rationale), and which surfaced an expertise-envelope limit needing routing.

## Purpose

Realize the operational form of D4: every transformation explicitly attests its expertise posture. Inline `**[Expertise amendment — axis: X — rationale: ...]**` markers in the emitted spec point back to rows in this log. Under-applied axs raise the D4 ◇ Gate at `**P1**` severity and block emission until either the axis applies (with a recorded amendment) or the row records `not-applicable-with-rationale` or `expertise-envelope-limited` with a downstream routing target.

## The seven axs (canonical)

| Axis | Scope |
| ---- | ----- |
| Domain | Direct subject-matter expertise on what the prose is about (e.g., database internals, payment systems, ML training). |
| Adjacent-domain | Expertise on neighboring domains whose patterns, failure modes, or vocabularies inform the prose's domain by analogy. |
| Meta-engineering | The discipline-of-engineering itself: SOLID, clean architecture, dependency direction, testability, reversibility. |
| Operational | Runtime behavior: deployment, observability, on-call rotations, incident response, runbooks. |
| Process | The work-process surface: sprint cadence, code review, RFC writing, change management, retrospection. |
| Scholarly-technical-literature | Citations to peer-reviewed papers, RFCs, industry case studies, formal specifications. |
| Second-order-systems-thinking | Implications a step removed: what the prose's requirements imply for downstream artifacts the prose does not name. |

## Schema

| Column | Type | Required | Content |
| ------ | ---- | -------- | ------- |
| `axis` | enum | Yes | One of the seven canonical axs above. |
| `disposition` | enum | Yes | `applied` (axis amended the spec; one or more inline amendment markers point here) · `not-applicable-with-rationale` (axis is genuinely orthogonal to the prose's domain; rationale captures why) · `expertise-envelope-limited` (axis would apply but the Forge's expertise envelope is insufficient; routing target captures where the gap closes). |
| `attestation-locus` | string | Conditional | Section anchor in `_spec/spec.md` where the inline amendment marker lands; required when `disposition: applied`. Multiple loci are admissible — list them comma-separated when the axis amends more than one section. |
| `rationale` | string | Conditional | One-sentence justification; required when `disposition: not-applicable-with-rationale` or `expertise-envelope-limited`. For `expertise-envelope-limited`, the rationale also names the expertise-gap closure target (operator clarification, downstream specialist consultation, or deferred routing). |
| `routing-target` | string | Conditional | When `disposition: expertise-envelope-limited`, names the downstream surface that closes the gap — e.g., `<USER-CONFIRM:kind=...>` placeholder, expert-consultation deferral, downstream-command consumption. |

## Sample row

```markdown
| axis | disposition | attestation-locus | rationale | routing-target |
|------|-------------|-------------------|-----------|----------------|
| Domain | applied | §2.1 Sprint Goal, §3.4 SLOs | — | — |
| Adjacent-domain | applied | §3.5 Failure modes (analog: Postgres connection-pool exhaustion) | — | — |
| Meta-engineering | applied | §4.2 Reversibility paths (closed-set enumeration), §5.1 Composition root | — | — |
| Operational | applied | §3.4 SLO measurement window, §6.1 Runbook pointer | — | — |
| Process | applied | §7 Sprint cadence | — | — |
| Scholarly-technical-literature | not-applicable-with-rationale | — | The prose covers an internal migration with no peer-reviewed scholarship to cite; informal industry references already inline at §3.5 are sufficient. | — |
| Second-order-systems-thinking | applied | §5.2 Downstream consequences (table) | — | — |
```

## Gate semantics

The D4 ◇ Gate fires at G4 (Pre-emission). All seven axs appear in the log. Any axis with `disposition: applied` carries a non-empty `attestation-locus`; any with `not-applicable-with-rationale` or `expertise-envelope-limited` carries a non-empty `rationale`. A row with `applied` but missing `attestation-locus`, or with `not-applicable-with-rationale` but missing `rationale`, is a gate failure (`**P1**` block).

When more than two axs carry `disposition: not-applicable-with-rationale`, the gate fires a soft warning: the prose may be narrowly scoped, OR the Forge may have under-applied breadth. The warning surfaces in the emitted spec's preamble and routes to the operator's review on next iteration.

## Cross-references

- Discipline D4 Extensive Expertise definition: `src/apothem/commands/plan-spec.md` §Workflow Phase 5.
- Inline amendment markers: appear in the emitted `_spec/spec.md` as `**[Expertise amendment — axis: X — rationale: ...]**` annotations whose `axis` field joins to a row in this log.
