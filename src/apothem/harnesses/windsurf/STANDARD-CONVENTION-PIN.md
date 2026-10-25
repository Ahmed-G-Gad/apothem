<!-- SPDX-License-Identifier: MIT -->

# Windsurf Standard Convention Pin

## Snapshot

- Snapshot date: 2026-10-24
- Snapshot note: the adapter now installs skills and command skills at the shared `~/.agents/skills/` and the rules and templates corpus at `~/.config/apothem/`.
- Adapter source: `src/apothem/harnesses/windsurf/`
- Evidence level: vendor-doc pinned (living docs at `docs.devin.ai`; no-immutable-source exception). No vendor-native UI claim is made here.

## Official Surface Refresh

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
  `~/.claude/skills/` when its Claude Code config import is on (the default is
  not stated).
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
- The adapter delivers the project rules file and the shared skills folder
  above. It authors no workflow, hook, or subagent.
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
`~/.agents/skills/`, and the rules and templates corpus at `~/.config/apothem/`,
and authors no other cohort. There is no standalone-installable bundle; every artifact requires the
full `apothem install --harness windsurf --project <path>` engine run.

| Artifact class | Persists standalone? | Mechanism / limit |
|---|---|---|
| Rules | No — requires `apothem install` | The merged `apothem-rules.md` (carrying the embedded behavioral mandates) is written only by the engine into the preferred `.devin/rules/` directory (`.windsurf/rules/` backward-compat fallback). Nothing persists before that run. |
| Skills and commands | No — requires `apothem install` | The engine writes them as skills to the user-level `~/.agents/skills/`, one copy shared by every project and every tool that reads that folder. Nothing persists before that run. |
| Agents | No — adapter scope | The vendor documents workflows (`.windsurf/workflows/`) and subagents; the adapter authors neither. |
| Hooks / MCP / Settings | No — operator-owned | `~/.config/devin/mcp_config.json` (MCP) and `hooks.json` (hooks) are operator-owned; the adapter authors no entries. |

The Devin CLI documents plugins and team marketplaces, but Apothem ships no
Devin plugin, so a
plugin-alone story does not exist — the files `apothem install` writes are the
sole persistence surface.
