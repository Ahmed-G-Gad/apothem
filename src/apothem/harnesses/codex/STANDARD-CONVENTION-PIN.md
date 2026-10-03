<!-- SPDX-License-Identifier: MIT -->

# Codex Standard Convention Pin

## Snapshot

- Snapshot date: 2026-10-03
- Snapshot note: refreshed against the Codex docs, which moved from `developers.openai.com/codex` to `learn.chatgpt.com/docs` (the old addresses redirect). The AGENTS.md chain (`CODEX_HOME`, `AGENTS.override.md`), `[mcp_servers.<name>]` tables in `config.toml`, `~/.codex/agents/*.toml` subagents, `$HOME/.agents/skills`, `hooks.json`, and the web search tool are confirmed. Previous 2026-06-25.
- Adapter source: `src/apothem/harnesses/codex/`
- Evidence level: vendor-doc pinned (living docs; no immutable pin). No vendor-native UI claim is made here.
- Shared root: Codex owns `~/.agents/skills/`, which Cursor, Gemini CLI, GitHub Copilot, Kimi Code, Open-Claw, OpenCode, Windsurf, and Zed also load. The registry records those readers and `apothem install` names them.

## MCP Surface Projection

- Status: vendor-native MCP is supported via `[mcp_servers.<name>]` tables in the operator-owned `~/.codex/config.toml` (and trusted-project `.codex/config.toml`).
- Mechanism: Apothem names this native surface in `capabilities.yml` but does not author MCP server entries; `config.toml` is operator-owned and outside the adapter's write surface.
- Boundary: STDIO transport keys (`command`, `args`, `env`, `cwd`) and HTTP keys (`url`, `bearer_token_env_var`, `http_headers`) are vendor-defined; this pin claims only that the surface exists, not that Apothem materializes it.

## Subagent and Skills Surface Projection

