<!-- SPDX-License-Identifier: MIT -->

# Open-Claw Standard Convention Pin

## Snapshot

- Snapshot date: 2026-11-08
- Snapshot note (rules file, 2026-11-08): the adapter now delivers Apothem's rules through the `bootstrap-extra-files` hook, the route the operator chose on 2026-11-07; see Rules File. Read against `docs.openclaw.ai` and the source at commit `89ba6b0f12ff`. Previous 2026-11-03.
- Snapshot note (agents and workspace files): re-read on 2026-11-03 against `docs.openclaw.ai` and the source at `openclaw/openclaw` commit `716621b9f55b` (the files cited below are identical at `bfa67fd1`). Correction: per-agent settings live in the `agents.entries` map, keyed by agent id. The `agents.list[]` array the earlier pin named fails config validation, and `openclaw doctor --fix` converts it. Correction: OpenClaw does load instruction files. It injects `AGENTS.md` and five other files from each agent's workspace into the system prompt (see Workspace Instruction Files); the adapter writes none of them. The skill-loading facts from 2026-10-24 hold, the skills page answers the two allowlist and state-directory questions (the 2026-10-24 check missed those passages), and the pin now lists every `openclaw mcp` subcommand. Previous 2026-10-24.
- Snapshot note (2026-10-24): skill loading re-checked against `docs.openclaw.ai` (skills, skills config, config extensions) on 2026-10-24. Correction: `skills.load.extraDirs` is a documented `string[]` of extra skill directories read at the lowest precedence of the skill sources, so the adapter lists its support skills directory there. The agent workspace, allowlist, MCP and plugin facts carry over from 2026-10-03: skills also filter through the agent skill allowlists (`agents.defaults.skills`); MCP servers live in the `mcp.servers` config block, managed with `openclaw mcp list|show|set|unset`; OpenClaw also documents plugins and the ClawHub registry. Previous 2026-10-03.
- Adapter source: `src/apothem/harnesses/open_claw/`
- Evidence level: vendor-doc pinned for `~/.openclaw/openclaw.json` (JSON5).
  Skills load from these sources, highest precedence first, and the highest
  source wins when the same skill name appears in more than one:
  `<workspace>/skills`, `<workspace>/.agents/skills`, `~/.agents/skills`
  (default state directory only), `<state-dir>/skills` (`~/.openclaw/skills` by
  default), workshop skills, bundled and custodian skills, then every directory
  under `skills.load.extraDirs` together with plugin skills (the config page
  puts `extraDirs` below plugin skills). A session that runs in a separate
  execution workspace also loads that workspace's `skills/` and
  `.agents/skills/`, after the whole list above, so there an `extraDirs` skill
  wins over a same-named execution-workspace skill (skills page, re-read
  2026-11-03). The vendor examples write an entry with a leading `~/`. With a
  non-default `OPENCLAW_STATE_DIR`, extra-directory skills "continue to load
  normally"; only home-scoped roots such as `~/.agents/skills` drop out. OpenClaw
  then reads its config from `$OPENCLAW_STATE_DIR/openclaw.json`
  (`OPENCLAW_CONFIG_PATH` overrides both; where-things-live FAQ, source
  `src/config/paths.ts:213-245`), while the adapter writes only
  `~/.openclaw/openclaw.json`, so under a non-default state directory, profile
  or config path OpenClaw does not read the Apothem entry. The operator's skill
  allowlist lives under `agents.defaults.skills`; an `agents.entries.<id>.skills`
  list replaces it for that agent, and `[]` means no skills. Allowlists filter
  skills wherever they load from, and an omitted `agents.defaults.skills` sets
  no allowlist for an agent without its own list (skills page,
  `#agent-allowlists`). Subagents are documented via
  `agents.entries.<id>.subagents.allowAgents`, which falls back to
  `agents.defaults.subagents.allowAgents` (sessions-and-subagents page). The
  per-agent `subagents` block accepts only `allowAgents`, `requireAgentId`,
  `delegationMode`, `delegateToolsTo`, `model` and `thinking`;
  `maxConcurrent` and `runTimeoutSeconds` belong under
  `agents.defaults.subagents` (source,
  `src/config/zod-schema.agent-entry-base.ts:116-125`,
  `src/config/zod-schema.agent-defaults-base.ts:231-268`), although the
  entries page still lists `subagents.maxConcurrent` among the per-agent keys.
  MCP servers live in the `mcp.servers` config block; the `openclaw mcp`
  subcommands list / show / set / unset read and write only that block. The CLI
  also has serve (OpenClaw as an MCP server), status, doctor, probe, add,
  configure, tools, login, logout and reload; the earlier pin listed only four,
  and the page's last change in the repository was on 2026-09-09 (commit
  `2393e17f27f2`). OpenClaw is a multi-channel
  messaging gateway. No vendor-native UI claim is
  made here. Versionless docs carry no version or SHA — no-immutable-source
  exception.
