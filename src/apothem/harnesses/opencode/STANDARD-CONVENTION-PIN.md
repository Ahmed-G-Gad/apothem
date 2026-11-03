<!-- SPDX-License-Identifier: MIT -->

# OpenCode Standard Convention Pin

## Snapshot

- Snapshot date: 2026-11-03
- Snapshot note (OpenCode 2): the OpenCode 2 docs and the v1.19.5 and v2.2.5 source were read on 2026-11-03 (see OpenCode 2 below). The install now writes only `deny` helper rules, writes each MCP `${NAME}` as `{env:NAME}`, installs into `$XDG_CONFIG_HOME/opencode` when that names an absolute folder, warns when `OPENCODE_CONFIG_DIR` names another folder, and finds an MCP server an operator converted to OpenCode 2's `mcp.servers` shape. Previous 2026-10-14.
- Snapshot note: refreshed against `opencode.ai/docs` (config, rules, skills, agents, commands, MCP servers, tools), and the `instructions` path semantics re-observed at opencode-ai 1.19.0 (see Vendor Sources). `opencode.json` sources (global `~/.config/opencode/opencode.json` plus project), Markdown agents and commands in plural `agents/` and `commands/` directories, `skills/<name>/SKILL.md`, the `instructions` key, plugins in `.opencode/plugins/` or `~/.config/opencode/plugins/`, and the `webfetch` / `websearch` tools are confirmed. Previous 2026-06-25.
- Adapter source: `src/apothem/harnesses/opencode/`
- Evidence level: vendor-doc pinned for `opencode.json` and its
  `instructions` / `agent` / `command` / `mcp` / `plugin` keys; skills are a
  documented native surface; plugins are vendor-native and operator-owned; the
  native config is rendered directly (no Jinja template). OpenCode also loads
  `~/.claude/skills/` and `~/.agents/skills/`, so the Claude Code and Codex
  skill installs reach it (shared roots in the registry). No vendor-native UI
  claim is made here. Rolling docs carry no version or SHA — no-immutable-source
  exception on every source row.
- Official references:
  - <https://opencode.ai/docs/config/>
  - <https://opencode.ai/docs/rules/>
  - <https://opencode.ai/docs/agents/>
  - <https://opencode.ai/docs/commands/>
  - <https://opencode.ai/docs/mcp-servers/>
  - <https://opencode.ai/docs/skills/>
  - <https://opencode.ai/docs/plugins/>

## Web-Fetch / Browser-Retrieval Surface

