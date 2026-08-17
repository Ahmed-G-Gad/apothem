<!-- SPDX-License-Identifier: MIT -->

# benchmarks

> **Role.** Per-class performance benchmark drivers. Each script runs an artifact class's representative invocations, measures runtime, compares against the class budget declared in `rules/performance-discipline.md` §1, and exits 0 on PASS / non-zero on FAIL with a measured-vs-budget delta.

## Files

| File | Purpose |
|------|---------|
| `bench_hooks.py` | Hook-handler runtime benchmark against the per-event budgets (`--event=<name>`). |
| `bench_tests.py` | Test-suite runtime benchmark against the per-suite budgets (full suite and per-module). |
| `bench_agents.py` | Agent-spawn runtime benchmark against the per-spawn budget. |
| `bench_install.py` | Install-all resolution-sweep runtime benchmark against the dry-run install-all budget (propagation-rule + capability-projection resolution across every adapter, no filesystem mutation). |
| `bench_validate_ecosystem.py` | Verify-ecosystem-sweep runtime benchmark against the composite and per-check budgets. |
| `__init__.py` | Package marker. |

## Conventions

- Budgets are operator-editorial at apply time; the recommended baselines align with the hook-timeout values in the harness configuration and `rules/performance-discipline.md` §1.
- Budget exceedances surface as high-priority Performance-axis findings.

## Operating in this folder

- **Budget constant is the single source.** Each driver declares its class's budget as a module-level `Final` constant; it stays aligned with the budget table in `../rules/performance-discipline.md` §1 and the harness hook-timeout values — a budget change is mirrored in both places in the same change-set.
- **Exit code is the verdict.** 0 = PASS, non-zero = FAIL with a measured-vs-budget delta line. A scaffold driver with no wired fixture reports the budget and exits 0 so the verifier surface stays usable.
- **Path resolution is anchored relative to `__file__`** (the drivers sit four parents below the repository root); do not hard-code an absolute path.
- **Adding a driver:** declare the class's budget constant, implement the measurement against the representative invocation, and return the exit-code verdict with a delta line on FAIL. **Revising a budget:** cite a concrete driver (measured workload increase, infrastructure change, dependency upgrade, or rule citation) and update the rule table in the same change-set.
- Validate a change with `python -m ruff check`, `python -m mypy` for the in-scope modules, and `python -m pytest` (benchmark-driver tests).

## Related

- [`rules/performance-discipline.md`](../rules/performance-discipline.md) — the per-class budget table the drivers verify.
- [`hooks/`](../hooks/) — the hook handlers `bench_hooks.py` measures.
