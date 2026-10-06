---
name: "performance-discipline"
description: "Per-class runtime performance budgets with quantitative pass/fail gates — each artifact class (hook handlers, the conformity sweep, the test suite, agent spawn, install resolution) carries a runtime ceiling, a measurement boundary, and a benchmark verifier that exits zero on compliance; budget exceedances surface as findings routed to the expertise-gap log. Closes the Performance axis of the seven-axs-of-breadth taxonomy."
pathFilter: "**/hooks/**, **/tools/**, **/tests/**, **/agents/**"
alwaysApply: false
paths:
  - "**/hooks/**"
  - "**/tools/**"
  - "**/tests/**"
  - "**/agents/**"
---

<!-- SPDX-License-Identifier: MIT -->

# Rule: Performance Discipline

## Purpose

Establish per-class performance budgets and quantitative gates; close the Performance gap of the seven-axs-of-breadth taxonomy at `rules/cognitive-identity.md` §1.

## Obligations

### 1. Per-Class Performance Budgets

Per-class runtime budgets; operator-editorial at apply time; baselines align with the hooks pipeline hook-timeout values. Every row's verifier exits 0 on budget compliance.

| Class | Budget | Measurement boundary | Verifier |
|-------|-------:|---------------------|----------|
| Hook handler — `PreToolUse` / `PostToolUse` / `UserPromptSubmit` / `Notification` | 10s | hook-fire to dispatcher-return | `python src/apothem/benchmarks/bench_hooks.py --event=<name>` |
| Hook handler — `SessionStart` / `PreCompact` / `PostCompact` | 30s | hook-fire to dispatcher-return | `python src/apothem/benchmarks/bench_hooks.py --event=<name>` |
| Hook handler — `Stop` | 60s | hook-fire to dispatcher-return | `python src/apothem/benchmarks/bench_hooks.py --event=Stop` |
| Verify-ecosystem sweep — composite | 30s | tool-invocation to exit | `python src/apothem/benchmarks/bench_validate_ecosystem.py` |
| Verify-ecosystem sweep — per-check | 5s | per-subcommand invocation to exit | `python src/apothem/benchmarks/bench_validate_ecosystem.py --check=<name>` |
| Conformity-gate orchestrator — single-file dispatch | 1s | `python -m apothem.conformity.gate <file>` invocation to exit | `time python -m apothem.conformity.gate <file>` |
| Test-suite — full (post-pytest-xdist) | 60s | `pytest -n auto` start to exit | `time pytest -n auto` |
| Test-suite — per-test-module | 10s | per-module collection to exit | `python src/apothem/benchmarks/bench_tests.py --module=<path>` |
| Agent spawn — research / audit / quality / generation | 60s | spawn to result-collection | `python src/apothem/benchmarks/bench_agents.py --pattern=<name>` |
| Install-all — resolution sweep (manifest rules + capability projection, all adapters) | 0.25s | dry-run install-all rule + capability resolution across every adapter, no filesystem mutation | `python src/apothem/benchmarks/bench_install.py` |

### 1.0.1 Measurement-Gate Outcome (Budget Revision History)

The measurement gate (per `rules/planning-techniques.md` §1 Iteration Loop Safety) measured the conformity-gate orchestrator's per-matcher work at **0.67ms mean** (sum across 20 matchers: 13.3ms; slowest `file-header-grep` at 4.70ms) against an interpreter-startup-dominated wall-clock of ~465ms per single-file dispatch. ProcessPoolExecutor spawn overhead on Windows hosts is ~50–300ms per worker; fanning out 20 matchers would add 2–6s of pure overhead — **slowing the gate 150–450×, not speeding it up**. Three revisions resolved: the composite-sweep revision (30s → 10s) was **rejected** by measurement (composite stays 30s; the new 1s per-dispatch rows reflect reality); the test-suite revision (120s → 60s) was **accepted** because pytest-xdist's per-test-file work is substantial and parallel execution wins; multi-agent dispatch budget stays **per-agent** (not per-wave) because agent-spawn cost is fixed regardless of parallelism shape.

### 1.1 Shell-Execution Sub-Budgets

Hook bootstrap stubs run synchronously on the critical path between hook-fire and dispatcher-handoff. Their startup cost lives inside the §1 hook-handler budget but is itself bounded so the dispatcher gets its full budget for the actual work. The shell-linter ratification (`shellcheck` + `Invoke-ScriptAnalyzer`) carries the same per-class discipline as `ruff check` for Python artifacts.

| Class | Budget | Measurement boundary | Verifier |
|-------|-------:|---------------------|----------|
| Bootstrap stub — `hooks/lib/bootstrap.sh` (POSIX bash; Linux / macOS / WSL) | 500ms | stub invocation to `exec` of `dispatch.py` | `time bash hooks/lib/bootstrap.sh SessionStart </dev/null` |
| Bootstrap stub — `hooks/lib/bootstrap.sh` (Windows Git Bash / mingw64) | 1500ms | stub invocation to `exec` of `dispatch.py` | `time bash hooks/lib/bootstrap.sh SessionStart </dev/null` |
| Bootstrap stub — `hooks/lib/bootstrap.ps1` | 1500ms | stub invocation to dispatcher exit | `Measure-Command { pwsh -NoProfile -File hooks/lib/bootstrap.ps1 -Event SessionStart }` |
| Interpreter locator — `find-python.{sh,ps1}` | 200ms | dot-source to first PATH probe success | included in the bootstrap-stub measurements above |
| Shell linter — `shellcheck` over `hooks/lib/*.sh` | 5s | `shellcheck` invocation to exit | `shellcheck hooks/lib/*.sh` |
| Shell linter — `Invoke-ScriptAnalyzer` over `hooks/lib/*.ps1` | 10s | analyzer invocation to exit | `pwsh -NoProfile -Command "Invoke-ScriptAnalyzer -Path hooks/lib -Severity Error,Warning"` |
| Python linter — `ruff check` over the ecosystem | 5s | `ruff` invocation to exit | `ruff check hooks/ tools/ tests/` |

