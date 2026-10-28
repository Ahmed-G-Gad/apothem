<!-- SPDX-License-Identifier: MIT -->

# Kimi Code Standard Convention Pin

## Snapshot

- Snapshot date: 2026-10-27
- Snapshot note (agents): the adapter now installs Apothem's agents as Kimi Code
  sub-agents in `<project>/.kimi-code/agents/`. The agents page, the tools
  reference, the configuration-files page and the changelog were read on
  2026-10-27; the other pages keep their 2026-10-24 and 2026-10-03 retrieval
  dates. Previous 2026-10-24.
- vendor-doc-url: <https://moonshotai.github.io/kimi-code/en/>
- snapshot-date: 2026-10-27
- Canonical docs host: `moonshotai.github.io/kimi-code/en/` (Kimi Code CLI,
  Moonshot). The earlier `moonshotai.github.io/kimi-cli` host documented the
  predecessor CLI and is no longer the authority for this adapter. The
  2026-10-24 refresh read the skills, agents, hooks and config-files pages at
  `www.kimi.com/code/docs/en/kimi-code-cli/` (see Vendor Sources); the refresh
  did not establish whether that host replaces the one above.
- canonical-filename: `AGENTS.md`
- canonical-schema: free-form Markdown agent instructions (the AGENTS.md
  convention); no frontmatter.
- Adapter source: `src/apothem/harnesses/kimi_code/`
- Evidence level: vendor-doc pinned (living docs; no-immutable-source
  exception). The vendor also publishes a changelog with versioned releases
  (latest `@moonshot-ai/kimi-code@2.3.3`, 2026-10-26) and an MIT-licensed
  repository, `MoonshotAI/kimi-code`, whose agent loader was read at commit
  `e2ad1dcf21` (2026-10-27) for the facts marked "source" below. No
  vendor-native UI claim is made here.

## Official Surface Refresh

- Re-pinned 2026-10-27 for the native agents surface. Read that day on the
  vendor's English pages (the agents page and the tools reference as raw
  Markdown) and, for the facts marked "source", in the agent loader of the open
  repository at commit `e2ad1dcf21`:
  - Agents, locations: project level `.kimi-code/agents/` and `.agents/agents/`
    (the project root is the nearest ancestor containing `.git`); user level
    `$KIMI_CODE_HOME/agents/` (default `~/.kimi-code/agents/`) and
    `~/.agents/agents/`, which stays under the real OS home; also the
    `extra_agent_dirs` array in `config.toml` and the `agents` field of an
    enabled plugin manifest. Each directory is scanned recursively for `.md`
    files; dot-prefixed entries and `node_modules` are skipped and the walk
    stops at depth 8 (source). Priority: explicit `--agent-file`, project,
    extra, user, plugin, built-in. Inside the project level `.kimi-code/agents/`
    is scanned before `.agents/agents/` and the first name wins, so the
    Kimi-specific folder beats the shared one on a name clash (source; the docs
    do not say). The docs name no `.claude` agents folder, so Kimi Code does not
    read Claude Code agents; its `/import-from-cc-codex` command imports
    instructions, skills and MCP settings, not agents.
  - Agents, file: Markdown with a frontmatter block, and the body is the system
    prompt. The loader reads seven keys: `name` (optional; kebab-case, matching
    `^[a-z0-9]+(?:-[a-z0-9]+)*$` or the file is skipped with a warning; the file
    name when absent), `description` (required, non-empty), `whenToUse`,
    `override`, `tools`, `disallowedTools` and `subagents`. Any other key is
    ignored. An empty body, or no frontmatter mapping, skips the file with a
    warning and leaves the other files alone (source).
  - Agents, tools: `tools` and `disallowedTools` take a YAML list or a
    comma-separated string. An omitted `tools`, or a lone `*`, allows every
    tool; `tools: []` allows none; `disallowedTools` applies after `tools`.
    Names match exactly and case-sensitively, `mcp__<server>__*` entries match
    MCP tools as globs, and a name no tool has only produces a warning. The
    tools reference lists: `Read`, `Write`, `Edit`, `Grep`, `Glob`,
    `ReadMediaFile`, `Bash`, `WebSearch`, `FetchURL`, `ExitPlanMode`,
    `TodoList`, `Agent`, `AgentSwarm`, `AskUserQuestion`, `NotifyUser`, `Skill`,
    `TaskList`, `TaskOutput`, `TaskStop`, `WaitFor`, `CronCreate`, `CronList`
    and `CronDelete`. There is no `WebFetch`, `TodoWrite`, `MultiEdit`,
    `NotebookEdit`, `PowerShell`, `Monitor`, `TaskCreate` or `TaskUpdate`.
  - Agents, model: there is no per-agent model key, and the page says Claude
    Code's `model` key is ignored. A sub-agent inherits the main agent's model or
    uses the global `[secondary_model]` in `config.toml`; with that pool
    configured the `Agent` tool gains a per-spawn `model` parameter that the main
    agent picks.
  - Agents, `override`: a directory-discovered file replaces a built-in agent of
    the same name (`agent`, `coder`, `explore`, `plan`) only when it sets
    `override: true`, and the page warns that a project file named `agent.md`
    with `override: true` replaces the default main agent's whole system prompt.
    Apothem never writes `override`.
  - Agents, body: the body is a `${var}` template. Unknown variables stay
    verbatim, a bare `$` is never special, and a known variable with no value in
    context renders as an empty string. No Apothem agent body holds `${`, and
    `tests/unit/test_kimi_devin_agents.py` pins that.
  - Agents, delegation: a custom agent's default list of agents it can dispatch
    is the built-ins (`coder`, `explore`, `plan`) unless its `subagents` key says
    otherwise, so Apothem's agents do not dispatch each other; the main agent's
    list includes every discovered custom agent. The page advises an agent meant
    for delegation to state in its body that its last message is the complete,
    self-contained result for the caller.
  - Changelog 2.3.2 (2026-10-25): the main agent now handles tasks directly by
    default instead of launching sub-agents on its own; delegation is requested
    in a message, in `AGENTS.md`, in a skill or by an enabled multi-agent mode.
    The agents page still says the main agent schedules sub-agents automatically.
  - Agents, reload: the project agent roots are watched and reloaded in a running
    session, with a 200 ms debounce (source; the docs state only that
    `config.toml`, `AGENTS.md`, skills and MCP configuration reload).
