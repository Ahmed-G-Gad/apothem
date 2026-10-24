<!-- SPDX-License-Identifier: MIT -->

# Hermes Standard Convention Pin

## Snapshot

- Snapshot date: 2026-10-24
- Snapshot note: skills and context files re-checked against the live Hermes docs on 2026-10-24; the rest was refreshed against the Hermes docs at commit `1c56fed0480e67ffd56675d10862e607fb61a55b` of `github.com/NousResearch/hermes-agent` (configuration, MCP, skills, hooks, context files, slash commands). Corrections: MCP servers live in the top-level `mcp_servers` map of `~/.hermes/config.yaml`, not an `auxiliary.mcp` block; `skills.external_dirs` is a documented key for extra skill directories, which the adapter now points at its support skills directory; and `skills.config` stores per-skill settings rather than a package list. Previous 2026-10-03 at that commit.
- Adapter source: `src/apothem/harnesses/hermes/`
- Evidence level: vendor-repo pinned at commit
  `1c56fed0480e67ffd56675d10862e607fb61a55b`. Hermes is a multi-platform
  messaging gateway. No vendor-native UI claim is made here.
  - Config: `~/.hermes/config.yaml`.
  - MCP: the top-level `mcp_servers` map. Each entry is a stdio server
    (`command`, `args`, `env`) or a remote server (`url`, with optional
    `auth: oauth`); `hermes import-agent claude-code` maps Claude Code's
    `mcpServers` onto it.
  - Skills: `~/.hermes/skills/` is the primary directory. The documented
    precedence is project skills, then local (`~/.hermes/skills/`), then
    `skills.create_dir`, then `skills.external_dirs` (opt-in extra
    directories under the `skills` section of `config.yaml`; the vendor example
    lists `~/.agents/skills`, an absolute path and `${SKILLS_REPO}/skills`).
    Project skills load from `<project-root>/.hermes/skills/` and
    `<project-root>/.agents/skills/`, and Hermes does not auto-load them from
    arbitrary cloned repos. `~/.agents/skills` is not a default location; it is
    only the vendor's example of an `external_dirs` entry. Every installed skill
    is available as a slash command, and per-skill settings live under
    `skills.config`.
  - Adapter skill wiring: the adapter appends `~/.hermes/.apothem/support/skills`
    to `skills.external_dirs` and owns only that entry. The operator's own
    `external_dirs` entries stay first and survive an uninstall, and the adapter
    writes into none of the earlier locations in the precedence order, so
    install, update and uninstall never replace a skill the operator keeps in
    any of them. `apothem verify` requires the entry.
  - Context files: Hermes loads one project context type per session, first
    match wins, in the order `.hermes.md`, `AGENTS.override.md`, `AGENTS.md`,
    `CLAUDE.md`, `.cursorrules`. The adapter writes none of them.
  - TODO(clarify): the Hermes context-files page contradicts itself on
    `AGENTS.override.md`: its "Priority system" section lists it in the chain,
    while its "At startup" scan step omits it.
  - TODO(clarify): the skills page states the precedence order, but the
    2026-10-24 check quotes no sentence saying which copy Hermes loads when two
    sources hold a skill of the same name; the adapter reads the order as
    "earlier wins".
  - TODO(clarify): the 2026-10-24 check does not name the `SKILL.md`
    frontmatter keys Hermes reads, so `capabilities.yml` `conversion_losses`
    keeps every key as `ignored`.
  - Sub-agent dispatch: the `delegation` block, bounded by
    `max_concurrent_children` and `max_spawn_depth`.
  - Commands: `quick_commands` plus skill slash commands.
  - Memory: `~/.hermes/memories/` (`MEMORY.md`, `USER.md`).
  - Hooks and plugins: `~/.hermes/hooks/<name>/` and `~/.hermes/plugins/<name>/`.

## Vendor Sources

Retrieved 2026-10-24 from the live docs site (versionless, no commit SHA — no-immutable-source exception).

- <https://hermes-agent.nousresearch.com/docs/user-guide/features/skills> (skill directories, the precedence order and `skills.external_dirs`)
- <https://hermes-agent.nousresearch.com/docs/user-guide/features/context-files> (project context-file priority)