- Adapter skill wiring: the adapter appends `~/.openclaw/.apothem/support/skills`
  to `skills.load.extraDirs` and owns only that entry. The operator's own
  `extraDirs` entries stay first and survive an uninstall, and the adapter
  writes into none of the higher-precedence skill folders, so a skill of the
  same name that the operator keeps in any of them wins over the Apothem copy.
  `apothem verify` requires the entry.
- The adapter edits neither allowlist, so an operator who keeps one names the
  Apothem skills in it. The two open questions the 2026-10-24 check left on the
  allowlist and on `OPENCLAW_STATE_DIR` are answered above: the skills page
  already held those passages, and that check missed them.
- TODO(clarify): which Apothem `SKILL.md` frontmatter keys OpenClaw honors. The
  skills page lists its optional keys (`#optional-frontmatter-keys`, read
  2026-11-03), but `capabilities.yml` `conversion_losses` still keeps every key
  as `ignored` until a change maps each Apothem key to what OpenClaw does with
  it.
- TODO(clarify): the adapter writes only `~/.openclaw/openclaw.json`, so it does
  not reach a config that `OPENCLAW_STATE_DIR`, a named profile or
  `OPENCLAW_CONFIG_PATH` moves elsewhere.

## Workspace Instruction Files

Read 2026-11-03 in the docs and, where marked "source", in the repository at
commit `716621b9f55b`. Source facts are implementation details, not documented
guarantees.

- Files: OpenClaw injects `AGENTS.md`, `SOUL.md`, `IDENTITY.md`, `USER.md`,
  `BOOTSTRAP.md` and `MEMORY.md`, in that order, from the agent's workspace
  into the system prompt (system prompt page,
  `#workspace-bootstrap-injection`; agent runtime page,
  `#bootstrap-files-(injected)`; source
  `src/agents/workspace-bootstrap-policy.ts:25-37`, "Canonical bootstrap
  filenames in prompt order"). `BOOTSTRAP.md` is seeded only on a brand-new
  workspace and drops once setup completes. A missing `MEMORY.md` or `USER.md`
  is left out, and any other missing file gets a `[MISSING]` marker (agent
  workspace page, `#workspace-file-map`; source); the agent runtime page
  exempts only `MEMORY.md`, and the context page lists the first five files
  and omits `MEMORY.md`. Sub-agent sessions get `AGENTS.md` only, cron
  sessions the first four files, and `MEMORY.md` is left out of sub-agent,
  cron, group and channel sessions (source, `src/agents/workspace.ts:859-912`).
- Workspace: an `agents.entries.<id>.workspace` when set. Otherwise a sole
  agent uses `agents.defaults.workspace`, then `OPENCLAW_WORKSPACE_DIR`, then
  `<state-dir>/workspace` (`~/.openclaw/workspace` by default); in a roster of
  several agents, an entry without its own `workspace` uses
  `<agents.defaults.workspace>/<id>`, else `<state-dir>/workspace-<id>`
  (source, `src/agents/agent-scope-config.ts:511-535`). Several agents
  therefore mean several workspaces, each with its own `AGENTS.md`
  (multi-agent page, `#paths`).
- Other roots: a session with a recorded workspace root, such as a managed
  worktree, and a run restricted by `workspaceOnly` read the bootstrap files
  from that root instead, with no fallback. Any other session that runs in a
  separate execution folder also gets that folder's `AGENTS.md` as project
  context, after the workspace files; a `cwd` override alone selects no
  bootstrap files (system prompt page).
- Limits: 20,000 characters per file and 60,000 in total by default
  (`agents.defaults.bootstrapMaxChars`, `bootstrapTotalMaxChars`); `USER.md`
  keeps a fixed 4,000-character cap. With the default
  `agents.defaults.contextInjection: "always"`, the embedded runtime re-reads
  and injects the files on every run; `"continuation-skip"` skips eligible
  continuation turns and `"never"` turns injection off.
- Seeding: `openclaw onboard`, `configure`, `setup` and the start of each turn
  create a missing `AGENTS.md`, `SOUL.md`, `IDENTITY.md` or `USER.md` from
  OpenClaw's templates (and `BOOTSTRAP.md` on a brand-new workspace, never
  `MEMORY.md`), only in the agent's configured workspace, and never overwrite
  an existing file (agent workspace page, `#workspace-file-map`; system prompt
  page). `agents.defaults.skipBootstrap` stops the creation, not the
  injection. The seeded `AGENTS.md` tells the agent to record lessons in
  `AGENTS.md` or the relevant skill (`/reference/templates/AGENTS`).
