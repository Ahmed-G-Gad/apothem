<!-- SPDX-License-Identifier: MIT -->

# Antigravity Standard Convention Pin

## Snapshot

- Snapshot date: 2026-10-03
- Snapshot note: refreshed against the Antigravity docs at `antigravity.google/docs`. The pages now return their full text to a plain fetch, so the earlier empty-body limitation and its partial-confidence caveat no longer apply. The refresh settles the MCP config path, confirms plugin-provided skills, and records the hooks file locations. Previous 2026-06-25.
- Adapter source: `src/apothem/harnesses/antigravity/`.
- Evidence level: vendor-doc pinned (living docs; Antigravity exposes no version or commit surface, so the no-immutable-source exception stands). No vendor-native UI claim is made here.

## Plugin rules and manifest (verified 2026-10-02)

- Rules: every `.md` file inside a `rules/` directory must start with YAML
  frontmatter declaring a valid `trigger` (`always_on`, `model_decision`,
  `glob`, or `manual`); a file without one, or with an unrecognised value, is
  silently discarded. `model_decision` requires `description`; `glob` requires
  `globs` (comma-separated patterns). The Antigravity CLI activates the rules
  packaged under `~/.gemini/antigravity-cli/plugins/<plugin_name>/rules/`.
  The adapter therefore converts each Apothem rule (`antigravity_rules` install
  mode): `alwaysApply: true` becomes `trigger: always_on`, a non-empty
  `pathFilter` becomes `trigger: glob` with `globs`, any other rule becomes
  `trigger: model_decision`; `description` is always emitted and the Apothem
  keys `name`, `pathFilter`, and `alwaysApply` are dropped.
- Always-on budget: all active global and `always_on` rules share a
  20,000-token budget; past it Antigravity demotes the largest rule files to
  `- <path>: <description>` pointers the agent reads on demand. Single rule
  files are truncated past 24,000 bytes; no Apothem rule is that large.
- Manifest: `plugin.json` admits only `name` (required for the CLI) and
  `description`; the published schema sets `additionalProperties: false`. The
  template carries exactly those two keys.

## Antigravity CLI Surface Projection

- Context: Antigravity reads global rules from `~/.gemini/AGENTS.md`,
  `~/.gemini/GEMINI.md`, `~/.gemini/config/AGENTS.md`,
  `~/.gemini/config/GEMINI.md`, and `~/.gemini/config/rules/*.md`, and
  workspace rules from `AGENTS.md`, `GEMINI.md`, and `.agents/rules/*.md`.
  Each rule file is truncated past 24,000 bytes. This user-scope adapter writes
  the managed block in `~/.gemini/GEMINI.md`; Gemini CLI loads the same file,
  so the block is tool-neutral and the registry records Antigravity as the
  file's owner. The sibling project-scope gemini_cli adapter writes
  `<project>/GEMINI.md`.
- Migration: the earlier reading records Google folding the standalone Gemini
  CLI for individual tiers into Antigravity CLI (binary `agy`), dated
  2026-06-18 on the launch blog; `GEMINI.md` and `AGENTS.md` keep working. Not
  re-read on 2026-10-03.
- CLI customization root: `~/.gemini/antigravity-cli/`.
- Apothem plugin root: `~/.gemini/antigravity-cli/plugins/apothem/`.
- MCP: `mcpServers` in `mcp_config.json`, globally at
  `~/.gemini/config/mcp_config.json` and per workspace at
  `.agents/mcp_config.json` (stdio and remote servers; OAuth tokens in
  `~/.gemini/antigravity/mcp_oauth_tokens.json`). Apothem names this surface and
  authors no entries. This settles the earlier ambiguity between
  `~/.gemini/config/`, `~/.gemini/antigravity-cli/`, and `~/.gemini/antigravity/`.
- Skills: workspace `.agents/skills/`, global `~/.gemini/config/skills/`, CLI
  global `~/.gemini/antigravity-cli/skills/`, and plugin-provided
  `~/.gemini/antigravity-cli/plugins/<name>/skills/`. Apothem installs its skills
  into its own plugin's `skills/` directory, a documented location, so the
  registry skills cell is `native`.
- Commands: converted into Antigravity skills under the Apothem plugin because
  the CLI routes command-like prompts through skills.
