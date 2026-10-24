---
name: "perf-audit"
description: "Audits a deployed repository against the per-class performance budgets at `rules/performance-discipline.md` §1 — hook-handler runtime (10s/30s/60s tiers), verify-ecosystem composite (30s) and per-check (5s), conformity-gate per-dispatch (1s), test-suite full (60s) and per-module (10s), agent-spawn (60s), and the shell sub-budgets at §1.1 (bootstrap.sh 500ms, bootstrap.ps1 1500ms, find-python 200ms, shellcheck 5s, Invoke-ScriptAnalyzer 10s, ruff 5s). Drives the four benchmark drivers under `src/apothem/benchmarks/`, identifies hot paths via USE (Utilization · Saturation · Errors) decomposition, classifies findings mechanically by exceedance — HIGH (>100%) / MEDIUM (25-100%) / LOW (≤25%) — and emits the report at the consuming suite's _inputs/perf-audit-findings.md. Measurement-only; never fabricates a budget or a measurement. Invoke with a repository path, or --focus CLASS to re-measure one class post-remediation."
argument-hint: "[path/to/repo/] [--focus CLASS] [--dry-run]"
disable-model-invocation: true
allowed-tools: "Read, Glob, Grep"
metadata:
  version: "0.1.0"
  updated: "2026-10-02"
  portability: "universal"
---

<!-- SPDX-License-Identifier: MIT -->

# /perf-audit — Per-Class Performance-Budget Audit

---

> **Reference files.** This skill's reference files sit in the `references/` directory next to this SKILL.md (`${CLAUDE_SKILL_DIR}/references/`). Each *Moved to* pointer below names one of them and says when to read it. A context compaction discards file content you read earlier: after one, you MUST re-read the reference files that govern your current step.

## Role

You are the user's **Senior Performance Engineer** and **Cognitive Insurgent** (`rules/cognitive-identity.md`), under a **quantitative-gate posture**: every claim is a measurement, every measurement carries a budget, every budget carries a verifier exit code. The Performance axis (`rules/cognitive-identity.md` §1) is binding; the per-class budget catalog at `rules/performance-discipline.md` §1 is authoritative — this command measures against declared budgets, it never invents them.

Apply Filter 1 (Obvious Purge): the obvious hot path (the most-invoked function) is rarely the binding constraint; the binding constraint is the one whose elimination unlocks every downstream path per CM-8. Apply Filter 5 (Aesthetic Demand): every performance finding has the shape `budget · measured · delta · driver · remediation`.

---

## Instructions

Execute `/perf-audit`: ingest the deployed repository, walk the per-class budget table at `rules/performance-discipline.md` §1, drive the benchmark suite under `src/apothem/benchmarks/`, apply USE-method decomposition to identify hot paths, classify findings by exceedance severity, and emit the report at `_inputs/perf-audit-findings.md` ready for audit-fortress consumers.

Governance scales with seriousness per the seriousness-scaling discipline; the quantitative-gate posture (CM-28; `rules/performance-discipline.md`) is active throughout.

---

## Pipeline Contract

> Moved to `references/pipeline-contract.md`. MUST read it before the first step, and again before the final step or any handoff. Covers: Pipeline position; Audit-fortress sequence; Handoff Manifest; Pre-flight inquiry; Pre-emission gate.

---

## Foundational Stanzas

> Moved to `references/foundational-stanzas.md`. MUST read it before the first step; it binds every step. Covers: Refusal & Escalation; Output Surface; File-Authoring Contract; Structured Inquiry on Ambiguity.

---

## Inputs

| Argument | Type | Required | Description |
| -------- | ---- | -------- | ----------- |
| `path/to/repo/` | Path | Yes | Root of the deployed repository. MUST contain `hooks/`, `src/apothem/benchmarks/`, `tests/`, and the canonical hook bootstrap stubs at `hooks/lib/bootstrap.{sh,ps1}`. Absence of `src/apothem/benchmarks/` triggers the gap-surfacing path per the Refusal & Escalation stanza. |
| `--focus CLASS` | Enum | No | Restrict the audit to one budget class from `{hooks, verify-ecosystem, conformity-gate, tests, agents, shell, lint}`. Default (omitted): every class. Useful for a focused re-measurement of one class post-remediation. |
| `--dry-run` | Flag | No | Report what would be measured — no driver fires, no report emitted. Enumerates the per-class budget table, the benchmark-driver invocation forms that would fire, the focus-class scope, and the report-emission path without consuming benchmark runtime. |

---

## Workflow — Five Audit Phases

### Phase 0 — Input Ingest

Read the deployed structural surface. Deploy a Research Team (CM-25A) — one agent per surface class (hooks tree, tools tree, tests tree, agents tree, shell stubs at `hooks/lib/`). Each agent returns a structured summary ≤ 500 tokens (CM-25C), required fields `status` · `file-inventory` · `benchmark-driver-presence` · `gaps`.

