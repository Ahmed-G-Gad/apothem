<!-- SPDX-License-Identifier: MIT -->

# Gemini CLI Standard Convention Pin

## Snapshot

- Snapshot date: 2026-06-25
- Snapshot note: live re-verification against `github.com/google-gemini/gemini-cli` docs — hierarchical `GEMINI.md` context (`@file.md` imports), TOML custom commands (`~/.gemini/commands/*.toml`, required `prompt`), and built-in `web_fetch` / `google_web_search` all confirmed current; previous live-fetch 2026-06-21 / 2026-05-22
- Adapter source: `src/apothem/harnesses/gemini_cli/`.
- Upstream authority: `github.com/google-gemini/gemini-cli`, release `v0.44.1`
  (2026-05-28), main HEAD commit `013914071c5412188661014f2670ce3818cb98c3`
  (2026-05-29) — an immutable pin (one of the three GitHub-backed harnesses).
- Evidence level: official-source-backed for the surfaces below; no vendor-native UI claim is made here.
- Lifecycle: Google's standalone Gemini CLI deprecation for the AI Pro / AI
  Ultra and free individual tiers (dated 2026-06-18) consolidates its developer
  tooling under Antigravity CLI (binary `agy`; see the sibling `antigravity`
  adapter and its pin, which materializes the successor). Gemini Code Assist
  Standard / Enterprise and paid API keys keep the legacy CLI working, so this
  adapter stays valid for those accounts; individual-tier users route to the
  `antigravity` harness. Primary source: Google Developers Blog "Transitioning
  Gemini CLI to Antigravity CLI" (I/O, 2026-05-19).

## Native Surfaces (live-confirmed 2026-05-31)

- Project context anchor: `<project>/GEMINI.md` (and global `~/.gemini/GEMINI.md`);
  the user-scope `~/.gemini/` tree is reserved for the antigravity adapter, so
  this project-scope adapter materializes under `<project>/` exclusively.
- MCP: the `mcpServers` object in the operator-owned `settings.json` (user
  `~/.gemini/settings.json`, project `.gemini/settings.json`). It supports stdio
  (`command`/`args`) and HTTP (`url` for SSE, `httpUrl` for streamable). Apothem
  names this surface but does not author MCP server entries; `settings.json` is
  operator-owned and never written by the adapter.
- Hooks: a native `hooks` object in `settings.json` with per-event arrays and a
  `matcher`, spanning eleven lifecycle events (SessionStart, SessionEnd,
  BeforeAgent, AfterAgent, BeforeModel, AfterModel, BeforeToolSelection,
  BeforeTool, AfterTool, PreCompress, Notification). Apothem keeps its hook
  message-context prose as support material under `<project>/.gemini/.apothem/support/`
  and does not register native settings.json hooks (the operator owns
  `settings.json`).
- Skills: four-tier discovery (built-in, extension, user `~/.gemini/skills/`,
  workspace `.gemini/skills/`), each with an `~/.agents/skills/` / `.agents/skills/`
  alias; `SKILL.md` entry. Apothem installs to the native `<project>/.gemini/skills/`.
- Commands: TOML custom commands (`.toml`, required `prompt`, optional
  `description`) under `~/.gemini/commands/` (user) / `.gemini/commands/`
  (project). Apothem converts its command cohort to this native TOML shape:
  `description` from the source, and a `prompt` holding the command body with
  the source frontmatter and license comment stripped. Every other source key
  is dropped (see `conversion_losses` in `capabilities.yml`).
