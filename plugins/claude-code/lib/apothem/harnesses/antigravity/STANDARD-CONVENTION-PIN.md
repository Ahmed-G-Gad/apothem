<!-- SPDX-License-Identifier: MIT -->

# Antigravity Standard Convention Pin

## Snapshot

- Snapshot date: 2026-11-03
- Snapshot note: refreshed against the Antigravity docs at `antigravity.google/docs` (plugins, build plugins, customization discovery, rules, skills, hooks, MCP, sidecars, CLI migration, CLI settings, CLI troubleshooting, changelog), the docs index, and the `google-antigravity/antigravity-cli` issue tracker. The plugin folder is now `~/.gemini/config/plugins/apothem/`, no longer `~/.gemini/antigravity-cli/plugins/apothem/` (see Plugin Location). The refresh also corrects the global hooks locations, the skills locations, the role of `~/.gemini/antigravity-cli/` (the CLI's app-data folder, not its customization root), and the `plugin.json` field list. The global rule files, the rule frontmatter and size limits, and the MCP paths read the same as on 2026-10-03. Previous 2026-10-03.
- Adapter source: `src/apothem/harnesses/antigravity/`.
- Evidence level: vendor-doc pinned (living docs; the pages carry no version or commit, so the no-immutable-source exception stands; the CLI changelog and the issue tracker supply the version evidence for the plugin folder). No vendor-native UI claim is made here.

## Plugin Location

- Plugin root: `~/.gemini/config/plugins/apothem/`. Current Antigravity CLI
  releases (binary `agy`) install plugins into, and load them from,
  `~/.gemini/config/plugins/<name>/`: the plugins page names it as the CLI's
  filesystem location, `agy plugin install` on CLI 1.2.7 placed a plugin there
  and a clean session loaded its rule (issue 1067), and the `/mcp` header on CLI
  1.2.13 names it (issue 1127). The Antigravity App and IDE load the same
  folder, so the plugin loads in all three. A plugin placed in that folder needs
  no registration: the plugins page documents manual placement there, CLI 1.2.11
  handles such plugins (one whose MCP server needs configuration variables
  starts disabled, as a plugin installed through `/plugin` does), and a
  `plugins.json` discovery manifest is optional and adds to the standard
  folders.
- Earlier folder: `~/.gemini/antigravity-cli/plugins/apothem/`, inside the CLI's
  private app-data folder. Issue 123 (2026-05-22) names
  `~/.gemini/antigravity-cli/plugins/<plugin_name>/` as the CLI's install path
  and `~/.gemini/config/plugins/` as the App's ("AGY 2.0") and IDE's, and the
  `/mcp` header read `Plugins (~/.gemini/antigravity-cli/plugins)` on
  2026-05-29 (issue 233). The docs kept naming that folder after the CLI's
  install target moved (issue 1067, 2026-09-20, reports the mismatch against
  CLI 1.2.7); the pages retrieved 2026-11-03 name `~/.gemini/config/plugins/`
  and none of them names the earlier plugin folder.
- Evidence for the move (issue numbers are in
  `google-antigravity/antigravity-cli`):
  - CLI changelog, v1.0.2: the `agy plugin` subcommand installs downloaded
    plugins to the shared configuration folder `~/.gemini/config/` instead of
    the private app-data folder. The entry records the install target only: it
    names `~/.gemini/config/`, not `~/.gemini/config/plugins/`, and does not
    say which folders the CLI loads plugins from. The changelog page shows the
    placeholder date January 1, 2026 for v1.0.0 to v1.0.2; issue 123 reports
    1.0.1 on 2026-05-22 and announces the change for the next release.
  - Issue 123 (2026-05-23): a collaborator wrote that the CLI would default
    installation to `~/.gemini/config/plugins/` in the next release. On
    2026-09-05 a collaborator wrote on the same issue that the CLI's plugin
    installation paths had been unified there.
  - Issue 1067 (2026-09-20): on CLI 1.2.7, `agy plugin install` placed a plugin
    in `~/.gemini/config/plugins/<name>/`, and a clean session discovered it
    there and loaded its rule.
  - Issue 1165 (2026-10-05): a valid plugin staged in
    `~/.gemini/antigravity-cli/plugins/` passes `agy plugin validate` but is not
    listed by `agy plugin list` and not loaded, while a plugin under
    `~/.gemini/config/plugins/` is discovered. The report names no CLI version.
  - The `/mcp` panel header reads `Plugins (~/.gemini/config/plugins)` on CLI
    1.2.13 (issue 1127, 2026-09-29); it read
    `Plugins (~/.gemini/antigravity-cli/plugins)` on 2026-05-29 (issue 233).
- Supported minimum: none pinned. CLI 1.2.7 is the oldest release with direct
  evidence of loading plugins from `~/.gemini/config/plugins/`; the 1.0.2
  release note records the install target only. The CLI updates itself in the
  background (a check at most every 15 minutes;
  `AGY_CLI_DISABLE_AUTO_UPDATE=true` turns the updater off). Among the
  tracker's issues 1007 to 1407 (filed 2026-09-12 to 2026-11-03), the oldest
  CLI version named in a version field is 1.1.8 (issue 1155).
- Earlier installs: an install or update over an install that holds the earlier
  folder backs `~/.gemini/antigravity-cli/plugins/apothem/` up under the Apothem
  backup root and removes it whole, then writes the new folder; an uninstall
  removes the earlier folder whole and Apothem's files from the current one.
  Other files under `~/.gemini/antigravity-cli/` are not touched.
- Shared folder: the App and IDE load the same folder as the CLI (the plugins
  page lists manual placement in `~/.gemini/config/plugins/` for the App and
  for the IDE, and says plugins installed in the App appear in the CLI's
  Installed tab; the customization discovery page lists `~/.gemini/config/` as
  the personal scope of the App and the CLI; issue 1165 describes plugins as
  shared across the CLI, the Desktop App and the IDE). A plugin there reaches
  every surface, so the Apothem plugin's always-on rules, skills and helper
  definitions apply in the App and IDE as well as the CLI. `plugin.json` has no
  field that limits a plugin to one surface and the docs describe no other
  per-surface switch; issue 1165 asks for one.
- TODO(clarify): whether the current CLI (1.4.12 on 2026-11-03) still loads a
  plugin from `~/.gemini/antigravity-cli/plugins/`. `agy` does not run in the
  repository's checks and no CI job installs it, so a run of a current `agy`
  against a plugin staged there settles it. Issue 1165 reports that such a
  plugin is not loaded; the adapter writes only the new folder either way.

## Plugin rules and manifest (verified 2026-11-03)

- Rules: every `.md` file inside a `rules/` directory must start with YAML
  frontmatter declaring a valid `trigger` (`always_on`, `model_decision`,
  `glob`, or `manual`); a file without one, or with an unrecognised value, is
  silently discarded. `model_decision` requires `description`; `glob` requires
  `globs` (comma-separated patterns). The Antigravity CLI activates the rules
  packaged under `~/.gemini/config/plugins/<plugin-folder>/rules/`.
  The adapter therefore converts each Apothem rule (`antigravity_rules` install
  mode): `alwaysApply: true` becomes `trigger: always_on`, a non-empty
  `pathFilter` becomes `trigger: glob` with `globs`, any other rule becomes
  `trigger: model_decision`; `description` is always emitted and the Apothem
  keys `name`, `pathFilter`, and `alwaysApply` are dropped.
- Always-on budget: all active global and `always_on` rules share a
  20,000-token budget; past it Antigravity demotes the largest rule files to
  `- <path>: <description>` pointers the agent reads on demand. The adapter
  emits five `always_on` rules (the four core rules and the rule index), about
  38,000 bytes or 11,000 tokens at 3.5 bytes per token, so none is demoted;
  every other rule is `glob`. Single rule files are truncated past 24,000
  bytes. Two path-scoped companions exceed that
  (`interactive-questions-canonical-shapes` and
  `canonical-layout-reporting-tiers`, measured 2026-10-24), so only their start
  loads on a match.
- Manifest: `plugin.json` at the plugin root (or `.antigravity-plugin/plugin.json`,
  which takes precedence) is checked by `agy plugin validate` against the
  published schema, which sets `additionalProperties: false`. `name` is the only
  required key (lowercase kebab-case). The schema also admits `$schema`,
  `displayName`, `description`, `version`, `disabled`, `logo`,
  `suggestedPrompts`, `skills`, `author`, `homepage`, `repository`, `license`,
  `keywords`, and `extensions`; `displayName`, `description`, `version`, `logo`,
  and `author` are required only for a Marketplace submission. The template
  carries `name` and `description` only.

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
  2026-06-18 on the launch blog; `GEMINI.md` and `AGENTS.md` keep working. The
  launch blog was not re-read on 2026-11-03; the CLI migration page, re-read
  that day, confirms that `~/.gemini/GEMINI.md`, workspace `GEMINI.md`, and
  `AGENTS.md` keep working.
- Customization root: `~/.gemini/config/`, shared by the CLI, the App, and the
  IDE. It holds `rules/`, `skills/`, `agents/`, `plugins/`, `hooks.json`, and
  `mcp_config.json`, plus the optional discovery manifests `skills.json`,
  `rules.json`, `agents.json`, and `plugins.json`.
- App-data folders: `~/.gemini/antigravity-cli/` is the CLI's own folder
  (`settings.json`, `keybindings.json`, `cache/`, `updater/`, `brain/`),
  `~/.gemini/antigravity/` is the App's, and `~/.gemini/antigravity-ide/` is the
  IDE's; the hooks page names all three as `<app_data_dir>`, which holds each
  one's session transcripts under `brain/`. The App's folder also holds
  `mcp_oauth_tokens.json` (MCP page), `sidecar_data/` (sidecars page) and the
  legacy global skills folder `skills/` (skills page). Apothem writes no file
  into them. Releases before 2026-11-03 also listed `antigravity` (the retired
  pre-v1.0.1 Apothem tree at `~/.gemini/antigravity/`, a layout Apothem used
  before its first release) in the manifest's stale-sweep list, so every
  install and update backed up and removed the App's folder, with its MCP OAuth
  tokens, session transcripts, legacy skills and `sidecar_data/`. The list
  named no CLI data: its only entries under `~/.gemini/antigravity-cli/` were
  two machinery folders inside Apothem's own plugin folder. The entry is gone:
  install, update and uninstall no longer touch `~/.gemini/antigravity/`. Each
  earlier install or update that found the folder left a copy under
  `~/.apothem/backups/<timestamp>/antigravity/.gemini/antigravity/`, and
  Apothem keeps only the newest 10 Antigravity backup sets.
- Apothem plugin root: `~/.gemini/config/plugins/apothem/` (see Plugin
  Location).
- MCP: `mcpServers` in `mcp_config.json`, globally at
  `~/.gemini/config/mcp_config.json` and per workspace at
  `.agents/mcp_config.json` (stdio and remote servers; OAuth tokens in
  `~/.gemini/antigravity/mcp_oauth_tokens.json`). Apothem names this surface and
  authors no entries. This settles the earlier ambiguity between
  `~/.gemini/config/`, `~/.gemini/antigravity-cli/`, and `~/.gemini/antigravity/`:
  the first holds the configuration and the other two are app-data folders.
- Skills: workspace `.agents/skills/`, global `~/.gemini/config/skills/` (shared
  by the CLI and the App), and plugin-provided
  `~/.gemini/config/plugins/<plugin-folder>/skills/`. The CLI also loads
  `~/.gemini/antigravity-cli/skills/` and `~/.gemini/skills/`, which the App does
  not read and which take priority over a same-name skill elsewhere. Apothem
  installs its skills into its own plugin's `skills/` directory, a documented
  location, so the registry skills cell is `native`.
- Commands: converted into Antigravity skills under the Apothem plugin because
  the CLI routes command-like prompts through skills.
- Hooks: `hooks.json` at `.agents/hooks.json` (workspace), at
  `~/.gemini/config/hooks.json` (global), and at the root of an installed
  plugin. The hooks page now states that hooks in
  `~/.gemini/antigravity-cli/settings.json` are not loaded; an archived copy of
  the page from 2026-10-16 still listed that file as a global location.
  Apothem registers no hooks for Antigravity and writes no `hooks.json` at the
  plugin root or in `~/.gemini/config/`: its hook scripts, with a copy of its
  `hooks.json`, ship as support files under the plugin's
  `.apothem/support/hooks/`, where Antigravity does not read them. Building the
  hook translation is adapter work, not a documentation gap.
- Memory: the docs index (`antigravity.google/llms.txt`, re-read 2026-11-03)
  lists no durable-memory page, and `antigravity.google/docs/memory` answered
  404 on 2026-10-03, so the registry memory cell stays `discovery-pending`.

## Vendor Sources

Retrieved 2026-11-03 unless marked.

- <https://antigravity.google/docs/rules> (rules and context files)
- <https://antigravity.google/docs/skills> (skill locations, including the legacy `~/.gemini/antigravity/skills/`)
- <https://antigravity.google/docs/mcp> (`mcp_config.json`, `mcp_oauth_tokens.json`)
- <https://antigravity.google/docs/plugins> (plugins and their folders)
- <https://antigravity.google/docs/build-plugins> (`plugin.json` and its schema, plugin layout)
- <https://antigravity.google/docs/customization-discovery> (customization folders, discovery manifests)
- <https://antigravity.google/docs/hooks> (`hooks.json`, `<app_data_dir>`)
- <https://antigravity.google/docs/sidecars> (`sidecar_data/`)
- <https://antigravity.google/docs/cli/gcli-migration> (CLI migration)
- <https://antigravity.google/docs/cli/troubleshooting> (the CLI self-updater)
- <https://antigravity.google/docs/cli/using> (the CLI's `settings.json` and `keybindings.json`)
- <https://antigravity.google/docs/cli/commands/changelog> (the CLI's `cache/` folder)
- <https://antigravity.google/docs/changelog> (CLI changelog, v1.0.2 and v1.2.11)
- <https://antigravity.google/llms.txt> (docs index)
- <https://github.com/google-antigravity/antigravity-cli/issues/123> (plugin installation default; the CLI's and the App's and IDE's install paths on 2026-05-22)
- <https://github.com/google-antigravity/antigravity-cli/issues/1067> (CLI 1.2.7 installs to `~/.gemini/config/plugins/`)
- <https://github.com/google-antigravity/antigravity-cli/issues/1165> (plugin staged in the earlier folder is not loaded)
- <https://github.com/google-antigravity/antigravity-cli/issues/1127> (`/mcp` header on CLI 1.2.13)
- <https://github.com/google-antigravity/antigravity-cli/issues/233> (`/mcp` header on 2026-05-29)
- <https://github.com/google-antigravity/antigravity-cli/issues/1155> (oldest CLI version in the sampled issues)

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
(`~/.gemini/config/plugins/apothem/`), but that tree is
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
distributable plugin-alone bundle. Antigravity documents installable plugins and
manual placement in `~/.gemini/config/plugins/<name>/`
(`antigravity.google/docs/plugins`); building a standalone Apothem plugin
package is a separate packaging decision. The engine install is the sole
persistence path today.
