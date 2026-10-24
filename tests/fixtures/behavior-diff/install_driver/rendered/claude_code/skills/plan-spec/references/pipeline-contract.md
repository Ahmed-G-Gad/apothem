<!-- SPDX-License-Identifier: MIT -->

## Pipeline Contract

**Pipeline position — Initial.** This command heads the `/plan` pipeline. Canonical sequence: `/plan-spec → /plan-generate → /plan-review → /plan-design (CONDITIONAL — architecture-bearing suites only) → /plan-execute`; `/plan-status` is orthogonal read-only at any point. Input is free-form prose, raw notes, or ad-hoc requirements; output is the upstream Handoff Manifest downstream commands consume.

**Handoff Manifest.**

- **Consumed.** None (initial-position command).
- **Emitted.** `{suite}/_inputs/handoff-manifest.yml` per `src/apothem/schemas/handoff-manifest.yaml`. Carries: the authored `_spec/spec.md` path; the five appendices' state (Consideration Log · Potency Map · Preservation Audit · Expertise-Gap Log · Question-Resolution Audit); the Question-Resolution Audit's open-vs-resolved counts; the Deferral Ledger's downstream routing entries; the four-discipline attestation block.

**Pre-flight inquiry set.** Phase 1 (Discovery & Extraction) opens the inquiry set: the suite-name inquiry surfaces before any forge write per `rules/interactive-questions.md`; every Phase 2 contradiction enters the set at G3 (Pre-amendment); every authoritative-data gap surfaces as a `<USER-CONFIRM:kind=...>` placeholder per the canonical-channel rule.

**Pre-emission gate.** G4 (Phase 4 Preservation Verification) runs the fifteen-bar pre-emission gate per `rules/pre-emission-gate.md` against the candidate `_spec/spec.md` before promotion from `_inputs/forge.md`. The G5 Handoff Manifest carries the gate attestation block; failure on any bar blocks promotion until resolved.

### Inquiry Cadence (D4)

This command operates at **maximal structured-inquiry saturation** per D4 (Q-022). Every architectural decision, option-set ratification, authority-data inquiry, contradiction-surfacing event, potency-pairing choice, and expertise-axis attestation routes through the structured-inquiry channel per `rules/interactive-questions.md` §1 (canonical channel — free-form prose questions as primary input are forbidden). Every invocation carries the three-segment option-annotation body per §3 (`rationale:` / `recommendation:` / `default-pointer:`); every non-neutral `recommendation:` cites a concrete-driver class per `rules/interactive-questions-canonical-shapes.md` §3.2.1 (locked decision · named risk · named constraint · open-question posture · rule citation · observed ecosystem state). Up to four questions batch per invocation; treat the input prose as a newbie sketch — surface every gap rather than silently inferring. **Question-fatigue-optimization is FORBIDDEN** per the §4.8.8 D8 anti-pattern catalog. The DURING cadence runs throughout Phases 1–6 at gate points G0–G5; the END-of-command synthesis question fires per D6 just before G5 Handoff Manifest emission (see `End-of-Command Synthesis (D6)` at the workflow tail).
