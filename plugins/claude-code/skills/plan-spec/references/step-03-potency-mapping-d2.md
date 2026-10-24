<!-- SPDX-License-Identifier: MIT -->

### Phase 3 — Potency Mapping (D2)

Every preserved prose element pairs with its potent operational form. The pairing dictionary:

| Preserved element | Potent operational form |
| ----------------- | ----------------------- |
| Reliability requirement | Service Level Objective (SLO) with a measurable threshold + measurement window |
| Flow / sequence | Mermaid diagram — `flowchart` (control-flow), `sequenceDiagram` (interaction-flow), `stateDiagram-v2` (state machine) |
| Decision / choice | Annotated structured-inquiry option set per `rules/interactive-questions.md` §3 three-segment body |
| Ordered execution | Sprint apparatus — Sprint Goal + DoR + DoD + Sprint Review + Retrospective + Velocity Log entry |
| Cross-reference | Canonical bidirectional binding per `rules/bidirectional-binding.md` (Drives → · Satisfies → · Established by ↑ · Gated by ← · Cross-bound with ↔) |
| Definitive statement | Airtight input-class coverage — closed-set enumeration with explicit-N/A attestation on the residue |
| Authoritative datum | Inquiry surfacing per `rules/authority-inquiry.md`, with a `<USER-CONFIRM:kind=...>` placeholder until operator-supplied |

**Potency Map deliverable.** Every preserved element + its paired potent form in the Potency Map appendix (Appendix B schema). Missing potent-form pairings = `**P1**` block per the D2 EXTREME Potency discipline.
