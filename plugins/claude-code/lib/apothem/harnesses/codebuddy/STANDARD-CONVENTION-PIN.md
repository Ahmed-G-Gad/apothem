<!-- SPDX-License-Identifier: MIT -->

# CodeBuddy Standard Convention Pin

## Snapshot

- Snapshot date: 2026-10-27
- Snapshot note (agents): the adapter now installs Apothem's agents as CodeBuddy subagents in `<project>/.codebuddy/agents/`. The CLI sub-agents, directory-structure, hooks and plugins-reference pages were read on 2026-10-27, and the IDE Subagents page the same day. The other sections below keep their earlier read dates. Previous 2026-10-24.
- Snapshot note (skills): the adapter now installs skills and command skills at CodeBuddy's own `~/.codebuddy/skills/` and the rules and templates corpus at `~/.config/apothem/`. The CodeBuddy skills page was read on 2026-10-24.
- Snapshot note: refreshed against `www.codebuddy.ai/docs`. Correction: MCP servers live in `.mcp.json` at the project root and `~/.codebuddy/.mcp.json`, not in `.codebuddy/settings.json` as the earlier pin said. CodeBuddy Code also reads `AGENTS.md` as project memory when no `CODEBUDDY.md` exists. Previous 2026-06-25.
- Adapter source: `src/apothem/harnesses/codebuddy/`
- Evidence level: vendor-doc pinned (living docs; no-immutable-source exception). The CLI sub-agents, directory-structure, hooks and plugins-reference pages and the IDE Subagents page were read on 2026-10-27; the IDE Rules page was re-read on 2026-10-03; the CLI memory and MCP pages were read on 2026-10-02. No CodeBuddy source code was read, so runtime behavior the docs do not state is unverified. No vendor-native UI claim is made here.

## Official Surface Refresh

- Canonical filename: `.codebuddy/rules/apothem-rules.md`. CodeBuddy reads
  project rules from `.codebuddy/rules/*.md` (Markdown with optional
  frontmatter: `enabled` and `alwaysApply`, both default `true`, and `paths`),
  auto-loaded as project memory with the same priority as
  `.codebuddy/CODEBUDDY.md`. The adapter writes only this dedicated file and
  never clobbers operator rules.
- Memory: `CODEBUDDY.md` or `.codebuddy/CODEBUDDY.md` (project) and
  `~/.codebuddy/CODEBUDDY.md` (user). When a project has no `CODEBUDDY.md`,
  CodeBuddy Code uses `AGENTS.md` instead, so the registry lists CodeBuddy as a
  reader of the project `AGENTS.md` that the Kimi Code adapter writes. The
  adapter authors neither file.
- MCP: `.mcp.json` at the project root (or the deprecated `mcp.json`) and
  `~/.codebuddy/.mcp.json` for user scope; the first existing file in each
  scope wins. Operator-owned; the adapter names the surface and authors no
  entries.
- Skills: project skills live in `.codebuddy/skills/` and user skills in
  `~/.codebuddy/skills/`, each a subdirectory with a `SKILL.md`. The skills page
  documents the frontmatter keys `name`, `description`, `agent`, `model`,
  `hooks`, `disable-model-invocation`, `user-invocable`, `allowed-tools`
  (comma-separated), and `context`; it does not mention `.agents/skills/`. The
  adapter writes Apothem's skills, plus its commands wrapped as skills, to
  `~/.codebuddy/skills/`, and not to the cross-tool folder. The page lists no
  `metadata` or `argument-hint` key. TODO(clarify): probe CodeBuddy with the
  shared emission's `metadata` map and `argument-hint`; if it rejects either,
  emit this folder without it (the only per-destination variant, chosen by
  folder).
- Agents (read 2026-10-27): a sub-agent is one Markdown file with YAML
  frontmatter and the system prompt as the body, in `.codebuddy/agents/`
  (project) or `~/.codebuddy/agents/` (user). On a name clash the project file
  wins, then a `--agents` flag definition, then the user file. A file added by
  hand loads at the next session start. The adapter writes the project folder
  only, one `<name>.md` per Apothem agent, and writes no user-level agents
  folder. A same-named file you wrote is backed up before it is replaced.
- Agent keys: `name` and `description` are required (`name` is lowercase
  letters and hyphens). `tools` is a comma-separated allowlist (omitted means
  every tool of the main thread, MCP tools included); `disallowedTools` is a
  denylist (an array or a comma-separated string) that the page says unions
  with the session's own; `maxTurns` is a documented optional key. The page
  also lists `model`, `permissionMode`, `skills`, `mcpServers`, `effort`,
  `background`, `initialPrompt`, `memory` and `disable-model-invocation`. The
  adapter writes `name`, `description`, `tools`, `disallowedTools` and
  `maxTurns` only. It writes no `model` (an agent runs on the model the
  harness selects), no `permissionMode`, and no `hooks`: the hooks page
  denies hooks in the frontmatter of a user or project agent file unless
  `allowUntrustedFrontmatterHooks` is on.
