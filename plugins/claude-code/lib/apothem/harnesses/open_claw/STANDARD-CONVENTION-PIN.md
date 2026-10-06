<!-- SPDX-License-Identifier: MIT -->

# Open-Claw Standard Convention Pin

## Snapshot

- Snapshot date: 2026-10-03
- Snapshot note: refreshed against `docs.openclaw.ai` (agent workspace and bootstrap files, skills, MCP CLI). Skills load from `~/.openclaw/skills` and each agent workspace, then filter through the agent skill allowlists (`agents.defaults.skills`); MCP servers live in the `mcp.servers` config block, managed with `openclaw mcp list|show|set|unset`. OpenClaw also documents plugins and the ClawHub registry. Previous 2026-06-25.
- Adapter source: `src/apothem/harnesses/open_claw/`
- Evidence level: vendor-doc pinned for `~/.openclaw/openclaw.json` (JSON5).
  Skills load from `~/.openclaw/skills` (shared root) plus each agent workspace,
  then are filtered by the effective allowlist under `agents.defaults.skills`
  (per-agent override `agents.list[].skills`). Subagents are documented via
  `agents.list[].subagents.allowAgents` (with `maxConcurrent` /
  `runTimeoutSeconds`). MCP servers live in the `mcp.servers` config block,
  managed via the `openclaw mcp` CLI subcommands (list / show / set / unset).
  OpenClaw is a multi-channel messaging gateway. No vendor-native UI claim is
  made here. Versionless docs carry no version or SHA — no-immutable-source
  exception.

## Vendor Sources

Retrieved 2026-10-03.

- <https://docs.openclaw.ai/gateway/config-agents/workspace-and-bootstrap> (agent workspace and bootstrap files)
- <https://docs.openclaw.ai/tools/skills> (skill loading and allowlists)
- <https://docs.openclaw.ai/cli/mcp> (`mcp.servers` and the `openclaw mcp` CLI)

## Discovery Targets

- None. No capability cell for this harness is discovery-pending.

## Recommended Postfix Rendering

- Status: supported as plain text.
- Mechanism: Apothem emits the literal ` (Recommended)` suffix in the option label. Open-Claw adapter output preserves that suffix when prompt text is materialized.
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

OpenClaw is a multi-channel messaging gateway with **no vendor plugin or
extension install surface** that Apothem ships. The adapter materializes
`~/.openclaw/openclaw.json` (JSON5) via its materializer and keeps non-native
cohorts under the Apothem support subtree (`~/.openclaw/.apothem/support/`). There is no
standalone-installable bundle; every artifact requires the full
`apothem install --harness open-claw` engine run.

| Artifact class | Persists standalone? | Mechanism / limit |
|---|---|---|
| Config / agents | No — requires `apothem install` | `~/.openclaw/openclaw.json` is materializer-rendered by the engine; nothing persists before that run. |
| Commands / Skills / Agents / Rules | No — requires `apothem install` | These land under `~/.openclaw/.apothem/support/` (support subtree) via the engine; OpenClaw `agents.defaults.skills` is a name-allowlist the adapter does not author. |
| Hooks / Settings | No — adapter scope | No Apothem-authored hook or settings surface beyond the config materializer. |
| MCP | No — operator-owned | OpenClaw MCP servers live in the `mcp.servers` config block (managed via the `openclaw mcp` CLI subcommands; `mcp.*` hot-applies); the adapter authors no entries. |

OpenClaw documents plugins and the ClawHub registry, but Apothem ships no
OpenClaw plugin, so the engine install is the sole persistence path.
