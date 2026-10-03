<!-- SPDX-License-Identifier: MIT -->

# Cursor Standard Convention Pin

## Snapshot

- Snapshot date: 2026-10-03
- Snapshot note: refreshed against `cursor.com/docs`. The rules page moved to `cursor.com/docs/rules`, the MCP page to `cursor.com/docs/mcp`, and the old `@Web` page is gone. The agent's Browser tool visits URLs, so `web_fetch` moves from partial to yes. Previous 2026-06-25.
- Adapter source: `src/apothem/harnesses/cursor/`
- Evidence level: vendor-doc pinned (living docs; no-immutable-source exception). No vendor-native UI claim is made here.

## Official Surface Refresh

- Rules: `.cursor/rules/*.mdc` with frontmatter `description` / `globs` /
  `alwaysApply`. The adapter writes only `apothem-rules.mdc`.
- MCP: `.cursor/mcp.json` (project) and `~/.cursor/mcp.json` (global), plus
  servers installed from the Customize page or the Cursor Marketplace.
  Operator-owned; the adapter names the surface and authors no entries.
- Skills: Cursor loads `.agents/skills/`, `.cursor/skills/`,
  `~/.agents/skills/`, and `~/.cursor/skills/`, and for compatibility
  `.claude/skills/`, `.codex/skills/`, `~/.claude/skills/`, and
  `~/.codex/skills/`. The Codex adapter's `~/.agents/skills/` and the Claude
  Code adapter's `~/.claude/skills/` therefore reach Cursor (shared roots in the
  registry).
- The vendor documents plugins (`.cursor-plugin/plugin.json`, bundling agents,
  commands, skills, and hooks) and a marketplace. The adapter delivers only the
  project rules file and authors none of those (deliberate rules-only posture).
- Settings (IDE-managed) and status lines are not file surfaces the adapter
  owns.

## Web-Fetch / Browser-Retrieval Surface

- Capability: `web_fetch` = **yes**. The backing dimension for
  `rules/source-accessibility.md` step 1 ("retrieve through the host's browser /
  fetch capability").
- Vendor-confirmed: Cursor's agent has a Browser tool that "can navigate
  anywhere on the web by visiting URLs, following links", run as a secure web
  view controlled through an MCP server. This replaces the earlier `partial`
  reading, which rested on the user-invoked `@Web` search alone.
- Evidence: vendor-doc-url <https://cursor.com/docs/agent/tools/browser>;
  snapshot-id living docs; snapshot-date 2026-10-03.

## Vendor Sources

Retrieved 2026-10-03.

- <https://cursor.com/docs/rules> (rules)
- <https://cursor.com/docs/mcp> (`mcp.json`)
- <https://cursor.com/docs/skills> (skill directories)
- <https://cursor.com/docs/agent/tools/browser> (Browser tool)

## Discovery Targets

- Discovery target: mcp_servers by 2026-12-31 — decide whether Apothem renders the profile's MCP inventory into `.cursor/mcp.json` or keeps naming it as operator-owned.

## Recommended Postfix Rendering

- Status: supported as plain text.
- Mechanism: Apothem emits the literal ` (Recommended)` suffix in the option label. Cursor rule templates preserve that suffix as authored.
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

Cursor documents a vendor plugin mechanism (`.cursor-plugin/plugin.json` that can
bundle agents, commands, skills, and hooks), but **Apothem ships no Cursor
plugin bundle** — the adapter is project-scope rules-only, writing a single
merged MDC rules file at `<project>/.cursor/rules/apothem-rules.mdc` and authoring
no other cohort. There is no Apothem-distributable standalone bundle; every
artifact requires the full `apothem install --harness cursor --project <path>`
engine run.

| Artifact class | Persists standalone? | Mechanism / limit |
|---|---|---|
| Rules | No — requires `apothem install` | The merged `apothem-rules.mdc` (carrying the embedded behavioral mandates) is written only by the engine into the vendor-native `.cursor/rules/` directory. Nothing persists before that run. |
| Commands / Skills / Agents / Hooks | No — Apothem ships no bundle | Cursor's `.cursor-plugin/plugin.json` accepts these cohorts, but Apothem authors no Cursor plugin; the rules-only posture is deliberate. Bundling the cohort into a Cursor plugin is a documented future propagation-write-planning concern, not part of this adapter today. |
| MCP / Settings | No — operator-owned | `~/.cursor/mcp.json` / `.cursor/mcp.json` and IDE-managed settings are operator-owned; the adapter authors no entries. |

Platform note: the vendor plugin surface exists; the Apothem-distributable
plugin bundle does not yet. The merged rules file via `apothem install` is the
sole persistence surface for now.
