<!-- SPDX-License-Identifier: MIT -->

### Phase 6 — Question-Resolution Sweep (Ten Disciplines D1–D10) — Mandatory Gates G0–G5

The ten disciplines govern every structured-inquiry invocation across the six mandatory gate points:

- **D1 Questionable Identification.** Ten trigger categories: authority datum absent · requirement ambiguity · constraint under-specification · ordering indeterminacy · contradiction · option-set decision · implicit assumption · expertise-envelope limit · scope boundary · consequence-acceptance. Skipping = P0.
- **D2 Invocation Convention.** Every question specifies kind / options / rationale / impact / resolve-by-gate per the canonical-channel rule's §3 three-segment body.
- **D3 Mandatory Gate Points G0–G5.**
  - **G0** Consideration-Log-Complete (standing).
  - **G1** Pre-structural-drafting.
  - **G2** Mid-drafting on-discovery.
  - **G3** Pre-amendment.
  - **G4** Pre-emission.
  - **G5** Handoff.
  - Skipping G1 / G2 / G5 = P0; skipping G3 / G4 = P1.
- **D4 Deferral Discipline — five conditions.** Any deferral requires ALL of: (i) explicit user action via the structured-inquiry channel; (ii) consequence disclosure; (iii) placeholder installation `<USER-CONFIRM:kind=...; defer-reason=...; defer-timestamp=<ISO-8601>; deferred-by-command=plan-spec/>`; (iv) deferral routing to downstream via the Handoff Manifest; (v) a resolve-by-gate marker. Missing any = silent defaulting = P0.
- **D5 Question-Resolution Audit.** Every invocation logged with the full schema (Question ID · Trigger category · Source verbatim · Question asked · Options presented · User's selection · Gate · Severity · Resolution status · Consequence). Silent-defaulted rows are forbidden.
- **D6 Command-Specific Instantiation.** This command realizes the binding by emitting the appendix at G5.
- **D7 Handoff Manifest Specification.** YAML-fronted; schema-enforced; emitted at G5 (command exit). Required fields: `command`, `repository`, `mission`, `created_at` (ISO-8601), `invocation_sequence`, `downstream` (target command or `none (standalone invocation)`), `p0-unresolved: 0`, `p1-unresolved: 0`, `placeholders: []`, `appendices`. Downstream refuses to proceed if the manifest is missing, malformed, or violates the P0/P1 invariant. A falsified manifest = P0 integrity failure.
- **D8 Anti-Patterns.** Twelve forbidden patterns: silent defaulting · silent inference · silent placeholder-filling · silent fabrication · silent probably-what-user-meant · silent deferral-to-next · silent option-narrowing · silent question-suppression · silent assumption-cascade · silent out-of-scope absorption · silent persona-substitution · silent answer-pre-selection. Each is a discipline failure.
- **D9 Bidirectional Binding** of the Resolution Mandate per `_spec/spec.md` §0.j.
- **D10 Resolution Invariant.** Every questionable / ambiguity / under-specification / implicit assumption / contradiction / tension / unresolved option / authority-datum gap / expertise-envelope limit MUST be definitively resolved via the structured-inquiry channel before the command exits and before any downstream command consumes its output.

**Question-Resolution Audit deliverable.** Per Appendix E schema; every row corresponds to an actual structured-inquiry call.