- Subagents: standalone TOML in `~/.codex/agents/` (personal) or `.codex/agents/` (project) requiring `name` / `description` / `developer_instructions`; any other `config.toml` key may be set, and omitted keys (`model`, `model_reasoning_effort`, `sandbox_mode`, ...) inherit from the parent session (re-checked 2026-10-02 against <https://learn.chatgpt.com/docs/agent-configuration/subagents>). The adapter's `codex_agents` converter emits the three required keys plus `sandbox_mode = "read-only"` for an agent whose tool grant authors no files (no Write or Edit after its deny list). It sets no model or reasoning effort, so both inherit. Codex has no per-agent tool allowlist or turn limit, so `tools` and `maxTurns` do not map (see `conversion_losses` in `capabilities.yml`).
- Skills: user-scope path is `$HOME/.agents/skills`. System skills are OpenAI-bundled with no official on-disk path — any `~/.codex/skills/.system` reference is an observed-runtime convenience, not an official path, and is never a write or sweep target.
- Skill invocation policy (verified 2026-10-02 against <https://learn.chatgpt.com/docs/build-skills>): Codex ignores `disable-model-invocation`. It reads `policy.allow_implicit_invocation` (default `true`) from `agents/openai.yaml` beside `SKILL.md`; `false` stops implicit selection while explicit `$skill` invocation still works. The `native_skills` and `command_skills` install modes write that file with `allow_implicit_invocation: false` for every skill or command whose source sets `disable-model-invocation: true`.

## Vendor Sources

Retrieved 2026-10-03 unless marked.

- <https://learn.chatgpt.com/docs/agent-configuration/agents-md> (AGENTS.md chain)
- <https://learn.chatgpt.com/docs/extend/mcp> (`[mcp_servers.<name>]`)
- <https://learn.chatgpt.com/docs/build-skills> (skill locations)
- <https://learn.chatgpt.com/docs/hooks> (`hooks.json`)
- <https://learn.chatgpt.com/docs/agent-configuration/subagents> (agent TOML; retrieved 2026-10-02)
- <https://learn.chatgpt.com/docs/web-search> (web search modes)

## Discovery Targets

- Discovery target: mcp_servers by 2026-12-31 — decide whether Apothem renders the profile's MCP inventory into `~/.codex/config.toml` (which the adapter does not overwrite today) or keeps naming it as operator-owned.

## Recommended Postfix Rendering

- Status: supported as plain text.
- Mechanism: Apothem emits the literal ` (Recommended)` suffix in the option label. Codex-facing prompts and fallback text preserve that suffix as authored.
- Boundary: this pin does not claim a harness-native recommended-option widget. It only pins the text-rendered convention used by `rules/interactive-questions.md`.

## Long Context and Compaction

- Status: profile-managed.
- Mechanism: Apothem keeps full-suite `/plan-execute` runs continuous by externalizing state to `.apothem/plans/`, compacting or restarting the harness session at phase boundaries as needed, and restoring via the Blind Bootstrap sequence.
- Boundary: this pin does not claim vendor-native autocompaction or a long-context size. It pins the adapter-local state handoff and compaction-restoration convention used by `rules/context-management.md`.

## Large-Codebase Practice Projection

- Layered context: declared in `capabilities.yml` under `layered_context_surface`; no vendor-native hierarchy is claimed beyond the adapter's documented file/template surface.
- LSP symbol navigation: `tracked-gap` until a vendor-ratified plugin or tool surface is pinned.
- Hook learning capture: routed through the `persistent-conventions-vigilance` artifact-evolution cycle; pass-class hooks stay silent and recurring findings become rule, skill, hook, or documentation updates.

## Web-Fetch / Browser-Retrieval Surface

- Capability: `web_fetch` = **yes**. The backing dimension for `rules/source-accessibility.md` step 1 ("retrieve through the host's browser / fetch capability").
- Vendor-confirmed: local Codex chats use cached web search by default (an OpenAI-maintained index); `codex --search` or `web_search = "live"` in `config.toml` fetches live results, `"indexed"` limits access to the index, and `"disabled"` turns the tool off.
- Evidence: vendor-doc-url <https://learn.chatgpt.com/docs/web-search>; snapshot-id living docs (no immutable commit); snapshot-date 2026-10-03.

## Hook Surface Projection

- Status: vendor-native user-scope hooks are supported through `~/.codex/hooks.json` and may also be declared in `~/.codex/config.toml`.
- Mechanism: Apothem installs managed hook configuration at `~/.codex/hooks.json` and helper material under `~/.codex/hooks/`.
- Boundary: Apothem does not overwrite `~/.codex/config.toml`; operator-owned hook declarations in that file remain outside the adapter's write surface.

## Plugin-alone Persistence

Codex exposes a plugin-marketplace surface (`codex plugin marketplace add`).
The bundle is `plugins/apothem/` with `.codex-plugin/plugin.json`
(`"skills": "./skills/"`) referenced by `.agents/plugins/marketplace.json`.
Installing the plugin *alone* — without running `apothem install` — persists
only what the plugin package bundles; the full user-scope cohort still requires
the engine, which converts agents to TOML and wires `~/.codex/hooks.json`.

| Artifact class | Persists plugin-alone? | Mechanism / limit |
|---|---|---|
| Skills | Bootstrap only | The plugin bundles one skill, `skills/apothem/SKILL.md`, a launcher that instructs the operator to run `npx @ahmed-g-gad/apothem install --harness codex`. It persists and is discoverable, but it carries the *entry-point*, not the cohort. |
| Commands | No — folded into the bootstrap skill | Codex has no separate marketplace command primitive in this bundle; the `/apothem`-equivalent entry is the bootstrap skill above. The full command cohort (command-prompt skills under `~/.agents/skills/`) lands only via `apothem install`. |
| Context anchor (rules-as-text) | No — requires `apothem install` | `~/.codex/AGENTS.md` is written by the engine, not the plugin package. The plugin bundles no AGENTS.md, so the embedded engineering disciplines persist only after the engine run. |
| Rules (as native primitive) | No — platform limit | Codex reserves `~/.codex/rules/` for `.rules` execution-policy files; Apothem rules are never a Codex-native rules primitive. They land as `~/.config/apothem/rules/` reference material via `apothem install`. |
| Agents | No — requires `apothem install` | `~/.codex/agents/*.toml` is engine-converted; the plugin package bundles no agents. |
| Hooks | No — requires `apothem install` | `~/.codex/hooks.json` + `~/.codex/hooks/` are engine-installed; the plugin package wires no hooks. |
| MCP servers | No — operator-owned | `[mcp_servers.<name>]` tables live in operator-owned `~/.codex/config.toml`; neither the plugin nor the engine authors them. |

Bundle wiring status: the plugin package persists a bootstrap launcher skill
that runs the engine. Embedding the full converted cohort (agents-as-TOML,
command skills, an AGENTS.md anchor carrying the engineering disciplines)
directly into `plugins/apothem/` is a documented future enhancement — the
conversion logic lives in the engine (`codex_agents` / `command_skills` modes
in `propagation-manifest.yaml`), so a build step that pre-renders those into the
bundled `plugins/apothem/` tree would let the plugin carry the cohort without a
post-install engine run.
