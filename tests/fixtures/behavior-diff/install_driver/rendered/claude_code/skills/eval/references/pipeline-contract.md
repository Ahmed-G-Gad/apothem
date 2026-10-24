<!-- SPDX-License-Identifier: MIT -->

## Pipeline Contract

**Pipeline position.** Diagnostic surface for the model-quality review track. It consumes the evaluation dataset, the scorer definition, and the candidate endpoint, and emits the campaign findings artifact that release-readiness consumers read. The command mutates neither the candidate nor the dataset; the findings are read-only diagnostics.

**Handoff Manifest.**

- **Consumed.** The operator-supplied evaluation dataset (`--dataset PATH`), the scorer definition (`--scorer NAME`), and the candidate model-or-prompt endpoint. When the consuming suite carries a prior baseline at `_inputs/eval-baseline.md`, it is read as the regression comparand.
- **Emitted.** The campaign findings artifact at `_inputs/eval-findings.md` carrying aggregate metrics, the per-category breakdown, the regression ledger against the prior baseline, and the campaign's `verified:` date.

**Pre-flight inquiry set.** Phase 1 (Define) emits the typed inquiry set per `rules/authority-inquiry.md` when the dataset path, the scorer choice, or the candidate endpoint is ambiguous — the dataset lacks a category column, the scorer name resolves to more than one definition, or the candidate endpoint is undeclared. Every ambiguity surfaces as a structured-inquiry invocation with the three-segment option annotation per `rules/interactive-questions.md` §3. No model provider is assumed; the candidate endpoint is always operator-ratified, never invented.

**Pre-emission gate.** Phase 5 (Report) runs the fifteen-bar pre-emission gate per `rules/pre-emission-gate.md` against the candidate findings artifact before promotion. The gate attestation block is recorded inside the emitted artifact. Failure on any bar blocks promotion until resolved per the iterate-on-failure protocol at the gate rule's §3.
