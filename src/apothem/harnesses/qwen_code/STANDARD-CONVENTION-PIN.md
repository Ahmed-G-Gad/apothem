<!-- SPDX-License-Identifier: MIT -->

# Qwen Code Standard Convention Pin

## Snapshot

- Snapshot date: 2026-06-25
- Snapshot note: live re-verification against `qwenlm.github.io/qwen-code-docs` + `github.com/QwenLM/qwen-code` — `~/.qwen/QWEN.md` (`context.fileName`, `@path` imports, `/memory` reload), Markdown+YAML custom commands (TOML deprecated), and settings.json / `mcpServers` / `.qwen/skills/` / hooks all confirmed current.
- Adapter source: `src/apothem/harnesses/qwen_code/`
- Evidence level: vendor-doc pinned (live re-fetch 2026-05-31) at release tag
  `v0.17.0` for `~/.qwen/settings.json`, `QWEN.md` (`context.fileName`),
  Markdown+YAML commands (TOML deprecated), `.qwen/skills/`, SubAgents
  (Markdown+YAML), `mcpServers`, settings hooks, and `.qwenignore`. The
  `settings.json` config renders directly (no Jinja template); the shipped
  instruction template is `templates/QWEN.md`. No vendor-native UI claim is made
  here. Docs pages are mutable — no-immutable-source exception anchored to the
  immutable release tag `v0.17.0`.
- Official references:
  - <https://qwenlm.github.io/qwen-code-docs/en/users/configuration/settings/>
  - <https://qwenlm.github.io/qwen-code-docs/en/users/features/commands/>
  - <https://qwenlm.github.io/qwen-code-docs/en/users/features/sub-agents/>
  - <https://qwenlm.github.io/qwen-code-docs/en/users/features/skills/>
  - <https://qwenlm.github.io/qwen-code-docs/en/users/features/hooks/>
  - <https://qwenlm.github.io/qwen-code-docs/en/users/configuration/qwen-ignore/>

## Web-Fetch / Browser-Retrieval Surface

- Capability: `web_fetch` = **partial**. The backing dimension for
  `rules/source-accessibility.md` step 1 ("retrieve through the host's browser /
  fetch capability").
- Vendor-confirmed PARTIAL: qwen-code ships a built-in `web_fetch` tool (URL
  retrieval), but the built-in `web_search` tool was removed and web search is
  now MCP-only (a documented breaking change). The `partial` subset boundary is:
  fetch yes, search via MCP only.
- Evidence: vendor-doc-url
  <https://github.com/QwenLM/qwen-code/blob/8f8ed0d7c184208ac3fc4b92020b207cec453723/docs/developers/tools/introduction.md>
  (web_fetch listed built-in) +
  <https://github.com/QwenLM/qwen-code/blob/8f8ed0d7c184208ac3fc4b92020b207cec453723/docs/developers/tools/web-search.md>
  (web_search removed, MCP-only); commit-sha
  `8f8ed0d7c184208ac3fc4b92020b207cec453723` (default-branch HEAD, both blobs
  confirmed reachable at this commit); snapshot-date 2026-06-21.

## Recommended Postfix Rendering

- Status: supported as plain text.
- Mechanism: Apothem emits the literal ` (Recommended)` suffix in the option label. Qwen Code adapter output preserves that suffix when prompt text is materialized.
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

Qwen Code exposes a vendor extension surface (`qwen extensions install`). The
repo root IS the extension root: `qwen-extension.json` (manifest), `QWEN.md`
(the manifest's `contextFileName` anchor), and a sibling `commands/apothem.toml`
the harness auto-discovers. Installing the extension *alone* — without running
`apothem install` — persists only what the vendor extension surface carries; the
full per-target cohort still requires the engine, which converts each Apothem
artifact to its Qwen-native shape (Markdown+YAML commands/agents, `.qwen/skills/`).

| Artifact class | Persists extension-alone? | Mechanism / limit |
|---|---|---|
| Context anchor (rules-as-text) | Yes | `QWEN.md` is loaded as session context by `context.fileName`; it now embeds the core engineering disciplines (Plans-Locality, Authority hygiene, Definitiveness, Production-ready, Plain-language) so those directives persist as context text. |
| Commands | Bootstrap only | The bundled `/apothem` command (`commands/apothem.toml`) auto-discovers and persists; it shells `npx @ahmed-g-gad/apothem`. The full converted command cohort (`~/.qwen/commands/`) requires `apothem install`, and the engine converts it to the current Markdown+YAML shape. The bootstrap file stays TOML deliberately: the snapshot above records TOML as **deprecated, not removed** — still auto-discovered by the harness — and this file is what launches the engine (it shells `npx`), so it is read before any conversion could run. Migrate it when the vendor drops TOML discovery; until then the two formats coexist by design, not by oversight. |
| Skills | No — requires `apothem install` | The extension manifest bundles no skills; `~/.qwen/skills/*/SKILL.md` lands only via the engine. |
| Rules (as native primitive) | No — platform limit | Qwen Code has no native rules-directory primitive; Apothem rules persist as the `QWEN.md` context text above, or as the engine-installed `~/.qwen/.apothem/support/rules/` reference tree. |
| Hooks | No — requires `apothem install` | The adapter's materializer authors the native `settings.json` `hooks` block (SessionStart, PreToolUse, PreCompact, PostCompact, Stop); the extension manifest bundles none, so hooks land only via the engine run. Hook helper material lands under `~/.qwen/.apothem/support/hooks/`. |
| MCP servers | No — requires `apothem install` | The adapter's materializer projects the profile's MCP inventory into the native `settings.json` `mcpServers` block; the extension manifest authors no MCP entries, so they land only via the engine run. |
| Tools / settings | No — requires `apothem install` | `~/.qwen/settings.json` is materializer-rendered by the engine (context anchor, hooks, MCP); the extension manifest writes none of it. |

Bundle wiring status: the extension bundle persists the context anchor + the
`/apothem` bootstrap command. Embedding the full converted command, skill, and
sub-agent cohort into the extension package is a documented future enhancement —
the conversion logic lives in the engine (`markdown_commands` / `qwen_agents`
modes in `propagation-manifest.yaml`), so a build step that pre-renders those
into a bundled `commands/` + `.qwen/` tree would let the extension carry the
cohort without a post-install engine run.