- Adapter: writes none of these six files. It brings Apothem's rules in through
  an extra file, `<workspace>/apothem/AGENTS.md` (see Rules File). The profile
  document at `~/.openclaw/apothem/rules/00-apothem-profile.md` carries the
  same content and is still not loaded by OpenClaw.
- Decision (operator, 2026-11-07): an Apothem-owned file named `AGENTS.md`
  in each workspace, registered with the bundled `bootstrap-extra-files` hook.
  The operator turned down a managed block in the workspace `AGENTS.md` (OpenClaw,
  Doctor and the agent rewrite that file), the Agent Guidance plugin (reach to
  sub-agent and cron sessions unconfirmed, and a plugin reload after every
  update) and no instruction file.

## Rules File (`bootstrap-extra-files`)

Read 2026-11-08 in the docs (hooks configuration and bundled hooks pages) and
in the repository at commit `89ba6b0f12ff` (2026-11-08), where marked "source".

- Adapter: writes `<workspace>/apothem/AGENTS.md` into every workspace it finds
  (see below) as a managed-block file, and adds `apothem/AGENTS.md` to the
  hook's entry `hooks.internal.entries.bootstrap-extra-files` in
  `~/.openclaw/openclaw.json`. It never writes the workspace's own `AGENTS.md`
  or `hooks.internal.enabled`. The file holds the profile's managed block and
  the support announcement, which names the rule index under
  `~/.openclaw/.apothem/support/rules/`.
- Hook config: `paths` (aliases `patterns`, `files`) lists glob or literal paths
  "resolve[d] relative to the event's workspace" that "must remain inside it,
  including after symlink resolution"; only the six bootstrap basenames load
  (bundled hooks page, `#bootstrap-extra-files-config`). The handler reads the
  first non-empty list of `paths`, `patterns`, `files`, so they are alternatives,
  not merged (source `src/agents/workspace-bootstrap-policy.ts:90-102`); the
  adapter joins the list the operator already uses. An entry set to
  `enabled: false` yields no paths. A missing file is skipped with a "missing"
  diagnostic (source `src/agents/workspace.ts:1012-1085`).
- Enabling: the entry alone turns the hook on unless `hooks.internal.enabled`
  is `false`. Named entries form an allowlist; `hooks.internal.enabled: true`
  with no named entry, no `load.extraDirs` and no tracked install means
  open-ended discovery, and "Adding the first named entry can narrow a
  previously broad selection" (hooks configuration page; source
  `src/hooks/configured.ts:14-57`). The adapter therefore registers nothing,
  and warns, when `hooks.internal.enabled` is `false`, when the entry is
  `enabled: false`, and when `hooks.internal.enabled` is `true` with no named
  hook and no `load.extraDirs`. `openclaw doctor --fix` removes a legacy-only
  `hooks.internal.enabled: true` "to avoid broad discovery" (same page).
