<!-- SPDX-License-Identifier: MIT -->

## Pipeline Contract

**Pipeline position — conditional mid-chain.** This command sits between `/plan-review` and `/plan-execute` only for architecture-bearing suites. Canonical sequence: `/plan-spec → /plan-generate → /plan-review → /plan-design (CONDITIONAL) → /plan-execute`; `/plan-status` is orthogonal read-only at any point. It consumes the reviewed plan suite plus its review-augmented Handoff Manifest and emits the design artifact downstream `/plan-execute` invocations consume. Non-architecture-bearing suites skip this command explicitly and proceed from `/plan-review` to `/plan-execute` with the reviewed suite as the authoritative trace surface.

**Handoff Manifest.**

- **Consumed.** The suite's `_inputs/handoff-manifest.yml` per `src/apothem/schemas/handoff-manifest.yaml`. The upstream manifest carries the Review Scorecards from `/plan-review`. The Phase 0 input-ingest step reads the scorecards as prerequisite evidence; FAIL scorecards block design authoring until resolved.
- **Emitted.** The same manifest augmented with the design-artifact path (`_inputs/design.md`), the design-gate attestation block from Phase 5, the per-axis attestation against the seven-axes-of-breadth taxonomy, and the design's Bidirectional Binding Matrix summary. Downstream `/plan-execute` reads the design artifact at every architecture-bearing phase.

**Pre-flight inquiry set.** Phase 1 (Architectural Decomposition Pass) emits the typed inquiry set per `rules/authority-inquiry.md`. Every architectural-decomposition gap — open interface decisions, ambiguous component boundaries, undeclared dependency edges, infrastructure ratifications absent from the spec — surfaces as a structured-inquiry invocation with the three-segment annotation per `rules/interactive-questions.md` §3.

**Pre-emission gate.** Phase 5 (Design Validation Gate) runs the fifteen-bar pre-emission gate per `rules/pre-emission-gate.md` against the candidate design artifact before promotion. The gate attestation block is recorded inside the emitted artifact and surfaced in the Manifest. Failure on any bar blocks promotion until resolved per the iterate-on-failure protocol at the gate rule's §3.

**Applicability gate.** Before Phase 0, classify the suite as architecture-bearing or non-architecture-bearing. Architecture-bearing surfaces include component boundaries, source layout, public interfaces, protocols, schemas, configuration contracts, cross-component data flow, release topology, security boundaries, performance/concurrency posture, observability contracts, and adapter behavior. If none are present, STOP without emitting `_inputs/design.md`; record that `/plan-design` is not applicable and hand off to `/plan-execute`. The skip is a positive classification, not a failure.

### Inquiry Cadence

This command operates at **maximal structured-inquiry saturation**. Every architectural-decomposition decision, interface-contract ratification, binding-edge closure, diagram-provenance choice, and gate-bar `n/a (with reason)` marking routes through the structured-inquiry channel per `rules/interactive-questions.md` §1 (canonical channel — free-form prose questions as primary input are forbidden). Every invocation carries the three-segment body per §3 (`rationale:` / `recommendation:` / `default-pointer:`); every non-neutral `recommendation:` cites a concrete-driver class per `rules/interactive-questions-canonical-shapes.md` §3.2.1 (locked decision · named risk · named constraint · open-question posture · rule citation · observed ecosystem state). Up to four questions batch per invocation. **Question-fatigue-optimization is FORBIDDEN** per the Anti-Patterns section of `rules/interactive-questions.md`.
