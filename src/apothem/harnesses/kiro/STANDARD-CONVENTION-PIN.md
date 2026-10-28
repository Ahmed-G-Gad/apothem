<!-- SPDX-License-Identifier: MIT -->

# Kiro Standard Convention Pin

## Snapshot

- Snapshot date: 2026-10-28
- Snapshot note (hooks): the adapter now registers a hook in `<project>/.kiro/hooks/apothem.json`. The hooks, hook-types, hook-actions and hooks-migration pages were re-read on 2026-10-28 (the actions page from its raw Markdown); the IDE 1.0 hooks and permissions pages were read on 2026-10-27. Previous 2026-10-28 (tool categories) and 2026-10-27.
- Snapshot note (tool categories): the Built-in tools page was read on 2026-10-28 from its raw Markdown, which closes the open question about which tools the `read` tag covers. Previous 2026-10-27.
- Snapshot note (agents): the adapter now installs Apothem's agents as Kiro custom agents in `<project>/.kiro/agents/`, as Markdown files for Kiro IDE 1.0 and Kiro CLI V3. The custom-agents pages, the configuration reference, the sub-agents page, the permissions page, the V3 pages and the changelog were read on 2026-10-27 from the raw Markdown each page serves. Previous 2026-10-24.
- Snapshot note (skills): the adapter now installs skills and command skills at Kiro's own `~/.kiro/skills/` and the rules and templates corpus at `~/.config/apothem/`. The Kiro skills page was read on 2026-10-24.
- Snapshot note: refreshed against `kiro.dev/docs` (steering, MCP configuration, skills, hooks). Steering inclusion modes (`always`, `fileMatch` with `fileMatchPattern`, `manual`, `auto`), `AGENTS.md` support (workspace root and `~/.kiro/steering/`), MCP at `.kiro/settings/mcp.json` and `~/.kiro/settings/mcp.json`, and agent files in `.kiro/agents` are confirmed. Previous 2026-06-25.
- Adapter source: `src/apothem/harnesses/kiro/`
- Evidence level: vendor-doc pinned (living docs; no-immutable-source exception). No vendor-native UI claim is made here.
- Vendor doc URL: <https://kiro.dev/docs/steering/>
- Canonical filename: `.kiro/steering/apothem-rules.md`

## Official Surface Refresh

- Steering: `.kiro/steering/*.md` (workspace) and `~/.kiro/steering/`
  (global), Markdown with optional front matter controlling inclusion
  (`inclusion: always | fileMatch | manual | auto`; `fileMatchPattern` for
  `fileMatch`, description matching for `auto`). The adapter writes only
  `<project>/.kiro/steering/apothem-rules.md` with `inclusion: always`, so it
  never clobbers the operator's foundation files (`product.md`, `tech.md`,
  `structure.md`).
- `AGENTS.md`: Kiro reads `AGENTS.md` at the workspace root and in
  `~/.kiro/steering/`, so the registry lists Kiro as a reader of the project
  `AGENTS.md` that the Kimi Code adapter writes. The Kiro adapter does not write
  `AGENTS.md`.
- MCP: `.kiro/settings/mcp.json` (workspace) and `~/.kiro/settings/mcp.json`
  (user), plus an agent's own `mcpServers` field. Operator-owned; the adapter
  names the surface and authors no entries.
- Skills: workspace skills live in `.kiro/skills/` and global skills in
  `~/.kiro/skills/`, each a folder with a required `SKILL.md`; a workspace skill
  wins over a global one. The skills page does not mention `.agents/skills/`. The
  adapter writes Apothem's skills, plus its commands wrapped as skills, to
  `~/.kiro/skills/`, and not to the cross-tool folder. Whether a custom agent
  sees those skills is a conflict between two vendor pages, read 2026-10-27: the
  skills page says custom agents load skills only through a `skill://` resource,
  while the configuration reference says custom agents inherit the default
  resources (steering files, skills and `AGENTS.md`) alongside their own, unless
  the CLI setting `chat.disableInheritingDefaultResources` is true (default
  false). The adapter writes no `resources` key, so the agents it installs see the
  skills only if the inheritance reading holds.
  TODO(clarify): which of the two pages is current for custom agents.
  TODO(clarify): the vendor docs do not say how Kiro treats a `SKILL.md`
  frontmatter key it does not list. The shared emission sets `user-invocable`,
  `disable-model-invocation`, `allowed-tools`, `argument-hint`, and a
  `metadata` map; probe Kiro with the full set before a release and, if it
  rejects extras, change `SHARED_TOPLEVEL_KEYS` in `install_driver_shared.py`.
