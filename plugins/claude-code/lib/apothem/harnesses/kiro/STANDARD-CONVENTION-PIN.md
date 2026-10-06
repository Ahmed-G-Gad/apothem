<!-- SPDX-License-Identifier: MIT -->

# Kiro Standard Convention Pin

## Snapshot

- Snapshot date: 2026-10-03
- Snapshot note: refreshed against `kiro.dev/docs` (steering, MCP configuration, skills, hooks). Steering inclusion modes (`always`, `fileMatch` with `fileMatchPattern`, `manual`, `auto`), `AGENTS.md` support (workspace root and `~/.kiro/steering/`), MCP at `.kiro/settings/mcp.json` and `~/.kiro/settings/mcp.json`, and agent files in `.kiro/agents` are confirmed. Previous 2026-06-25.
- Adapter source: `src/apothem/harnesses/kiro/`
- Evidence level: vendor-doc pinned (living docs; no-immutable-source exception). No vendor-native UI claim is made here.
- Vendor doc URL: https://kiro.dev/docs/steering/
- Canonical filename: `.kiro/steering/apothem-rules.md`

## Official Surface Refresh

- Steering: `.kiro/steering/*.md` (workspace) and `~/.kiro/steering/`
  (global), Markdown with optional front matter controlling inclusion
  (`inclusion: always | fileMatch | manual | auto`; `fileMatchPattern` for
  `fileMatch`, description matching for `auto`). The adapter writes only
  `<project>/.kiro/steering/apothem-rules.md` with `inclusion: always`, so it
  never clobbers the operator's foundation files (`product.md`, `tech.md`,
  `structure.md`).
- `AGENTS.md`: Kiro reads `AGENTS.md` at the workspace root and in
  `~/.kiro/steering/`, so the registry lists Kiro as a reader of the project
  `AGENTS.md` that the Kimi Code adapter writes. The Kiro adapter does not write
  `AGENTS.md`.
- MCP: `.kiro/settings/mcp.json` (workspace) and `~/.kiro/settings/mcp.json`
  (user), plus an agent's own `mcpServers` field. Operator-owned; the adapter
  names the surface and authors no entries.
- The vendor documents specs (`.kiro/specs/`), agent hooks, Agent Skills,
  custom agents (`.kiro/agents` and the Kiro CLI), and Kiro powers. The adapter
  delivers only the project steering file and authors none of those: a
  deliberate rules-only posture, not a claim that the surfaces are absent.

## Vendor Sources

Retrieved 2026-10-03 unless marked.

- <https://kiro.dev/docs/steering/> (steering and `AGENTS.md`)
- <https://kiro.dev/docs/mcp/> (MCP overview)
- <https://kiro.dev/docs/mcp/configuration/> (`mcp.json` locations, `.kiro/agents`)
- <https://kiro.dev/docs/skills/> (skills; retrieved 2026-10-02)
- <https://kiro.dev/docs/hooks/> (hooks; retrieved 2026-10-02)

## Discovery Targets

- Discovery target: mcp_servers by 2026-12-31 — decide whether Apothem renders the profile's MCP inventory into `.kiro/settings/mcp.json` or keeps naming it as operator-owned.

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
| Commands / Skills / Agents | No — deliberate rules-only posture | Kiro documents specs (`.kiro/specs/`), agent hooks, Agent Skills, and custom agents (`.kiro/agents`, Kiro CLI), but the adapter authors none of them (preserve-first rules-only delivery); these cohorts are not materialized for this harness by design. |
| Hooks / MCP / Settings | No — operator-owned | `.kiro/settings/mcp.json` (MCP) and the foundation steering files are operator-owned; the adapter authors no entries. |

Kiro documents installable powers, but Apothem ships no Kiro power, so the
merged steering file via `apothem install` is the sole persistence surface.
