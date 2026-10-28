<!-- SPDX-License-Identifier: MIT -->

# CodeBuddy Standard Convention Pin

## Snapshot

- Snapshot date: 2026-10-28
- Snapshot note (hooks): the adapter now registers hooks. The CLI hooks and hooks-guide pages were re-read on 2026-10-28 (the hooks page through its official Chinese mirror, as raw Markdown, and through the vendor site) to settle which events deliver `additionalContext`. Previous 2026-10-27.
- Snapshot note (review): the Settings page was read on 2026-10-28 for the complete tool list. Previous 2026-10-27.
- Snapshot note (agents): the adapter now installs Apothem's agents as CodeBuddy subagents in `<project>/.codebuddy/agents/`. The CLI sub-agents, directory-structure, hooks and plugins-reference pages were read on 2026-10-27, and the IDE Subagents page the same day. The other sections below keep their earlier read dates. Previous 2026-10-24.
- Snapshot note (skills): the adapter now installs skills and command skills at CodeBuddy's own `~/.codebuddy/skills/` and the rules and templates corpus at `~/.config/apothem/`. The CodeBuddy skills page was read on 2026-10-24.
- Snapshot note: refreshed against `www.codebuddy.ai/docs`. Correction: MCP servers live in `.mcp.json` at the project root and `~/.codebuddy/.mcp.json`, not in `.codebuddy/settings.json` as the earlier pin said. CodeBuddy Code also reads `AGENTS.md` as project memory when no `CODEBUDDY.md` exists. Previous 2026-06-25.
- Adapter source: `src/apothem/harnesses/codebuddy/`
- Evidence level: vendor-doc pinned (living docs; no-immutable-source exception). The CLI sub-agents, directory-structure, hooks and plugins-reference pages and the IDE Subagents page were read on 2026-10-27; the IDE Rules page was re-read on 2026-10-03; the CLI memory and MCP pages were read on 2026-10-02. The CLI hooks and hooks-guide pages were read on 2026-10-28. No CodeBuddy source code was read, so runtime behavior the docs do not state is unverified. No vendor-native UI claim is made here.

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
- Agent tools (read 2026-10-28): the sub-agents page says a sub-agent can use
  any of CodeBuddy Code's internal tools and points to the Settings page for the
  complete list. That page's "Tools Available to CodeBuddy" table names
  AskUserQuestion, Bash, Edit, ExitPlanMode, Glob, Grep, LSP, MultiEdit,
  NotebookEdit, Read, Skill, SlashCommand, Task, TaskCreate, TaskGet, TaskList,
  TaskOutput, TaskStop, TaskUpdate, WebFetch, WebSearch and Write. `Agent` is
  not in that table, but the sub-agents page names an Agent tool, so it is kept.
  The `tools` and `disallowedTools` fields carry a source tool only when its name
  is in that vocabulary, in the source order, so PowerShell, Monitor, Artifact
  and TodoWrite, which neither page names, are left out. A source denial of
  MultiEdit and NotebookEdit (citation-auditor and research-scout) and of
  TaskCreate and TaskUpdate (twelve of the fourteen agents) is carried. A source tool
  with a pattern, such as `Bash(rm *)`, has no form in a comma list: as a grant it
  is left out, and as a denial it denies the whole tool. A source with `tools` is
  never widened: the allowlist stays, and an allowlist that loses every name is
  written as an empty string instead of being omitted.
- CodeBuddy documents no read of `.claude/agents/` or `~/.claude/agents/` (the
  only Claude-named path it accepts is the plugin manifest folder
  `.claude-plugin/`), so the Claude Code adapter's agents do not reach it and the
  native folder is the only route.
- The IDE Subagents page uses the same two folders but its example shows the
  keys `agentMode`, `enabled` and `enabledAutoRun`, and none of `permissionMode`,
  `skills`, `mcpServers` or `disallowedTools`. The adapter writes the CLI keys.
