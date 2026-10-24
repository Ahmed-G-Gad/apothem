<!-- SPDX-License-Identifier: MIT -->

# Codex Standard Convention Pin

## Snapshot

- Snapshot date: 2026-10-24
- Snapshot note: the plugin-package facts (manifest location, compatibility fallback, bundled components, marketplace `policy`) are re-checked against the Codex plugin build guide, which lives at `developers.openai.com/plugins/build/plugins` (the older `developers.openai.com/codex/plugins/build` address carries the same text). The rest was last refreshed on 2026-10-03 against the Codex docs, which moved from `developers.openai.com/codex` to `learn.chatgpt.com/docs` (the old addresses redirect): the AGENTS.md chain (`CODEX_HOME`, `AGENTS.override.md`), `[mcp_servers.<name>]` tables in `config.toml`, `~/.codex/agents/*.toml` subagents, `$HOME/.agents/skills`, `hooks.json`, and the web search tool are confirmed. Custom agent files re-checked 2026-10-24: a file's `sandbox_mode`, `approval_policy`, `model_provider`, and `mcp_servers` do not override the parent session. Previous 2026-10-03.
- Adapter source: `src/apothem/harnesses/codex/`
- Evidence level: vendor-doc pinned (living docs; no immutable pin). No vendor-native UI claim is made here.
- Shared roots: Codex owns `~/.agents/skills/`, which Cursor, Gemini CLI, GitHub Copilot, Kimi Code, Open-Claw, OpenCode, Qwen Code, Windsurf, and Zed also load (re-checked 2026-10-24; Open-Claw reads it only under its default state directory), and `~/.codex/agents/` (`$CODEX_HOME/agents/`, which is that path by default), which Cursor lists as a Codex compatibility folder (re-checked 2026-10-24). TODO(clarify): the Cursor docs do not say which file formats Cursor parses in `~/.codex/agents/`, and Codex writes TOML there. The registry records those readers and `apothem install` names them.

## MCP Surface Projection

- Status: vendor-native MCP is supported via `[mcp_servers.<name>]` tables in the operator-owned `~/.codex/config.toml` (and trusted-project `.codex/config.toml`).
- Mechanism: Apothem names this native surface in `capabilities.yml` but does not author MCP server entries; `config.toml` is operator-owned and outside the adapter's write surface.
- Boundary: STDIO transport keys (`command`, `args`, `env`, `cwd`) and HTTP keys (`url`, `bearer_token_env_var`, `http_headers`) are vendor-defined; this pin claims only that the surface exists, not that Apothem materializes it.

## Subagent and Skills Surface Projection