- Re-pinned 2026-10-24 for the native skills surface. Read that day on the
  vendor's English and Chinese pages (one vendor, one upstream):
  - Skills, project level: `.kimi-code/skills/` and `.agents/skills/`. The
    project root is the nearest directory containing `.git`, searching upward
    from the working directory, so `--project` must name the repository root
    for Kimi Code to find `<project>/.kimi-code/skills/`.
  - Skills, user level: `$KIMI_CODE_HOME/skills/` (default
    `~/.kimi-code/skills/`) and `~/.agents/skills/`. The Kimi-specific user
    directory moves with `KIMI_CODE_HOME`; `~/.agents/skills/` stays under the
    real OS home. A skill is a subdirectory of a skills directory whose main
    file is named `SKILL.md`.
  - Skills, priority (English page): the page scans four tiers and says "more
    specific scopes take higher priority": Project > User > Extra > Built-in.
    Extra directories come from `extra_skill_dirs` in `config.toml`. The page
    does not rank `.kimi-code/skills/` against `.agents/skills/` inside the
    project tier.
  - Skills, `SKILL.md` frontmatter (English page): `name` and `description`
    (both required in directory form; omitting either one makes parsing fail),
    `type` (`prompt` by default, `inline`, or `flow`; other values are
    skipped), `whenToUse` (also `when-to-use` and `when_to_use`),
    `disableModelInvocation` (also `disable-model-invocation` and
    `disable_model_invocation`), and `arguments`. The page states no rule for a
    key outside that list.
  - Agents, project level: `.kimi-code/agents/` and `.agents/agents/`; user
    level: `$KIMI_CODE_HOME/agents/` and `~/.agents/agents/`. Each directory is
    scanned recursively for `.md` files, and an agent file is "plain Markdown
    with a frontmatter block". Priority: explicit `--agent-file`, then project,
    extra, user, plugin, built-in.
  - Agents, frontmatter (English page): `name` (optional, kebab-case, defaults
    to the file name), `description` (required), `whenToUse`, `override`,
    `tools`, `disallowedTools` and `subagents`. `tools` and `disallowedTools`
    take a YAML list or a comma-separated string; built-in and user tool names
    match exactly and case-sensitively, MCP tools match as `mcp__<server>__*`
    globs, and a name no tool has is reported with a warning. Unknown fields
    are ignored, including those of other agent tools such as Claude Code's
    `model`, and the comma-separated `tools` form keeps Claude Code-style agent
    files loadable.
  - Hooks: all rules are `[[hooks]]` entries in `~/.kimi-code/config.toml`
    (`$KIMI_CODE_HOME/config.toml` when that variable is set). An entry takes
    exactly four fields: `event` (required), `matcher` (optional regular
    expression), `command` (required), `timeout` (optional, seconds, 1 to 600,
    default 30). An extra field makes the config file fail to load.
  - Facts below that this refresh did not re-read keep their 2026-10-03
    retrieval date under Vendor Sources.
