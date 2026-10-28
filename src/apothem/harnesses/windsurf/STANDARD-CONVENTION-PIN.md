<!-- SPDX-License-Identifier: MIT -->

# Windsurf Standard Convention Pin

## Snapshot

- Snapshot date: 2026-10-28
- Snapshot note (hooks): the adapter now registers Devin Local hooks. The CLI hooks overview, the lifecycle hooks page, the configuration import page and the Devin Local page were re-read on 2026-10-28 from the raw Markdown each page serves, and the Cascade hooks page the day before. Previous 2026-10-27.
- Snapshot note (agents): the adapter now installs eleven of Apothem's fourteen agents as Devin Local subagents in `<project>/.devin/agents/`. The subagents page, the Devin Local page, the extensibility overview, the configuration import page, the plugins page, the skills page, the models page and both changelogs were read on 2026-10-27 from the raw Markdown each page serves. Previous 2026-10-24.
- Snapshot note: the adapter now installs skills and command skills at the shared `~/.agents/skills/` and the rules and templates corpus at `~/.config/apothem/`.
- Adapter source: `src/apothem/harnesses/windsurf/`
- Evidence level: vendor-doc pinned (living docs at `docs.devin.ai`; no-immutable-source exception). No vendor-native UI claim is made here.

## Official Surface Refresh

