<!-- SPDX-License-Identifier: MIT -->

# Antigravity Standard Convention Pin

## Snapshot

- Snapshot date: 2026-06-25
- Snapshot note: live re-verification via the official Antigravity codelabs (`codelabs.developers.google.com`) + launch blog (`antigravity.google/blog`) — the `antigravity.google/docs` SPA still returns empty bodies under fetch, so partial confidence persists, but official Google sources now CONFIRM the `~/.gemini/GEMINI.md` global anchor, the `~/.gemini/antigravity-cli/plugins/` plugin root, and plugin `skills/` auto-discovery (resolving the prior unverified skills-scan limitation below), and REFINE the MCP-config path toward `~/.gemini/config/mcp_config.json` (vs the prior `antigravity-cli/` reading — the adapter authors no MCP entries, so no write is affected). Previous 2026-05-31 / 2026-05-28.
- Adapter source: `src/apothem/harnesses/antigravity/`.
- Evidence level: **partial confidence.** The official `antigravity.google/docs/*`
  pages are a JavaScript single-page app that returns empty bodies under fetch;
  a browser-capable re-fetch on 2026-05-31 could not defeat the empty-body
  problem. Every convention claim below rests on dated-2026 authority-domain
  snapshots and third-party sources quoting the official docs, not raw official
  page text. No vendor-native UI claim is made here.
- Immutable pin: none — Antigravity is a hosted product with no version or
  commit surface (the sitemap exposes a changelog but no pin); the
  `no-immutable-source` exception stands for every claim.

## Antigravity CLI Surface Projection (partial confidence)

- Global context anchor: `~/.gemini/GEMINI.md` (this user-scope adapter writes
  the global file; the sibling project-scope gemini_cli adapter writes
  `<project>/GEMINI.md` — distinct targets that share only the filename and the
  `~/.gemini/` config root). `AGENTS.md` continues working unchanged.
- Migration: the standalone Gemini CLI sunset for individual tiers (dated
  2026-06-18 at the launch blog) folds that surface into Antigravity CLI
  (binary `agy`); `GEMINI.md` and `AGENTS.md` continue working unchanged.
- CLI customization root: `~/.gemini/antigravity-cli/`.
- Apothem plugin root: `~/.gemini/antigravity-cli/plugins/apothem/`.
- MCP: the `mcpServers` object in the global `mcp_config.json` /
  `.agents/mcp_config.json` (workspace); stdio entries use `command`/`args`/`env`,
  remote entries use `serverUrl`. Apothem names this surface but does not author
  MCP server entries. The global-config path carries a known ambiguity across
  authority snapshots: the 2026-06-25 re-verification refines it toward
  `~/.gemini/config/mcp_config.json`, while an earlier snapshot read
  `~/.gemini/antigravity-cli/mcp_config.json` and another the IDE-scoped
  `~/.gemini/antigravity/`. The adapter writes no MCP entries, so the ambiguity
  affects no write; the path is left unresolved pending a browser-verifiable
  docs pass.
- Skills: the confirmed global discovery root is `~/.gemini/antigravity-cli/skills/`;
  workspace skills live at `.agents/skills/`; the shared `~/.gemini/skills/`
  still auto-loads. Apothem installs its skills cohort into its own
  `plugins/apothem/skills/` namespace to avoid colliding with the operator's
  skills and Gemini CLI project-local files. The agent's auto-discovery of
  skills inside each plugin's `skills/` directory is confirmed by the official
  Antigravity codelabs + launch blog (re-verified 2026-06-25), resolving the
  prior tracked limitation; Apothem's `plugins/apothem/skills/` namespace is
  therefore a confirmed-discovered placement.
- Commands: converted into Antigravity skills under the Apothem plugin because the current CLI migration convention routes command-like prompts through skills.
- Hooks: Antigravity now documents a simple-JSON lifecycle-hook surface
  (global and workspace scope). Apothem retains its hook prose as support
  material under the Apothem plugin and does not register Antigravity hook
  events, because the adapter does not yet own a verified schema translation
  layer for the Antigravity hook JSON; building one is deferred until the docs
  are browser-verifiable.

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
distributable plugin-alone bundle. Building a standalone Antigravity plugin
package is deferred until the docs are browser-verifiable (the docs SPA returns
empty bodies under fetch — partial-confidence pin). The engine install is the
sole persistence path today.