Retrieved 2026-10-03 unless marked, at commit `1c56fed0480e67ffd56675d10862e607fb61a55b`.

- <https://raw.githubusercontent.com/NousResearch/hermes-agent/1c56fed0480e67ffd56675d10862e607fb61a55b/website/docs/user-guide/configuration.md> (`config.yaml`, `delegation`, `quick_commands`)
- <https://raw.githubusercontent.com/NousResearch/hermes-agent/1c56fed0480e67ffd56675d10862e607fb61a55b/website/docs/user-guide/features/mcp.md> (`mcp_servers`)
- <https://raw.githubusercontent.com/NousResearch/hermes-agent/1c56fed0480e67ffd56675d10862e607fb61a55b/website/docs/reference/slash-commands.md> (slash commands)
- <https://raw.githubusercontent.com/NousResearch/hermes-agent/1c56fed0480e67ffd56675d10862e607fb61a55b/website/docs/user-guide/features/skills.md> (skill directories, `skills.config`; retrieved 2026-10-02)
- <https://raw.githubusercontent.com/NousResearch/hermes-agent/1c56fed0480e67ffd56675d10862e607fb61a55b/website/docs/user-guide/features/hooks.md> (hooks and plugins; retrieved 2026-10-02)

## Discovery Targets

- None. No capability cell for this harness is discovery-pending.

## MCP correction (2026-10-02)

- Hermes reads MCP servers from the top-level `mcp_servers` map in
  `~/.hermes/config.yaml` (`mcp_servers: <name>: command / args / env` for a
  local server, `url` / `headers` for a remote one), per
  <https://raw.githubusercontent.com/NousResearch/hermes-agent/main/website/docs/user-guide/features/mcp.md>
  (the "Add an MCP server" example).
- `auxiliary.mcp` is a different setting: the auxiliary model slot Hermes uses
  for MCP tool dispatch (`provider` / `model` / `base_url` / `api_key` /
  `timeout`), per
  <https://raw.githubusercontent.com/NousResearch/hermes-agent/main/website/docs/user-guide/configuration.md>
  and the same file at the pinned commit
  <https://raw.githubusercontent.com/NousResearch/hermes-agent/355af2c20f495b97c22c9aeb4c227fb0ca010da7/website/docs/user-guide/configuration.md>.
  The earlier pin read that block as the MCP server list.
- The adapter therefore renders the profile's servers under `mcp_servers`. An
  update over an install from an earlier release removes the server map that
  release wrote under `auxiliary.mcp` (only while it still holds exactly that
  value), and so does an uninstall over such an install with no update since.
  Uninstall otherwise removes only the server entries the install ledger
  records as Apothem's, so the operator's own `auxiliary` routing and
  `mcp_servers` entries survive.

## Recommended Postfix Rendering

- Status: supported as plain text.
- Mechanism: Apothem emits the literal ` (Recommended)` suffix in the option label. Hermes adapter output preserves that suffix when prompt text is materialized.
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

Hermes is a multi-platform messaging gateway with **no vendor plugin or
extension install surface** that Apothem ships. The adapter materializes
`~/.hermes/config.yaml` (MCP under the top-level `mcp_servers` map, the skills
directory under `skills.external_dirs`) via its materializer and keeps non-native cohorts under the Apothem support subtree
(`~/.hermes/.apothem/support/`). There is no standalone-installable bundle; every artifact
requires the full `apothem install --harness hermes` engine run.

| Artifact class | Persists standalone? | Mechanism / limit |
|---|---|---|
| Config / MCP | No — requires `apothem install` | `~/.hermes/config.yaml` is materializer-rendered by the engine; nothing persists before that run. |
| Commands / Skills / Agents / Rules | No — requires `apothem install` | These land under `~/.hermes/.apothem/support/` (support subtree) via the engine; the support skills directory is listed under `skills.external_dirs`, while Hermes's own skill directories and `skills.config` settings are operator-owned and the adapter authors neither. |
| Hooks / Settings | No — adapter scope | Hermes documents hooks (`~/.hermes/hooks/`) and plugins (`~/.hermes/plugins/`); Apothem authors neither beyond the config materializer. |

Apothem ships no Hermes plugin, so the engine install is the sole persistence
path.