- Re-pinned 2026-10-03 to the Kimi Code docs at
  `moonshotai.github.io/kimi-code/en/`. This resolves the earlier open question
  about the `.kimi-code/` paths: the current docs place every Kimi Code surface
  under `.kimi-code/` (project) and `~/.kimi-code/` (user, relocatable with
  `KIMI_CODE_HOME`).
- Instructions: project instructions live in `AGENTS.md` or
  `.kimi-code/AGENTS.md` under the project tree; Kimi-specific global
  instructions live in `~/.kimi-code/AGENTS.md`, and cross-tool global
  instructions in `~/.agents/AGENTS.md`. The docs do not say which of the two
  project files wins when both exist, so the adapter keeps writing the
  project-root `AGENTS.md` managed block (operator prose outside the sentinels
  is preserved).
- Configuration: `~/.kimi-code/config.toml` (runtime settings) and
  `~/.kimi-code/tui.toml` (terminal UI). Operator-owned; the adapter writes
  neither.
- MCP: `mcp.json` at two levels, `~/.kimi-code/mcp.json` (user) and
  `.kimi-code/mcp.json` (project, overrides same-named user entries; stdio
  entries prompt through workspace trust). Operator-owned; the adapter names
  the project file and authors no entries.
- Skills: `~/.kimi-code/skills/`, `~/.agents/skills/`, `.kimi-code/skills/`,
  and `.agents/skills/` (`SKILL.md` folders). The adapter writes Apothem's
  skills, and its commands wrapped as skills, to `<project>/.kimi-code/skills/`
  (native). It never writes `.agents/skills/`: that folder is shared with other
  tools, so a write there would reach them too. Operator-authored skills with
  other names beside Apothem's in `.kimi-code/skills/` are kept on install,
  update and uninstall. A skill whose name matches an Apothem skill is
  replaced: install and update overwrite its directory (a file of the operator
  skill that Apothem's skill lacks is gone) and uninstall removes it, each after
  a timestamped copy under `~/.apothem/backups/`. The install prints no
  collision notice, and `tests/unit/test_kimi_code_native_skills.py` pins this
  behavior.
- Agents: `~/.kimi-code/agents/`, `.kimi-code/agents/`, `~/.agents/agents/` and
  `.agents/agents/`. The adapter writes one `<name>.md` per Apothem agent (all
  fourteen) into `<project>/.kimi-code/agents/`, with `name`, `description` and,
  where the source restricts tools, `tools` and `disallowedTools` as YAML lists
  of Kimi tool names. `WebFetch` becomes `FetchURL` and `TodoWrite` becomes
  `TodoList`; a name Kimi Code has no tool for (`MultiEdit`, `NotebookEdit`,
  `PowerShell`, `Monitor`, `Artifact`, `TaskCreate`, `TaskUpdate`, an `mcp__`
  entry) is left out, and a grant that loses every name is written as
  `tools: []` because an omitted `tools` would allow every tool. A source tool
  pattern such as `Bash(git status)` has no Kimi form: in a grant it is left out
  and in a denial it denies the whole tool. The adapter never writes `model`
  (Kimi Code has no such key), `override`, `subagents` or `whenToUse`, nor
  Apothem's `maxTurns`, `version`, `updated` and `portability`. It never writes
  `.agents/agents/` (shared with Devin, whose tool names are lowercase, so one
  file could not serve both readers), `~/.kimi-code/agents/` or
  `~/.agents/agents/`. A same-named file you wrote in `.kimi-code/agents/` is
  backed up before it is replaced. A project-level file there ranks above a
  same-name definition at the extra, user and plugin levels, so an Apothem agent
  would shadow a user-level definition of the same name; the names are the
  agents' own (`test-runner`, `quality-gate` and so on). The agent bodies copy
  the source text, so the three web agents still name `WebFetch` in prose where
  Kimi Code's tool is `FetchURL`.
- Hooks: `[[hooks]]` in the user-scope `~/.kimi-code/config.toml`. The adapter
  writes no hooks (see Open Questions). Apothem's hook helpers land in the
  support tree.
- Tool permissions: `default_permission_mode` (`manual`, `yolo`, `auto`) and
  `[[permission.rules]]` entries in `config.toml`. Apothem does not yet project
  its universal-deny floor into them (see Discovery Targets).
- Support tree: the cohorts Apothem does not install natively (rules,
  templates, hooks) land under the Apothem-owned
  `<project>/.kimi-code/.apothem/support/` subtree and are referenced from the
  `AGENTS.md` anchor. They are never written into `.agents/` or other
  vendor-read directories.
- Migration: an install from before 2026-10-24 held skills at
  `<project>/.kimi-code/.apothem/support/skills/`, and every release from v1.0.1
  to v1.4.0 held the agents at `<project>/.kimi-code/.apothem/support/agents/`.
  Both paths are in the manifest's `stale-sweep` list: an update removes them
  (after a backup) and writes the native directories, and an uninstall removes
  them too, so each skill and each agent is present once and no orphan copy of
  the agents stays in the support tree.
- Web fetch (`web_fetch` = **yes**): Kimi Code ships built-in `FetchURL`
  (returns a page's body text) and `WebSearch` tools, both auto-allowed, backed
  by the `moonshot_fetch` and `moonshot_search` services in `config.toml`.
- Model family: vendor-pinned and selected through the operator's own Kimi Code
  configuration; the adapter authors no model id.

## Vendor Sources

Retrieved 2026-10-27.

- <https://moonshotai.github.io/kimi-code/en/customization/agents.md> (agent
  locations, file format, keys, tool matching, `override`, delegation, priority)
- <https://moonshotai.github.io/kimi-code/en/reference/tools.md> (the built-in
  tool names, including `FetchURL` and `TodoList`)
