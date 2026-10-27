<!-- SPDX-License-Identifier: MIT -->

# Windsurf Standard Convention Pin

## Snapshot

- Snapshot date: 2026-10-27
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
- Hooks (resolved): `hooks.json` at `.devin/hooks.json` in the workspace (the
  legacy `.windsurf/hooks.json` is used only when the `.devin` file is absent or
  defines no hooks), `~/.codeium/windsurf/hooks.json` for the user, and
  OS-level system paths; all levels merge. The earlier "unverified" flag is
  cleared.
- MCP (corrected): Cascade reads `~/.config/devin/mcp_config.json`
  (`%APPDATA%\devin\mcp_config.json` on Windows), and the Devin Local agent
  uses the Devin CLI config files. The earlier
  `~/.codeium/windsurf/mcp_config.json` path is no longer in the docs.
  Operator-owned; the adapter authors no entries.
- Memories: auto-generated memories apply to the legacy Cascade agent only and
  stay on the machine; the Devin Local agent does not persist memories.
- The adapter delivers the project rules file, the shared skills folder above
  and, for the Devin Local agent, eleven of Apothem's agents as subagents in
  `<project>/.devin/agents/`. It authors no workflow or hook.
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

## Vendor Sources

Retrieved 2026-10-03 unless marked.

- <https://docs.devin.ai/desktop/cascade/memories> (memories and rules)
- <https://docs.devin.ai/desktop/cascade/agents-md> (`AGENTS.md`)
- <https://docs.devin.ai/desktop/cascade/mcp> (`mcp_config.json`)
- <https://docs.devin.ai/desktop/cascade/web-search> (web search)
- <https://docs.devin.ai/cli/extensibility/rules.md> (Devin CLI rules)
- <https://docs.devin.ai/cli/reference/configuration/read-config-from.md> (Devin CLI config imports)
- <https://docs.devin.ai/desktop/cascade/skills.md> (skills; retrieved 2026-10-24, the folder the adapter writes)
- <https://docs.devin.ai/desktop/cascade/hooks.md> (hooks; retrieved 2026-10-02)

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
`~/.agents/skills/`, the rules and templates corpus at `~/.config/apothem/`, and
eleven agents as Devin Local subagents at `<project>/.devin/agents/`, and authors
no other cohort. There is no standalone-installable bundle; every artifact
requires the full `apothem install --harness windsurf --project <path>` engine run.

| Artifact class | Persists standalone? | Mechanism / limit |
|---|---|---|
| Rules | No — requires `apothem install` | The merged `apothem-rules.md` (carrying the embedded behavioral mandates) is written only by the engine into the preferred `.devin/rules/` directory (`.windsurf/rules/` backward-compat fallback). Nothing persists before that run. |
| Skills and commands | No — requires `apothem install` | The engine writes them as skills to the user-level `~/.agents/skills/`, one copy shared by every project and every tool that reads that folder. Nothing persists before that run. |
| Agents | No — requires `apothem install` | The engine writes eleven of the fourteen as Devin Local subagents to the project's `.devin/agents/`. Nothing persists before that run. |
| Workflows | No — adapter scope | The vendor documents workflows (`.windsurf/workflows/`), which reach the legacy Cascade agent only; the adapter authors none. |
| Hooks / MCP / Settings | No — operator-owned | `~/.config/devin/mcp_config.json` (MCP) and `hooks.json` (hooks) are operator-owned; the adapter authors no entries. |

The Devin CLI documents plugins and team marketplaces, but Apothem ships no
Devin plugin, so a
plugin-alone story does not exist — the files `apothem install` writes are the
sole persistence surface.
