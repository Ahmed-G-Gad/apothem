<!-- SPDX-License-Identifier: MIT -->

# Claude Code Standard Convention Pin

## Snapshot

- Snapshot date: 2026-10-03
- Snapshot note: refreshed against the Claude Code docs at `code.claude.com/docs/en/` (settings, permissions, memory, hooks, MCP, skills, sub-agents, status line, output styles). The 2026-10-02 adapter changes followed these pages: agent and command frontmatter name the Task tools, and the settings template carries the documented `$schema` line. Previous 2026-06-25.
- Adapter source: `src/apothem/harnesses/claude_code/`
- Evidence level: vendor-doc pinned (living MDX docs; no immutable pin). No vendor-native UI claim is made here.
- Authority host: `code.claude.com`; the older `docs.anthropic.com` and `docs.claude.com` paths redirect there.

## MCP and Permissions Surface Projection

- MCP: registered with `claude mcp add --scope local|project|user` and stored in `~/.claude.json` (user and local scope) and the project `.mcp.json`, not `settings.json`. Apothem authors no MCP server entries; the template `settings.json` carries no `mcpServers`.
- Permissions: `settings.json` `permissions` holds `allow`, `ask`, and `deny` rules, evaluated deny, then ask, then allow; the first match in that order decides. The Apothem template uses `allow` and `deny`.
- Hook events: Apothem wires a current subset (SessionStart, PreToolUse with Write/Edit/NotebookEdit/Bash matchers, PreCompact, PostCompact, Stop).
- Shared root: `~/.claude/skills/`, where the adapter installs skills, is also loaded by Cursor and OpenCode; the registry records Claude Code as its owner and `apothem install` names the other readers.

## Vendor Sources

Retrieved 2026-10-03 unless marked.

- <https://code.claude.com/docs/en/settings> (settings, `$schema`)
- <https://code.claude.com/docs/en/memory> (CLAUDE.md files)
- <https://code.claude.com/docs/en/hooks> (hook events)
- <https://code.claude.com/docs/en/mcp> (MCP scopes and storage)
- <https://code.claude.com/docs/en/permissions> (rule order; retrieved 2026-10-02)
- <https://code.claude.com/docs/en/skills> (skills; retrieved 2026-10-02)
- <https://code.claude.com/docs/en/sub-agents> (agent frontmatter; retrieved 2026-10-02)

## Discovery Targets

- Discovery target: mcp_servers by 2026-12-31 — decide whether Apothem renders the profile's MCP inventory into the project `.mcp.json` or keeps naming it as operator-owned.

## Recommended Postfix Rendering

- Status: supported as plain text.
- Mechanism: Apothem emits the literal ` (Recommended)` suffix in the option label. Claude Code-facing prompts and rule text preserve that suffix as authored.
- Boundary: this pin does not claim a harness-native recommended-option widget. It only pins the text-rendered convention used by `rules/interactive-questions.md`.

## Long Context and Compaction

- Status: profile-managed.
- Mechanism: Apothem keeps full-suite `/plan-execute` runs continuous by externalizing state to `.apothem/plans/`, compacting or restarting the harness session at phase boundaries as needed, and restoring via the Blind Bootstrap sequence.
- Boundary: this pin does not claim vendor-native autocompaction or a long-context size. It pins the adapter-local state handoff and compaction-restoration convention used by `rules/context-management.md`.

## Large-Codebase Practice Projection

- Layered context: declared in `capabilities.yml` under `layered_context_surface`; no vendor-native hierarchy is claimed beyond the adapter's documented file/template surface.
- LSP symbol navigation: `tracked-gap` until a vendor-ratified plugin or tool surface is pinned.
- Hook learning capture: routed through the `persistent-conventions-vigilance` artifact-evolution cycle; pass-class hooks stay silent and recurring findings become rule, skill, hook, or documentation updates.

## Web-Fetch / Browser-Retrieval Surface

- Capability: `web_fetch` = **yes**. The backing dimension for `rules/source-accessibility.md` step 1 ("retrieve through the host's browser / fetch capability").
- Vendor-confirmed: Claude Code ships built-in WebFetch and WebSearch tools (the CLI surface of the `web_fetch_*` / `web_search_*` server tools).
- Evidence: vendor-doc-url <https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-fetch-tool> (the prior `docs.claude.com` path 302-redirects here); snapshot-id living MDX (no immutable commit; living-docs host); snapshot-date 2026-06-21.

## Plugin-alone Persistence

Claude Code is the one harness with a **full standalone plugin**:
`plugins/claude-code/.claude-plugin/plugin.json` (the marketplace `source`,
installed via `/plugin marketplace add ahmed-g-gad/apothem`) declares
`commands`, `agents`, `skills`, and `hooks` (`./lib/apothem/hooks/hooks.json`,
resolved against `${CLAUDE_PLUGIN_ROOT}`). The repository root carries no
plugin manifest. Installing the plugin *alone* — without running
`apothem install` — persists most of the cohort directly.

| Artifact class | Persists plugin-alone? | Mechanism / limit |
|---|---|---|
| Commands | Yes | The manifest `commands` array (45 entries, one per command file) loads the 45 slash-commands from the plugin tree. |
| Agents | Yes | The manifest `agents` array (12 entries) loads sub-agents from the plugin tree. |
| Skills | Yes | The manifest `skills` reference loads the skill cohort from the plugin tree. |
| Hooks | Yes | The manifest `hooks` field points at the bundled `hooks.json`, wired with `${CLAUDE_PLUGIN_ROOT}`-relative dispatch — the PreToolUse/SessionStart/etc. pipeline fires from the plugin alone. |
| Output styles | Yes | The 4 styles ship in the plugin's default `output-styles/` folder, which Claude Code scans when the manifest sets no `outputStyles` key ([plugins reference](https://code.claude.com/docs/en/plugins-reference), retrieved 2026-10-03); they are selectable from `/config` with the plugin alone. |
| Rules | Degraded — requires `apothem install` for full reference tree | The plugin carries no rules-directory primitive; the embedded directives degrade to a SessionStart `additionalContext` pointer. The full `${HARNESS_ROOT}/rules/` reference tree lands only via the engine. |
| Settings / statuslines / gate matchers | No — requires `apothem install` | `settings.json` (managed allow/deny gates only — see the MCP row above), `statuslines/`, and the conformity `gate.py` + `schemas/` ride beside the engine install, not the plugin package. The statusline ships as `statuslines/statusline.md`, not as a `settings.json` key. |
| MCP | No — operator-owned | MCP servers register via `claude mcp add` into `~/.claude.json` / project `.mcp.json`; neither the plugin nor the engine authors entries. |

Bundle status: this is the reference plugin-alone implementation — commands,
agents, skills, output styles, and hooks persist from the plugin package
directly; only the full rules reference tree, settings, and the gate engine
need `apothem install`.