- <https://moonshotai.github.io/kimi-code/en/configuration/config-files.md>
  (`extra_agent_dirs`, `[secondary_model]`, the `[watch]` switch)
- <https://moonshotai.github.io/kimi-code/en/release-notes/changelog.md>
  (release 2.3.3 and the 2.3.2 delegation default)
- The agent loader in the `MoonshotAI/kimi-code` repository at commit
  `e2ad1dcf21` (`agentFile.ts`, `agentFileDiscovery.ts`, `agentRoots.ts`), read
  for the name pattern, the empty-body rule, the scan depth and the first-name-
  wins order. These are implementation facts, not documented guarantees.

Retrieved 2026-10-24.

- <https://www.kimi.com/code/docs/en/kimi-code-cli/customization/skills.html>
  (skill directories, project and user level, `KIMI_CODE_HOME`)
- <https://www.kimi.com/code/docs/kimi-code-cli/customization/skills.html>
  (the same page, Chinese edition)
- <https://www.kimi.com/code/docs/en/kimi-code-cli/customization/agents.html>
  (agent file locations and format, priority order)
- <https://www.kimi.com/code/docs/kimi-code-cli/customization/agents>
  (the same page, Chinese edition)
- <https://www.kimi.com/code/docs/en/kimi-code-cli/customization/hooks.html>
  (`[[hooks]]` location and four-field schema)
- <https://www.kimi.com/code/docs/kimi-code-cli/customization/hooks.html>
  (the same page, Chinese edition)
- <https://www.kimi.com/code/docs/en/kimi-code-cli/configuration/config-files>
  (`config.toml` location, `hooks` as an `array<table>`)

Retrieved 2026-10-03.

- <https://moonshotai.github.io/kimi-code/en/> (docs home)
- <https://moonshotai.github.io/kimi-code/en/customization/agents> (instruction
  files, agent files, `SYSTEM.md`)
