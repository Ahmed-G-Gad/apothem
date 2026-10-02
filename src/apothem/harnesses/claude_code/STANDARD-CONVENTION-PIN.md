<!-- SPDX-License-Identifier: MIT -->

# Claude Code Standard Convention Pin

## Snapshot

- Snapshot date: 2026-06-25
- Snapshot note: live re-verification against `code.claude.com` docs (hooks-guide, sdk-permissions) — the `code.claude.com` authority host, the `settings.json` hooks structure + permission tiers (allow / ask / deny, deny-first), and the hook-event taxonomy all confirmed current; no immutable pin (living MDX docs)
- Adapter source: `src/apothem/harnesses/claude_code/`
- Evidence level: adapter-local projection; no vendor-native UI claim is made here.
- Authority host: `code.claude.com` — the prior `docs.anthropic.com` / `docs.claude.com` hosts 301-redirect here (confirmed live 2026-05-31). The adapter pins no doc URLs in code, so no in-code URL change is required.

## MCP and Permissions Surface Projection

- MCP: registered via `claude mcp add --scope local|project|user`. Storage is `~/.claude.json` (user/local scope) and project `.mcp.json` — **not** `settings.json` (confirmed live 2026-05-31; `settings.json` carries only managed allow/deny gates). Apothem authors no MCP server entries; the template `settings.json` carries no `mcpServers`.
- Permissions: `settings.json` `permissions` carries three tiers — `allow`, `ask`, `deny` — evaluated deny → ask → allow, first match wins. The Apothem template uses the `allow` and `deny` tiers; the `ask` tier is available but unused by default.
- Hook events: the vendor taxonomy has expanded to roughly 30 events. Apothem wires a current, valid subset — SessionStart, PreToolUse (Write/Edit/NotebookEdit/Bash matchers), PreCompact, PostCompact, Stop — all confirmed current 2026-05-31; no template change required.

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
| Rules | Degraded — requires `apothem install` for full reference tree | The plugin carries no rules-directory primitive; the embedded directives degrade to a SessionStart `additionalContext` pointer. The full `${HARNESS_ROOT}/rules/` reference tree lands only via the engine. |
| Settings / output-styles / statuslines / gate matchers | No — requires `apothem install` | `settings.json` (managed allow/deny gates only — see the MCP row above), `output-styles/`, `statuslines/`, and the conformity `gate.py` + `schemas/` ride beside the engine install, not the plugin package. The statusline ships as `statuslines/statusline.md`, not as a `settings.json` key. |
| MCP | No — operator-owned | MCP servers register via `claude mcp add` into `~/.claude.json` / project `.mcp.json`; neither the plugin nor the engine authors entries. |

Bundle status: this is the reference plugin-alone implementation — commands,
agents, skills, and hooks persist from the plugin package directly; only the full
rules reference tree, settings, output-styles, and the gate engine need
`apothem install`.
