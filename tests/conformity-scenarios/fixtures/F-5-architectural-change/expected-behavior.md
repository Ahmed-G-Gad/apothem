---
fixture: F-5
title: Architectural-change request
spec-source: _spec/spec.md §7.1 row 5
mandates: [M9, M10, M11, M12]
---

<!-- SPDX-License-Identifier: MIT -->

# F-5 — Architectural-change request

## Spec binding

This fixture realizes spec §7.1 row 5: **Architectural-change
request** (refactor a multi-module subsystem) testing
**M9 + M10 + M11 + M12**. The host carries a three-module
checkout backend (`auth`, `billing`, `notifications`) plus a
shared `db` session factory, with direct cross-module Python
imports producing tight synchronous coupling. The
`REFACTOR-REQUEST.md` artifact at the host root names the
operational drivers (test-isolation pain; degraded-notifications
slows the charge path) and asks for an event-bus migration
producing four named deliverables (architecture diagram, binding
matrix, sprint structure, directory shape).

The retrofit's correct behavior is to treat the request as
**non-trivial multi-step structural work** per the trivial
threshold ratification at user-scope CLAUDE.md §8.1 and respond
with the full apparatus M9 + M10 + M11 + M12 demand.

## Synthetic host description

| Path | Role | Cross-module surface present |
|---|---|---|
| `before/src/pulse/auth.py` | Session/token validation | imports `db` and `notifications` directly. |
| `before/src/pulse/billing.py` | Order pricing, charge, refund | imports `auth`, `db`, `notifications` directly. |
| `before/src/pulse/notifications.py` | Outbound transactional email | imports `db` directly; consumed by `auth` and `billing`. |
| `before/src/pulse/db.py` | Shared session factory | imported by every sibling module. |
| `before/REFACTOR-REQUEST.md` | The architectural-change request | Names the four deliverables the agent must produce. |

The cross-module call graph is observable by static inspection
of the import statements; it is the input to the binding-matrix
deliverable.

## Mandate-firing expectations

### M9 — Visual Leverage

`src/apothem/rules/visual-leverage.md` §1 declares architecture
to be a structural subject matter; a current-reality diagram
(plus a target-state diagram for the proposed refactor) is
mandatory. The agent's emitted artifact set carries:

- A current-reality Mermaid `graph TD` diagram of the
  before-state import graph.
- A target-state Mermaid `graph TD` diagram of the post-refactor
  event-bus topology, carrying the literal label
  `[Aspirational — target: <name>; date: <ISO-8601>]` per §4
  aspirational-state declaration.
- Both diagrams carry the `%% verified: <ISO-8601> %%` and
  `%% provenance: <hand-authored | extracted-from <source>> %%`
  metadata header per §2 provenance discipline.

### M10 — Bidirectional Binding Matrix

`src/apothem/rules/bidirectional-binding.md` §4 declares the
matrix mandatory when an artifact carries five or more elements
with bindings AND at least one element binds to three or more
peers. The four-module subsystem (`auth`, `billing`,
`notifications`, `db`) plus the new event-bus element trips the
threshold. The agent emits a bidirectional matrix recording the
`Drives →` / `Driven by ←` / `Cross-bound with ↔` relations
both before and after the refactor; reciprocity is preserved on
every edge per the §2 half-edge invariant.

### M11 — Agile Sprint Structure

`src/apothem/rules/agile-sprints.md` §1 declares the canonical
seven-element apparatus for non-trivial multi-step work. The
agent's migration plan emits each element with the literal
heading from the rule:

- **Sprint Goal** — one outcome-shaped sentence.
- **Sprint Backlog** — INVEST-shaped work-items with story-point
  estimates.
- **Definition of Ready** — checklist applied at sprint entry.
- **Definition of Done** — checklist applied at sprint exit.
- **Sprint Review** — inspection record.
- **Sprint Retrospective** — Continue / Stop / Start sections.
- **Velocity tracking** — sized against the operational-driver
  pressure (test-isolation pain; charge-path resilience).

### M12 — Canonical Layout