- Agent tools: the tool names the CLI docs show are Read, Grep, Glob, Bash,
  Edit, Write, WebFetch, WebSearch and Agent. The `tools` and `disallowedTools`
  fields carry a source tool only when its name is in that list, in the source
  order, so MultiEdit, NotebookEdit, PowerShell, Monitor, Artifact, TodoWrite,
  TaskCreate and TaskUpdate are left out. A source with `tools` is never
  widened: the allowlist stays, and an allowlist that loses every name is
  written as an empty string instead of being omitted.
- CodeBuddy documents no read of `.claude/agents/` or `~/.claude/agents/` (the
  only Claude-named path it accepts is the plugin manifest folder
  `.claude-plugin/`), so the Claude Code adapter's agents do not reach it and the
  native folder is the only route.
- The IDE Subagents page uses the same two folders but its example shows the
  keys `agentMode`, `enabled` and `enabledAutoRun`, and none of `permissionMode`,
  `skills`, `mcpServers` or `disallowedTools`. The adapter writes the CLI keys.
- The vendor also documents slash commands, hooks, and plugins. The adapter
  authors none of them. Hooks and the Mods middleware layer are separate
  surfaces that Apothem does not write.
- TODO(clarify): how CodeBuddy treats an agent-file frontmatter key it does not
  list is not documented.
- TODO(clarify): whether the IDE accepts the CLI keys the adapter writes
  (`disallowedTools` and `maxTurns`) is not documented; its Subagents page shows
  no `disallowedTools`.
- TODO(clarify): the docs do not itemize the full tool-name list or say whether
  an unknown name in `tools` or `disallowedTools` is ignored or rejected; the
  adapter writes only the nine names above for that reason.
- TODO(clarify): the docs do not say what an empty `tools` string means. The
  adapter writes it only when a source allowlist loses every name, which no
  current Apothem agent does.

## Vendor Sources

Retrieved 2026-10-03 unless marked.

- <https://www.codebuddy.ai/docs/ide/Rules> (project rules)
- <https://www.codebuddy.ai/docs/cli/memory> (memory files, rules frontmatter, `AGENTS.md` fallback; retrieved 2026-10-02)
- <https://www.codebuddy.ai/docs/cli/skills> (skills; retrieved 2026-10-24)
- <https://www.codebuddy.ai/docs/cli/mcp> (`.mcp.json` locations; retrieved 2026-10-02)
- <https://www.codebuddy.ai/docs/cli/hooks> (hooks and sub-agent events; retrieved 2026-10-02; frontmatter-hooks gate re-read 2026-10-27)
- <https://www.codebuddy.ai/docs/cli/sub-agents> (sub-agent folders, frontmatter keys, precedence, model fallback; retrieved 2026-10-27)
- <https://www.codebuddy.ai/docs/cli/codebuddy-dir> (project and user `agents/` folders and the project-over-user rule; retrieved 2026-10-27)
- <https://www.codebuddy.ai/docs/cli/plugins-reference> (fields a plugin agent accepts and the `.claude-plugin/` compatibility note; retrieved 2026-10-27)
- <https://www.codebuddy.ai/docs/ide/Features/Subagents> (IDE Subagents page, same two folders; retrieved 2026-10-27)

## Discovery Targets

- Discovery target: mcp_servers by 2026-12-31 — decide whether Apothem renders the profile's MCP inventory into the project `.mcp.json` or keeps naming it as operator-owned.

## Recommended Postfix Rendering

- Status: supported as plain text.
- Mechanism: Apothem emits the literal ` (Recommended)` suffix in the option label. CodeBuddy rule templates preserve that suffix as authored.
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

CodeBuddy exposes **no vendor plugin or extension install surface** that Apothem
ships. The adapter writes a merged rules file at
`<project>/.codebuddy/rules/apothem-rules.md`, the agents at
`<project>/.codebuddy/agents/`, the skills at `~/.codebuddy/skills/`, and the
rules and templates corpus at `~/.config/apothem/`, and authors no other
cohort. There is no standalone-installable bundle; every artifact requires the
full `apothem install --harness codebuddy --project <path>` engine run.

| Artifact class | Persists standalone? | Mechanism / limit |
|---|---|---|
| Rules | No — requires `apothem install` | The merged `apothem-rules.md` (carrying the embedded behavioral mandates) is written only by the engine into the vendor-native `.codebuddy/rules/` directory. Nothing persists before that run. |
| Skills and commands | No — requires `apothem install` | The engine writes them as skills to the user-level `~/.codebuddy/skills/`. Nothing persists before that run. |
| Agents | No — requires `apothem install` | The engine writes them as subagents to the project's `.codebuddy/agents/`. Nothing persists before that run. |
| Hooks / MCP / Tools / Settings | No — operator-owned | `.mcp.json` (MCP servers), `.codebuddy/settings.json`, and `CODEBUDDY.md` memory are operator-owned; the adapter authors no entries. CodeBuddy documents hooks and slash commands; the adapter authors neither. |

CodeBuddy documents a plugin surface, but Apothem ships no CodeBuddy plugin, so
the files `apothem install` writes are the sole persistence surface.
