<!-- SPDX-License-Identifier: MIT -->

# Hermes Standard Convention Pin

## Snapshot

- Snapshot date: 2026-06-25
- Snapshot note: live re-verification — Hermes docs are now also published at `hermes-agent.nousresearch.com/docs`; the `~/.hermes/config.yaml` `delegation` block (subagent model/provider override, bounded), the `skills.config` namespace (skills auto-exposed as commands; `hermes config migrate` / `show`), and `quick_commands` all confirmed current; the commit anchor `355af2c…` is retained as the immutable evidence pin. Previous 2026-05-31.
- Adapter source: `src/apothem/harnesses/hermes/`
- Evidence level: vendor-repo pinned (live re-verification 2026-06-25;
  previous 2026-05-31) at commit
  `355af2c20f495b97c22c9aeb4c227fb0ca010da7` for `~/.hermes/config.yaml`.
  Skills are installable registry packages under `skills.config` (auto-exposed
  as commands) — NOT `skills.external_dirs` (that earlier claim is refuted). MCP
  is the `auxiliary.mcp` config block; sub-agent dispatch is the `delegation`
  block (`delegate_task`, bounded by `max_concurrent_children` /
  `max_spawn_depth`); user commands are `quick_commands` plus skill-exposed
  commands; durable memory lives at `~/.hermes/memories/`. Hermes is a
  multi-platform messaging gateway. No vendor-native UI claim is made here.
- Official references (commit-permalinked to the pinned SHA):
  - <https://github.com/NousResearch/hermes-agent/blob/355af2c20f495b97c22c9aeb4c227fb0ca010da7/website/docs/user-guide/configuration.md>
  - <https://github.com/NousResearch/hermes-agent/blob/355af2c20f495b97c22c9aeb4c227fb0ca010da7/website/docs/reference/slash-commands.md>

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
`~/.hermes/config.yaml` (native MCP under `auxiliary.mcp`) via its materializer
and keeps non-native cohorts under the Apothem support subtree
(`~/.hermes/.apothem/support/`). There is no standalone-installable bundle; every artifact
requires the full `apothem install --harness hermes` engine run.

| Artifact class | Persists standalone? | Mechanism / limit |
|---|---|---|
| Config / MCP | No — requires `apothem install` | `~/.hermes/config.yaml` is materializer-rendered by the engine; nothing persists before that run. |
| Commands / Skills / Agents / Rules | No — requires `apothem install` | These land under `~/.hermes/.apothem/support/` (support subtree) via the engine; Hermes `skills.config` registry packages are a vendor list the adapter does not author. |
| Hooks / Settings | No — platform limit | No Apothem-authored hook or settings surface beyond the config materializer. |

Platform limit: Hermes ships no marketplace/extension channel, so a plugin-alone
story does not exist — the engine install is the sole persistence path.
