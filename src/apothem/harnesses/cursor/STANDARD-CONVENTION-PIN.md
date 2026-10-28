<!-- SPDX-License-Identifier: MIT -->

# Cursor Standard Convention Pin

## Snapshot

- Snapshot date: 2026-10-28
- Snapshot note (review): the Subagents page was re-read on 2026-10-28 for how it treats Claude-style keys in the Claude-compatibility folders (it does not say). Previous 2026-10-27.
- Snapshot note (agents): the adapter now installs Apothem's agents as Cursor subagents in `<project>/.cursor/agents/`. The Subagents page, the plugins reference, the third-party hooks page and the CLI changelog were read on 2026-10-27 from the raw Markdown each page serves. Previous 2026-10-24.
- Snapshot note: the adapter now installs skills and command skills at the shared `~/.agents/skills/` and the rules and templates corpus at `~/.config/apothem/`. Refreshed against `cursor.com/docs`. The rules page moved to `cursor.com/docs/rules`, the MCP page to `cursor.com/docs/mcp`, and the old `@Web` page is gone. The agent's Browser tool visits URLs, so `web_fetch` moves from partial to yes. The skills page was re-read on 2026-10-24; the other pages keep their 2026-10-03 retrieval date. Previous 2026-10-03.
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
  registry). The Cursor adapter writes Apothem's skills, plus its commands
  wrapped as skills, to `~/.agents/skills/`, the one user-level copy shared with
  Codex, GitHub Copilot, Windsurf, and Zed. Cursor may also list the same names
  from `~/.claude/skills/` when a Claude Code install is present, and the docs
  do not say which copy wins.
  TODO(clarify): the vendor docs do not say how Cursor treats a `SKILL.md`
  frontmatter key it does not list. The shared emission sets `user-invocable`,
  `disable-model-invocation`, `allowed-tools`, `argument-hint`, and a
  `metadata` map; probe Cursor with the full set before a release and, if it
  rejects extras, change `SHARED_TOPLEVEL_KEYS` in `install_driver_shared.py`.
- Subagents (re-read 2026-10-27): Cursor loads `.cursor/agents/` and
  `~/.cursor/agents/`, and for compatibility the project folders `.claude/agents/`
  and `.codex/agents/` and the user folders `~/.claude/agents/` and
  `~/.codex/agents/`. Project subagents win over user ones on a name clash, and
  `.cursor/` wins over `.claude/` and `.codex/`. The Claude Code adapter's
  `~/.claude/agents/` therefore reaches Cursor, and the Codex adapter's
  `~/.codex/agents/` is a folder Cursor lists (both are shared roots in the
  registry, which records the user-level folders because those are the ones the
  adapters write).
- Agent file: one Markdown file with YAML frontmatter and the system prompt as the
  body. Every key is optional: `name` (lowercase letters and hyphens; the file name
  when absent), `description` (what Cursor matches a request against), `model`
  (`inherit`, the default, or a model id with optional bracketed settings such as
  `claude-opus-5[effort=high]`), `readonly` (boolean, default false) and
  `is_background` (boolean, default false). No `tools` key is documented, and the
  FAQ says a subagent inherits every tool of its parent, MCP tools included.
  `readonly: true` runs the subagent with restricted write permissions: no file
  edits and no state-changing shell commands. It is the only documented
  restriction. A pinned `model` that is blocked, needs Max Mode or is unavailable
  runs on the parent agent's model (CLI changelog 2026.10.22).
