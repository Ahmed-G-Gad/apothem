<!-- SPDX-License-Identifier: MIT -->

# Kiro Standard Convention Pin

## Snapshot

- Snapshot date: 2026-06-25
- Snapshot note: live re-verification against `kiro.dev/docs` surfaced TWO findings: (1) the steering inclusion-mode enumeration was INCOMPLETE — the vendor documents FOUR modes (`always | auto | fileMatch | manual`); the prior pin omitted `auto` (description-matched, skill-like inclusion); (2) STALENESS — the pin framed Kiro's skill/agent surface as absent, but the vendor documents Agent Skills (`kiro.dev/docs/skills`), CLI custom agents (`kiro.dev/docs/cli/custom-agents`), and Kiro powers (`POWER.md`). The adapter's rules-only steering delivery remains a DELIBERATE posture. `.kiro/steering/*.md` (workspace) + `~/.kiro/steering/` (global), specs (`.kiro/specs/`), agent hooks, and MCP (`.kiro/settings/mcp.json`) all confirmed current. Previous 2026-06-09.
- Adapter source: `src/apothem/harnesses/kiro/`
- Evidence level: adapter-local projection; no vendor-native UI claim is made here.
- Vendor doc URL: https://kiro.dev/docs/steering/
- Canonical filename: `.kiro/steering/apothem-rules.md`

## Official Surface Refresh

- Refreshed live 2026-06-09 against the current Kiro documentation
  (`kiro.dev/docs`). No immutable version pin is exposed (mutable docs site),
  so every captured convention carries a no-immutable-source exception.
- Kiro reached general availability 2026 with a documented steering surface at
  `.kiro/steering/*.md`. Steering files are Markdown with optional YAML front
  matter controlling inclusion (`inclusion: always | auto | fileMatch | manual`,
  with `fileMatchPattern` for the `fileMatch` mode and description-matched
  inclusion for the `auto` mode). The adapter is project-scope and
  writes only `<project>/.kiro/steering/apothem-rules.md` with
  `inclusion: always`, so it never clobbers the operator-authored foundation
  files (`product.md`, `tech.md`, `structure.md`).
- MCP is recognized: `.kiro/settings/mcp.json` (workspace) and
  `~/.kiro/settings/mcp.json` (user) are operator-owned; the adapter recognizes
  them but does not author entries. `capabilities.yml` `mcp_servers` and the
  shared capability matrix were set accordingly.
- Steering is a `.kiro/steering/*.md` directory, not a single file;
  `layered_context_surface` was set to match. Kiro also recognizes `AGENTS.md`
  at the project root; the adapter does not write `AGENTS.md` (the dedicated
  steering file is the deliberate, non-clobbering surface).
- The vendor documents specs (`.kiro/specs/`), agent hooks, Agent Skills
  (`kiro.dev/docs/skills`), CLI custom agents (`kiro.dev/docs/cli/custom-agents`),
  and Kiro powers (`POWER.md`). The adapter delivers only the project steering
  file and authors none of those cohorts: a DELIBERATE rules-only posture, not a
  claim the surfaces are absent. Settings and status surfaces remain undocumented
  as adapter-owned file surfaces.

## Recommended Postfix Rendering

- Status: supported as plain text.
- Mechanism: Apothem emits the literal ` (Recommended)` suffix in the option label. Kiro steering files preserve that suffix as authored.
- Boundary: this pin does not claim a harness-native recommended-option widget. It only pins the text-rendered convention used by `rules/interactive-questions.md`.

## Long Context and Compaction

- Status: profile-managed.
- Mechanism: Apothem keeps full-suite `/plan-execute` runs continuous by externalizing state to `.apothem/plans/`, compacting or restarting the harness session at phase boundaries as needed, and restoring via the Blind Bootstrap sequence.
- Boundary: this pin does not claim vendor-native autocompaction or a long-context size. It pins the adapter-local state handoff and compaction-restoration convention used by `rules/context-management.md`.

## Large-Codebase Practice Projection

- Layered context: declared in `capabilities.yml` under `layered_context_surface`; no vendor-native hierarchy is claimed beyond the adapter's documented file/template surface. Kiro steering inclusion modes (`always`, `fileMatch`, `manual`) are the vendor-native context-scoping mechanism; the adapter ships the `always` mode for its governance surface.
- LSP symbol navigation: `tracked-gap` until a vendor-ratified plugin or tool surface is pinned.
- Hook learning capture: routed through the `persistent-conventions-vigilance` artifact-evolution cycle; pass-class hooks stay silent and recurring findings become rule, skill, hook, or documentation updates.

## Plugin-alone Persistence

Kiro exposes **no vendor plugin or extension install surface** that Apothem
ships. The adapter is project-scope rules-only: it writes a single merged
steering file at `<project>/.kiro/steering/apothem-rules.md` (`inclusion: always`)
and authors no other cohort. There is no standalone-installable bundle; every
artifact requires the full `apothem install --harness kiro --project <path>`
engine run.

| Artifact class | Persists standalone? | Mechanism / limit |
|---|---|---|
| Rules (steering-as-text) | No — requires `apothem install` | The merged `apothem-rules.md` steering file (carrying the embedded behavioral mandates) is written only by the engine into the vendor-native `.kiro/steering/` directory. Nothing persists before that run. |
| Commands / Skills / Agents | No — deliberate rules-only posture | Kiro documents specs (`.kiro/specs/`), agent hooks, Agent Skills, and CLI custom agents, but the adapter authors none of them (preserve-first rules-only delivery); these cohorts are not materialized for this harness by design. |
| Hooks / MCP / Settings | No — operator-owned / platform limit | `.kiro/settings/mcp.json` (MCP) and the foundation steering files are operator-owned; the adapter authors no entries. |

Platform limit: Kiro ships no marketplace/extension channel, so a plugin-alone
story does not exist — the merged steering file via `apothem install` is the sole
persistence surface.