`src/apothem/rules/canonical-layout.md` §2 declares the
canonical-layout discipline. The agent's deliverables sit at a
single ratified location the host can adopt — proposed as
`migration/event-bus-extraction/{architecture-current.md,
architecture-target.md, binding-matrix.md, sprint-plan.md,
directory-shape.md}` with a top-level
`migration/event-bus-extraction/README.md` indexing the five
artifacts and naming each artifact's producer / consumer
relations. Orphan-output prevention per §3 — every artifact
carries a producer attribution (the agent), a consumer (the
team executing the migration), and an index entry (the README).

## Agent-output contract

When apothem is asked to "respond to the refactor request" or
similar, the emitted artifact set satisfies:

1. **Six artifacts** at canonical paths under
   `migration/event-bus-extraction/` (the four deliverables
   from `REFACTOR-REQUEST.md` plus a README index plus the
   current-reality diagram as the architecture deliverable's
   "before" leg).
2. **Two diagrams** with provenance metadata and aspirational
   labeling on the target-state diagram (M9).
3. **One binding matrix** showing reciprocal bindings for every
   cross-module edge before and after the refactor (M10).
4. **One sprint plan** carrying the seven-element apparatus
   (M11).
5. **One directory-shape proposal** at the canonical path
   (M12).
6. **Disclosure ledger** carrying:
   - `[Diagram — emitted: …]` rows for both diagrams.
   - `[Output — emitted: …]` rows for each migration artifact
     citing the canonical-location verification.
   - `[Sprint — opened: <sprint-id>; goal: …; backlog-size: …]`
     row for the sprint-structure artifact.

## Pass signals (consumed by 09B verify driver)

- [ ] Six artifacts present at
      `migration/event-bus-extraction/` (or the host's discovered
      equivalent if the host has a ratified migration location).
- [ ] Both Mermaid diagrams parse — the verifier extracts the
      ` ```mermaid ` fences and confirms each opens with the
      canonical `graph TD` / `flowchart` directive plus the
      `%% verified: %%` and `%% provenance: %%` metadata
      comments.
- [ ] The target-state diagram carries the
      `[Aspirational — target: <name>; date: <ISO-8601>]` label.
- [ ] The binding matrix table carries the diagonal `—`,
      reciprocal symbols on every off-diagonal edge (`→` ↔ `←`,
      `↔` self-reciprocal), and an entry for every cross-module
      pair both before and after.
- [ ] The sprint plan carries all seven canonical headings
      (Sprint Goal, Sprint Backlog, Definition of Ready,
      Definition of Done, Sprint Review, Sprint Retrospective,
      Velocity).
- [ ] Every artifact carries a `Bindings (§0.j five-direction)`
      section per `src/apothem/rules/bidirectional-binding.md`
      §1.
- [ ] The fifteen-bar attestation block records `M9: pass`,
      `M10: pass`, `M11: pass`, `M12: pass` with the relevant
      surfaces enumerated.

## Fail signals (release-blockers)

- Architectural prose with no Mermaid diagram (M9 systematic
  under-utilization per the rule's failure tells).
- A target-state diagram missing the `[Aspirational — …]` label
  (M9 §4 fidelity violation — depicting future state as current).
- A binding matrix where `auth → notifications` lacks the
  reciprocal `notifications ← auth` row (M10 half-edge).
- A migration plan without the Sprint Goal heading or with the
  goal phrased as an activity ("refactor the cross-module
  imports") rather than an outcome ("the charge path remains
  green when the notifications backend is degraded") (M11 §1.1
  outcome-shaped invariant).
- Migration artifacts scattered across ad-hoc locations
  (`docs/refactor.md`, `notes/event-bus.md`) instead of a single
  canonical layout (M12 §2 orphan-output prevention).
- Any artifact missing the §0.j five-direction Bindings section
  (M10 reciprocal-binding floor).

## Bindings (§0.j five-direction)

- **Drives →** Sub-phase 09B `verify.py`.
- **Satisfies →** Spec §7.1 row 5. Sub-phase 09A task 5.
- **Established by ↑** Sub-phase 09A `PHASE.md` task 5.
  Spec §7.1 row 5.
- **Cross-bound with ↔** Sibling fixture F-10 (multi-mandate
  stress test, authored at sub-phase 09B). F-5 specifically tests
  the structural-mandate quartet (M9 + M10 + M11 + M12); F-10
  re-exercises the same quartet alongside the other eleven
  mandates in a single integrated invocation.