- Session reach: an extra file keeps its basename as its bootstrap name, so
  `apothem/AGENTS.md` passes the sub-agent allowlist (`AGENTS.md` only) and the
  cron allowlist (`AGENTS.md`, `SOUL.md`, `IDENTITY.md`, `USER.md`); session
  filtering runs after the hook (source `src/agents/workspace.ts:859-916`,
  `src/hooks/bundled/bootstrap-extra-files/handler.ts`). The bundled hooks page
  says extra files "go through normal bootstrap filtering".
- Brand-new workspaces: OpenClaw treats a workspace as brand-new when
  `AGENTS.md`, `SOUL.md`, `IDENTITY.md`, `USER.md` and `memory/` are absent and
  there is no `MEMORY.md` or workspace skill; an `apothem/` folder is none of
  these (source `src/agents/workspace.ts:173-213, 676-690`). The adapter writes
  only into workspace folders that already exist.
- Workspaces: `agents.entries.<id>.workspace` when set; otherwise the entry
  OpenClaw treats as owning the default workspace uses
  `agents.defaults.workspace` (else the default workspace), and any other
  entry uses `<agents.defaults.workspace>/<id>`, else
  `<state-dir>/workspace-<id>` (source `src/agents/agent-scope-config.ts:511-535`).
  The default workspace is `OPENCLAW_WORKSPACE_DIR`, else
  `<state-dir>/workspace` (source `src/agents/workspace-default-path.ts:8-25`).
  The adapter writes into `agents.defaults.workspace` (else
  `OPENCLAW_WORKSPACE_DIR`, else `~/.openclaw/workspace`) and each entry's
  workspace by those rules, when the folder exists inside the home directory;
  the others are skipped with a warning.
- Limits: 20,000 characters per file and 60,000 in total by default
  (`agents.defaults.bootstrapMaxChars`, `bootstrapTotalMaxChars`), `USER.md`
  4,000; extra files come after the six workspace files, and a file is skipped
  once less than 64 characters of the total remain (source
  `src/agents/embedded-agent-helpers/bootstrap.ts:87-91, 377-425`). The adapter
  refuses to write a rules file over the per-file limit (OpenClaw would keep its
  head and tail and drop the middle) and warns when the workspace's six files
  leave too little of the total. With the default profile the file is a few
  thousand characters.
- TODO(clarify): per-entry overrides of `bootstrapMaxChars` and
  `bootstrapTotalMaxChars` exist (source `bootstrap.ts:128-153`); the adapter
  checks only the `agents.defaults` values.
- TODO(clarify): whether sandboxed sessions (`workspaceAccess` `none` or `ro`,
  which copy the canonical files into the sandbox) see the extra file; not
  checked.
- TODO(clarify): which entry OpenClaw treats as owning the default workspace
  (`tryResolveLegacyDataOwnerAgentId`) is not replicated; the adapter always
  writes into the default workspace, which covers it.

## Vendor Sources

Retrieved 2026-11-03.

- <https://docs.openclaw.ai/gateway/config-agents/entries-and-multi-agent> (`agents.entries`, keyed by agent id; per-agent `skills` and `subagents` keys)
- <https://docs.openclaw.ai/gateway/doctor/config-migrations> (Doctor converts a legacy `agents.list` roster to `agents.entries`)
- <https://docs.openclaw.ai/concepts/system-prompt> (workspace bootstrap injection and the execution folder's `AGENTS.md`)
- <https://docs.openclaw.ai/concepts/agent> (the injected bootstrap files)
- <https://docs.openclaw.ai/concepts/agent-workspace> (workspace location, seeding from templates, existing files kept)
- <https://docs.openclaw.ai/concepts/multi-agent> (one workspace per agent)
- <https://docs.openclaw.ai/concepts/context> (the injected workspace files it lists, five of the six)
- <https://docs.openclaw.ai/gateway/config-tools/sessions-and-subagents> (`agents.defaults.subagents`, the fallback for `allowAgents`)
- <https://docs.openclaw.ai/help/faq/where-things-live-on-disk> (`$OPENCLAW_STATE_DIR/openclaw.json` as the main config)
- <https://docs.openclaw.ai/reference/templates/AGENTS> (the seeded `AGENTS.md` and its instruction to record lessons)
- <https://docs.openclaw.ai/plugins/agent-guidance> (the bundled Agent Guidance plugin, off by default)
- <https://docs.openclaw.ai/tools/skills> (re-read: loading order, execution workspace skills, allowlists, `OPENCLAW_STATE_DIR`, frontmatter keys)
- <https://docs.openclaw.ai/cli/mcp> (re-read: the `openclaw mcp` subcommands and the `mcp.servers` block)
- <https://docs.openclaw.ai/gateway/config-agents/workspace-and-bootstrap> (re-read: `agents.defaults.workspace`, the bootstrap file limits, `skipBootstrap`; per-agent keys are now under `agents.entries`)
- <https://docs.openclaw.ai/tools/skills-config> (re-read: `skills.load.extraDirs` as a `string[]` at the lowest precedence; first read 2026-10-24)
- <https://docs.openclaw.ai/gateway/config-extensions> (re-read: `load.extraDirs` example and precedence; first read 2026-10-24)
- Source: `openclaw/openclaw` commit `716621b9f55b` (`src/config/zod-schema.agents.ts`, `src/config/zod-schema.agent-entry-base.ts`, `src/config/zod-schema.agent-defaults-base.ts`, `src/config/legacy.roster.ts`, `src/config/paths.ts`, `src/agents/workspace-bootstrap-policy.ts`, `src/agents/embedded-agent-helpers/bootstrap.ts`, `src/agents/workspace-file-read.ts`, `src/agents/workspace.ts`, `src/agents/agent-scope-config.ts`)

