<!-- SPDX-License-Identifier: MIT -->

# Cursor Standard Convention Pin

## Snapshot

- Snapshot date: 2026-06-25
- Snapshot note: live re-verification against `cursor.com/docs/context/rules` — the `.cursor/rules/*.mdc` rules surface, the frontmatter fields (`description` / `globs` / `alwaysApply`), and the `docs.cursor.com`→`cursor.com/docs` host move all confirmed current.
- Adapter source: `src/apothem/harnesses/cursor/`
- Evidence level: adapter-local projection; no vendor-native UI claim is made here.

## Official Surface Refresh

- Refreshed live 2026-05-31 against the current Cursor documentation. The
  authority host moved: `docs.cursor.com` now 308-redirects to `cursor.com/docs`.
  No immutable version pin is exposed (mutable docs site), so every captured
  convention carries a no-immutable-source exception.
- Confirmed live: rules surface `.cursor/rules/*.mdc` (frontmatter
  `description`/`globs`/`alwaysApply`); MCP via `~/.cursor/mcp.json` plus
  `.cursor/mcp.json` (operator-owned; the adapter recognizes it but does not
  author entries).
- The vendor now documents a plugin mechanism (`.cursor-plugin/plugin.json`)
  that can bundle agents, commands, skills, and hooks. The adapter delivers only
  the project rules file (`apothem-rules.mdc`) and authors none of those cohorts;
  this rules-only posture is deliberate and the plugin-bundle delivery question
  is a propagation write-planning concern, not part of this adapter.
- Settings (IDE-managed) and status-lines remain undocumented as file surfaces.

## Web-Fetch / Browser-Retrieval Surface

- Capability: `web_fetch` = **partial**. The backing dimension for
  `rules/source-accessibility.md` step 1 ("retrieve through the host's browser /
  fetch capability").
- Vendor-confirmed PARTIAL: Cursor exposes `@Web` — a user-invoked
  context-injection web search ("performs a live web search to retrieve
  up-to-date information"), plus an "Always search the web" auto setting. It is a
  context-injection symbol rather than a documented autonomous agent-loop fetch
  tool, hence the `partial` subset boundary (user-invoked search yes; autonomous
  fetch tool not documented).
- Evidence: vendor-doc-url <https://docs.cursor.com/context/@-symbols/@-web>;
  snapshot-id living docs; snapshot-date 2026-06-21.

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