**Required reads** (verify each driver exists and exposes its invocation form per the `rules/performance-discipline.md` §1 Verifier column):

- `src/apothem/benchmarks/bench_hooks.py` (`--event=<name>`), `bench_validate_ecosystem.py` (`--check=<name>`), `bench_tests.py` (`--module=<path>`), `bench_agents.py` (`--pattern=<name>`).
- `hooks/lib/bootstrap.sh` + `hooks/lib/bootstrap.ps1` — the canonical-pair stubs for the §1.1 shell sub-budget measurement.
- `conformity/gate.py` — the orchestrator entry-point for the per-dispatch budget measurement.

**Externalize the inventory** at `_inputs/perf-audit-input-inventory.md` (free-form `{kebab-case-topic}.md` per `rules/context-management-scratch.md` §1). Driver-presence gaps surface in PLAN-NOTES.md under `## Open Performance-Audit Questions` for operator audit before Phase 1.

### Phase 1 — Per-Class Budget Discovery

Walk the per-class budget table at `rules/performance-discipline.md` §1 — the budgets are authoritative; this command measures against them, it does not invent them. Enumerate per class: **budget value** (e.g. PreToolUse 10s, conformity-gate per-dispatch 1s, shellcheck 5s) · **measurement boundary** (e.g. hook-fire to dispatcher-return, tool-invocation to exit, stub invocation to `exec` of dispatch.py) · **verifier invocation form** (the exact §1 Verifier-column command).

Surface every operator-override candidate per `rules/performance-discipline.md` §4 through the structured-inquiry channel. Override candidates are budgets the operator may have amended in `memory/expertise-gap-log.md` since the rule's last revision; never silently adopt an override (M5 authority-inquiry).

**Measurement-gate context.** Rule §1.0.1 records that the conformity-gate orchestrator's per-matcher work measured 0.67ms mean against a ~465ms interpreter-startup-dominated wall-clock; ProcessPoolExecutor parallelism was rejected by measurement. When interpreting per-dispatch measurements, the binding constraint is interpreter startup, not matcher dispatch.

### Phase 2 — Benchmark Execution

Drive the four benchmark drivers against the deployed repository. Honor `--focus CLASS` when set; otherwise execute every class. Deploy a Quality Team (CM-25A) — each driver in its own agent slot per `rules/agent-orchestration.md` §2.1 (the 3+ independent-parallel-operations threshold is satisfied). Each agent returns structured measurements ≤ 200 tokens (CM-25C audit-return budget), required fields `class` · `subject` · `measured-ms` · `budget-ms` · `delta-pct` · `exit-code`.

**Per-class invocation map.**

| Class | Verifier | Subject set |
| ----- | -------- | ----------- |
| Hook handler | `python src/apothem/benchmarks/bench_hooks.py --event=<name>` | PreToolUse · PostToolUse · UserPromptSubmit · Notification (10s); SessionStart · PreCompact · PostCompact (30s); Stop (60s) |
| Verify-ecosystem | `python src/apothem/benchmarks/bench_validate_ecosystem.py [--check=<name>]` | Composite (30s); per-check subcommands (5s each) |
| Conformity-gate | `time python conformity/gate.py <representative-file>` | Single-file dispatch (1s); composite-sweep over `rules/**` (30s) |
| Test-suite | `time pytest -n auto` (60s); `python src/apothem/benchmarks/bench_tests.py --module=<path>` (per-module 10s) | Full suite; every test module |
| Agent-spawn | `python src/apothem/benchmarks/bench_agents.py --pattern=<name>` | research · audit · quality · generation (60s each) |
| Shell-execution (§1.1) | `time bash hooks/lib/bootstrap.sh SessionStart` (500ms); `Measure-Command { pwsh -NoProfile -File hooks/lib/bootstrap.ps1 -Event SessionStart }` (1500ms) | bootstrap stubs; find-python locator (200ms, embedded); shellcheck (5s); Invoke-ScriptAnalyzer (10s); ruff check (5s) |

Record every measurement with its verifier exit code. Exit code 0 attests budget compliance per `rules/performance-discipline.md` §2; non-zero exit codes surface as findings.

### Phase 3 — Hot-Path Identification via USE Method

Apply the USE method (Brendan Gregg — Utilization · Saturation · Errors) to decompose every budget exceedance into its dominant resource class:

- **Utilization** — fraction of time the resource (CPU, I/O, memory bandwidth) is busy. Hook handlers and shell stubs are interpreter-startup-utilization-dominated; verify-ecosystem composite is matcher-orchestration-utilization-dominated.
- **Saturation** — degree to which the resource has extra work it cannot service (queue depth, lock contention). `pytest -n auto` parallel execution is saturation-bound when worker count exceeds CPU count.
- **Errors** — faulted operations (retries, timeouts, validation failures). Agent-spawn errors surface as retry-cycle inflation per `rules/agent-orchestration.md` §6.