The PowerShell budget is wider than POSIX-bash because PowerShell's startup cost dominates on Windows hosts; the dispatcher accommodates this by running its work asynchronously after the stub's `exec` boundary. The Windows Git Bash / mingw64 row carries the same 1500ms budget as PowerShell for the same reason: on Windows, `bash` is the mingw64 port and pays a per-invocation `fork()`-emulation cost that lifts baseline bash startup from ~50ms (POSIX) to ~800ms (mingw64). The POSIX-bash row remains the canonical 500ms budget for Linux / macOS / WSL hosts; the per-platform classification is enforced at audit time by the bench driver's host-detection logic. Empirical evidence: a 5-run mean of 1004ms (min 960ms, max 1042ms) on a Windows Git Bash mingw64 host against the prior 500ms uniform budget.

### 2. Quantitative Gates

Every code change touching an artifact class above runs the relevant verifier; exit code 0 attests budget compliance. A budget exceedance surfaces as a high-priority finding under the Performance axis and routes to `memory/expertise-gap-log.md` for closure tracking.

### 3. Benchmark Suite

`src/apothem/benchmarks/` carries per-class entry-point scripts. Each script runs the artifact class's representative invocations, measures runtime (optionally peak memory), compares against the §1 budget, and exits 0 on PASS / non-zero on FAIL with a measured-vs-budget delta line.

### 4. Operator Override

An operator MAY amend a per-class budget at the §1 table; each amendment cites a concrete-driver class (measured workload increase, infrastructure change, dependency upgrade, or rule citation) per the Proactive Expertise Incorporation discipline's concrete-driver requirement.

## Seriousness Scaling

| Level | Performance Discipline |
|-------|------------------------|
| Awareness | Measurements logged in `memory/expertise-gap-log.md`; budgets advisory only |
| Daily use | Per-class budgets enforced at the verifier level; budget exceedances surface as high-priority findings |
| Release-tier | Full enforcement + benchmark-suite gating in the CI pipeline |

## Anti-Patterns

- **DON'T** measure runtime without a budget — **BECAUSE** observation without a gate doesn't prevent regression.
- **DON'T** set budgets without measurement — **BECAUSE** speculative budgets either over-approve or block valid work.
- **DON'T** suppress budget exceedances without a recorded rationale — **BECAUSE** silent suppression compounds technical debt invisibly.

## Enforcement

Path-filtered (the four glob entries in this rule's `pathFilter` field), scaling per the table above. Canonical specification for per-class performance budgets and quantitative gates across the Performance axis of the seven-axs-of-breadth taxonomy.

## Bindings (§0.j five-direction)

- **Drives →** ● Every artifact-class touch under the four path-filter entries (`**/hooks/**`, `**/tools/**`, `**/tests/**`, `**/agents/**`) — the per-class budget table at §1 enforces a quantitative ceiling. ● Every benchmark-suite invocation under `src/apothem/benchmarks/` (the four scripts `bench_hooks.py` + `bench_validate_ecosystem.py` + `bench_tests.py` + `bench_agents.py` realize the §3 verifier specification). ● Every budget-exceedance routing to `memory/expertise-gap-log.md` for closure tracking. ◐ The CI pipeline's release-tier benchmark gating.
- **Satisfies →** ● the rules registry row "Performance Discipline" (W19-BIS extension). ● The Performance axis declared in `rules/cognitive-identity.md` §1's seven-axs-of-breadth taxonomy. ● the hooks pipeline timeout cliffs (the per-class budgets at §1 align with the canonical hook-event timeout values).
- **Established by ↑** ● `rules/cognitive-identity.md` §1 (the seven-axs-of-breadth taxonomy declares the Performance axis this rule operationalizes). ● the hooks pipeline (the timeout-value canonical block this rule's §1 budgets align with).
- **Gated by ←** ● The path-filter (the four glob entries: hooks/, tools/, tests/, agents/) — this rule activates only on matching artifact touches. ● `rules/cognitive-identity.md` Senior Software Architect role declaration.
- **Cross-bound with ↔** ↔ `rules/cognitive-identity.md` (the seven-axs-of-breadth declaration this rule closes). ↔ `src/apothem/benchmarks/` (the per-class benchmark scripts the §3 verifier specification operationalizes). ↔ `memory/expertise-gap-log.md` (per-axis amendment ledger; budget exceedances route here per §2). ↔ `scripts/dev/validate_ecosystem.py` (the `--check perf-budgets` subcommand operationalizes the §1 budgets). ↔ `rules/code-craft-python.md` (the per-class performance budgets apply to Python artifacts under this rule's path-filter). ↔ `rules/code-craft-shell.md` (per-shell budgets — bootstrap.sh ≤ 500ms, bootstrap.ps1 ≤ 1500ms, find-python.{sh,ps1} ≤ 200ms, shellcheck ≤ 5s, Invoke-ScriptAnalyzer ≤ 10s; this rule is the static-form quality discipline whose runtime is governed there). ↔ `rules/token-budget-discipline.md` (the budget methodology).