- Agents, locations (read 2026-10-27): a custom agent is `.kiro/agents/<name>.md`
  or `.kiro/agents/<name>.json` in the workspace, or the same under
  `~/.kiro/agents/` for every project. Nested folders are allowed and the agent
  name is the path under the agents folder without its extension. A workspace
  agent wins over a global one of the same name. `kiro-cli agent create` saves to
  the global folder unless `--directory` is given. Global agents reach the IDE and
  the CLI only; Kiro Web loads project agents. In V3, `KIRO_HOME` moves the global
  folder, and Kiro ignores a value that is relative, a filesystem root, the home
  directory or one of its ancestors. The adapter writes the project folder only,
  one `<name>.md` per Apothem agent, and a same-named file you wrote there is
  backed up before it is replaced. It never writes `~/.kiro/agents/`.
- Agents, format: the Markdown file carries the configuration in YAML frontmatter
  and the agent's system prompt as the body, and the JSON file "supports
  identical fields". The Markdown format and the `permissions`, `excludedTools`,
  `includeMcpJson`, `includePowers` and `welcomeMessage` keys are new in IDE 1.0
  and Kiro CLI V3; V3 is opt-in (`kiro-cli --v3`, an early release that runs
  beside CLI 2.x). The adapter targets that surface and writes Markdown only. A
  CLI 2.x JSON profile (`allowedTools`, `toolsSettings`) is skipped by V3 until
  `/upgrade-agent` converts it, so no JSON profile and no 2.x key is written.
