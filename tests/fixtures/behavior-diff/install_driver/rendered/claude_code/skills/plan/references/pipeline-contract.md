<!-- SPDX-License-Identifier: MIT -->

## Pipeline Contract

**Pipeline position.** Wrapped-workflow meta-orchestrator over the whole `/plan` pipeline — the canonical single-call entry. It consumes a planning mission (raw prose or an existing suite path) and drives the stage chain to completion through the workflow harness. It emits no artifact of its own beyond the chain's outputs (the suite, its reports, its `COMPLETION.md`) plus the workflow's deterministic result surface and run trace.

**Consumed.** The operator's mission or suite path; the `--autonomous` opt-in; the `--verify-panel N` budget; the optional `--from <stage>` resume point. At each stage transition, the upstream stage's **Handoff Manifest** at `{suite}/_inputs/handoff-manifest.yml` is the named return contract the next phase consumes.

**Emitted.** The chain's own artifacts (owned by each stage command), plus the workflow's deterministic result surface: the planning outcome; the per-stage verified hand-offs with evidence; the disclosure ledger of any beyond-mission remediation; the fifteen-bar gate attestation; the per-run workflow trace (stages run, manifest hand-offs, verification verdicts, halt/continue decisions); and the single recommended next move.

**Pre-flight inquiry set.** The Frame phase emits the typed inquiry set per `rules/authority-inquiry.md` when the mission or entry point is underspecified — fresh mission vs. resume, which suite, which resume stage, scope direction, identity, public-surface naming, security posture. Required-category inquiries block dispatch until answered; the `--autonomous` opt-in is itself confirmed before continuous chaining engages.

**Pre-emission gate.** Each stage command runs its own fifteen-bar gate per `rules/pre-emission-gate.md`. This command does not duplicate a stage's gate — it verifies each stage's gate attestation is present in its manifest before dispatching downstream, and runs the workflow's own fifteen-bar gate over the final synthesized result.