- Subagents: standalone TOML in `~/.codex/agents/` (personal) or `.codex/agents/` (project) requiring `name` / `description` / `developer_instructions`. The optional keys an agent file may set are `model`, `model_reasoning_effort`, `model_reasoning_summary`, `model_verbosity`, `features.shell_tool`, `features.apps`, `features.plugins`, `features.memories`, and `features.request_permissions_tool` (each can only be set to `false`), and `skills.config`, `skills.bundled.enabled`, and `skills.include_instructions`; omitted keys inherit from the parent session. `sandbox_mode`, `approval_policy`, `model_provider`, and `mcp_servers` placed in an agent file do not override the parent session: sandbox and approval controls are set on the parent session, and agent instructions can ask an agent to avoid edits but do not create a separate read-only sandbox (re-checked 2026-10-24 against <https://learn.chatgpt.com/docs/agent-configuration/subagents>, <https://github.com/openai/codex/pull/39299>, and the `codex-rs/core/src/agent/role.rs` source). The adapter's `codex_agents` converter emits only the three required keys; a read-only agent states its limit in `developer_instructions`, which is the agent body. It sets no model or reasoning effort, so both inherit. The docs and `role.rs` disagree on whether an agent file controls `service_tier`, and the docs do not list `personality`; the converter sets neither. TODO(clarify): a live Codex run settles both. TODO(clarify): the first Codex release that shipped the restriction is not established (the pull request merged 2026-08-18 and the `rust-v0.155.0` release page does not list it), so a Codex build older than that change may still honour `sandbox_mode` in an agent file; the converter writes none, which drops the only native read-only enforcement for such a build until a release is named. Codex has no per-agent tool allowlist or turn limit, so `tools` and `maxTurns` do not map (see `conversion_losses` in `capabilities.yml`).
- Skills: user-scope path is `$HOME/.agents/skills`. System skills are OpenAI-bundled with no official on-disk path — any `~/.codex/skills/.system` reference is an observed-runtime convenience, not an official path, and is never a write or sweep target.
- Skill invocation policy (verified 2026-10-02 against <https://learn.chatgpt.com/docs/build-skills>): Codex ignores `disable-model-invocation`. It reads `policy.allow_implicit_invocation` (default `true`) from `agents/openai.yaml` beside `SKILL.md`; `false` stops implicit selection while explicit `$skill` invocation still works. The `native_skills` and `command_skills` install modes write that file with `allow_implicit_invocation: false` for every skill or command whose source sets `disable-model-invocation: true`.

## Vendor Sources

Retrieved 2026-10-03 unless marked.

- <https://learn.chatgpt.com/docs/agent-configuration/agents-md> (AGENTS.md chain)
- <https://learn.chatgpt.com/docs/extend/mcp> (`[mcp_servers.<name>]`)
- <https://learn.chatgpt.com/docs/build-skills> (skill locations)
- <https://learn.chatgpt.com/docs/hooks> (`hooks.json`)
- <https://learn.chatgpt.com/docs/agent-configuration/subagents> (agent TOML; retrieved 2026-10-24)
- <https://github.com/openai/codex/pull/39299> (agent roles restricted to bounded configuration overrides; merged 2026-08-18; retrieved 2026-10-24)
- <https://raw.githubusercontent.com/openai/codex/main/codex-rs/core/src/agent/role.rs> (the role overrides a custom agent file may apply; living file on `main`, retrieved 2026-10-24)
- <https://learn.chatgpt.com/docs/web-search> (web search modes)
- <https://developers.openai.com/plugins/build/plugins> (plugin layout, `.codex-plugin/plugin.json` fallback, bundled components, marketplace `policy`; retrieved 2026-10-24)
- <https://learn.chatgpt.com/docs/plugins> (plugin component overview; retrieved 2026-10-24)
- <https://raw.githubusercontent.com/openai/skills/main/skills/.system/plugin-creator/references/plugin-json-spec.md> (marketplace `policy` allowed values and defaults; retrieved 2026-10-24)
- <https://agent-plugins.org/schemas/1.0.0/plugin.schema.json> (portable `plugin.json` schema; retrieved 2026-10-24)
- <https://github.com/openai/codex/issues/18988> (open request: plugins that bundle custom agents; retrieved 2026-10-24)
- <https://github.com/openai/codex/issues/18308> (open request: agents in the plugin system; retrieved 2026-10-24)

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
The bundle is `plugins/apothem/`, referenced by `.agents/plugins/marketplace.json`.
Its manifest is the root `plugins/apothem/plugin.json`, the location Codex
documents for a new package: it declares the Agent Plugins 1.0.0 schema
(`$schema`, `additionalProperties: false`) and carries identity only, with no
`skills` key because Codex discovers a portable package's `skills/` directory
from the plugin root. `plugins/apothem/.codex-plugin/plugin.json`
(`"skills": "./skills/"`) stays beside it as a compatibility fallback: Codex
documents existing `.codex-plugin/plugin.json` files as still supported, treats
the root manifest as canonical for identity, and reads the fallback only for
OpenAI-specific settings and only while the root has no `extensions.com.openai`
object (that object replaces the whole overlay; the two are not merged). The
fallback holds no such settings today, so on a Codex build that reads the root
manifest it adds nothing; it exists for builds that read only the older
location. `tests/unit/test_codex_plugin_manifest.py` holds both manifests to
this shape, and `tests/unit/test_manifest_version_sync.py` holds their versions
to `apothem.__version__`.

The plugin components Codex documents include skills, an `mcp.json` of bundled
MCP servers, hooks, and assets. None of the reviewed pages lists a custom-agents
component, so neither manifest declares one.

Installing the plugin *alone* — without running `apothem install` — persists
only what the plugin package bundles; the full user-scope cohort still requires
the engine, which converts agents to TOML and wires `~/.codex/hooks.json`.

| Artifact class | Persists plugin-alone? | Mechanism / limit |
|---|---|---|
| Skills | Bootstrap only | The plugin bundles one skill, `skills/apothem/SKILL.md`, a launcher that instructs the operator to run `npx @ahmed-g-gad/apothem install --harness codex`. It persists and is discoverable, but it carries the *entry-point*, not the cohort. |
| Commands | No — folded into the bootstrap skill | Codex has no separate marketplace command primitive in this bundle; the `/apothem`-equivalent entry is the bootstrap skill above. The full command cohort (command-prompt skills under `~/.agents/skills/`) lands only via `apothem install`. |
| Context anchor (rules-as-text) | No — requires `apothem install` | `~/.codex/AGENTS.md` is written by the engine, not the plugin package. The plugin bundles no AGENTS.md, so the embedded engineering disciplines persist only after the engine run. |
| Rules (as native primitive) | No — platform limit | Codex reserves `~/.codex/rules/` for `.rules` execution-policy files; Apothem rules are never a Codex-native rules primitive. They land as `~/.config/apothem/rules/` reference material via `apothem install`. |
| Agents | No — no documented plugin component | `~/.codex/agents/*.toml` is engine-converted and stays that way: Codex documents agents as standalone TOML files and lists no agents component for plugins (the upstream requests openai/codex#18988 and #18308 are open). The plugin package bundles no agents. |
| Hooks | No — requires `apothem install` | `~/.codex/hooks.json` + `~/.codex/hooks/` are engine-installed; the plugin package wires no hooks. Codex plugins can bundle lifecycle hooks, but only for plugins installed manually in Codex desktop; installing or enabling a plugin does not trust its hooks, and a plugin that carries them is not eligible for the public plugin directory. |
| MCP servers | No — operator-owned | `[mcp_servers.<name>]` tables live in operator-owned `~/.codex/config.toml`; neither the plugin nor the engine authors them. Codex plugins can bundle an `mcp.json`; this plugin ships none. |

Bundle wiring status: the plugin package persists a bootstrap launcher skill
that runs the engine. Of the cohorts the engine converts, command skills are the
only one that maps onto a documented plugin component (skills) without an engine
run: a build step that pre-renders the `command_skills` mode of
`propagation-manifest.yaml` into the bundled `plugins/apothem/skills/` tree
would carry them, and it is not built. Agents-as-TOML do not follow, because
Codex documents no plugin component for agents, so `~/.codex/agents/*.toml`
stays engine-installed. Hooks stay engine-installed for the reasons in the
table.

TODO(clarify): whether a Codex plugin can carry an AGENTS.md instruction anchor
is not stated in the reviewed plugin pages, so the context anchor stays
engine-written until the vendor documents a component for it.

TODO(clarify): the Codex changelog gives no release for when a root
`plugin.json` became readable, so the `.codex-plugin/plugin.json` fallback is
kept on the strength of "still supported" rather than a known minimum Codex
version. Name that version, then decide whether to retire the fallback (retire
its anchors in `scripts/release/bump_version.py` and
`tests/unit/test_manifest_version_sync.py` and the fallback tests in
`tests/unit/test_codex_plugin_manifest.py` in the same change).

The marketplace entry in `.agents/plugins/marketplace.json` carries a `policy`
block. Codex tells authors to always include `policy.installation` (allowed
values `NOT_AVAILABLE`, `AVAILABLE`, `INSTALLED_BY_DEFAULT`; default for a new
entry `AVAILABLE`) and `policy.authentication` (allowed values `ON_INSTALL`,
`ON_USE`; default for a new entry `ON_INSTALL`) on each plugin entry; the
vendor's marketplace example sets `ON_INSTALL`. The entry sets the two defaults,
and `tests/unit/test_codex_plugin_manifest.py` holds both fields to the
documented sets.

TODO(clarify): the Codex pages reviewed on 2026-10-24 do not say which
`policy.authentication` timing the vendor intends for a plugin that needs no
sign-in. The entry uses the documented default, `ON_INSTALL`; switch to `ON_USE`
only if a live Codex shows an install-time sign-in prompt for this plugin.
