<!-- SPDX-License-Identifier: MIT -->

# Zed Standard Convention Pin

## Snapshot

- Snapshot date: 2026-06-25
- Adapter source: `src/apothem/harnesses/zed/`
- Evidence level: adapter-local projection; no vendor-native UI claim is made here.
- canonical-filename: `.rules`
- vendor-doc-url: https://zed.dev/docs/ai/instructions

## Official Surface Refresh

- Captured 2026-06-25 against the current Zed documentation (`zed.dev/docs`).
  No authority-host move; no immutable version pin is exposed (mutable docs
  site), so every captured convention carries a no-immutable-source exception.
- Zed reorganized its AI docs (Reusable Rules → Skills, Always-on Rules →
  Instructions, ~v1.4.0): `zed.dev/docs/ai/instructions`, `.../ai/skills`, and
  `.../ai/rules` now coexist (the `ai/rules` page still resolves and documents
  `.rules` / `.cursorrules` / `CLAUDE.md` / `AGENTS.md`). The `.rules`
  project-root file behavior is unchanged and current — Zed still auto-includes
  the flat `.rules` file as agent instructions; only the docs were reorganized
  (re-verified live 2026-06-25 against `zed.dev/docs`).
- Surface: Zed reads one project instruction file, the first match in the
  list `.rules`, `.cursorrules`, `.windsurfrules`, `.clinerules`,
  `.github/copilot-instructions.md`, `AGENT.md`, `AGENTS.md`, `CLAUDE.md`,
  `GEMINI.md`, so `.rules` hides every later file. The format is
  free-form plaintext / Markdown with no schema. The global surface is
  `~/.config/zed/AGENTS.md`.
- DIVERGENCE (flat file, no dedicated apothem file): unlike the cohort's
  rules-directory shape (a dedicated `apothem-rules.md` inside a `rules/`
  directory), Zed reads one flat `.rules` file at the project root. The adapter
  therefore writes `<project>/.rules` directly. There is no per-tool rules
  subdirectory to scope the apothem block into.
- DIVERGENCE (backup-on-replace): because `.rules` is a single shared file an
  operator may already maintain, the shared install driver backs up any
  pre-existing `.rules` to a timestamped copy under `~/.apothem/backups/`
  before replacement (and `apothem uninstall` renames the live file to a
  timestamped sibling backup). The operator's prior instruction file is never
  silently lost.
- MCP is recognized: Zed's context servers are configured via
  `.zed/settings.json` (and global settings) under `context_servers`
  (operator-owned). The adapter recognizes the surface but does not author
  entries. `capabilities.yml` `mcp_servers` and the shared capability matrix
  reflect this.
- The vendor documents threads, agent profiles, and MCP context servers as
  separate surfaces. The adapter delivers only the project `.rules` file and
  authors none of those cohorts (deliberate rules-only posture). Sub-agent
  dispatch, hooks, skills, and output-styles remain undocumented as
  adapter-owned file surfaces.
- Skills (`discovery-pending`): Zed now documents a native Skills surface at
  `zed.dev/docs/ai/skills` (the Reusable Rules → Skills migration). The adapter
  does not yet author skill files for this harness; the surface is recognized
  but its adapter-owned shape is discovery-pending against a pinned snapshot.
  No absence is asserted — the surface exists and awaits a discovery pass.

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
for its instruction surface. The adapter is project-scope rules-only: it writes a
single flat merged file at `<project>/.rules` (backing up any pre-existing
`.rules` first) and authors no other cohort. There is no standalone-installable
bundle; every artifact requires the full
`apothem install --harness zed --project <path>` engine run.

| Artifact class | Persists standalone? | Mechanism / limit |
|---|---|---|
| Rules (flat `.rules`) | No — requires `apothem install` | The merged `.rules` file (carrying the embedded behavioral mandates) is written only by the engine to the project root. Nothing persists before that run. |
| Commands / Agents | No — platform limit | Zed documents threads, agent profiles, and MCP context servers but no command/agent file primitive Apothem targets; these cohorts are not materialized for this harness. |
| Skills | No — adapter gap, not a platform limit | Zed documents a native Skills surface at `zed.dev/docs/ai/skills` (the Reusable Rules → Skills migration). The adapter does not yet author skill files for it — the `discovery-pending` entry above. The surface exists; Apothem has not targeted it. |
| Hooks / MCP / Settings | No — operator-owned / platform limit | `context_servers` in `.zed/settings.json` (MCP) is operator-owned; the adapter authors no entries. |

Platform limit: Zed's editor extensions are language/theme plugins, not an
instruction-cohort channel; a plugin-alone story does not exist for the
governance surface — the merged `.rules` file via `apothem install` is the sole
persistence surface.
