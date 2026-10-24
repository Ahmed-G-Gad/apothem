<!-- SPDX-License-Identifier: MIT -->

## Pipeline Contract

**Pipeline position — mid-chain.** This command sits between `/plan-spec` (upstream Forge) and `/plan-review → /plan-design (CONDITIONAL — architecture-bearing suites only) → /plan-execute` (downstream consumers). Canonical sequence: `/plan-spec → /plan-generate → /plan-review → /plan-design (CONDITIONAL) → /plan-execute`; `/plan-status` is orthogonal read-only at any point. It consumes the Forge's emitted Handoff Manifest and the authored `_spec/spec.md`, and emits a complete plan suite.

**Handoff Manifest.**

- **Consumed.** `{suite}/_inputs/handoff-manifest.yml` per `src/apothem/schemas/handoff-manifest.yaml`. The upstream manifest is the source of truth for the spec path, the five-appendix attestations, the Question-Resolution Audit's open / resolved counts, and the four-discipline attestation block. `/plan-generate` refuses to proceed when the manifest's `refuses_to_proceed_if` preconditions fail.
- **Emitted.** An updated Manifest at the same path, augmented with the suite-generation outcome — phase count, sub-phase count, dependency-graph hash, decision-log entries, scorecard verdicts, and the spec-version pin propagated from the upstream manifest. Downstream commands (`/plan-review`, `/plan-execute`) consume this updated manifest as their authoritative input.

**Pre-flight inquiry set.** Step 3 (Discovery & User Clarification) emits the typed inquiry set as an upfront workflow operation per `rules/interactive-questions.md`. Every authoritative-data gap surfaces as a structured-inquiry invocation with the three-segment annotation; placeholders that would otherwise carry a fabricated default route to the inquiry surface. The inquiry set's resolution is recorded in PLAN-NOTES.md and the answers feed downstream Steps 4–8.

**Pre-emission gate.** Step 7 (Final Sweep) runs the fifteen-bar pre-emission gate per `rules/pre-emission-gate.md` against every emitted artifact (PREAMBLE.md, MASTER-PLAN.md, PROGRESS.md, PLAN-NOTES.md, every `phases/NN-topic/PHASE.md`). The Step 7 scorecards are the M3 ten-dimension surface; the gate attestation block is recorded in PLAN-NOTES.md and surfaced in the emitted Handoff Manifest. Failure on any bar blocks Step 9 user-approval until resolved.

### Inquiry Cadence

This command operates at **maximal structured-inquiry saturation**. Every phase-decomposition decision, gate placement, dependency-ordering choice, option-set ratification, authority-data inquiry, and architectural ratification routes through the structured-inquiry channel per `rules/interactive-questions.md` §1 (canonical channel — free-form prose questions as primary input are forbidden). Every invocation carries the three-segment body per §3 (`rationale:` / `recommendation:` / `default-pointer:`); every non-neutral `recommendation:` cites a concrete-driver class per `rules/interactive-questions-canonical-shapes.md` §3.2.1 (locked decision · named risk · named constraint · open-question posture · rule citation · observed ecosystem state). Up to four questions batch per invocation; treat the spec input as a newbie sketch — surface every gap rather than silently inferring decomposition or ordering. **Question-fatigue-optimization is FORBIDDEN**. The DURING cadence runs throughout Steps 3 (Discovery), 6 (Phase Files), and 7 (Final Sweep); the END-of-command synthesis question fires just before Step 9 user-approval (see `End-of-Command Synthesis` at the workflow tail).
