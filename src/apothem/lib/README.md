<!-- SPDX-License-Identifier: MIT -->

# lib

> **Role.** Shared internal helpers reused across the `apothem` subpackages — the harness registry and adapter protocol, the profile model and its harness projection, materializer building blocks, durable state stores (memory, contexts, learning, install ledger), atomic filesystem IO, frontmatter probing, parallel sweep, and structured reporting.

## Files

| File | Purpose |
|------|---------|
| `frontmatter.py` | YAML frontmatter field probing and value extraction for ecosystem files. |
| `harness_materializer.py` | Shared building blocks for the per-harness materializers. |
| `harness_protocol.py` | The `HarnessAdapter` structural Protocol every concrete adapter satisfies — defined in the foundation layer so the registry references the contract without importing its consumers; re-exported by `apothem.harnesses` as the public import path. |
| `harness_registry.py` | Harness identity, adapter entry-point, target, docs, capability, package-data, and test-fixture registry — authoritative at runtime (filesystem-convention `discover_adapters` is a conformance parity check, not the runtime resolver). |
| `harness_registry_data.py` | The static, declarative `HARNESS_REGISTRY` data table (split from `harness_registry.py`) — the per-adapter identity / entry-point / target / capability / package-data records plus the dataclass and capability-matrix builders; the sibling module holds the resolution logic and is the runtime surface. |
| `plugin_tree.py` | Plugin source-tree assembler and manifest generator — materializes the canonical `.claude-plugin` distribution bundle (engine plus catalog) that runs as a self-contained tree with vendored dependencies. |
| `plugin_bootstrap.py` | Self-contained engine-import bootstrap for the bundled plugin tree — resolves `import apothem` against the bundled engine copy under `<plugin_root>/lib/apothem`. |
| `plan_tiers.py` | Three-tier scalability classification (small / medium / large) for the `/plan-<stage>` planning pipeline — governs a plan suite's validation cadence, indexing, and decomposition as it scales. |
| `profile.py` | Canonical shared-profile model, normalization, and diagnostics. |
| `profile_projection.py` | Shared profile→harness projection seam — turns a per-harness-resolved profile into the two surfaces an adapter materializes: a Markdown managed-block body folded into the instruction anchor, and the structured settings payload. |
| `propagation.py` | Propagation-manifest loader for harness adapters — parses the per-harness install rules from `propagation-manifest.yaml`. |
| `parallel_sweep.py` | Parallel file-sweep utilities backed by `ProcessPoolExecutor` — kept available with no production caller today (deliberate, per its docstring: adopt only after a benchmark confirms a win); exercised by `tests/unit/test_parallel_sweep.py`. |
| `atomic_io.py` | Shared atomic-write, durable-append, and advisory-lock filesystem primitives (`write_bytes_atomically`, `append_line_durably`) reused by every state store and the install driver — a crash leaves the original file intact, never truncated. |
| `reporter.py` | Structured pass/fail/warn reporting for the validation tools. |
| `schema_errors.py` | Shared jsonschema-validation error formatting (`format_schema_errors`) — orders a validator's errors by instance path and joins them into one deterministic message; consumed by the memory / contexts / learning stores and `auditor.py`. |
| `data_home.py` | Shared data-home resolution for the memory, contexts, learning, and plans surfaces — derives one Apothem-owned `<base>/.apothem/` working directory shared across every installation target rooted at the same base (a write under one harness is visible to the others), deliberately not per-harness silos. |
| `memory.py` | Agnostic, operator-portable durable knowledge store — `MemoryRecord` value type, schema validation, and a canonical-serialized `MemoryStore` with byte-equivalent export/import. |
| `contexts.py` | Injectable, enable/disable-able context fragments — `ContextFragment` value type, schema validation, and a `ContextStore` with an activation switch. |
| `learning.py` | Opt-in (default-off) continuous-learning loop — signal capture gated on the profile flag, confidence-scored pattern extraction, and promotion of above-threshold patterns to catalog-skill artifacts. |
| `auditor.py` | Unified conformance / security auditor — configuration-file scanning, closed-catalog secret detection, and rule-based conformance over a parsed config, emitting advisory `Finding`s that validate against `advisory-finding.schema.json`. Standalone via `python -m apothem.lib.auditor`; `pr_audit` is the changed-path integration entry point for a CI / pull-request audit caller. |
| `clean_slate.py` | Opt-in clean-slate removal routine — closed removal target set, unsafe-root guard, timestamped backup taken before any removal, per-target confirmation, dry-run preview, and a non-interactive override. |
| `install_ledger.py` | Append-only per-install state ledger (`~/.apothem/state/<harness>/ledger.jsonl`) — the source of truth for uninstall and rollback, so manifest drift after install cannot strand or over-remove operator content. |
| `python_resolver.py` | Resolves an absolute CPython interpreter for install-time hook-command wiring — never a bare `python` name that a host `PATH` could resolve to a Microsoft Store `WindowsApps` launcher stub. |
| `workspace_migration.py` | Migrates a legacy per-harness workspace (`.apothem/<harness>/…` plus a sibling `.plans` tree) into the current shared `.apothem/{plans,memory,learning,contexts}` layout (`apothem migrate-workspace`). |
| `__init__.py` | Package marker. |

## Operating in this folder

- **High blast radius.** A defect here propagates into every adapter, the CLI, and the conformity tooling — changes are high-blast-radius; favor narrow, well-tested edits.
- **The harness registry is the single source of truth** for harness identity, entry points, targets, capabilities, package-data globs, and test fixtures. When the registry changes, the coupled surfaces it indexes (profile schema, manifest, golden fixtures, compatibility matrix, `pyproject.toml`, tests) must move in the same change-set or the suite breaks.
- **Profile ↔ schema sync.** Keep the profile model and its schema in sync; a profile-shape change without the matching schema update is a defect.
- **Strict typing.** Public surfaces here are part of the `mypy --strict` scope — keep type annotations exact (`list[T]` / `dict[K, V]` / `X | None`, `typing.Protocol` for structural typing, `typing.cast()` to narrow `Any`); never widen a public signature to escape a strict failure.
- **Agnostic, operator-portable data stores.** Memory records and context fragments serialize to a byte-equivalent canonical form, and the learning loop is **default-off**, gated on its profile flag. Do not bias any store toward a particular harness or model, and do not flip the learning loop on by default. Reference harnesses only by catalog slug; privilege none.
- **Adding or changing a module:** update the module table above in the same change-set, and confirm the public API stays `mypy --strict`-clean. Validate with `python -m ruff check` and `python -m ruff format`, `python -m mypy src/apothem/cli/ src/apothem/harnesses/` (plus this package where it falls in strict scope), `python -m pytest`, and `python -m apothem.conformity.gate --all .`.

## Related

- [`harnesses/`](../harnesses/) — adapters loaded and tested against `harness_registry.py`; the shared install driver consumes `frontmatter.py`, `propagation.py`, `atomic_io.py`, and `install_ledger.py`.
- [`conformity/`](../conformity/) — the registry-coupled greps resolve harness identity and capability data through `harness_registry.py`.
- [`scripts/dev/`](../../../scripts/dev/) — `validate_ecosystem.py` and `validate_hooks.py` import `frontmatter.py` and `reporter.py` directly.
