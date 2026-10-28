<!-- SPDX-License-Identifier: MIT -->

# Cursor Standard Convention Pin

## Snapshot

- Snapshot date: 2026-10-28
- Snapshot note (hooks): the adapter now registers a hook. The hooks page was re-read on 2026-10-28 from the raw Markdown it serves, with the third-party hooks page (read 2026-10-27) for the Claude Code import. Previous 2026-10-28 (agents review below).
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
  adapter authors no plugin bundle; it delivers the project rules file, the
  project subagents, the skills folder above and one hook (next section).
- Settings (IDE-managed) and status lines are not file surfaces the adapter
  owns.

## Hooks

Read 2026-10-28 (<https://cursor.com/docs/hooks>, raw Markdown) and 2026-10-27
(<https://cursor.com/docs/reference/third-party-hooks>,
<https://cursor.com/docs/cli/changelog>).

- Files: `<project>/.cursor/hooks.json` ("run in any trusted workspace and are
  checked into version control with your project") and `~/.cursor/hooks.json`;
  enterprise (macOS `/Library/Application Support/Cursor/hooks.json`, Linux and
  WSL `/etc/cursor/hooks.json`, Windows `C:\ProgramData\Cursor\hooks.json`) and
  team (cloud dashboard) sources; a plugin's `hooks/hooks.json`. Priority runs
  Enterprise, Team, Project, User, with plugin hooks after them. Project hook
  commands run from the project root and user ones from `~/.cursor/`. Cursor
  watches the files and reloads them on save; the troubleshooting section says to
  restart Cursor if they still do not load. There is no uncommitted variant of the
  project file.
- Schema: `{"version": 1, "hooks": {"<event>": [{"command": "<string>", "type":
  "command" | "prompt", "timeout": <seconds>, "loop_limit": <n | null>,
  "failClosed": <bool>, "matcher": "<regex>"}]}}`. `version` is required (a
  positive integer). `timeout` has a platform default that the page does not state.
  A prompt hook carries `prompt` instead of `command`; the page marks `command`
  required while its prompt example omits it. `failClosed: true` makes a crash,
  timeout, non-zero exit or empty output block; the permission events block on
  invalid JSON even with it off.
- Events: 21 camelCase names (`sessionStart`, `sessionEnd`, `preToolUse`,
  `postToolUse`, `postToolUseFailure`, `subagentStart`, `subagentStop`,
  `beforeShellExecution`, `afterShellExecution`, `beforeMCPExecution`,
  `afterMCPExecution`, `beforeReadFile`, `afterFileEdit`, `beforeSubmitPrompt`,
  `preCompact`, `stop`, `afterAgentResponse`, `afterAgentThought`,
  `beforeTabFileRead`, `afterTabFileEdit` and `workspaceOpen`).
- Command contract: JSON on stdin with the common fields `conversation_id`,
  `generation_id`, `model`, `hook_event_name`, `cursor_version`,
  `workspace_roots`, `user_email` and `transcript_path`; sessionStart adds
  `session_id` (the page says it is the same as `conversation_id`),
  `is_background_agent` and `composer_mode`. sessionStart's stdout is
  `{"env": {...}, "additional_context": "..."}`: it runs "fire-and-forget", the
  agent loop does not wait for or enforce a blocking response, and the context goes
  into the conversation's initial system context. Exit 0 uses the JSON output,
  exit 2 blocks, and any other code is a failure that lets the action proceed.
  `CURSOR_PROJECT_DIR` (alias `CLAUDE_PROJECT_DIR`) is the workspace root. The
  page's Environment Variables table lists `CURSOR_PROJECT_DIR`,
  `CURSOR_VERSION` and the `CLAUDE_PROJECT_DIR` alias as set for every hook
  command (read 2026-10-28); `CURSOR_VERSION` and `CURSOR_PROJECT_DIR` are how
  the dispatcher knows it runs under Cursor, and `CLAUDE_PROJECT_DIR` is no
  signal because Cursor exports it as an alias.
- Where the adapter's context can land: `additional_context` is documented for
  sessionStart and, on the page read 2026-10-28, for postToolUse and
  postToolUseFailure as well. Version 1 of the adapter registers sessionStart only,
  the session bootstrap, on the maintainer's decision; the postToolUse tracker
  stays unregistered until a probe shows its context reaches the model (the
  2026-10-27 reading did not confirm it). `agent_message` is documented as the
  message fed back to the agent when an action is denied, and Apothem's guards
  never deny, so no preToolUse or beforeShellExecution guard is registered. No
  Stop gate, compaction hook, NotebookEdit or AskUserQuestion guard and no
  conformity-gate hook is registered. The output the dispatcher writes under
  `--contract cursor` is `{"additional_context": ...}` and nothing else: no
  permission, no decision, no `followup_message`.
- Windows: "the desktop app runs hook commands through PowerShell and pipes the
  JSON into the command". A line that starts with a quoted program path is not a
  call in PowerShell, so the registration starts the command with the call
  operator (`& "<interpreter>" ...`) when the install ran on a Windows host, and
  not otherwise (`sh` reads a leading `&` as a syntax error). That is a design
  inference from PowerShell syntax; the vendor page names the shell, not the
  quoting. It was checked locally on 2026-10-28 with PowerShell 7 on a Windows
  host, not against Cursor: `pwsh -Command '& "<interpreter>" "<script>" ...'`
  runs the dispatcher, and the same line without `&` fails to parse. The CLI
  changelog (v2026.10.15) reports a hook whose command cannot be
  found as failed, and the session goes on.
- Cloud agents: a repository's project hooks run in cloud agents (command hooks
  only). User hooks do not, and sessionStart is deferred there, so the adapter's
  hook does not fire. Self-hosted workers fire sessionStart when a session claims
  the worker; the command then names an interpreter that may not exist there, and
  fails open.
- Claude Code import: Cursor loads Claude Code hooks from
  `.claude/settings.local.json`, `.claude/settings.json` and
  `~/.claude/settings.json` (below Cursor's own files in priority) while "Include
  Third-Party Plugins, Skills, and Other Configs" is on in Settings, Agents,
  Third-Party Imports, which is the default. It accepts Claude Code's nested
  `hookSpecificOutput` as well as its own flat output, and runs every matching hook
  from every source. If the Apothem Claude Code install wrote its hooks to
  `~/.claude/settings.json`, Cursor can run both sets. The install prints a note
  naming the switch and what turning it off also stops. The sessionStart command
  the adapter registers and the Claude Code copy of it (the default command line)
  share one marker per (session, source) in the hook state directory, so whichever
  runs second is silent. The default command line takes part only when
  `CURSOR_PROJECT_DIR` or `CURSOR_VERSION` is set; the marker binds for ten
  seconds, so a later start of the same session delivers; no PostToolUse counter
  is de-duplicated.
- TODO(clarify): whether the environment variables above are also set for a hook
  Cursor imports from `~/.claude/settings.json`; the page lists them for hook
  commands without distinguishing the source. If they are not, the Claude Code
  copy runs unmarked and the bootstrap can be delivered twice.
- Files the adapter writes: the dispatcher tree at
  `<project>/.apothem/support/cursor/hooks/` (Apothem-owned; nested under the
  harness name; the project's `.gitignore` snippet ignores `.apothem/*`) and one
  entry in `<project>/.cursor/hooks.json`, which is the operator's file: the
  `native_hooks` mode (operator-owned) keeps their entries and other keys ahead of
  Apothem's, tells Apothem's entry apart by what its command runs (the `.apothem/support/<harness>/hooks/dispatch.py` path with a `--contract` argument, read from the command text alone, so the project path it was written under does not matter and an operator's own `hooks/dispatch.py` or `python -m apothem.conformity.gate` is never taken for Apothem's), and
  on an uninstall removes only that entry (deleting the file, after a backup, when
  nothing else remains: `native_hooks` does not record who created the file). An uninstall that finds the file unreadable (comments, trailing commas) while it still names the dispatcher leaves it as it is and reports the entry as skipped, with the reason, instead of a success. `verify` requires the file to hold at least one such entry. A project or interpreter path holding `$`, a backtick, a double quote, a backslash or a control character is refused at install (the plan validation reports it before anything is written): one escape rule cannot serve `sh`, Git Bash and PowerShell, and inside the quoted command such a path runs a different file. A file with comments, trailing commas, a non-object value or the
  other vendor's `hooks` shape is refused with `config.unparseable` and left as it
  is. The user file `~/.cursor/hooks.json` is never written. The registration names
  an absolute interpreter and project path, which are machine-specific, in a file
  Cursor documents as committed; the install prints that hazard.
- TODO(clarify): the default `timeout` is not stated; the entry sets 30 seconds.
- TODO(clarify): how the Cursor CLI and other non-desktop surfaces run hook
  commands on Windows, and whether any one command string is valid under both `sh`
  and PowerShell. The page's example hooks are shell scripts, and whether a bare
  `.sh` hook is runnable on Windows is not documented; the adapter calls the
  interpreter directly instead.
- TODO(clarify): whether the postToolUse `additional_context` output reaches the
  model; register the PostToolUse tracker once a probe shows it does.
- TODO(clarify): whether Apothem's `.gitignore` snippet should list a hook file;
  `.cursor/hooks.json` is shared, so the answer differs from the local files of
  CodeBuddy and Devin.
- TODO(clarify): whether the third-party import switch also gates Claude Code's
  `.claude/agents/` (already recorded above for agents).

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
- <https://cursor.com/docs/reference/third-party-hooks> (the Third-Party Imports switch and the Claude Code hook import, priority order and response compatibility; retrieved 2026-10-27)
- <https://cursor.com/docs/hooks> (hook files, schema, events, the sessionStart contract, exit codes, the Windows PowerShell note, cloud agents, the Environment Variables table; retrieved 2026-10-28)
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
`<project>/.cursor/agents/`, one hook entry in `<project>/.cursor/hooks.json` with
its scripts under `<project>/.apothem/support/cursor/hooks/`, the skills at
`~/.agents/skills/`, and the rules and templates corpus at `~/.config/apothem/`,
and authors no other cohort. There is no Apothem-distributable standalone bundle; every
artifact requires the full `apothem install --harness cursor --project <path>`
engine run.

| Artifact class | Persists standalone? | Mechanism / limit |
|---|---|---|
| Rules | No — requires `apothem install` | The merged `apothem-rules.mdc` (carrying the embedded behavioral mandates) is written only by the engine into the vendor-native `.cursor/rules/` directory. Nothing persists before that run. |
| Skills and commands | No — requires `apothem install` | The engine writes them as skills to the user-level `~/.agents/skills/`, one copy shared by every project and every tool that reads that folder. Nothing persists before that run. |
| Agents | No — requires `apothem install` | The engine writes them as subagents to the project's `.cursor/agents/`. Nothing persists before that run. |
| Hooks | No — requires `apothem install` | The engine writes the dispatcher to `<project>/.apothem/support/cursor/hooks/` and merges a `sessionStart` entry into `<project>/.cursor/hooks.json`. Nothing persists before that run. Cursor's `.cursor-plugin/plugin.json` also accepts hooks, but Apothem authors no Cursor plugin; bundling the cohort into one is a documented future propagation-write-planning concern, not part of this adapter today. |
| MCP / Settings | No — operator-owned | `~/.cursor/mcp.json` / `.cursor/mcp.json` and IDE-managed settings are operator-owned; the adapter authors no entries. |

Platform note: the vendor plugin surface exists; the Apothem-distributable
plugin bundle does not yet. The files `apothem install` writes are the sole
persistence surface for now.
