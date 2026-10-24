<!-- SPDX-License-Identifier: MIT -->

## Pipeline Contract

**Pipeline position.** **Wrapping / orthogonal.** `/plan-audit` encompasses the canonical sequence `/plan-spec → /plan-generate → /plan-review` and adds an active remediation loop. Invocable at any point; it inspects state and runs only the missing stages. It never executes phase implementation work — it leaves the suite ready for `/plan-execute`.

**Consumed.** The target suite's `_spec/spec.md`, `_inputs/handoff-manifest.yml`, infrastructure files, `phases/**/PHASE.md`, and any existing phase reports.

**Emitted.** A persistent, bounded report at `<suite>/_outputs/audit-report-<YYYY-MM-DD>.md`; an updated handoff manifest carrying the zero-finding verdict, the open-finding count, the remediation ledger, and any maintenance routing; and a non-zero terminal status when residual findings remain.