- <https://moonshotai.github.io/kimi-code/en/configuration/config-files>
  (`config.toml`, permissions, services)
- <https://moonshotai.github.io/kimi-code/en/customization/mcp> (`mcp.json`)
- <https://moonshotai.github.io/kimi-code/en/customization/skills> (skill
  directories)
- <https://moonshotai.github.io/kimi-code/en/reference/tools> (`FetchURL`,
  `WebSearch`)

## Open Questions

Each item below is a decision the vendor docs read on 2026-10-24 did not settle.
No Apothem behavior was changed on the strength of a guess; the item names what
stays as it is.

- TODO(clarify): how Kimi Code treats a `SKILL.md` frontmatter key outside the
  list the skills page documents (`name`, `description`, `type`, `whenToUse`,
  `disableModelInvocation`, `arguments`). The page states no rule for an unknown
  key. Apothem ships the source frontmatter unchanged, with no Kimi-specific
  translation. Every shipped skill and command-as-skill carries `name`,
  `description` (both required in directory form) and `disable-model-invocation`
  (a spelling the page accepts), so those three are read. The keys outside the
  documented list are `version`, `updated`, `archetype`, `userInvocable`,
  `argument-hint`, `portability` and `allowed-tools`; until the vendor states a
  rule for them, a key Kimi Code rejects would surface when it loads that skill,
  and a key it ignores changes behavior (a tool restriction that
  `allowed-tools` declares would not apply).
- TODO(clarify): whether the main agent delegates to Apothem's agents on its own.
  The agents page says the main agent schedules sub-agents automatically, while
  changelog 2.3.2 (2026-10-25) says tasks are handled directly by default and
  delegation must be requested. The `AGENTS.md` block tells the reader to ask for
  a helper by name; revisit when the page and the changelog agree.
- TODO(clarify): whether the `[watch]` switch also governs the reload of project
  agent files. The reload is source-derived (a 200 ms debounce at commit
  `e2ad1dcf21`); the docs state it only for `config.toml`, `AGENTS.md`, skills
  and MCP configuration.
- TODO(clarify): hooks. Apothem writes no `[[hooks]]` entry. Three facts decide
  it. (1) The repository has no TOML read-merge-write with a surgical
  uninstall: the shared ownership merge reads and rewrites JSON and YAML, the
  plain-file uninstall deletes a file only when it equals the rendered
  template, the engine supports Python 3.10 where `tomllib` is absent, and no
  TOML writer is vendored. (2) `~/.kimi-code/config.toml` is user scope and
  moves with `KIMI_CODE_HOME`, while this adapter writes under `--project` and
  the install driver refuses a target outside the project root. (3) An entry
  allows exactly four fields and an extra one stops the config from loading, so
  there is no field to mark an entry as Apothem's; removal would have to match
  on the `command` text. Decide whether Apothem takes on a user-scope TOML
  surface before any hook is written.
- TODO(clarify): how Kimi Code ranks `<project>/.kimi-code/skills/` against
  `<project>/.agents/skills/` when both hold a skill of the same name. The
  skills page ranks the tiers (Project > User > Extra > Built-in), so the
  project-level copy this adapter writes takes precedence over a user-level copy
  of the same name, such as the `~/.agents/skills/` copy the Codex adapter
  writes. The page does not rank the two project folders against each other.

## Discovery Targets

- Discovery target: mcp_servers by 2026-12-31 — decide whether Apothem renders
  the profile's MCP inventory into `.kimi-code/mcp.json` or keeps naming it as
  operator-owned.
- Discovery target: tool_surface_restrictions by 2026-12-31 — decide how the
  universal-deny floor maps onto `[[permission.rules]]` in `config.toml`.

## Verification

Adapter output MUST produce an `AGENTS.md` managed block that Kimi Code reads as
project instructions, MUST write each skill and each command-as-skill to
`<project>/.kimi-code/skills/<name>/SKILL.md`, and MUST write each agent to
`<project>/.kimi-code/agents/<name>.md`; deviations are findings per
`rules/harness-adapter-shape.md` §4 Standard-Conformance.

## MCP Surface Projection

