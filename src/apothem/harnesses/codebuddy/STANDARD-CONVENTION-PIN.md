<!-- SPDX-License-Identifier: MIT -->

# CodeBuddy Standard Convention Pin

## Snapshot

- Snapshot date: 2026-10-24
- Snapshot note (skills): the adapter now installs skills and command skills at CodeBuddy's own `~/.codebuddy/skills/` and the rules and templates corpus at `~/.config/apothem/`. The CodeBuddy skills page was read on 2026-10-24.
- Snapshot note: refreshed against `www.codebuddy.ai/docs`. Correction: MCP servers live in `.mcp.json` at the project root and `~/.codebuddy/.mcp.json`, not in `.codebuddy/settings.json` as the earlier pin said. CodeBuddy Code also reads `AGENTS.md` as project memory when no `CODEBUDDY.md` exists. Previous 2026-06-25.
- Adapter source: `src/apothem/harnesses/codebuddy/`
- Evidence level: vendor-doc pinned (living docs; no-immutable-source exception). The IDE Rules page was re-read on 2026-10-03; the CLI memory, MCP, and hooks pages were read on 2026-10-02. No vendor-native UI claim is made here.

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
- The vendor also documents sub-agents, slash commands, hooks, and plugins. The
  adapter authors none of them.

## Vendor Sources

Retrieved 2026-10-03 unless marked.

- <https://www.codebuddy.ai/docs/ide/Rules> (project rules)
- <https://www.codebuddy.ai/docs/cli/memory> (memory files, rules frontmatter, `AGENTS.md` fallback; retrieved 2026-10-02)
- <https://www.codebuddy.ai/docs/cli/skills> (skills; retrieved 2026-10-24)
- <https://www.codebuddy.ai/docs/cli/mcp> (`.mcp.json` locations; retrieved 2026-10-02)
- <https://www.codebuddy.ai/docs/cli/hooks> (hooks and sub-agent events; retrieved 2026-10-02)

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
`<project>/.codebuddy/rules/apothem-rules.md`, the skills at
`~/.codebuddy/skills/`, and the rules and templates corpus at
`~/.config/apothem/`, and authors no other cohort. There is no standalone-installable bundle; every artifact requires the
full `apothem install --harness codebuddy --project <path>` engine run.

| Artifact class | Persists standalone? | Mechanism / limit |
|---|---|---|
| Rules | No — requires `apothem install` | The merged `apothem-rules.md` (carrying the embedded behavioral mandates) is written only by the engine into the vendor-native `.codebuddy/rules/` directory. Nothing persists before that run. |
| Skills and commands | No — requires `apothem install` | The engine writes them as skills to the user-level `~/.codebuddy/skills/`. Nothing persists before that run. |
| Agents | No — adapter scope | CodeBuddy documents sub-agents, slash commands, and plugins; the adapter authors none of them. |
| Hooks / MCP / Tools / Settings | No — operator-owned | `.mcp.json` (MCP servers), `.codebuddy/settings.json`, and `CODEBUDDY.md` memory are operator-owned; the adapter authors no entries. |

CodeBuddy documents a plugin surface, but Apothem ships no CodeBuddy plugin, so
the files `apothem install` writes are the sole persistence surface.