- Agent keys: `name` (optional, taken from the file name when absent),
  `description`, `prompt`, `model`, `mcpServers`, `tools`, `excludedTools`,
  `permissions` (`rules` of a capability, `match` patterns and an `effect` of
  `allow`, `ask` or `deny`), `resources` (`file://` and `skill://`), `hooks`,
  `includeMcpJson`, `includePowers` and `welcomeMessage`. In a Markdown agent the
  body is the prompt. The adapter writes `name`, `description` and `tools` only.
  It writes no `model` (the value must match a model Kiro's model service
  returns, and an unknown id can fail the first prompt instead of falling back to
  the default), no `permissions` (tool authorization stays at Kiro's defaults),
  no `excludedTools`, `resources`, `mcpServers`, `hooks` or `welcomeMessage`, and
  none of Apothem's `maxTurns`, `version`, `updated` or `portability`.
- Agent tools: `tools` selects which tools the agent sees, with the category tags
  `read`, `write`, `shell`, `web` and `subagent`, `@builtin`, `@mcp`,
  `@<server>`, `@<server>/<tool>` and `*`; `excludedTools` removes tools `tools`
  allows. The adapter turns the source `tools` and `disallowedTools` into one
  `tools` allowlist of tags, written as a flow list the way the vendor example
  writes it (`tools: ["read", "shell"]`): `Read`, `Glob` and `Grep` are `read`;
  `Write`, `Edit`, `MultiEdit` and `NotebookEdit` are `write`; `Bash` and
  `PowerShell` are `shell`; `WebSearch` and `WebFetch` are `web`; `Agent` and
  `Task` are `subagent`. A source tool with no tag (`TodoWrite`, `Monitor`,
  `Artifact`, `TaskCreate`, `TaskUpdate`, an `mcp__` entry) is left out. A tag is
  left out when the source denies any tool it covers, so a restriction is never
  relaxed; a source tool pattern such as `Bash(git status)` has no tag form and is
  left out of a grant (a patterned denial denies the whole tool); a grant that
  loses every tag is written as `tools: []`; a source with denials and no grant
  gets every tag it does not deny; a source with neither writes no `tools` key.
  Of the fourteen agents, two carry the `write` tag (mcp-builder and
  refactor-surgeon), nine carry `shell` and three carry `web`.
- Agents, sub-agents: the sub-agents page says any custom agent can be invoked as
  a sub-agent on the IDE, the CLI and Web (not Mobile), that the main agent picks
  one by its `description`, and that an agent which spawns sub-agents needs
  `subagent` in `tools` (or `@builtin`). The registry therefore records
  `sub_agent_dispatch` as native. No Apothem agent grants `Agent`, so none is
  given the `subagent` tag.
- Agents, workspace trust: in Kiro CLI 2.33 and later (changelog 2026-10-20), an
  interactive V3 session asks "Trust this workspace?" before it loads the folder's
  hooks, agents, MCP servers, steering and workflows. `--no-interactive` and V1/V2
  sessions are not gated, and 2.34 adds `--trust-workspace` for one launch. The
  permissions page states the same for workspace agents in general: until the
  workspace is trusted, Kiro does not load its custom agents. A freshly installed
  project agent is therefore inactive until the operator trusts the folder. A
  saved agent file reloads without a restart (MCP configuration page).
- Agents, other roots: the configuration page lists `~/.kiro/agents/` and
  `.kiro/agents/` as Kiro's agent folders and documents no read of
  `~/.claude/agents/`, `.agents/agents/` or another vendor's agent folder. That
  absence is inferred from the file-path table, not stated, so the registry does
  not list Kiro as a reader of any shared agents root.
- No release shipped an agents entry for this harness (checked v1.0.1 to
  v1.4.0), so there is nothing to retire and the manifest's `stale-sweep` list
  stays empty.
- Agent tool categories (read 2026-10-28): the Built-in tools page, which the
  configuration reference names as the authority on category membership, lists
  under "Configuring tool access" what each tag commonly includes. `read` is
  `read_file`, `list_directory`, `file_search`, `grep_search`, `code`,
  `tool_search` (V2) and `introspect`; `write` is `fs_write`, `fs_append`,
  `str_replace`, `delete_file` and `code`; `shell` is `execute_bash` or
  `execute_pwsh` and, on IDE clients, the process-control tools; `web` is
  `web_fetch` and `remote_web_search`; `subagent` is the per-agent dispatch
  tools. The same page names `file_search` as the CLI 2.x `glob` and
  `grep_search` as the CLI 2.x `grep`, so mapping `Glob` and `Grep` to `read` is
  the vendor's own grouping. The page words the table as mappings that
  "include" those tools, not as a closed list. The adapter's mapping is
  unchanged. A `read` tag also selects `code` (AST-based code analysis) and
  `introspect` (answers questions about Kiro's own features from its docs), and
  `code` appears under `write` as well.
- TODO(clarify): whether the `read` tag alone gives an agent every operation of
  the `code` tool, which the Built-in tools page also lists under `write`; the
  page does not say whether the tool edits files.
- TODO(clarify): what an omitted `tools` key selects, and how Kiro reads
  `tools: []`. The adapter writes `[]` only for a source grant that loses every
  tag (no agent in the corpus does), so that the agent is not given every tool.
- TODO(clarify): whether CLI 2.x loads a V3 Markdown agent. The 2.x reference says
  only that the Markdown format was added in V3.
- TODO(clarify): whether the global folder `~/.kiro/agents/` is gated by
  workspace trust; the docs describe only workspace configuration as gated.
- TODO(clarify): the frontmatter keys the docs mark required beyond the optional
  `name`, and how Kiro treats a key it does not list.
- The vendor also documents specs (`.kiro/specs/`) and Kiro powers. The adapter
  authors neither. It does author a hook (next section).

## Hooks

Read 2026-10-28 (<https://kiro.dev/docs/hooks/>, <https://kiro.dev/docs/hooks/types/>,
<https://kiro.dev/docs/hooks/actions/> and <https://kiro.dev/docs/cli/v3/hooks-migration/>);
the IDE 1.0 and permissions pages were read 2026-10-27.

- Files: a project hook file is `<project>/.kiro/hooks/<id>.json`; "any `.json`
  filename works" and one file may hold several hooks. Hooks "activate
  automatically when a session starts", with no registration step. Kiro CLI V3
  also loads global hooks from `~/.kiro/hooks/`, and global and workspace hooks
  run alongside each other; whether the IDE reads that folder is not stated. An
  agent profile may also carry an inline `hooks` array (CLI V3). Kiro Web sessions
  can read the project folder but do not run the event-driven triggers. The
  adapter writes one file, `apothem.json`, and never `~/.kiro/hooks/`.
- Schema (version `v1`): `{"version": "v1", "hooks": [{"name": ...,
  "description": ..., "trigger": ..., "matcher": ..., "action": {"type":
  "command", "command": ...}, "timeout": ..., "enabled": ...}]}`. `version`,
  `hooks`, `name`, `trigger` and `action.type` are required; `matcher` defaults to
  always-match; `action.type` is `command` or `agent` (an agent action injects a
  prompt and cannot block); `timeout` is in seconds (default 60, `0` disables it)
  and applies to command actions; `enabled` defaults to true; `confirm` is for
  Stop command hooks. The adapter writes `name`, `description`, `trigger`,
  `action` and `timeout`.
- Triggers: `SessionStart`, `UserPromptSubmit`, `PreToolUse`, `PostToolUse`,
  `PostFileCreate`, `PostFileSave`, `PostFileDelete`, `PreTaskExec`,
  `PostTaskExec` and `Stop`, plus `SessionEnd` in CLI V3 only. The vendor says to
  use the PascalCase names in a standalone file; CLI 2.x spellings such as
  `agentSpawn` are accepted as compatibility input (V3 treats `agentSpawn` as
  `SessionStart`). The `matcher` of a `SessionStart` hook is not evaluated.
- Command contract: a command action "runs a shell command in your project
  root" and receives the event as JSON on stdin (`hook_event_name`, `cwd`,
  `session_id`; tool events add `tool_name` and `tool_input`, PostToolUse adds
  `tool_response`, UserPromptSubmit adds `prompt`). Exit 0 succeeds and stdout
  joins the agent's context for SessionStart and UserPromptSubmit only; exit 2
  blocks PreToolUse and PreTaskExec (stderr goes back to the model); any other
  code shows a warning and the run goes on.
- Why SessionStart only: a PreToolUse or PostToolUse hook's stdout is ignored, so
  the write, edit and shell guards and the compaction tracker would run on every
  tool call and deliver nothing. UserPromptSubmit does deliver stdout, but Apothem
  has no handler for it that is worth a process start on every prompt. The
  dispatcher never blocks and never uses exit 2 or a Stop decision.
- Timeout: the schema table, the migration examples, the IDE 1.0 reference and
  the actions page as read on 2026-10-28 give seconds with a 60-second default
  (`0` disables it). The actions page as read on 2026-10-27, and the management
  and best-practices pages, named `timeout_ms` (default 30,000) and
  `cache_ttl_seconds`, which no schema table defines. The adapter writes `timeout`
  only, set to 30.
- Workspace trust: in Kiro CLI 2.33 and later, an interactive V3 session shows
  "Trust this workspace?" before it loads the folder's hooks, agents, MCP servers,
  steering and workflows. `--no-interactive` and V1/V2 sessions are not gated, and
  2.34 adds `--trust-workspace` for one launch. The install prints that step as an
  advisory. A session of the agent itself cannot write the hooks folder without a
  prompt (the permissions page), which does not apply to the installer.
- Files the adapter writes: the dispatcher tree at
  `<project>/.apothem/support/kiro/hooks/` (Apothem-owned; the project's
  `.gitignore` snippet ignores `.apothem/*`) and the hook file
  `<project>/.kiro/hooks/apothem.json` (the `native_hooks` mode, Apothem-owned).
  An uninstall removes only the hooks whose command runs the Apothem dispatcher
  under the project, with or without an install record, deletes the file when
  nothing else is in it, and leaves the operator's own hook files untouched. The
  tree is nested under `kiro/` so that another project-scope hook adapter's
  uninstall cannot remove this dispatcher.
- Committed file: the command names an absolute interpreter and project path,
  which are machine-specific, in a folder a project can share through version
  control, and the dispatcher sits
  under the gitignored `.apothem/`. On a machine without that path the hook
  fails; Kiro shows a warning for a non-zero exit and the session goes on.
- TODO(clarify): the shell Kiro runs a command action in on Windows is not
  documented (the V3 tool ids include `execute_pwsh`). The command is written for
  sh and cmd.exe, with a quoted program path; PowerShell would need a call
  operator in front of it.
- TODO(clarify): the Session Start section of the hook-types page gives no
  payload or output rule; the rule that stdout joins the context is from the
  actions page and the page's Agent Spawn section, which V3 maps to SessionStart.
- TODO(clarify): whether the global `~/.kiro/hooks/` is gated by workspace trust,
  and whether the IDE reads it.
- TODO(clarify): the stdin fields of the file-change triggers are not documented
  (not used).
- TODO(clarify): the IDE 1.0 hooks page lists a shorter schema table (no
  `description`, `timeout` or `enabled`), while the IDE reference lists those as
  v1 fields; the adapter writes the keys the main hooks page lists.

## Vendor Sources

Retrieved 2026-10-03 unless marked.

- <https://kiro.dev/docs/steering/> (steering and `AGENTS.md`)
- <https://kiro.dev/docs/mcp/> (MCP overview)
- <https://kiro.dev/docs/mcp/configuration/> (`mcp.json` locations, `.kiro/agents`; agent configs reload when saved, re-read 2026-10-27)
- <https://kiro.dev/docs/skills/> (skills; retrieved 2026-10-24)
- <https://kiro.dev/docs/hooks/> (hook files, the v1 schema, activation, global hooks; retrieved 2026-10-28)
- <https://kiro.dev/docs/hooks/types/> (triggers, the SessionStart and Agent Spawn sections, exit codes, matchers; retrieved 2026-10-28)
- <https://kiro.dev/docs/hooks/actions/> (command actions, exit codes ("STDOUT is added to context (SessionStart, UserPromptSubmit) or ignored (others)"), timeouts; read from the raw Markdown at `https://kiro.dev/docs/hooks/actions.md` on 2026-10-28)
- <https://kiro.dev/docs/cli/v3/hooks-migration/> (the trigger table, `SessionStart` matcher "Not evaluated", and the PascalCase names; retrieved 2026-10-28)
- <https://kiro.dev/docs/ide/whats-new-v1/hooks/> (IDE 1.0 hooks and the exit-code rule; retrieved 2026-10-27)
- <https://kiro.dev/docs/custom-agents/> (agent folders, the two formats, nesting, precedence; retrieved 2026-10-27, the folder the adapter writes agents to)
- <https://kiro.dev/docs/custom-agents/configuration-reference/> (agent keys, `tools` selectors, `permissions`, the V3 additions, default resources; retrieved 2026-10-27)
- <https://kiro.dev/docs/custom-agents/creating/> (`kiro-cli agent create` and the global default; retrieved 2026-10-27)
- <https://kiro.dev/docs/custom-agents/subagents/> (any custom agent as a sub-agent, the `subagent` tool tag; retrieved 2026-10-27)
- <https://kiro.dev/docs/tools/> (Built-in tools: the commonly included tools of each category tag, "Configuring tool access"; read from the raw Markdown at `https://kiro.dev/docs/tools.md` on 2026-10-28)
- <https://kiro.dev/docs/cli/v3/> (V3 is opt-in through `kiro-cli --v3`; retrieved 2026-10-27)
- <https://kiro.dev/docs/cli/v3/agent-config/> (the same fields in both formats, `model`; retrieved 2026-10-27)
- <https://kiro.dev/docs/cli/2x-reference/> (the Markdown format added in V3; retrieved 2026-10-27)
- <https://kiro.dev/docs/configuration/> (`~/.kiro/agents/`, `.kiro/agents/` and `KIRO_HOME`; retrieved 2026-10-27)
- <https://kiro.dev/docs/permissions/> (workspace trust before agents load; retrieved 2026-10-27)
- <https://kiro.dev/changelog/> (workspace trust in CLI 2.33.0, 2026-10-20; retrieved 2026-10-27)

## Discovery Targets

- Discovery target: mcp_servers by 2026-12-31 — decide whether Apothem renders the profile's MCP inventory into `.kiro/settings/mcp.json` or keeps naming it as operator-owned.

## Recommended Postfix Rendering

- Status: supported as plain text.
- Mechanism: Apothem emits the literal ` (Recommended)` suffix in the option label. Kiro steering files preserve that suffix as authored.
- Boundary: this pin does not claim a harness-native recommended-option widget. It only pins the text-rendered convention used by `rules/interactive-questions.md`.

## Long Context and Compaction

- Status: profile-managed.
- Mechanism: Apothem keeps full-suite `/plan-execute` runs continuous by externalizing state to `.apothem/plans/`, compacting or restarting the harness session at phase boundaries as needed, and restoring via the Blind Bootstrap sequence.
- Boundary: this pin does not claim vendor-native autocompaction or a long-context size. It pins the adapter-local state handoff and compaction-restoration convention used by `rules/context-management.md`.

## Large-Codebase Practice Projection

- Layered context: declared in `capabilities.yml` under `layered_context_surface`; no vendor-native hierarchy is claimed beyond the adapter's documented file/template surface. Kiro steering inclusion modes (`always`, `fileMatch`, `manual`) are the vendor-native context-scoping mechanism; the adapter ships the `always` mode for its governance surface.
- LSP symbol navigation: `tracked-gap` until a vendor-ratified plugin or tool surface is pinned.
- Hook learning capture: routed through the `persistent-conventions-vigilance` artifact-evolution cycle; pass-class hooks stay silent and recurring findings become rule, skill, hook, or documentation updates.

## Plugin-alone Persistence

Kiro exposes **no vendor plugin or extension install surface** that Apothem
ships. The adapter writes a merged steering file at
`<project>/.kiro/steering/apothem-rules.md` (`inclusion: always`), the agents at
`<project>/.kiro/agents/`, the hook file at `<project>/.kiro/hooks/apothem.json`
with its scripts under `<project>/.apothem/support/kiro/hooks/`, the skills at
`~/.kiro/skills/`, and the rules and templates corpus at `~/.config/apothem/`, and
authors no other cohort. There is no standalone-installable bundle; every
artifact requires the full `apothem install --harness kiro --project <path>`
engine run.

| Artifact class | Persists standalone? | Mechanism / limit |
|---|---|---|
| Rules (steering-as-text) | No — requires `apothem install` | The merged `apothem-rules.md` steering file (carrying the embedded behavioral mandates) is written only by the engine into the vendor-native `.kiro/steering/` directory. Nothing persists before that run. |
| Skills and commands | No — requires `apothem install` | The engine writes them as skills to the user-level `~/.kiro/skills/`. Nothing persists before that run. |
| Agents | No — requires `apothem install` | The engine writes them as Markdown custom agents to the project's `.kiro/agents/`. Nothing persists before that run. |
| Hooks | No — requires `apothem install` | The engine writes the dispatcher to `<project>/.apothem/support/kiro/hooks/` and registers SessionStart in `<project>/.kiro/hooks/apothem.json`. Nothing persists before that run, and Kiro CLI V3 loads the hook only after the operator trusts the workspace. |
| Specs / MCP / Settings | No — operator-owned | Kiro documents specs (`.kiro/specs/`); the adapter authors none. `.kiro/settings/mcp.json` (MCP) and the foundation steering files are operator-owned; the adapter authors no entries. |

Kiro documents installable powers, but Apothem ships no Kiro power, so the
files `apothem install` writes are the sole persistence surface.
