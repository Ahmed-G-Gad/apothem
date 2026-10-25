<!-- SPDX-License-Identifier: MIT -->

# Zed Standard Convention Pin

## Snapshot

- Snapshot date: 2026-10-24
- Snapshot note: the adapter now installs skills and command skills at the shared `~/.agents/skills/` and the rules and templates corpus at `~/.config/apothem/`.
- Adapter source: `src/apothem/harnesses/zed/`
- Evidence level: vendor-doc pinned (living docs; no-immutable-source exception). No vendor-native UI claim is made here.
- canonical-filename: `.rules`
- vendor-doc-url: <https://zed.dev/docs/ai/instructions>

## Official Surface Refresh

- Refreshed 2026-10-03 against `zed.dev/docs` (instructions, skills, MCP).
- Surface: Zed reads one project instruction file, the first match in the
  list `.rules`, `.cursorrules`, `.windsurfrules`, `.clinerules`,
  `.github/copilot-instructions.md`, `AGENT.md`, `AGENTS.md`, `CLAUDE.md`,
  `GEMINI.md`, so `.rules` hides every later file. Zed names `AGENTS.md` its
  primary instruction file and supports `.rules` for compatibility. The format
  is free-form plaintext / Markdown with no schema. The global surface is
  `~/.config/zed/AGENTS.md`.
- DIVERGENCE (flat file, no dedicated apothem file): unlike the cohort's
  rules-directory shape, Zed reads one flat `.rules` file at the project root,
  so the adapter writes `<project>/.rules` directly. Install warns when the new
  `.rules` hides an instruction file that holds operator text.
- DIVERGENCE (backup-on-replace): because `.rules` is a single shared file an
  operator may already maintain, the shared install driver backs up any
  pre-existing `.rules` to a timestamped copy under `~/.apothem/backups/`
  before replacement. The operator's prior instruction file is never silently
  lost.
- MCP: Zed's context servers are configured under `context_servers` in
  `.zed/settings.json` and the global settings. Operator-owned; the adapter
  names the surface and authors no entries.
- Skills: Zed loads skills only from `~/.agents/skills/` (global) and
  `<worktree>/.agents/skills/` (project), flat layout, with no custom search
  paths. The Zed adapter writes Apothem's skills, plus its commands wrapped as
  skills, to `~/.agents/skills/`, the one user-level copy shared with Codex,
  Cursor, GitHub Copilot, and Windsurf. Only project-local skills are gated on a
  trusted worktree; the docs tie no such gate to the global folder. One reading
  reported a size cap on the skill catalog that this pin did not confirm.
  TODO(clarify): the vendor docs do not say how Zed treats a `SKILL.md`
  frontmatter key it does not list, and whether a skill that disables model
  invocation counts toward the catalog cap mentioned above. The shared
  emission sets `user-invocable`, `disable-model-invocation`, `allowed-tools`,
  `argument-hint`, and a `metadata` map; probe Zed with the full set before a
  release and, if it rejects extras, change `SHARED_TOPLEVEL_KEYS` in
  `install_driver_shared.py`.
- The vendor documents threads, agent profiles, and external agents as
  separate surfaces; the adapter authors none of them.

## Vendor Sources

Retrieved 2026-10-03 unless marked.

- <https://zed.dev/docs/ai/instructions> (instruction files and priority)
- <https://zed.dev/docs/ai/mcp> (`context_servers`)
- <https://zed.dev/docs/ai/skills> (skill locations; retrieved 2026-10-24, the folder the adapter writes)

## Discovery Targets

- Discovery target: mcp_servers by 2026-12-31 — decide whether Apothem renders the profile's MCP inventory into `.zed/settings.json` `context_servers` or keeps naming it as operator-owned.

## Recommended Postfix Rendering

- Status: supported as plain text.
- Mechanism: Apothem emits the literal ` (Recommended)` suffix in the option label. Zed instruction files preserve that suffix as authored.
- Boundary: this pin does not claim a harness-native recommended-option widget. It only pins the text-rendered convention used by `rules/interactive-questions.md`.

## Long Context and Compaction

- Status: profile-managed.
- Mechanism: Apothem keeps full-suite `/plan-execute` runs continuous by externalizing state to `.apothem/plans/`, compacting or restarting the harness session at phase boundaries as needed, and restoring via the Blind Bootstrap sequence.
- Boundary: this pin does not claim vendor-native autocompaction or a long-context size. It pins the adapter-local state handoff and compaction-restoration convention used by `rules/context-management.md`.

## Large-Codebase Practice Projection

- Layered context: declared in `capabilities.yml` under `layered_context_surface`; Zed reads a single flat `.rules` file, so no vendor-native rule hierarchy is claimed beyond that file and template surface.
- LSP symbol navigation: `tracked-gap` until a vendor-ratified plugin or tool surface is pinned.
- Hook learning capture: routed through the `persistent-conventions-vigilance` artifact-evolution cycle; pass-class hooks stay silent and recurring findings become rule, skill, hook, or documentation updates.

## Plugin-alone Persistence

Zed exposes **no vendor plugin or extension install surface** that Apothem ships
for its instruction surface. The adapter writes a flat merged file at
`<project>/.rules` (backing up any pre-existing `.rules` first), the skills at
`~/.agents/skills/`, and the rules and templates corpus at `~/.config/apothem/`,
and authors no other cohort. There is no standalone-installable
bundle; every artifact requires the full
`apothem install --harness zed --project <path>` engine run.

| Artifact class | Persists standalone? | Mechanism / limit |
|---|---|---|
| Rules (flat `.rules`) | No — requires `apothem install` | The merged `.rules` file (carrying the embedded behavioral mandates) is written only by the engine to the project root. Nothing persists before that run. |
| Agents | No — adapter scope | Zed documents threads, agent profiles, and external agents; the adapter authors none of them. |
| Skills and commands | No — requires `apothem install` | Zed loads skills from `~/.agents/skills/` and `.agents/skills/`; the engine writes Apothem's skills and wrapped commands to `~/.agents/skills/`, one copy shared with every other tool that reads it. Nothing persists before that run. |
| Hooks / MCP / Settings | No — operator-owned | `context_servers` in `.zed/settings.json` (MCP) is operator-owned; the adapter authors no entries. |

Apothem ships no Zed extension, so the files `apothem install` writes are the
sole persistence surface.
