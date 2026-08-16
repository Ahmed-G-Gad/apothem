<!-- SPDX-License-Identifier: MIT -->

# apothem

> **Role.** `apothem` is a harness-agnostic AI-configuration manager. It maintains one shared corpus of rules, agents, commands, skills, output-styles, and templates, and materializes that corpus into each AI tool's native configuration directory through a per-harness adapter. Author the conventions once; `apothem` propagates them to every harness the operator runs.

## Package Map

### Code subpackages

| Child | Holds |
|-------|-------|
| [`audit/`](audit/) | Inventory and drift scanners that map the ecosystem and surface staleness, leakage, and convention findings. |
| [`benchmarks/`](benchmarks/) | Per-class performance benchmark drivers (hooks, tests, agents, ecosystem sweep). |
| [`cli/`](cli/) | The `apothem` command-line surface, shared flags, JSON formatter, propagation loader, and shell completions. |
| [`conformity/`](conformity/) | Pre-emission conformity validators — the gate orchestrator plus mechanical `*_grep` matchers and the link checker. |
| [`harnesses/`](harnesses/) | Per-harness adapter subpackages implementing the `HarnessAdapter` protocol — one per supported AI tool. |
| [`hooks/`](hooks/) | The hook dispatcher, bootstrap stubs, event vocabulary, and per-event Markdown context messages. |
| [`lib/`](lib/) | Shared internal helpers (frontmatter probing, materializer building blocks, parallel sweep, reporting). |
| [`statuslines/`](statuslines/) | The conformity-posture statusline renderer plus shell shims and reference docs. |

### Content / asset directories

| Child | Holds |
|-------|-------|
| `agents/` | Persistent agent definitions (mission, deliverable, constraints) materialized into harness agent dirs. |
| `commands/` | Slash-command definitions — the `/plan` pipeline and the audit/review commands. |
| `rules/` | The shared behavioral rule corpus (always-on and path-filtered `.md` rules). |
| `skills/` | Folder skills, each with a `SKILL.md` entry point. |
| `output-styles/` | Output-style definitions controlling response shape. |
| `templates/` | Scaffolding templates consumed by the planning workflow and renderers. |
| `schemas/` | Schema fixtures used by validators and tests. |

### Package files

| File | Holds |
|------|-------|
| `__init__.py` | Package marker and version surface for `apothem`. |
| `__main__.py` | Module entry point — `python -m apothem` dispatches to the [`cli/`](cli/) command surface. |

## Conventions

- Code subpackages are importable Python modules; content directories are corpora the harness adapters propagate.
- The `claude_code` harness consumes the full surface (code directories travel with the bundled plugin tree, convention directories flatten into the harness config root); the other harnesses receive a materialized native config and, where the native format differs, converted cohorts per their adapter.
- The code-vs-content split is load-bearing: an adapter subpackage in `harnesses/` is named by its catalog slug, never privileged by a brand phrase, and content corpora carry no executable Python.

## Operating in this folder

- **Self-contained run model.** The engine runs from source via `PYTHONPATH=src python -m apothem ...` with its dependencies vendored under `_vendor/`; do not assume an installed entry point when verifying changes here. `_vendor/` is a vendored tree an agent does not hand-edit.
- Add or modify code inside the owning subpackage rather than at this root; add corpus artifacts inside the owning content directory.
- After any change, validate with `python -m ruff check . --fix`, then `python -m mypy` (bare — it reads the `[tool.mypy] files` key in `pyproject.toml`, whose strict scope is `cli`, `harnesses`, `lib`, `conformity`; passing paths on the command line overrides that key and silently drops the rest), then `python -m pytest`, then `python -m apothem.conformity.gate --all .`.
- A new harness adapter touches several coupled surfaces beyond its subpackage (registry, manifest, golden fixtures, profile schema, tests) — consult `harnesses/README.md` before adding one.
