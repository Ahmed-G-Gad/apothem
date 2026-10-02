<!-- SPDX-License-Identifier: MIT -->

# benchmarks

> **Role.** Per-class performance benchmark drivers. Each script runs an artifact class's representative invocations, measures runtime, compares against the class budget declared in `rules/performance-discipline.md` §1, and exits with a verdict code and a measured-vs-budget line.

## Files

| File | Purpose |
|------|---------|
| `bench_hooks.py` | Hook-chain end-to-end benchmark. Runs every `shell: bash` command `hooks/hooks.json` registers, as written, on a real event payload per event and matcher (a `Write` of `app.py`, an `ls -la`, a two-option question, …), and reports per chain the median total time, the slowest command, and the context characters injected. `--event=<name>` selects one event; `--json` prints a report. |
| `bench_tests.py` | Test-suite runtime benchmark against the per-suite budgets (full suite and per-module). |
| `bench_agents.py` | Agent-spawn budget anchor. Not measured: a spawn needs a host harness and a model call, so it reports `NOT MEASURED` and exits 3. Not part of `make benchmarks`. |
| `bench_install.py` | Install-all resolution-sweep runtime benchmark against the dry-run install-all budget (propagation-rule + capability-projection resolution across every adapter, no filesystem mutation). |
| `bench_validate_ecosystem.py` | Verify-ecosystem-sweep runtime benchmark against the composite and per-check budgets. |
| `__init__.py` | Package marker. |

## Conventions

- Budgets are operator-editorial at apply time; the recommended baselines align with the hook-timeout values in the harness configuration and `rules/performance-discipline.md` §1.
- Budget exceedances surface as high-priority Performance-axis findings.

## Operating in this folder

- **Budget constant is the single source.** Each driver declares its class's budget as a module-level `Final` constant; it stays aligned with the budget table in `../rules/performance-discipline.md` §1 and the harness hook-timeout values — a budget change is mirrored in both places in the same change-set.
- **Exit code is the verdict.** `0` pass, `1` over budget, `2` error (the target is missing, or the measured run did not execute: a non-zero exit, a hook command that cannot run as registered, a fail-open diagnostic envelope, or output that is not JSON), `3` not measured (nothing is wired to measure, or no hook is registered for the event). A driver never reports a pass for a run that did not execute the real code.
- **Measure the real path.** `bench_hooks.py` runs the registered commands as a harness does (`bash -c <command>` with `CLAUDE_PLUGIN_ROOT` at the repository root), with a fresh session id, `HOME`, `TMPDIR` and project directory per run. It times the bootstrap, interpreter discovery, the dispatcher, the handler and the emission, not a `--help` start-up.
- **Path resolution is anchored relative to `__file__`** (the drivers sit four parents below the repository root); do not hard-code an absolute path.
- **Adding a driver:** declare the class's budget constant, implement the measurement against the representative invocation, and return the exit-code verdict with a delta line on FAIL. **Revising a budget:** cite a concrete driver (measured workload increase, infrastructure change, dependency upgrade, or rule citation) and update the rule table in the same change-set.
- Validate a change with `python -m ruff check`, `python -m mypy` for the in-scope modules, and `python -m pytest tests/unit/test_benchmarks.py`.

## Related

- [`rules/performance-discipline.md`](../rules/performance-discipline.md) — the per-class budget table the drivers verify.
- [`hooks/`](../hooks/) — the hook handlers `bench_hooks.py` measures, and `hooks/hooks.json`, the chain it runs.
- [`scripts/dev/collect_metrics.py`](../../../scripts/dev/collect_metrics.py) — records `bench_hooks.py --json` as `hook_e2e_ms` in the CI metrics artifact.
