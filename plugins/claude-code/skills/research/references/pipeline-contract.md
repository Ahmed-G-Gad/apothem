<!-- SPDX-License-Identifier: MIT -->

## Pipeline Contract

**Pipeline position.** Wrapped-workflow meta-orchestrator over the whole `/research` pipeline; the canonical single-call entry for the pipeline. It consumes a research mission (raw question or an existing suite path) and drives the stage chain to completion through the workflow harness; it emits no artifact of its own beyond the chain's outputs (the suite, its per-stage artifacts, the paper deliverable, the publication record) plus the workflow's deterministic result surface and run trace.

**Consumed.** The operator's question or suite path; the `--autonomous` opt-in; the `--quick` mode; the `--verify-panel N` budget; the optional `--from <stage>` resume point. At each stage transition, the upstream stage's **Handoff Manifest** at `{suite}/_inputs/handoff-manifest.yml` (per `src/apothem/schemas/handoff-manifest.yaml`) is the named return contract the next phase consumes.

**Emitted.** The chain's own artifacts (owned by each stage command — the research spec, source ledger, synthesis, study design, experiment log, analysis, paper, review report, publication record), plus the workflow's deterministic result surface: the research outcome, the per-stage verified hand-offs with evidence, the per-deliverable advance-gate decisions with the thresholds each cleared (verified from the stage's own advancement-gate attestation, never recomputed), the disclosure ledger of any beyond-mission remediation, the fifteen-bar gate attestation, the per-run workflow trace (stages run, manifest hand-offs, verification verdicts, halt/continue decisions), and the single recommended next move.

**Pre-flight inquiry set.** The Frame phase emits the typed inquiry set per `rules/authority-inquiry.md` when the mission or entry point is underspecified — fresh idea vs. resume, which suite, which resume stage, scope direction, time horizon, domain boundary, operative term definitions, identity, public-surface naming, ethics / data-privacy posture (R6). Required-category inquiries block dispatch until answered; the `--autonomous` opt-in is itself confirmed before continuous chaining engages.

**Pre-emission gate.** Each stage command runs its own fifteen-bar gate per `rules/pre-emission-gate.md`; this command does not duplicate a stage's gate but verifies each stage's gate attestation is present in its manifest before dispatching downstream, and runs the workflow's own fifteen-bar gate over the final synthesized result.