- The vendor also documents slash commands and plugins. The adapter authors
  neither. It does author hooks (next section). The Mods middleware layer is a
  separate TypeScript surface that Apothem does not write.
- TODO(clarify): how CodeBuddy treats an agent-file frontmatter key it does not
  list is not documented.
- TODO(clarify): whether the IDE accepts the CLI keys the adapter writes
  (`disallowedTools` and `maxTurns`) is not documented; its Subagents page shows
  no `disallowedTools`.
- TODO(clarify): the docs do not say whether an unknown name in `tools` or
  `disallowedTools` is ignored or rejected; the adapter writes only the names the
  Settings and sub-agents pages show for that reason.
- TODO(clarify): the docs do not say what an empty `tools` string means. The
  adapter writes it only when a source allowlist loses every name, which no
  current Apothem agent does.

## Hooks

Read 2026-10-28 (<https://www.codebuddy.ai/docs/cli/hooks>,
<https://www.codebuddy.ai/docs/cli/hooks-guide>). Hooks are Beta and need
CodeBuddy Code v1.16.0 or later.

- Files: hooks live in the `hooks` key of `~/.codebuddy/settings.json` (user),
  `<project>/.codebuddy/settings.json` (shared) and
  `<project>/.codebuddy/settings.local.json` (local, not committed); an
  enterprise policy bundle and a plugin's `hooks/hooks.json` are the other
  sources. The scopes merge, and every matching hook runs in parallel.
- Schema: `{"hooks": {"<Event>": [{"matcher": "<regex, optional>", "hooks":
  [{"type": "command", "command": "<bash string>", "timeout": <seconds>}]}]}}`.
  `type` is `command` or `prompt`. The page documents a single `command`
  string and no `args` array, so the adapter writes the command form only, with
  no `statusMessage` and no `async`. The default timeout is 60 s, and `timeout`
  is in seconds. Identical commands are deduplicated. `disableAllHooks` in the
  settings turns every hook off; it is the vendor's kill switch, beside
  Apothem's `APOTHEM_HOOKS_DISABLE=1`.
- Events: 27 names. Only ten have a documented stdin payload and exit-code row
  (PreToolUse, PostToolUse, Notification, UserPromptSubmit, Stop, SubagentStop,
  PreCompact, PostCompact, SessionStart, SessionEnd). The other seventeen are
  named only.
- Command contract: JSON on stdin (`session_id`, `transcript_path`, `cwd`,
  `permission_mode`, `hook_event_name`, plus `tool_name`, `tool_input` and, for
  PostToolUse, `tool_response`; SessionStart adds `source`). Exit 0 succeeds,
  exit 2 blocks (stdout message first, stderr as the fallback), and any other
  code is non-blocking. Stdout JSON may carry `continue`, `stopReason`,
  `suppressOutput`, `systemMessage` (shown to the operator, not the model) and
  `hookSpecificOutput`. A stdout that parses as a JSON object is read field by
  field; only text that does not parse is used as plain context, and only for
  UserPromptSubmit and SessionStart.
- Where `additionalContext` reaches the model: SessionStart, UserPromptSubmit
  and PostToolUse document `hookSpecificOutput.additionalContext`. PreToolUse
  documents only `permissionDecision`, `permissionDecisionReason` and
  `modifiedInput`, so a guard that speaks through `additionalContext` there is
  not known to be delivered. Apothem registers SessionStart (the bootstrap) and
  PostToolUse (the proactive-compaction tracker), and registers no PreToolUse
  guard, no Stop gate, no compaction hook, no NotebookEdit or AskUserQuestion
  guard and no conformity-gate hook. The envelope the dispatcher writes is
  Claude's, which CodeBuddy reads (`--contract codebuddy` changes no byte of it).
- Matcher: a case-sensitive regex over the tool name for PreToolUse and
  PostToolUse; `*`, an empty string or an omitted field matches all tools. The
  adapter writes `"matcher": "*"` for PostToolUse and omits the field for
  SessionStart, which the page lists with the sources
  `startup|resume|clear|compact` and which has no tool name to match.
- Shell: commands run through `$SHELL` on macOS and Linux and through Git Bash
  on Windows (cmd.exe and PowerShell are not supported), so the adapter writes
  bash quoting: `"<interpreter>" "<script>" ...`. The page recommends calling
  Python as `python3 script.py` because a shebang is unreliable under Git Bash;
  the adapter names the interpreter Apothem resolved at install time (an absolute
  path, version-probed), not `python3`. `$CODEBUDDY_PROJECT_DIR` is the project
  root.
- Activation: settings are snapshotted at startup and are not hot-loaded, and
  an externally edited settings file needs review in the `/hooks` panel before
  its hooks apply (the page says the change "Requires review in the `/hooks`
  panel before changes apply"). The install prints that step as an advisory.
  The only pre-approval setting the docs name is
  `allowUntrustedFrontmatterHooks`, which covers agent and skill frontmatter,
  not settings files.
- Files the adapter writes: the dispatcher tree at
  `<project>/.apothem/support/hooks/` (Apothem-owned; the project's
  `.gitignore` snippet ignores `.apothem/*`) and the registration in the
  uncommitted `<project>/.codebuddy/settings.local.json`, key-merged: the
  operator's own hooks and keys stay, and an uninstall removes only the handlers
  that tells Apothem's entry apart by what its command runs (the `.apothem/support/<harness>/hooks/dispatch.py` path with a `--contract` argument, read from the command text alone, so the project path it was written under does not matter and an operator's own `hooks/dispatch.py` or `python -m apothem.conformity.gate` is never taken for Apothem's). An uninstall that finds the file unreadable (comments, trailing commas) while it still names the dispatcher leaves it as it is and reports the entry as skipped, with the reason, instead of a success. `verify` requires the file to hold at least one such entry. A project or interpreter path holding `$`, a backtick, a double quote, a backslash or a control character is refused at install (the plan validation reports it before anything is written): one escape rule cannot serve `sh`, Git Bash and PowerShell, and inside the quoted command such a path runs a different file. Each command
  names an absolute interpreter and project path, which are machine-specific;
  that is why the registration goes in the local file and not the committed
  `settings.json`. The adapter never edits `settings.json`, never writes
  frontmatter hooks (denied by default, `allowUntrustedFrontmatterHooks` false)
  and ships no plugin.
- TODO(clarify): whether the `/hooks` review is a one-time trust prompt or
  recurs on every change, and whether it can be pre-approved or skipped
  non-interactively, are not documented.
- TODO(clarify): whether PreToolUse consumes `additionalContext` is not
  documented; until a probe shows it does, the PreToolUse guards stay
  unregistered.
- TODO(clarify): the matcher for a sub-agent spawn is `Task` on the hooks page
  and the spawning tool is named `Agent` on the sub-agents page; no sub-agent
  matcher is registered.
- TODO(clarify): the payload, matcher and blocking behavior of the seventeen
  name-only events, and whether the IDE (which documents seven events and says
  project configuration overrides user configuration, against the CLI's
  "merged") reads a CLI settings file the same way.
- TODO(clarify): whether CodeBuddy trims or caps `additionalContext` is not
  documented; the SessionStart bootstrap is a few kilobytes.
- TODO(clarify): the support tree at `<project>/.apothem/support/hooks/` is the
  first one to sit directly under the project's `.apothem/` folder (the Kimi Code
  and Gemini CLI trees nest under their own harness folder). A second project-scope
  adapter that writes the same path would share it with no install-ledger count,
  so one uninstall would remove the other's dispatcher. Either give the shared
  project tree ledger-counted sharing, as the `${USER_HOME}` folders have, or nest
  one tree per harness, before another adapter targets this path.
- TODO(clarify): Apothem's `.gitignore` snippet ignores `.apothem/*` but not
  `.codebuddy/settings.local.json`. CodeBuddy documents that file as not
  committed and the install does not edit `.gitignore`; whether the snippet
  should list hook registration files is undecided.
- TODO(clarify): the format of the file `transcript_path` names is not documented. The
  PostToolUse tracker reads the context size from a Claude-style usage record in it;
  where it finds none it counts tool calls and output bytes instead.

## Vendor Sources

Retrieved 2026-10-03 unless marked.

- <https://www.codebuddy.ai/docs/ide/Rules> (project rules)
- <https://www.codebuddy.ai/docs/cli/memory> (memory files, rules frontmatter, `AGENTS.md` fallback; retrieved 2026-10-02)
- <https://www.codebuddy.ai/docs/cli/skills> (skills; retrieved 2026-10-24)
- <https://www.codebuddy.ai/docs/cli/mcp> (`.mcp.json` locations; retrieved 2026-10-02)
- <https://www.codebuddy.ai/docs/cli/hooks> (hook files, schema, events, command contract, matcher, Windows shell, `additionalContext` per event; retrieved 2026-10-28; frontmatter-hooks gate read 2026-10-27)
- <https://www.codebuddy.ai/docs/cli/hooks-guide> (the `/hooks` panel review of externally edited files, the `python3` and `$CODEBUDDY_PROJECT_DIR` command forms; retrieved 2026-10-28)
- <https://cnb.cool/codebuddy/codebuddy-code/-/git/raw/main/docs/hooks.md> (the official project mirror of the hooks page, raw Markdown in Chinese, read 2026-10-28 for the `additionalContext` rules; corroboration only)
- <https://www.codebuddy.ai/docs/ide/Features/hooks> (the IDE hooks page, seven events; retrieved 2026-10-27)
- <https://www.codebuddy.ai/docs/cli/sub-agents> (sub-agent folders, frontmatter keys, precedence, model fallback; retrieved 2026-10-27)
- <https://www.codebuddy.ai/docs/cli/settings> (the "Tools Available to CodeBuddy" table, the complete tool list the sub-agents page points to; retrieved 2026-10-28)
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
`<project>/.codebuddy/agents/`, the hook registration at
`<project>/.codebuddy/settings.local.json` with its scripts under
`<project>/.apothem/support/hooks/`, the skills at `~/.codebuddy/skills/`, and
the rules and templates corpus at `~/.config/apothem/`, and authors no other
cohort. There is no standalone-installable bundle; every artifact requires the
full `apothem install --harness codebuddy --project <path>` engine run.

| Artifact class | Persists standalone? | Mechanism / limit |
|---|---|---|
| Rules | No — requires `apothem install` | The merged `apothem-rules.md` (carrying the embedded behavioral mandates) is written only by the engine into the vendor-native `.codebuddy/rules/` directory. Nothing persists before that run. |
| Skills and commands | No — requires `apothem install` | The engine writes them as skills to the user-level `~/.codebuddy/skills/`. Nothing persists before that run. |
| Agents | No — requires `apothem install` | The engine writes them as subagents to the project's `.codebuddy/agents/`. Nothing persists before that run. |
| Hooks | No — requires `apothem install` | The engine writes the dispatcher to `<project>/.apothem/support/hooks/` and registers SessionStart and PostToolUse in `<project>/.codebuddy/settings.local.json`. Nothing persists before that run, and CodeBuddy applies the entries only after the operator restarts it and reviews them in `/hooks`. |
| MCP / Tools / Settings | No — operator-owned | `.mcp.json` (MCP servers), `.codebuddy/settings.json`, and `CODEBUDDY.md` memory are operator-owned; the adapter authors no entries. CodeBuddy documents slash commands; the adapter authors none. |

CodeBuddy documents a plugin surface, but Apothem ships no CodeBuddy plugin, so
the files `apothem install` writes are the sole persistence surface.
