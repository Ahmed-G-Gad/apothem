<!-- SPDX-License-Identifier: MIT -->

# OpenCode Standard Convention Pin

## Snapshot

- Snapshot date: 2026-06-25
- Snapshot note: live re-verification of `opencode.ai/docs` — `opencode.json` config sources (global `~/.config/opencode/opencode.json` + project), markdown agents/commands (plural `agents/`/`commands/` subdirs) with frontmatter, `skills/<name>/SKILL.md`, the AGENTS.md instruction-combination (`instructions` key), and `webfetch` (always-on) / `websearch` (provider/`OPENCODE_ENABLE_EXA`-gated) all confirmed current.
- Adapter source: `src/apothem/harnesses/opencode/`
- Evidence level: vendor-doc pinned (live re-fetch 2026-05-31) for
  `opencode.json` and the `instructions`/`agent`/`command`/`mcp`/`plugin`
  keys; skills are a documented native surface (`skills/<name>/SKILL.md`);
  plugins are vendor-native (`plugin` key + `plugins/`) and operator-owned;
  the native config is rendered directly (no Jinja template). No vendor-native
  UI claim is made here. Rolling docs carry no version/SHA — no-immutable-source
  exception on every source row.
- Official references:
  - <https://opencode.ai/docs/config/>
  - <https://opencode.ai/docs/agents>
  - <https://opencode.ai/docs/mcp-servers>
  - <https://opencode.ai/docs/skills>
  - <https://opencode.ai/docs/plugins>

## Web-Fetch / Browser-Retrieval Surface

- Capability: `web_fetch` = **partial**. The backing dimension for
  `rules/source-accessibility.md` step 1 ("retrieve through the host's browser /
  fetch capability").
- Vendor-confirmed PARTIAL: opencode ships an unconditional built-in `webfetch`
  tool (fetch + read web pages), but the `websearch` tool is available only when
  using the OpenCode provider or when the `OPENCODE_ENABLE_EXA` env var is set.
  The `partial` subset boundary is: fetch always-on, search provider/env-gated.
- Evidence: vendor-doc-url <https://opencode.ai/docs/tools/> ("webfetch … Allows
  the LLM to fetch and read web pages"; "websearch … only available when using
  the OpenCode provider or when the `OPENCODE_ENABLE_EXA` environment variable is
  set"); snapshot-id living docs; snapshot-date 2026-06-21.

## Recommended Postfix Rendering

- Status: supported as plain text.
- Mechanism: Apothem emits the literal ` (Recommended)` suffix in the option label. OpenCode adapter output preserves that suffix when prompt text is materialized.
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

OpenCode documents a vendor-native `plugin` key plus a `plugins/` directory, but
that surface is operator-owned and **Apothem ships no OpenCode plugin bundle** —
and OpenCode exposes no harness-native plugin marketplace Apothem distributes
through. The cohort lands via native skills/commands/agents surfaces, all written
by the engine. There is no standalone-installable bundle; every artifact requires
the full `apothem install --harness opencode` engine run.

| Artifact class | Persists standalone? | Mechanism / limit |
|---|---|---|
| Skills | No — requires `apothem install` | Native `~/.config/opencode/skills/*/SKILL.md` is engine-written; no pre-built bundle carries it. |
| Commands | No — requires `apothem install` | Apothem commands are engine-converted to OpenCode Markdown under `~/.config/opencode/commands/`. |
| Agents | No — requires `apothem install` | Apothem agents are engine-converted to OpenCode Markdown under `~/.config/opencode/agents/`. |
| Rules (as native primitive) | No — platform limit | OpenCode has no native rules-directory primitive; Apothem rules land as `~/.config/opencode/.apothem/support/rules/` reference material via the engine. |
| Hooks | No — platform limit | Engine support material only under `~/.config/opencode/.apothem/support/hooks/`. |
| MCP | No — requires `apothem install` | The adapter's materializer projects the profile's MCP inventory into the `opencode.json` `mcp` block; nothing persists before the engine run. |
| Plugins / Settings | No — operator-owned | The `plugin` key in `opencode.json` is operator-owned; the adapter authors no plugin entries. |

Platform limit: OpenCode's `plugin` surface is operator-owned and Apothem
distributes no OpenCode plugin package, so a plugin-alone story does not exist —
the engine install is the sole persistence path.
