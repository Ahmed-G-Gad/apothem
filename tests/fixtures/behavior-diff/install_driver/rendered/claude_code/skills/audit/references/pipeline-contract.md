<!-- SPDX-License-Identifier: MIT -->

## Pipeline Contract

**Pipeline position.** Wrapped-workflow meta-orchestrator over the whole eleven-command audit fortress; the canonical single-call entry for the sweep. It consumes an audit target (a repository path) and a dimension set, fans the dimensions out as parallel phases, and emits one synthesized findings report plus the workflow's deterministic result surface and run trace. It is distinct from `/plan-audit` (closed-loop audit + remediation of a *plan suite*), `/elevate` (aggressive whole-repo critique **and remediation** to SOTA), and `/release-readiness` (a single pass/fail release-gate verdict — distinct from the fortress and never counted among the eleven dimensions): `/audit` is the report-only, multi-dimension findings sweep.

**Consumed.** The operator's target path; the `--dimensions` scope; the `--autonomous` opt-in; the `--verify-panel N` budget. Each dispatched audit consumes the deployed repository surface its own contract defines.

**Emitted.** The per-dimension findings artifacts (owned by each audit command, at the consuming suite's `_inputs/`), plus the workflow's deterministic result surface: the synthesized severity-triaged findings report (deduplicated across dimensions), the per-dimension verified-findings sets with evidence, the fifteen-bar gate attestation, the verifier ledger (every dropped finding with its reason), the per-run workflow trace (dimensions run, verification verdicts, dedup decisions), and the single recommended next move (route HIGH findings to remediation).

**Pre-flight inquiry.** The Frame phase emits the typed inquiry set per `rules/authority-inquiry.md` when the target or dimension set is underspecified — which repository, which dimensions, scope direction. The `--autonomous` opt-in is itself confirmed before continuous parallel dispatch engages.

**Pre-emission gate.** Each audit runs its own fifteen-bar gate per `rules/pre-emission-gate.md`; this command does not duplicate a dimension's gate, but runs the workflow's own fifteen-bar gate over the final synthesized report.
