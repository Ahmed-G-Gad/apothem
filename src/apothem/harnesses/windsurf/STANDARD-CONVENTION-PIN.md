<!-- SPDX-License-Identifier: MIT -->

# Windsurf Standard Convention Pin

## Snapshot

- Snapshot date: 2026-06-25
- Adapter source: `src/apothem/harnesses/windsurf/`
- Evidence level: adapter-local projection; no vendor-native UI claim is made here.

## Official Surface Refresh

- Refreshed live 2026-06-25 against the current vendor documentation
  (`docs.devin.ai`). The windsurf harness rebranded to **Devin Desktop**
  (OTA rollout 2026-06-02); the docs authority host moved from
  `docs.windsurf.com` to the first-party Devin host `docs.devin.ai`. No
  immutable version pin is exposed (mutable docs site), so every captured
  convention carries a no-immutable-source exception. The harness slug stays
  `windsurf`.
- **Write-target migration.** The vendor's current docs make
  `<project>/.devin/rules/*.md` the **preferred** workspace-rules surface, which
  **takes precedence** over the retained backward-compat fallback at
  `<project>/.windsurf/rules/*.md`. The adapter migrated its canonical write
  target to `<project>/.devin/rules/apothem-rules.md` so the merged rules file is
  never silently shadowed by any `.devin/rules/` content the operator already
  keeps. Evidence: vendor-doc-url
  <https://docs.devin.ai/desktop/cascade/workspace-rules>; snapshot-id living
  docs; snapshot-date 2026-06-25.
- Config-root correction: the global config root is `~/.codeium/windsurf/`
  (global rules, MCP, skills, memories), not `~/.windsurf/`. The workspace
  directory carries both the preferred `.devin/` tree (rules, skills) and the
  retained `.windsurf/` fallback tree.
- MCP is now recognized: `~/.codeium/windsurf/mcp_config.json` (stdio / HTTP /
  SSE / OAuth) is operator-owned; the adapter recognizes it but does not author
  entries. `capabilities.yml` `mcp_servers` and the shared capability matrix were
  refreshed accordingly.
- Workspace rules are a `*.md` directory (12k char per file), not a single file;
  `layered_context_surface` names the preferred `.devin/rules/*.md` directory
  with the `.windsurf/rules/` backward-compat fallback noted.
- Native skills are a documented vendor surface at
  `.windsurf/skills/<name>/SKILL.md` (Markdown SKILL.md with YAML frontmatter
  carrying `name` + `description`); workflows (`.windsurf/workflows/`) and a
  `hooks.json` hook surface are also vendor-side. The adapter delivers only the
  project rules file and authors none of those cohorts (deliberate rules-only
  posture). The `hooks.json` surface is **unverified against current docs** —
  it could not be confirmed in the current official `docs.devin.ai` documentation
  and is carried as a tracked claim pending re-verification. Settings,
  agent-dispatch, plugins, and status-lines remain undocumented as file surfaces.
- Web-fetch / browser-retrieval (`web_fetch` = **yes**): the Cascade agent
  ships Web Search + URL Read (page fetch/chunk) tools, forced via `@web` and
  `@docs`, gated by the "Enable Web Search" admin setting — the backing dimension
  for `rules/source-accessibility.md` step 1. Evidence: vendor-doc-url
  <https://docs.devin.ai/desktop/cascade/web-search>; snapshot-id living docs;
  snapshot-date 2026-06-25.

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
that Apothem ships. The adapter is project-scope rules-only: it writes a single
merged rules file at `<project>/.devin/rules/apothem-rules.md` (the preferred
surface; `.windsurf/rules/` is the backward-compat fallback) and authors no other
cohort. There is no standalone-installable bundle; every artifact requires the
full `apothem install --harness windsurf --project <path>` engine run.

| Artifact class | Persists standalone? | Mechanism / limit |
|---|---|---|
| Rules | No — requires `apothem install` | The merged `apothem-rules.md` (carrying the embedded behavioral mandates) is written only by the engine into the preferred `.devin/rules/` directory (`.windsurf/rules/` backward-compat fallback). Nothing persists before that run. |
| Commands / Skills / Agents | No — platform limit | The vendor documents native skills (`.windsurf/skills/<name>/SKILL.md`), workflows, and an unverified `hooks.json` surface but no command/agent primitive Apothem targets; these cohorts are not materialized for this harness (deliberate rules-only posture). |
| Hooks / MCP / Settings | No — operator-owned / platform limit | `~/.codeium/windsurf/mcp_config.json` (MCP) is operator-owned and the `hooks.json` surface is unverified against current docs; the adapter authors no entries. |

Platform limit: Windsurf ships no marketplace/extension channel, so a
plugin-alone story does not exist — the merged rules file via `apothem install`
is the sole persistence surface.