- Status: `.kimi-code/mcp.json` (project) and `~/.kimi-code/mcp.json` (user) are
  the documented MCP surfaces. Apothem names the project file in
  `capabilities.yml` and authors no entries.
- Boundary: the registry capability cell stays `discovery-pending` until the
  target above is resolved.

## Tool-Surface Restriction Projection

- Status: `discovery-pending`. The vendor surface is now identified
  (`default_permission_mode` and `[[permission.rules]]` in `config.toml`); the
  projection of the universal-deny floor (secrets paths, destructive shell ops,
  network-write to unsigned endpoints) into it is not yet built. The floor binds
  regardless per `rules/agent-capability-discipline.md` §5 and is named in
  `capabilities.yml` under `tool_surface_restrictions`.

## Recommended Postfix Rendering

- Status: supported as plain text.
- Mechanism: Apothem emits the literal ` (Recommended)` suffix in the option
  label. Kimi Code-facing prompts and fallback text preserve that suffix as
  authored.
- Boundary: this pin does not claim a harness-native recommended-option widget.
  It only pins the text-rendered convention used by
  `rules/interactive-questions.md`.

## Long Context and Compaction

- Status: profile-managed.
- Mechanism: Apothem keeps full-suite `/plan-execute` runs continuous by
  externalizing state to `.apothem/plans/`, compacting or restarting the harness session
  at phase boundaries as needed, and restoring via the Blind Bootstrap sequence.
- Boundary: this pin does not claim vendor-native autocompaction or a
  long-context size. It pins the adapter-local state handoff and
  compaction-restoration convention used by `rules/context-management.md`.

## Large-Codebase Practice Projection

- Layered context: declared in `capabilities.yml` under
  `layered_context_surface` — `AGENTS.md` plus the native skills and agents and
  the support tree; no vendor-native hierarchy is claimed beyond the adapter's
  documented file/template surface.
- LSP symbol navigation: `tracked-gap` until a vendor-ratified plugin or tool
  surface is pinned.
- Hook learning capture: routed through the `persistent-conventions-vigilance`
  artifact-evolution cycle; pass-class hooks stay silent and recurring findings
  become rule, skill, hook, or documentation updates.

## Refresh cadence

Re-verify against vendor reality every 90 days. On refresh, update the snapshot
date, the retrieval date under Vendor Sources, and any moved URL in the same
change-set, and emit a `[Pin — refreshed: kimi_code; …]` ledger entry per
`rules/disclosure-ledger.md`. A pin older than 90 days, or a discovery target
past its date, fails `scripts/dev/validate_harness_convention_pins.py`.

## Plugin-alone Persistence

Kimi Code documents a plugin mechanism (`/plugins install`, per user, with
manifest fields for agents and hooks), but **Apothem ships no Kimi Code plugin**.
The adapter is project-scope: it writes the `AGENTS.md` managed block plus
native skills under `<project>/.kimi-code/skills/`, native agents under
`<project>/.kimi-code/agents/` and an Apothem support tree under
`<project>/.kimi-code/.apothem/support/`. There is no
standalone-installable bundle; every artifact requires the full
`apothem install --harness kimi-code --project <path>` engine run.

| Artifact class | Persists standalone? | Mechanism / limit |
|---|---|---|
| Context anchor (rules-as-text) | No — requires `apothem install` | `AGENTS.md` is written by the engine; nothing persists before that run. |
| Skills / Commands (as skills) | No — requires `apothem install` | Written by the engine to the native `<project>/.kimi-code/skills/`. |
| Agents | No — requires `apothem install` | Written by the engine to the native `<project>/.kimi-code/agents/`. |
| Rules / Templates / Hooks | No — deliberate posture | The support tree under the Apothem-owned subtree is engine-materialized as reference material. Kimi Code documents `[[hooks]]` in `~/.kimi-code/config.toml`; the adapter authors none, for the reasons under Open Questions, not an absence-of-surface claim. |
| MCP servers | No — operator-owned | `.kimi-code/mcp.json` is operator-owned; the adapter authors no entries. |

## Bindings

- Established by ↑ `rules/harness-adapter-shape.md` §6.
- Cross-bound with ↔ `src/apothem/harnesses/kimi_code/__init__.py` (the adapter
  whose discovery walk this pin anchors).
