<!-- SPDX-License-Identifier: MIT -->

### Phase 4 — Design-Artifact Emission

Emit the suite's `_inputs/design.md` with the following canonical sections:

1. **`## §1 Executive Summary`** — one paragraph stating the architectural mission + the seven-axes coverage + the component count.
2. **`## §2 ... §N` Per-Component Sections** — one section per principal component carrying Purpose · Interface · Contracts · Bindings (§0.j five-direction). Components ordered by dependency depth (innermost domain first; outermost adapters last) per Clean Architecture layer discipline.
3. **`## §Diagrams` Mermaid Diagrams** — every structural relationship carries its diagram per `rules/visual-leverage.md` §1 trigger catalog. Required diagram classes: architecture sketch (`graph TD` / `flowchart`); component-interaction sequence (`sequenceDiagram`); state machine (`stateDiagram-v2`) where applicable; dependency graph (`graph LR`). Every diagram carries the metadata header (`%% verified: <ISO-8601> %%` + `%% provenance: <source> %%` + `%% cross-reference: <peer> %%`) per the rule §2.
4. **`## §Decision Records`** — every ratified architectural decision recorded as `AD-<N>: <one-sentence summary>` followed by Rationale (concrete-driver classes per `rules/interactive-questions-canonical-shapes.md` §3.2.1) + Alternatives Considered + Trade-offs + Reversibility note.
5. **`## §Validation Gate Outcome`** — the Phase 5 fifteen-bar gate attestation block per `rules/pre-emission-gate.md` §2.
6. **`## §Bidirectional Binding Matrix`** — the square matrix authored at Phase 3, when the ≥5-components-with-≥3-peers threshold triggers.
7. **`## §Bindings (§0.j five-direction)`** — the artifact's own outward bindings to upstream and downstream surfaces.

Apply incremental generation per `rules/large-file-generation.md` when the artifact exceeds 500 lines. Plan the section structure before authoring; emit the first section via Write; append subsequent sections via Edit; verify transition coherence at every boundary.