- Hooks: `hooks.json` at `.agents/hooks.json` (workspace),
  `~/.gemini/config/hooks.json` or `~/.gemini/antigravity-cli/settings.json`
  (global), and inside an installed plugin. Apothem keeps its hook prose as
  support material under the plugin and registers no hook events; building the
  hook translation is adapter work, not a documentation gap.
- Memory: the docs index (`antigravity.google/llms.txt`) lists no durable-memory
  page and `antigravity.google/docs/memory` answers 404, so the registry memory
  cell stays `discovery-pending`.

## Vendor Sources

Retrieved 2026-10-03 unless marked.

- <https://antigravity.google/docs/rules> (rules and context files)
- <https://antigravity.google/docs/skills> (skill locations)
- <https://antigravity.google/docs/mcp> (`mcp_config.json`)
- <https://antigravity.google/docs/plugins> (plugins)
- <https://antigravity.google/docs/hooks> (`hooks.json`; retrieved 2026-10-02)
- <https://antigravity.google/llms.txt> (docs index; retrieved 2026-10-02)

## Discovery Targets

- Discovery target: mcp_servers by 2026-12-31 — decide whether Apothem renders the profile's MCP inventory into `~/.gemini/config/mcp_config.json` or keeps naming it as operator-owned.
- Discovery target: agent_memory by 2026-12-31 — re-check the Antigravity docs
  for a durable-memory surface; record the cell as `unsupported` if none is
  documented.

## Recommended Postfix Rendering

- Status: supported as plain text.
- Mechanism: Apothem emits the literal ` (Recommended)` suffix in the option label. The adapter forwards instruction text without transforming that suffix.
- Boundary: this pin does not claim a harness-native recommended-option widget. It only pins the text-rendered convention used by `rules/interactive-questions.md`.

## Long Context and Compaction

- Status: profile-managed.
- Mechanism: Apothem keeps full-suite `/plan-execute` runs continuous by externalizing state to `.apothem/plans/`, compacting or restarting the harness session at phase boundaries as needed, and restoring via the Blind Bootstrap sequence.
- Boundary: this pin does not claim vendor-native autocompaction or a long-context size. It pins the adapter-local state handoff and compaction-restoration convention used by `rules/context-management.md`.

## Large-Codebase Practice Projection

- Layered context: declared in `capabilities.yml` under `layered_context_surface`; no vendor-native hierarchy is claimed beyond the adapter's documented file/template surface.
- LSP symbol navigation: `tracked-gap` until a vendor-ratified plugin or tool surface is pinned.
- Hook learning capture: routed through the `persistent-conventions-vigilance` artifact-evolution cycle; pass-class hooks stay silent and recurring findings become rule, skill, hook, or documentation updates.

## Plugin-alone Persistence

Antigravity has a plugin directory convention
(`~/.gemini/antigravity-cli/plugins/apothem/`), but that tree is
**engine-materialized**, not a standalone-installable bundle: the `plugin.json`
and every cohort beneath it are written by `apothem install`, not shipped as a
pre-built plugin an operator installs by itself. There is no Apothem-distributed
plugin-alone install path for this harness; everything requires the full
`apothem install --harness antigravity` engine run.

| Artifact class | Persists standalone? | Mechanism / limit |
|---|---|---|
| Context anchor (rules-as-text) | No — requires `apothem install` | `~/.gemini/GEMINI.md` is engine-written; no pre-built bundle carries it. |
| Commands / Skills / Agents / Rules | No — requires `apothem install` | The plugin tree (`plugins/apothem/{skills,agents,rules}/`) is engine-materialized; nothing exists before the install run. |
| Hooks | No — tracked-gap | Antigravity documents a JSON lifecycle-hook surface, but the adapter owns no verified schema-translation layer yet, so it registers no hooks even via the engine. |
| MCP / Settings | No — operator-owned | `mcpServers` lives in operator-owned `mcp_config.json`; the adapter authors no entries. |

Platform note: a plugin directory exists, but as an engine-write target, not a
distributable plugin-alone bundle. Antigravity documents installable plugins
(`antigravity.google/docs/plugins`); building a standalone Apothem plugin
package is a separate packaging decision. The engine install is the sole
persistence path today.