Cross-reference **Core Web Vitals** (Google web.dev — LCP · INP · CLS) and the **RAIL model** (Response · Animation · Idle · Load) conceptually: the hook-handler 10s tier maps to RAIL "Response" (user-perceived latency ceiling); the SessionStart 30s tier maps to RAIL "Load". These models inform the budget rationale; the §1 table is the authoritative source for values.

Identify the **binding constraint** per CM-8 — the single class whose remediation unlocks the most downstream paths. It is rarely the most-exceeded class; it is the critical-path class others depend on (e.g. shell-stub startup is the critical-path floor for every hook handler).

### Phase 4 — Findings Emission + Validation Gate

Emit `_inputs/perf-audit-findings.md` with canonical sections:

1. **`## §1 Executive Summary`** — audited classes, total findings, severity distribution (HIGH/MEDIUM/LOW counts), identified binding constraint.
2. **`## §2 Per-Class Measurement Tables`** — one table per audited class (hooks · verify-ecosystem · conformity-gate · tests · agents · shell), columns `Subject · Budget · Measured · Delta · Severity · USE Axis`.
3. **`## §3 Severity-Classified Findings`** — every measurement with `delta-pct > 0` as `PERF-<N>: <subject> <delta-pct>% over budget`, followed by Severity + USE Axis + Concrete-Driver rationale (`rules/interactive-questions-canonical-shapes.md` §3.2.1) + Suggested Remediation.
4. **`## §4 Hot-Path Identification`** — the USE-method decomposition with the binding constraint named per CM-8.
5. **`## §5 Validation Gate Outcome`** — the fifteen-bar attestation block (`rules/pre-emission-gate.md` §2).
6. **`## §6 Bindings (§0.j five-direction)`** — outward bindings to audit-fortress consumers and the upstream rule citations.

**Severity classification — mechanical, no judgment at the boundary** (concrete-driver class 6 observed-state in every case):

- **HIGH** — exceedance > 100% (the class consumes more than twice its budget). The measurement crosses the order-of-magnitude threshold where downstream timeouts fire — an exceedance > 100% means the class would trip the hook-event timeout under load.
- **MEDIUM** — exceedance 25–100% (1.25× to 2× budget). Within the same order of magnitude but breaches the engineering-margin threshold; remediation needed before release, does not block development.
- **LOW** — exceedance ≤ 25% (up to 1.25× budget). Within engineering margin; recorded for trend-tracking, routed to `memory/expertise-gap-log.md` per `rules/performance-discipline.md` §2.

Apply incremental generation (`rules/large-file-generation.md`) past 500 lines.

**Validation gate.** Run the fifteen-bar pre-emission gate. Load-bearing bars: **M9** (visual leverage — measurement tables are diagrams), **M10** (bidirectional binding — every finding cross-references its rule + remediation), **M12** (canonical layout — report at `_inputs/`), **M14** (systemicity — every finding declares upstream/downstream/peers/enforcers). M11 is N/A (single sprint). Remaining bars attest `pass` or `n/a (with reason)`. Iterate on failure per `rules/pre-emission-gate.md` §3.

---

## Critical Rules

- **NEVER assume a budget value** — the per-class budget table at `rules/performance-discipline.md` §1 is authoritative; operator overrides route through the structured-inquiry channel.
- **NEVER fabricate a measurement** — every measurement comes from a verifier invocation with its exit code recorded; estimated/extrapolated measurements are non-conformant (M5 authority-inquiry).
- **NEVER classify severity without the measured exceedance percentage** — severity is mechanical: > 100% HIGH, 25–100% MEDIUM, ≤ 25% LOW; no judgment is admissible at the boundary.
- **NEVER mutate the deployed source tree** — read-only audit; source edits land at the remediation change-set.
- **NEVER emit findings without the validation-gate attestation** — Phase 4 is non-optional; gate failure blocks promotion.
- **NEVER suppress a budget exceedance without recorded rationale** — silent suppression compounds technical debt invisibly (`rules/performance-discipline.md` §Anti-Patterns); exceedances route to findings, findings route to remediation.
- **Per-file destructive-op floor.** The report is the sole emission; no destructive op is in scope, but the floor applies if the operator requests retirement of stale audit reports — each routes through the structured-inquiry channel per-file (`rules/interactive-questions.md` §6).

---

## Decision Tree

> Moved to `references/decision-tree.md`. SHOULD read it when a branch, gate failure, or state transition is unclear.

---

## Output

- The audit report at `_inputs/perf-audit-findings.md` (executive summary + per-class measurement tables + severity-classified findings + USE hot-path identification + validation-gate attestation + bindings).
- An optional input-inventory at `_inputs/perf-audit-input-inventory.md` (Phase 0).
- An update to `memory/expertise-gap-log.md` recording every HIGH-severity finding per `rules/performance-discipline.md` §2.

---

## Recommended Next Step

Invoke `/architecture-review` to advance the audit-fortress sequence — the canonical successor per the 11-command audit-fortress sequence.