- Capability: `web_fetch` = **partial**. The backing dimension for
  `rules/source-accessibility.md` step 1 ("retrieve through the host's browser /
  fetch capability").
- Vendor-confirmed PARTIAL: opencode ships an unconditional built-in `webfetch`
  tool (fetch + read web pages), but the `websearch` tool is available only when
  using the OpenCode provider or when the `OPENCODE_ENABLE_EXA` env var is set.
  The `partial` subset boundary is: fetch always-on, search provider/env-gated.
- Evidence: vendor-doc-url <https://opencode.ai/docs/tools/>; snapshot-id living
  docs; snapshot-date 2026-06-21 (the URL still resolves on 2026-10-03).

## Vendor Sources

Retrieved 2026-10-03 unless marked.

- <https://opencode.ai/docs/config/> (config sources, plural directories, plugins)
- <https://opencode.ai/docs/rules/> (`AGENTS.md` and `instructions`)
- Runtime observation, 2026-10-14: opencode-ai 1.19.0 (npm), run against a
  local OpenAI-compatible mock provider that recorded the request. The
  `instructions` entries `~/probe/home-note.md`, an absolute
  `<dir>/*.md` glob and `rel-note.md` loaded `<home>/probe/home-note.md`, both
  files the glob matched, and `<project>/rel-note.md`. So a leading `~/`
  expands to the home directory, an absolute entry matches as a glob on its
  final segment, and a relative entry resolves against the project directory.
  The upstream source moved from `sst/opencode` (now
  <https://github.com/anomalyco/opencode>, under `packages/core/`), and the
  docs page above does not describe these semantics. This is an observation,
  not a retrieved source; re-run it when the CLI version changes.
- <https://opencode.ai/docs/mcp-servers/> (`mcp` block)
- <https://opencode.ai/docs/skills/> (skill locations; retrieved 2026-10-02)
- <https://opencode.ai/docs/agents/> (agents; retrieved 2026-10-02)
- <https://opencode.ai/docs/commands/> (commands; retrieved 2026-10-02)

## OpenCode 2

OpenCode 2 (`anomalyco/opencode` v2.2.0, 2026-10-27, to v2.2.5, 2026-10-30;
npm `@opencode/cli`) reads the same configuration folder as OpenCode 1
(v1.19.5; npm `opencode-ai`, which `opencode.ai/install` still installs). What
each surface the install writes does under each line, read on 2026-11-03 from
the OpenCode 2 docs and the v1.19.5 and v2.2.5 source:

| Surface the install writes | OpenCode 1.19.5 | OpenCode 2.2.5 |
| --- | --- | --- |
| `opencode.json` in `$XDG_CONFIG_HOME/opencode`, else `~/.config/opencode` | read | read; `OPENCODE_CONFIG_DIR` replaces that folder (OpenCode 1 adds it), so the install warns when it names another folder |
| `$schema` and `instructions` (`~/`-anchored or absolute paths) | read | read the same way |
| `mcp.<name>` (`type`, `command`, `environment`, `url`, `headers`, `enabled`) | read | read in place and converted in memory, `enabled` to `disabled` (`packages/core/src/v1/config/migrate.ts`); the file is never rewritten, but an operator may convert it to the `mcp.servers` shape (migrate-v1 page), and update and uninstall find a converted entry there too |
| `${NAME}` in an MCP value | not expanded | not expanded; the install writes `{env:NAME}`, which both lines substitute |
| helper `permission` map | read | translated in memory (`bash` becomes `shell`); the install writes only `deny` rules, so the default ask before reading `.env` and `.env.*` files and the operator's stricter rules apply |
| commands, skills and `$ARGUMENTS` | read | read; a skill with `disable-model-invocation: true` is hidden from the model |
| `~/.claude/CLAUDE.md` (the Claude Code install) | read when no global `AGENTS.md` exists | not read |

Re-check by 2027-02-01, when this snapshot passes the 90-day limit: whether
OpenCode 2 still translates the helper `permission` map and the bare
`mcp.<name>` entries (its live schema marks them deprecated), and whether the
install should write OpenCode 2's own shapes.

- <https://opencode.ai/v2/docs/migrate-v1/> (shared configuration locations; V1 shapes keep working; retrieved 2026-11-03)
- <https://opencode.ai/v2/docs/instructions/> (`AGENTS.md` only; retrieved 2026-11-03)
- <https://github.com/anomalyco/opencode/tree/v2.2.5> (the instruction, agent, command and skill loaders, `packages/core/src/v1/config/migrate.ts`, `packages/core/src/config/variable.ts`, `packages/schema/src/agent.ts`; read 2026-11-03)
- <https://github.com/anomalyco/opencode/tree/v1.19.5> (`packages/opencode/src/agent/agent.ts`, `packages/opencode/src/permission/index.ts`, `packages/core/src/global.ts`; read 2026-11-03)

## Discovery Targets

- None. No capability cell for this harness is discovery-pending.

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
| Rules (as native primitive) | No — platform limit | OpenCode has no native rules-directory primitive; Apothem rules land as `~/.config/opencode/.apothem/support/rules/` reference material via the engine, and `opencode.json` `instructions` names the projected profile document and the `alwaysApply: true` rules by explicit path (OpenCode loads every listed file in every session): the four core rules and the rule index. OpenCode scopes no rule by path, so every other rule is read on demand through the index. |
| Hooks | No — platform limit | Engine support material only under `~/.config/opencode/.apothem/support/hooks/`. |
| MCP | No — requires `apothem install` | The adapter's materializer projects the profile's MCP inventory into the `opencode.json` `mcp` block; nothing persists before the engine run. |
| Plugins / Settings | No — operator-owned | The `plugin` key in `opencode.json` is operator-owned; the adapter authors no plugin entries. |

Platform limit: OpenCode's `plugin` surface is operator-owned and Apothem
distributes no OpenCode plugin package, so a plugin-alone story does not exist —
the engine install is the sole persistence path.
