<!-- SPDX-License-Identifier: MIT -->

# harnesses

> **Role.** Per-harness adapter subpackages. Each adapter translates the shared `apothem` corpus into one AI tool's native configuration on disk. Harness identity, entry-point paths, target declarations, docs coverage, package-data expectations, and capability support live in `apothem.lib.harness_registry`; `pyproject.toml` mirrors the same entry-point set.

## The `HarnessAdapter` protocol

`HarnessAdapter` is defined in the foundation layer at [`lib/harness_protocol.py`](../lib/harness_protocol.py) and re-exported by `__init__.py`, so `from apothem.harnesses import HarnessAdapter` stays the public import path every concrete adapter satisfies. The lifecycle contract is intentionally small; registry metadata carries the public identity, docs, capability, package-data, and target-path obligations:

| Member | Contract |
|--------|----------|
| `name` | Canonical kebab-case harness identifier (e.g. `'claude-code'`). |
| `output_path` | Absolute path to the target configuration file. |
| `install(profile)` | Materialize the harness configuration from the shared profile dict and return a structured materialization run when the adapter writes through the shared driver. |
| `update(profile)` | Re-materialize the harness configuration from an updated profile dict and return the same structured run surface. |
| `uninstall()` | Remove the harness configuration file if present. |
| `is_installed()` | Return `True` if the harness configuration file exists on disk. |
| `verify()` | Return `True` if the installed harness configuration is valid. |

## Adapter subpackage shape

Each harness subpackage carries the same core module set: `__init__.py` (the adapter class), `install.py`, `uninstall.py`, `update.py`, and `verify.py`. Adapters that render a native configuration file also carry `materializer.py`. Every subpackage also ships two declarative companions — `capabilities.yml` (the adapter's per-cohort capability matrix, cross-checked by the registry-capability-consistency validator) and `STANDARD-CONVENTION-PIN.md` (the pinned upstream-convention reference the adapter honors) — and, where the harness materializes native config from fixed files, a `templates/` directory. Template-propagation and conversion behavior is declared in `lib/propagation-manifest.yaml`.

## The seventeen harnesses

| Harness | Native config target | Shape |
|---------|----------------------|-------|
| `claude_code` | `~/.claude/settings.json`, `~/.claude/{agents,rules,skills,statuslines,output-styles}/`, plus `~/.claude/.apothem/support/{templates,hooks,conformity,schemas}/` | Native Claude Code adapter; command prompts are wrapped as skills. |
| `antigravity` | `~/.gemini/GEMINI.md` plus `~/.gemini/antigravity-cli/plugins/apothem/` | Antigravity CLI plugin adapter (no materializer). |
| `codex` | `~/.codex/AGENTS.md`, `~/.codex/hooks.json`, `~/.codex/hooks/`, `~/.codex/agents/*.toml`, `~/.agents/skills/`, `~/.config/apothem/{rules,templates}/` | Native Codex adapter; does not write `config.toml`. |
| `cursor` | `<project>/.cursor/rules/apothem-rules.mdc` | Project-scope manifest adapter. |
| `gemini_cli` | `<project>/GEMINI.md` plus `<project>/.gemini/{commands,skills,agents}/` and `<project>/.gemini/.apothem/support/` | Project-scope manifest adapter with TOML command conversion. |
| `github_copilot` | `<project>/.github/copilot-instructions.md` | Project-scope manifest adapter. |
| `hermes` | `~/.hermes/config.yaml` plus `~/.hermes/.apothem/support/` | Materializer (native MCP via `mcp_servers`); support cohorts under `~/.hermes/.apothem/support/`. |
| `kimi_code` | `<project>/AGENTS.md` plus `<project>/.kimi-code/.apothem/support/` | Project-scope manifest adapter; native agent memory. |
| `open_claw` | `~/.openclaw/openclaw.json` plus `~/.openclaw/.apothem/support/` | Support cohorts under `~/.openclaw/.apothem/support/`; no config keys authored (name-allowlist skills, CLI MCP). |
| `opencode` | `~/.config/opencode/opencode.json`, `commands/`, `skills/`, `agents/`, `.apothem/support/` | Materializer plus native commands, skills, and agents. |
| `qwen_code` | `~/.qwen/settings.json`, `~/.qwen/QWEN.md`, `commands/`, `skills/`, `agents/`, `.apothem/support/` | Materializer plus native hooks, commands, skills, agents, context anchor, and support cohorts. |
| `windsurf` | `<project>/.devin/rules/apothem-rules.md` | Project-scope manifest adapter (Devin Desktop preferred surface; `.windsurf/rules/` fallback). |
| `codebuddy` | `<project>/.codebuddy/rules/apothem-rules.md` | Project-scope manifest adapter. |
| `kiro` | `<project>/.kiro/steering/apothem-rules.md` | Project-scope manifest adapter. |
| `trae` | `<project>/.trae/rules/apothem-rules.md` | Project-scope manifest adapter. |
| `zed` | `<project>/.rules` | Project-scope manifest adapter; flat project-root file. |
| `glm` | `<project>/.apothem/providers/glm.toml` | Project-scope provider adapter (GLM / Z.ai model backend; TOML config only). |

## Conventions

- Adapters consume their propagation contract from `lib/propagation-manifest.yaml` when they copy or convert shared cohorts.
- Registry rows are the source of truth for the exact seventeen public IDs, package keys, adapter entry points, docs pages, test fixtures, package-data keys, target declarations, and capability states.
- The `~/.gemini/` user-scope home namespace belongs to the `antigravity` adapter; the `gemini_cli` adapter is project-scope and writes only under the operator-supplied `--project <path>` root, so the two never collide on the shared Gemini home.
- Project-scope adapters (`cursor`, `gemini_cli`, `github_copilot`, `kimi_code`, `windsurf`, `codebuddy`, `kiro`, `trae`, `zed`, `glm`) opt in via `requires_project = True`; `output_path` is a display-only sentinel and the concrete target resolves per-invocation through `resolve_output_path(project)`. The CLI rejects any lifecycle invocation that omits `--project <path>`, and `is_installed` / `verify` return `False` when no project is supplied.
- The shared install driver validates every manifest source and target before writing, reports created/updated/unchanged/skipped/warning/error outcomes, supports dry-run, and projects unsupported or discovery-pending registry capability cells as warnings.
- Existing matching targets are backed up before replacement. Shared discovery directories are merged child-by-child so unrelated operator-authored entries survive Apothem updates, and unchanged generated content is left untouched.
- The `claude_code` adapter deliberately does **not** manage the operator-owned memory file at the harness root; governance reaches that harness through the propagated `rules/` tree and the `SessionStart` hook, never by rewriting the operator's memory.
- The `codex` adapter resolves the harness home through the `CODEX_HOME` environment variable, defaulting to the user-scope root when the variable is unset.

## Related

- [`lib/harness_materializer.py`](../lib/harness_materializer.py) — shared building blocks for the single-file materializers.
- [`lib/harness_protocol.py`](../lib/harness_protocol.py) — the `HarnessAdapter` Protocol contract, defined in the foundation layer and re-exported here.
- [`lib/harness_registry.py`](../lib/harness_registry.py) — central exact-seventeen registry and adapter contract metadata.
- [`lib/propagation-manifest.yaml`](../lib/propagation-manifest.yaml) — the propagation contract consumed by manifest-driven adapters.