Retrieved 2026-11-08.

- <https://docs.openclaw.ai/automation/hooks/configuration> (selection rules for `hooks.internal`; a first named entry narrows open-ended discovery)
- <https://docs.openclaw.ai/automation/hooks/bundled-hooks> (`#bootstrap-extra-files-config`: `paths` / `patterns` / `files`, workspace-relative paths, bootstrap basenames, limits and filtering)
- Source: `openclaw/openclaw` commit `89ba6b0f12ff` (`src/hooks/configured.ts`, `src/hooks/config.ts`, `src/hooks/policy.ts`, `src/hooks/bundled/bootstrap-extra-files/`, `src/agents/workspace-bootstrap-policy.ts`, `src/agents/workspace.ts`, `src/agents/agent-scope-config.ts`, `src/agents/workspace-default-path.ts`, `src/agents/embedded-agent-helpers/bootstrap.ts`)

Retrieved 2026-11-03.

- <https://docs.openclaw.ai/install> (install methods, among them the npm package `openclaw`, installed as `openclaw@latest`)

## Discovery Targets

- None. No capability cell for this harness is discovery-pending.

## Recommended Postfix Rendering

- Status: supported as plain text.
- Mechanism: Apothem emits the literal ` (Recommended)` suffix in the option label. Open-Claw adapter output preserves that suffix when prompt text is materialized.
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

OpenClaw is a multi-channel messaging gateway with **no vendor plugin or
extension install surface** that Apothem ships. The adapter materializes
`~/.openclaw/openclaw.json` (JSON5) via its materializer and keeps non-native
cohorts under the Apothem support subtree (`~/.openclaw/.apothem/support/`). There is no
standalone-installable bundle; every artifact requires the full
`apothem install --harness open-claw` engine run.

| Artifact class | Persists standalone? | Mechanism / limit |
|---|---|---|
| Config / agents | No — requires `apothem install` | `~/.openclaw/openclaw.json` is materializer-rendered by the engine; nothing persists before that run. |
| Commands / Skills / Agents / Rules | No — requires `apothem install` | These land under `~/.openclaw/.apothem/support/` (support subtree) via the engine; the support skills directory is listed under `skills.load.extraDirs`, and OpenClaw `agents.defaults.skills` is a name-allowlist the adapter does not author. |
| Hooks / Settings | No — requires `apothem install` | The only hook setting is Apothem's path in the bundled `bootstrap-extra-files` entry, written by the engine with the workspace rules files. |
| MCP | No — operator-owned | OpenClaw MCP servers live in the `mcp.servers` config block (managed via the `openclaw mcp` CLI subcommands; `mcp.*` hot-applies); the adapter authors no entries. |

OpenClaw documents plugins and the ClawHub registry, but Apothem ships no
OpenClaw plugin, so the engine install is the sole persistence path.