- Re-pinned 2026-10-27 for the native agents surface (Devin Local only). Read that
  day on `docs.devin.ai`:
  - Agents, which agent: custom subagents exist for the Devin Local agent only.
    The legacy Cascade agent has "no Cascade equivalent at all", and new Desktop
    conversations never start on Cascade. The adapter therefore targets Devin
    Local and ignores Cascade for agents.
  - Agents, locations: project `.devin/agents/<name>.md` or
    `.devin/agents/<name>/AGENT.md` (`AGENTS.md`, `agent.md` and `agents.md` are
    also accepted as the file name, in that order of precedence), and also
    `.agents/agents/` in the project; user `~/.config/devin/agents/` on
    Linux and macOS, `%APPDATA%\devin\agents\` on Windows. No user-level
    `~/.agents/agents/` is documented. A `name:` in the frontmatter overrides the
    name taken from the path. A plugin's `agents/` folder is surfaced as
    `<plugin>:<name>`. The Desktop pages defer to the CLI page for where the
    folders are discovered, and the Desktop changelog (v3.6.21, 2026-07-29)
    confirms the flat `agents/<name>.md` form and the Subagents (Preview)
    toggle; no Desktop page lists the roots.
  - Agents, file: Markdown with the same YAML frontmatter as skills, then the
    body as the subagent's system prompt. Keys, all optional: `name` (default the
    file or directory name; a name equal to a built-in, `subagent_explore` or
    `subagent_general`, is skipped with a warning), `description`, `model`
    (default the router-selected subagent model, which is **not** the parent's
    model), `allowed-tools` (a list, default every tool; the alias `tools` is also
    accepted; it cannot grant `ask_user_question`; on a subagent profile it
    restricts the tool set, on a skill it only auto-approves) and `max-nesting`.
    The page labels custom subagents experimental. `devin doctor` checks
    profiles for incorrect frontmatter, and its rules are unpublished.
  - Agents, tool names: the skills page lists `read`, `edit`, `grep`, `glob` and
    `exec` for `allowed-tools`, and the CLI changelog (v3000.11.1) adds `write`.
    The hooks page lists more lowercase tool names (`apply_patch`,
    `notebook_read`, `notebook_edit`, `webfetch` and others) as hook matcher
    values; nothing says `allowed-tools` accepts them, and no page names a web
    search tool.
  - Agents, switch: "Subagents (Preview)" in Devin Settings on Desktop;
    `subagents_enabled` in the CLI config (user only, on by default). An admin
    setting of Default subagent model = None disables subagents.
  - Agents, other roots: the Configuration Import page lists the Claude Code
    imports as rules, skills, commands and MCP servers, with no agents row, but
    the Extensibility overview says the Devin CLI imports custom subagents from
    the `.claude/` directory, without naming a subpath. The two pages describe
    the CLI, not Desktop's Local agent.
- Refreshed 2026-10-03 against `docs.devin.ai`. The windsurf harness is Devin
  Desktop (rebranded 2026-06-02); the slug stays `windsurf`. Devin Desktop now
  has two agents: the Devin Local agent, the default for new tabs, which
  configures MCP in the Devin CLI config files, and the legacy Cascade agent.
- Rules (resolved): the Memories & Rules page lists workspace rules at
  `.devin/rules/*.md` (preferred) or `.windsurf/rules/*.md` (fallback), 12,000
  characters per file, plus the legacy `.windsurfrules` file and `AGENTS.md` in
  any directory; the global rule file is
  `~/.codeium/windsurf/memories/global_rules.md`. The Devin CLI rules page
  documents the same `.devin/rules/` precedence for the CLI. The adapter's
  `<project>/.devin/rules/apothem-rules.md` therefore sits at the preferred
  location. The earlier `docs.devin.ai/desktop/cascade/workspace-rules` page now
  answers 404.
- Skills (resolved): `.devin/skills/` (preferred) or the legacy
  `.windsurf/skills/` in the workspace; `~/.codeium/windsurf/skills/` or
  `~/.config/devin/skills/` globally. Devin Desktop also discovers
  `.agents/skills/` and `~/.agents/skills/`, so a Codex install's skills reach it.
  This settles the earlier open question: skills follow the same
  `.devin/`-over-`.windsurf/` order as rules. The adapter writes Apothem's
  skills, plus its commands wrapped as skills, to `~/.agents/skills/`, the one
  user-level copy shared with Codex, Cursor, GitHub Copilot, and Zed, and not to
  the Windsurf-specific folders. Windsurf may also list the same names from
  `~/.claude/skills/` when its Claude Code config import is on (the Devin CLI
  docs make that import on by default; the Desktop pages do not say whether the
  Local agent applies it).
  TODO(clarify): the vendor docs do not say how Windsurf treats a `SKILL.md`
  frontmatter key it does not list. The shared emission sets `user-invocable`,
  `disable-model-invocation`, `allowed-tools`, `argument-hint`, and a
  `metadata` map; probe Windsurf with the full set before a release and, if it
  rejects extras, change `SHARED_TOPLEVEL_KEYS` in `install_driver_shared.py`.
- Hooks (resolved, two agents, two formats): the legacy Cascade agent reads
  `hooks.json` at `.devin/hooks.json` in the workspace (the legacy
  `.windsurf/hooks.json` is used only when the `.devin` file is absent or defines
  no hooks), `~/.codeium/windsurf/hooks.json` for the user, and OS-level system
  paths; all levels merge. The Devin Local agent, the default for new tabs, has
  its own format and files (next section). The adapter targets Devin Local and
  writes no Cascade hook file. The earlier "unverified" flag is cleared.
- MCP (corrected): Cascade reads `~/.config/devin/mcp_config.json`
  (`%APPDATA%\devin\mcp_config.json` on Windows), and the Devin Local agent
  uses the Devin CLI config files. The earlier
  `~/.codeium/windsurf/mcp_config.json` path is no longer in the docs.
  Operator-owned; the adapter authors no entries.
- Memories: auto-generated memories apply to the legacy Cascade agent only and
  stay on the machine; the Devin Local agent does not persist memories.
- The adapter delivers the project rules file, the shared skills folder above
  and, for the Devin Local agent, eleven of Apothem's agents as subagents in
  `<project>/.devin/agents/` and two hooks in `<project>/.devin/config.local.json`.
  It authors no workflow and no Cascade hook.
- Agents the adapter writes: one `<name>.md` per Apothem agent in
  `<project>/.devin/agents/`, with `name`, `description` and, where the source
  restricts tools, `allowed-tools` as a YAML list of lowercase Devin tool names
  (`read`, `edit`, `grep`, `glob`, `exec`, `write`; the source `Bash` is `exec`).
  Devin documents no deny key, so the source grant minus its denials is compiled
  into the allowlist, a source tool pattern such as `Bash(git status)` has no
  Devin form and is left out of a grant (a patterned denial denies the whole
  tool), and a source with denials and no grant gets the documented names it does
  not deny. Eleven agents are installed. The three that need web tools
  (citation-auditor, fact-checker, research-scout) are held back: Devin documents
  no `allowed-tools` name for web search or fetch, and installing them without the
  web grant would leave a research agent unable to research, while installing them
  without `allowed-tools` would give them every tool. The hold is the `exclude`
  set of the `devin_agents` row in `AGENT_EMITTERS`, and a file you wrote in
  `.devin/agents/` under one of those names is never read, replaced or removed.
  No release shipped an agents entry for this harness (checked v1.0.1 to
  v1.4.0), so there is nothing to retire; an agent added to that set after a
  release shipped it needs a `stale-sweep` entry in the same change. The adapter
  never writes `model` (the default subagent model is router-selected and is not
  the parent's), `max-nesting`, `maxTurns`, `version`, `updated` or
  `portability`, nor `.agents/agents/` (shared with Kimi Code, whose tool names
  are capitalised, so one file could not serve both readers), nor the user
  folders `~/.config/devin/agents/` and `%APPDATA%\devin\agents\`. A same-named
  file you wrote in `.devin/agents/` is backed up before it is replaced.
- Shared roots: the registry records no new shared root and does not list Windsurf
  as a reader of `~/.claude/agents/`, because the `.claude/` subagent import the
  extensibility overview describes has no named subpath.
- TODO(clarify): the `allowed-tools` names for Devin's web search and fetch tools.
  The held-back agents install once the docs name them.
- TODO(clarify): which values `model` accepts. The subagents page shows
  `model: sonnet` and never defines the values; the short names are defined on the
  models page for the `--model` flag, and linking the two is an inference. The
  adapter writes no `model`.
- TODO(clarify): how Devin reads `allowed-tools: []`. The adapter writes it only for
  a source grant that loses every tool (no agent in the corpus does), so that the
  agent is not given every tool; the page does not define an empty list.
- TODO(clarify): whether `apply_patch`, a tool the hooks page lists, is covered by
  `edit` or `write` in `allowed-tools`; an agent granted `edit` and `write` may or
  may not be able to apply a patch.
- TODO(clarify): the `.claude/` subagent import. The extensibility overview says
  the CLI imports custom subagents from the `.claude/` directory, the
  configuration import page has no agents row, and neither names a subpath or
  says that Devin Desktop's Local agent applies it. Until a probe settles it,
  Windsurf is not recorded as a reader of `~/.claude/agents/`.
- TODO(clarify): whether Devin Desktop's Local agent discovers the same folders as
  the CLI (`.agents/agents/`, `~/.config/devin/agents/`); the Desktop pages defer
  to the CLI page and list none.
- TODO(clarify): how Devin treats a frontmatter key it does not list; the rules
  `devin doctor` applies are unpublished. The adapter writes only listed keys.
- Open question (review by 2026-12-31): the Devin CLI imports other tools'
  rules by default (`AGENTS.md`, `.cursor/rules/*.mdc`, `CLAUDE.md` and
  `~/.claude/CLAUDE.md`). If Devin Desktop's Local agent applies the same
  defaults, Apothem's Cursor and Claude Code blocks also load there. The
  Desktop docs do not say, so the registry records no shared root for it yet.
- Web-fetch / browser-retrieval (`web_fetch` = **yes**): Cascade searches the
  web and documentation through `@web` and `@docs` mentions and URL parsing,
  gated by the "Enable Web Search" admin setting — the backing dimension for
  `rules/source-accessibility.md` step 1. Evidence: vendor-doc-url
  <https://docs.devin.ai/desktop/cascade/web-search>; snapshot-id living docs;
  snapshot-date 2026-10-03.

## Hooks

Read 2026-10-28 (<https://docs.devin.ai/cli/extensibility/hooks/overview.md>,
<https://docs.devin.ai/cli/extensibility/hooks/lifecycle-hooks.md>,
<https://docs.devin.ai/desktop/devin-local.md>), with the CLI changelog and the
Desktop changelog read 2026-10-27. The hooks pages describe the Devin CLI. The
Cascade hooks page says the Devin Local agent has its own lifecycle hooks, with a
different configuration format, on those pages, and the Devin Local page lists
hooks in its Customizations surface, so the adapter treats the CLI's format as
Devin Local's. The legacy Cascade agent has a different format that the adapter
does not write.

- Files, project: `.devin/hooks.v1.json` (the recommended standalone file: the
  hooks object is the whole file, no wrapper key), the `hooks` key of
  `.devin/config.json`, the `hooks` key of `.devin/config.local.json` ("local
  override, gitignored"), and `.claude/settings.json` and
  `.claude/settings.local.json` (Claude Code format). Project files are found in
  the working directory and its ancestors up to the repository root.
- Files, user: the `hooks` key of `~/.config/devin/config.json`
  (`%APPDATA%\devin\config.json` on Windows), and `~/.claude.json`,
  `~/.claude/settings.json` and `~/.claude/settings.local.json`. There is no
  user-level `hooks.v1.json`.
- Schema: `{"<Event>": [{"matcher": "<regex, optional>", "hooks": [{"type":
  "command", "command": "<string>", "timeout": <seconds, optional>}]}]}`; `type`
  is `command` or `prompt`. The changelog adds `fail_closed: true` (v3000.11.205,
  2026-10-22), which blocks the guarded action when the hook itself fails; it does
  not say where in the schema the field sits, and the adapter writes it nowhere.
- Events: the overview lists eight (PreToolUse, PostToolUse, PermissionRequest,
  UserPromptSubmit, Stop, PostCompaction, SessionStart, SessionEnd); the changelog
  adds PreCompact and PostCompact (v3000.11.92, 2026-10-14).
- Command contract: JSON on stdin (`hook_event_name`, `session_id`, a per-turn
  `prompt_id` that is absent before the first prompt, plus `tool_name` and
  `tool_input` for tool events; PostToolUse adds `tool_response` with `success`,
  `output` and `error`; SessionStart adds `source`). `DEVIN_PROJECT_DIR` is set to
  the project root; the stdin payload carries no working directory, so the
  `devin` contract fills `cwd` from that variable and the SessionStart summaries
  (plan, memory, knowledge base) resolve against the project. Exit 0 succeeds, exit 2 blocks, and any other code, a timeout
  or unreadable output is logged and does not block. Stdout JSON may carry
  `decision` (`approve` or `block`) with `reason`, `hookSpecificOutput.updatedInput`
  (PreToolUse) and `hookSpecificOutput.additionalContext`.
- Where `additionalContext` reaches the model: UserPromptSubmit, SessionStart and
  PostToolUse. PreToolUse documents `updatedInput` and a decision, and no context
  channel, so a guard that speaks through `additionalContext` there is not known
  to be delivered. Apothem registers SessionStart (the bootstrap) and PostToolUse
  (the proactive-compaction tracker), and registers no PreToolUse guard, no Stop
  gate, no compaction hook, no NotebookEdit or AskUserQuestion guard and no
  conformity-gate hook. The envelope the dispatcher writes is Claude's, which
  Devin reads (`--contract devin` changes no byte of it); the contract only maps
  Devin's lowercase tool names (`exec`, `write`, `edit`, `read`, `grep`, `glob`)
  onto the Claude spellings the handlers test.
- Matcher: a regex over `tool_name` (unanchored: `exec` matches any name that
  contains `exec`), available for PreToolUse, PostToolUse and PermissionRequest.
  An empty or omitted matcher matches every tool name, and a glob such as `*` is
  not a regex. The adapter writes no matcher: SessionStart has no tool name, and
  the PostToolUse tracker counts every tool. Devin's built-in tool names are
  lowercase (`read`, `write`, `edit`, `apply_patch`, `grep`, `glob`, `exec`,
  `webfetch`, ...), so Claude Code matchers such as `Bash` or `Edit` are not
  Devin's names.
- Activation: hooks load and run only in a workspace that is not in Restricted
  Mode (the Devin Local page: they "neither load nor run" there). The CLI's
  `/hooks` command lists the loaded hooks with
  their source files, and the Desktop changelog (v3.5.17, 2026-07-17) says the
  Hooks tab in Devin Local's Customizations lists them with their source and
  trigger events. The install prints a note with these two ways to check.
- Claude Code import: `.claude/` hooks load while `read_config_from.claude` is on,
  and the configuration page states it is on by default when `read_config_from`
  is not set. The Desktop pages do not say whether the Local agent applies that
  default. If the Apothem Claude Code install wrote its hooks to
  `~/.claude/settings.json`, Devin can run both sets. The install prints a note
  naming the switch (`"claude": false` under `read_config_from` in the user config
  or the project's `.devin/config.json`) and what turning it off also stops
  (Claude Code's rules, skills, commands and MCP servers). The SessionStart
  command the adapter registers and the Claude Code copy of it (the default
  command line) share one marker per (session, source) in the hook state
  directory, so whichever runs second is silent. The default command line takes
  part only when `DEVIN_PROJECT_DIR` is set; the marker binds for ten seconds, so
  a later start of the same session delivers; no PostToolUse counter is
  de-duplicated.
- TODO(clarify): whether `DEVIN_PROJECT_DIR` is also set for a hook Devin imports
  from `~/.claude/settings.json`; the overview page states it for hooks without
  distinguishing the source. If it is not, the Claude Code copy runs unmarked and
  the bootstrap can be delivered twice.
- Files the adapter writes: the dispatcher tree at
  `<project>/.apothem/support/windsurf/hooks/` (Apothem-owned; nested under the
  harness name so another project-scope adapter's uninstall cannot remove it; the
  project's `.gitignore` snippet ignores `.apothem/*`) and the registration in
  `<project>/.devin/config.local.json`, key-merged: the operator's own hooks and
  keys stay, and an uninstall removes only the handlers that tells Apothem's entry apart by what its command runs (the `.apothem/support/<harness>/hooks/dispatch.py` path with a `--contract` argument, read from the command text alone, so the project path it was written under does not matter and an operator's own `hooks/dispatch.py` or `python -m apothem.conformity.gate` is never taken for Apothem's). The shared `.devin/config.json`, the
  standalone `.devin/hooks.v1.json`, the user config and the `.claude/` files are
  never written. A file with comments is refused with `config.unparseable` and
  left as it is. An uninstall that finds the file unreadable (comments, trailing commas) while it still names the dispatcher leaves it as it is and reports the entry as skipped, with the reason, instead of a success. `verify` requires the file to hold at least one such entry. A project or interpreter path holding `$`, a backtick, a double quote, a backslash or a control character is refused at install (the plan validation reports it before anything is written): one escape rule cannot serve `sh`, Git Bash and PowerShell, and inside the quoted command such a path runs a different file.
- TODO(clarify): which shell Devin runs a hook command in on Windows. The
  Cascade page names `bash -c` and `powershell -Command`, and the Local pages name
  none (the changelog's PowerShell default is for the `exec` tool). The adapter
  writes bash quoting (`"<interpreter>" "<script>" ...`), which PowerShell would
  not parse without a call operator; the install note says to confirm the hooks
  loaded.
- TODO(clarify): whether Devin Desktop's Local agent applies the CLI's
  `read_config_from` defaults, and whether it reads the project `.devin/` files
  of an ancestor directory the way the CLI does.
- TODO(clarify): where `fail_closed` sits in the schema; the adapter relies on
  the default (fail open).
- Local config is excluded from git by Devin itself: "Local config files are
  automatically excluded from git via `.git/info/exclude`"
  (<https://docs.devin.ai/cli/reference/configuration/global-vs-local.md>, read
  2026-10-28), and the precedence table calls `.devin/config.local.json`
  "Personal, gitignored". The registration therefore stays out of the
  repository without any edit to `.gitignore`, which Apothem does not make.
- TODO(clarify): whether the Local agent also reads Cascade-format hook files
  (`.devin/hooks.json`, `.windsurf/hooks.json`, `~/.codeium/windsurf/hooks.json`).
  The changelog says Windsurf-format command and write hooks fire on GPT models
  (v3000.11.92) and `post_setup_worktree` runs for Local sessions (Desktop v3.8.20),
  so some are read; no page says which. The adapter does not rely on it.
- TODO(clarify): whether Devin trims or caps `additionalContext`; the SessionStart
  bootstrap is a few kilobytes.

## Vendor Sources

Retrieved 2026-10-03 unless marked.

- <https://docs.devin.ai/desktop/cascade/memories> (memories and rules)
- <https://docs.devin.ai/desktop/cascade/agents-md> (`AGENTS.md`)
- <https://docs.devin.ai/desktop/cascade/mcp> (`mcp_config.json`)
- <https://docs.devin.ai/desktop/cascade/web-search> (web search)
- <https://docs.devin.ai/cli/extensibility/rules.md> (Devin CLI rules)
- <https://docs.devin.ai/cli/reference/configuration/read-config-from.md> (Devin CLI config imports)
- <https://docs.devin.ai/desktop/cascade/skills.md> (skills; retrieved 2026-10-24, the folder the adapter writes)
- <https://docs.devin.ai/desktop/cascade/hooks.md> (Cascade hooks, a different format from the Devin Local hooks the adapter writes; retrieved 2026-10-27)

Retrieved 2026-10-28 (the hooks the adapter writes).

- <https://docs.devin.ai/cli/extensibility/hooks/overview.md> (hook files and
  locations, schema, events, stdin and stdout contract, exit codes,
  `read_config_from.claude`, `/hooks`)
- <https://docs.devin.ai/cli/extensibility/hooks/lifecycle-hooks.md> (per-event
  stdin, the matcher regex, the lowercase tool names)
- <https://docs.devin.ai/cli/reference/configuration/read-config-from.md> (the
  `claude` import option and its default, the project and user config examples)
- <https://docs.devin.ai/cli/reference/configuration/global-vs-local.md> (local
  config files, `.devin/config.local.json`, and their exclusion from git)
- <https://docs.devin.ai/desktop/devin-local.md> (Restricted Mode, the
  Customizations surface that lists hooks)

Retrieved 2026-10-27 (the agents the adapter writes).

- <https://docs.devin.ai/cli/subagents.md> (agent folders, layouts, keys,
  `allowed-tools`, the experimental label, the `subagents_enabled` switch)
- <https://docs.devin.ai/desktop/devin-local.md> (the Subagents (Preview)
  toggle, no Cascade equivalent, hooks and workflows on Devin Local)
- <https://docs.devin.ai/desktop/changelog.md> (flat `agents/<name>.md` files and
  the toggle in v3.6.21, the Subagents section in Customizations)
- <https://docs.devin.ai/cli/extensibility/index.md> (the `.claude/` import
  table)
- <https://docs.devin.ai/cli/reference/configuration/read-config-from.md> (the
  Claude Code import has no agents row; the import default)
- <https://docs.devin.ai/cli/extensibility/plugins/overview.md> (plugin
  subagents, `<plugin>:<name>`)
- <https://docs.devin.ai/cli/extensibility/skills/creating-skills.md> (the
  `allowed-tools` names; restricts on a subagent profile)
- <https://docs.devin.ai/cli/extensibility/hooks/lifecycle-hooks.md> (the
  lowercase tool names hook matchers see)
- <https://docs.devin.ai/cli/changelog/stable.md> (`write` in `allowed-tools`,
  the `tools` alias, `devin doctor` for subagent profiles)
- <https://docs.devin.ai/cli/models.md> (short model names for `--model`)

## Discovery Targets

- Discovery target: mcp_servers by 2026-12-31 — decide whether Apothem renders the profile's MCP inventory into `~/.config/devin/mcp_config.json` or keeps naming it as operator-owned.

## Recommended Postfix Rendering

- Status: supported as plain text.
- Mechanism: Apothem emits the literal ` (Recommended)` suffix in the option label. Windsurf rule templates preserve that suffix as authored.
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

Windsurf (Devin Desktop) exposes **no vendor plugin or extension install surface**
that Apothem ships. The adapter writes a merged rules file at
`<project>/.devin/rules/apothem-rules.md` (the preferred surface;
`.windsurf/rules/` is the backward-compat fallback), the skills at
`~/.agents/skills/`, the rules and templates corpus at `~/.config/apothem/`,
eleven agents as Devin Local subagents at `<project>/.devin/agents/`, and the hook
registration at `<project>/.devin/config.local.json` with its scripts under
`<project>/.apothem/support/windsurf/hooks/`, and authors no other cohort. There is no standalone-installable bundle; every artifact
requires the full `apothem install --harness windsurf --project <path>` engine run.

| Artifact class | Persists standalone? | Mechanism / limit |
|---|---|---|
| Rules | No — requires `apothem install` | The merged `apothem-rules.md` (carrying the embedded behavioral mandates) is written only by the engine into the preferred `.devin/rules/` directory (`.windsurf/rules/` backward-compat fallback). Nothing persists before that run. |
| Skills and commands | No — requires `apothem install` | The engine writes them as skills to the user-level `~/.agents/skills/`, one copy shared by every project and every tool that reads that folder. Nothing persists before that run. |
| Agents | No — requires `apothem install` | The engine writes eleven of the fourteen as Devin Local subagents to the project's `.devin/agents/`. Nothing persists before that run. |
| Workflows | No — adapter scope | The vendor documents workflows (`.windsurf/workflows/`), which reach the legacy Cascade agent only; the adapter authors none. |
| Hooks | No — requires `apothem install` | The engine writes the dispatcher to `<project>/.apothem/support/windsurf/hooks/` and registers SessionStart and PostToolUse in `<project>/.devin/config.local.json`. Nothing persists before that run, and Devin runs no hook while the workspace is in Restricted Mode. |
| MCP / Settings | No — operator-owned | `~/.config/devin/mcp_config.json` (MCP) and the shared `config.json` and `hooks.v1.json` are operator-owned; the adapter authors no entries. The Cascade `hooks.json` is not written. |

The Devin CLI documents plugins and team marketplaces, but Apothem ships no
Devin plugin, so a
plugin-alone story does not exist — the files `apothem install` writes are the
sole persistence surface.
