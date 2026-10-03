<!-- SPDX-License-Identifier: MIT -->

# cli

> **Role.** The `apothem` command-line surface — the host-agnostic AI harness configuration manager. Reached via the module surface `python -m apothem`; `pyproject.toml` intentionally declares no console script. A bare `apothem` command exists only where an install path provides a launcher (the npm shim's `bin/apothem.mjs`, or the one-shot installers).

## Files

| File | Purpose |
|------|---------|
| `__init__.py` | Thin assembly layer: defines the `main` group, re-exports the patchable helper seam (the shared helpers the test suite patches through `apothem.cli.NAME`), and imports the `_cmd_*` modules for their registration side effects. |
| `_helpers.py` | Shared constants, the structured CLI-error type, the adapter protocol + load helpers, profile read/write, lifecycle-envelope builders, harness selection, project-root resolution, `AliasedGroup`, and the drift/plan helpers. |
| `_epilogs.py` | The per-subcommand `--help` epilog strings. |
| `_materialize.py` | The shared install/update materialization orchestrators (`_materialize`, `_dry_run_materialization`). |
| `_group.py` | Group plumbing that loads without the materialization stack: the root group that imports each command module on first use (with the static command summaries the root `--help` renders), the usage-error contract (exit 64, JSON error envelope), context settings, and UTF-8 stdio setup. |
| `_common_flags.py` | Shared Click options plus the console factory used across CLI commands. |
| `_json_formatter.py` | JSON-output helper for the CLI (machine-readable command output). |
| `_cmd_install.py` | The `install` **and `quickstart`** commands. `quickstart` is the guided profile → preview → install path and shares this module's materialization machinery, so it lives beside `install` rather than in a module of its own. |
| `_cmd_uninstall.py` | The `uninstall` command. |
| `_cmd_update.py` | The `update` **and `rollback`** commands. `rollback` restores from the backup set an update wrote, so it shares this module's ledger and backup handling. |
| `_cmd_verify.py` | The `verify` command. |
| `_cmd_status.py` | The `status` command. |
| `_cmd_diff.py` | The `diff` command. |
| `_cmd_harnesses.py` | The `harnesses` command group. |
| `_cmd_profile.py` | The `profile` command group. |
| `_cmd_doctor.py` | The `doctor` command. |
| `_doctor_hooks.py` | Harness-neutral hook probe for `doctor`: reads the files the latest install wrote (install ledger), collects the Apothem hook commands registered there, and starts each interpreter and script pair once with a no-op payload. |
| `_cmd_migrate_workspace.py` | The `migrate-workspace` command. |
| `_cmd_completion.py` | The `completion` command (shell-completion script emission). |
| `_cmd_backups.py` | The `backups` command group (`backups prune`: on-demand retention of the install backups and ledger). |
| `reference_export.py` | Deterministic JSON exporter for source-generated documentation reference — introspects the CLI command tree, the conformity validator modules and the harness registry. Runnable via `python -m apothem.cli.reference_export <kind>`; spawned by `site/scripts/update-reference-inventory.mjs` and the docs-drift CI gate. |
| `completions/` | Shell completion scripts: `apothem.bash`, `apothem.zsh`, `apothem.fish`, `apothem.ps1`. |

## Conventions

- The propagation domain model (`propagation.py` loader + `propagation-manifest.yaml` contract) lives in the shared [`lib/`](../lib/) package, not here — harness adapters consume it without importing the presentation-layer cli package.

## Operating in this folder

- **Layer boundary.** The CLI consumes the propagation domain and the harness registry; it does not host them. New presentation-only helpers belong here; new domain logic belongs in the shared [`lib/`](../lib/) or per-harness packages.
- **Strict-typed surface.** This package sits inside the `mypy --strict` scope (`src/apothem/cli/`). Keep modern typing — `list[T]` / `dict[K, V]` / `X | None`, `typing.Protocol` for structural typing, `typing.cast()` to narrow `Any`.
- Snake_case modules; private/shared helpers use a leading underscore (the `_common_flags`, `_json_formatter` pattern). Ambiguity is surfaced through structured inquiry or a `TODO(clarify)` marker — never invented.
- **Adding a command/helper:** author it as a `.py` module under this package, wiring it into the command tree rather than as a free-standing script. Preserve the JSON-output path for any machine-readable command.
- **A documented public CLI surface change** (a command, a flag, an environment variable) updates its `site/content/docs/` page in the same change-set.
- Validate with `python -m ruff check` and `python -m ruff format`, `python -m mypy` (bare — naming a path overrides the `[tool.mypy] files` key and drops the sibling packages from strict checking), then `python -m pytest`, then `python -m apothem.conformity.gate --all .`.

## Related

- [`lib/`](../lib/) — the shared package hosting the propagation domain model + manifest.
- [`harnesses/`](../harnesses/) — the per-harness adapters that consume the propagation manifest via the shared install driver.