- Agents the adapter writes: one `<name>.md` per Apothem agent in
  `<project>/.cursor/agents/`, with `name`, `description` and, only for an agent
  that is read-only by its source rule and holds no Bash grant, `readonly: true`.
  That is five of the fourteen agents (citation-auditor, convention-auditor,
  fact-checker, memory-auditor, research-scout). `readonly` would also bar a test
  or lint run, so the seven read-only agents that keep Bash (codebase-explorer,
  dependency-auditor, design-critic, prompt-evaluator, quality-gate,
  security-scanner, test-runner) get no flag and their descriptions drop the
  read-only wording that Cursor would not enforce; they run with every tool the
  parent has. Only the description is rewritten: the body is copied unchanged, so
  the instructions of those seven agents still call them read-only and refer to a
  tool restriction in frontmatter that a Cursor file does not carry. The model
  follows that text; Cursor does not enforce it. The two agents that write files
  are unchanged. The source `tools`
  and `disallowedTools` have no other Cursor home, so they are not written. No
  `model` is written (the agent then inherits the parent's model), nor
  `is_background`, `maxTurns`, `version`, `updated` or `portability`. A same-named
  file you wrote in `.cursor/agents/` is backed up before it is replaced, and the
  adapter never writes `.agents/agents/`, `~/.cursor/agents/` or the Claude Code
  agents folder.
- Shared roots: the project `.cursor/agents/` copy supersedes the Claude-format
  agents Cursor imports from `~/.claude/agents/` inside an installed project, by
  the precedence above (`.cursor/` wins over `.claude/` and `.codex/` on a name
  clash). The native copy is the one that carries `readonly`, the only restriction
  the Subagents page documents. Cursor still loads `~/.claude/agents/` in every
  project without a native copy, so it stays a reader of that shared root.
- TODO(clarify): whether Cursor honors `tools` and `disallowedTools` in a
  Claude-format file found in `.claude/agents/` or `~/.claude/agents/`. The
  Subagents page lists the keys `name`, `description`, `model`, `readonly` and
  `is_background` and has no `tools` key, and it says nothing about how the
  Claude-compatibility folders treat Claude-style keys; the adapter relies on
  neither behavior.
- TODO(clarify): whether Cursor loads both the `.cursor/agents/` copy and a
  `~/.claude/agents/` copy of one agent name, or drops the lower-precedence one.
- TODO(clarify): the page does not say which file formats Cursor parses in the
  Codex folders, and Codex writes TOML there.
- TODO(clarify): whether the Settings > Agents > Third-Party Imports switch
  (documented, on by default, for Claude Code hooks) also gates the `.claude/` and
  `.codex/` agent folders.
- TODO(clarify): file extensions other than `.md` in `.cursor/agents/` (the plugin
  `agents/` folder accepts `.md`, `.mdc` and `.markdown`; the Subagents page names
  `.md` only), nested folders (CLI 2026.08.11: subagent scans no longer descend
  into hidden dot-directories), and the Claude model aliases (`sonnet`, `opus`)
  as a `model` value, which the page does not list.
- The vendor documents plugins (`.cursor-plugin/plugin.json`, bundling skills, MCP
  servers, rules, agents, commands, hooks and variables) and a marketplace. The
  adapter authors no plugin bundle or hook; it delivers the project rules file, the
  project subagents and the skills folder above.
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

Retrieved 2026-10-03 unless marked.

- <https://cursor.com/docs/rules> (rules)
- <https://cursor.com/docs/mcp> (`mcp.json`)
- <https://cursor.com/docs/skills> (skill directories; retrieved 2026-10-24, the folder the adapter writes)
- <https://cursor.com/docs/subagents> (subagent folders, keys, `readonly`, precedence; retrieved 2026-10-27, the folder the adapter writes agents to)
- <https://cursor.com/docs/cli/changelog> (model fallback for a pinned subagent model, no descent into hidden directories; retrieved 2026-10-27)
- <https://cursor.com/docs/reference/plugins> (the plugin `agents/` folder, a separate surface; retrieved 2026-10-27)
- <https://cursor.com/docs/reference/third-party-hooks> (the Third-Party Imports switch; retrieved 2026-10-27)
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
plugin bundle** — the adapter writes a merged MDC rules file at
`<project>/.cursor/rules/apothem-rules.mdc`, the agents at
`<project>/.cursor/agents/`, the skills at `~/.agents/skills/`, and
the rules and templates corpus at `~/.config/apothem/`, and authors no other cohort. There is no Apothem-distributable standalone bundle; every
artifact requires the full `apothem install --harness cursor --project <path>`
engine run.

| Artifact class | Persists standalone? | Mechanism / limit |
|---|---|---|
| Rules | No — requires `apothem install` | The merged `apothem-rules.mdc` (carrying the embedded behavioral mandates) is written only by the engine into the vendor-native `.cursor/rules/` directory. Nothing persists before that run. |
| Skills and commands | No — requires `apothem install` | The engine writes them as skills to the user-level `~/.agents/skills/`, one copy shared by every project and every tool that reads that folder. Nothing persists before that run. |
| Agents | No — requires `apothem install` | The engine writes them as subagents to the project's `.cursor/agents/`. Nothing persists before that run. |
| Hooks | No — Apothem ships no bundle | Cursor's `.cursor-plugin/plugin.json` and `hooks.json` accept hooks, but Apothem authors no Cursor plugin and registers no hook. Bundling the cohort into a Cursor plugin is a documented future propagation-write-planning concern, not part of this adapter today. |
| MCP / Settings | No — operator-owned | `~/.cursor/mcp.json` / `.cursor/mcp.json` and IDE-managed settings are operator-owned; the adapter authors no entries. |

Platform note: the vendor plugin surface exists; the Apothem-distributable
plugin bundle does not yet. The files `apothem install` writes are the sole
persistence surface for now.