- Subagents (re-checked 2026-10-02 against
  https://geminicli.com/docs/core/subagents): Markdown files with YAML
  frontmatter under `.gemini/agents/`; `name` and `description` are required,
  and `kind`, `tools` (an allowlist of Gemini tool names; omitted means every
  tool), `model` (default `inherit`), `temperature`, `max_turns` and
  `timeout_mins` are optional. The `gemini_agents` converter emits `name`,
  `description`, `kind: local`, the source tool grant minus its deny list
  mapped to Gemini tool names (`Read` to `read_file` / `read_many_files` /
  `list_directory`, `Glob` to `glob`, `Grep` to `grep_search`, `Bash` to
  `run_shell_command`, `Write` to `write_file`, `Edit` to `replace`,
  `WebSearch` to `google_web_search`, `WebFetch` to `web_fetch`, `TodoWrite`
  to `write_todos`, per https://geminicli.com/docs/reference/tools), and
  `max_turns` from `maxTurns`. No model is set, so it inherits.
- Memory: the Auto Memory feature scans transcripts and writes candidate diffs
  plus skill drafts to a review inbox (`/memory inbox`), with durable memory
  stored in `GEMINI.md`. There is no `.gemini/memory/` directory; the adapter's
  memory surface is the GEMINI.md context anchor.
- Web-fetch / browser-retrieval (`web_fetch` = **yes**): gemini-cli ships
  built-in `web_fetch` and `google_web_search` tools — the backing dimension for
  `rules/source-accessibility.md` step 1. Evidence: vendor-doc commit-pinned to
  the same immutable snapshot as this adapter's pin (the `Upstream authority`
  commit-sha above, `013914071c5412...`) at the repo-relative docs paths
  `docs/tools/web-fetch.md` (+ `docs/tools/web-search.md`) under
  `github.com/google-gemini/gemini-cli`; snapshot-date 2026-06-21.

## Recommended Postfix Rendering

- Status: supported as plain text.
- Mechanism: Apothem emits the literal ` (Recommended)` suffix in the option label. Gemini CLI-facing templates preserve that suffix as authored.
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

Gemini CLI exposes a vendor extension surface (`gemini extensions install`). The
repo root IS the extension root: `gemini-extension.json` (manifest), `GEMINI.md`
(the manifest's `contextFileName` anchor), and a sibling `commands/apothem.toml`
the harness auto-discovers. Installing the extension *alone* — without running
`apothem install` — persists only what the vendor extension surface carries; the
full per-project cohort still requires the engine, which converts each Apothem
artifact to its Gemini-native shape.

| Artifact class | Persists extension-alone? | Mechanism / limit |
|---|---|---|
| Context anchor (rules-as-text) | Yes | `GEMINI.md` is loaded as session context by `contextFileName`; it now embeds the core engineering disciplines (Plans-Locality, Authority hygiene, Definitiveness, Production-ready, Plain-language) so those directives persist as context text. |
| Commands | Bootstrap only | The bundled `/apothem` command (`commands/apothem.toml`) auto-discovers and persists; it shells `npx @ahmed-g-gad/apothem`. The full converted command cohort (`.gemini/commands/*.toml`) requires `apothem install`. |
| Skills | No — requires `apothem install` | The extension manifest bundles no skills; `.gemini/skills/*/SKILL.md` lands only via the engine. |
| Rules (as native primitive) | No — platform limit | Gemini CLI has no native rules-directory primitive; Apothem rules persist as the `GEMINI.md` context text above, or as the engine-installed `.gemini/.apothem/support/rules/` reference tree. |
| Hooks | No — platform limit | Native `settings.json` hooks are operator-owned; Apothem does not register them. Hook support material lands only via `apothem install` under `.gemini/.apothem/support/hooks/`. |
| MCP servers | No — operator-owned | `mcpServers` lives in operator-owned `settings.json`; neither the extension manifest nor the engine authors MCP entries. |
| Tools / settings | No — operator-owned | `settings.json` is operator-owned and never written by the adapter or the extension. |

Bundle wiring status: the extension bundle persists the context anchor + the
`/apothem` bootstrap command. Embedding the full converted command, skill, and
agent cohort into the extension package is a documented future enhancement —
the conversion logic lives in the engine (`gemini_commands` / `gemini_agents`
modes in `propagation-manifest.yaml`), so a build step that pre-renders those
into a bundled `commands/` + `.gemini/` tree would let the extension carry the
cohort without a post-install engine run.
