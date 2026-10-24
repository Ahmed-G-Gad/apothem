<!-- SPDX-License-Identifier: MIT -->

# Qwen Code Standard Convention Pin

## Snapshot

- Snapshot date: 2026-10-24
- Snapshot note: refreshed against `qwenlm.github.io/qwen-code-docs` (settings, commands, sub-agents, skills, hooks, MCP, `.qwenignore`) and the Qwen Code source. The 2026-10-02 adapter changes followed these pages: hook timeouts are written in seconds, the hook interpreter path is quoted, and the extension's `/apothem` command is Markdown, since TOML commands are deprecated. The 2026-10-24 refresh re-checked skills and hooks against the Qwen Code v0.26.0 source: a skill's tool allow-list is the `allowedTools` array, skills are also read from `.agents/skills/`, and hooks have 22 events (see Skills and Hook Events below). Previous 2026-10-03.
- Adapter source: `src/apothem/harnesses/qwen_code/`
- Evidence level: vendor-doc pinned for `~/.qwen/settings.json`, `QWEN.md`
  (`context.fileName`), Markdown+YAML commands (TOML deprecated),
  `.qwen/skills/`, sub-agents (Markdown+YAML), `mcpServers`, settings hooks, and
  `.qwenignore`. The extension command-directory behavior is pinned to commit
  `a011f66944768e05b432a10548ffa4576f1d8ef8` of `FileCommandLoader.ts`. The
  `settings.json` config renders directly (no Jinja template); the shipped
  instruction template is `templates/QWEN.md`. No vendor-native UI claim is made
  here. Docs pages are mutable — no-immutable-source exception for them.
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
  <https://raw.githubusercontent.com/QwenLM/qwen-code/8f8ed0d7c184208ac3fc4b92020b207cec453723/docs/developers/tools/introduction.md>
  (web_fetch listed built-in) +
  <https://raw.githubusercontent.com/QwenLM/qwen-code/8f8ed0d7c184208ac3fc4b92020b207cec453723/docs/developers/tools/web-search.md>
  (web_search removed, MCP-only); commit-sha
  `8f8ed0d7c184208ac3fc4b92020b207cec453723`; snapshot-date 2026-06-21.

## Vendor Sources

Retrieved 2026-10-03 unless marked.

- <https://qwenlm.github.io/qwen-code-docs/en/users/configuration/settings/> (settings, hooks, `mcpServers`)
- <https://qwenlm.github.io/qwen-code-docs/en/users/features/commands/> (Markdown commands)
- <https://qwenlm.github.io/qwen-code-docs/en/users/features/mcp/> (MCP)
- <https://qwenlm.github.io/qwen-code-docs/en/users/features/sub-agents/> (sub-agents; retrieved 2026-10-02)
- <https://qwenlm.github.io/qwen-code-docs/en/users/features/skills/> (skills; retrieved 2026-10-24)
- <https://qwenlm.github.io/qwen-code-docs/en/users/features/hooks/> (hook events, matchers, timeouts; retrieved 2026-10-24)
- <https://raw.githubusercontent.com/QwenLM/qwen-code/v0.26.0/packages/core/src/skills/types.ts> (`parseAllowedToolsField`; retrieved 2026-10-24)
- <https://raw.githubusercontent.com/QwenLM/qwen-code/v0.26.0/packages/core/src/config/storage.ts> (`SKILL_PROVIDER_CONFIG_DIRS`; retrieved 2026-10-24)
- <https://raw.githubusercontent.com/QwenLM/qwen-code/v0.26.0/packages/core/src/skills/skill-manager.ts> (skill base directories; retrieved 2026-10-24)
- <https://raw.githubusercontent.com/QwenLM/qwen-code/v0.26.0/packages/core/src/hooks/types.ts> (`HookEventName`; retrieved 2026-10-24)
- <https://raw.githubusercontent.com/QwenLM/qwen-code/a011f66944768e05b432a10548ffa4576f1d8ef8/packages/cli/src/services/FileCommandLoader.ts> (extension command directories; retrieved 2026-10-02)

## Skills

Pinned to the Qwen Code v0.26.0 source (tag `ac97ce7a`, published 2026-10-21),
retrieved 2026-10-24.

- Tool allow-list key: `SKILL.md` frontmatter only. Qwen Code reads the
  camelCase `allowedTools` key, and its value must be a YAML array of strings;
  any other shape throws `"allowedTools" must be an array`
  (`parseAllowedToolsField` in `packages/core/src/skills/types.ts`). The
  hyphenated `allowed-tools` key written for other agents is ignored (the skills
  page says so, and neither `types.ts` nor `skill-manager.ts` mentions it). The
  `native_skills` install mode therefore rewrites each skill's `allowed-tools`
  string as an `allowedTools` list (`lib/qwen_skill_frontmatter.py`); a plain key
  rename would leave a string that Qwen Code rejects.
- Not changed: sub-agent files keep `tools` and `disallowedTools` in Qwen Code's
  tool names, Markdown commands carry only `description`, and `settings.json`
  holds no allow-list key. No vendor evidence at this snapshot says any of them
  reads `allowedTools`.
- Discovery roots: `SKILL_PROVIDER_CONFIG_DIRS = ['.qwen', '.agents']`
  (`packages/core/src/config/storage.ts`), joined with the project root and with
  the home directory. Qwen Code reads `<project>/.qwen/skills/`,
  `<project>/.agents/skills/`, `~/.qwen/skills/` and `~/.agents/skills/`. A skill
  in a `.qwen` root wins over a same-named skill in the matching `.agents` root.
  Apothem writes `~/.qwen/skills/`, so its copy shadows a same-named skill that
  another adapter wrote to `~/.agents/skills/` (the Codex adapter does). A stale
  comment in `skill-manager.ts` orders the roots `.qwen > .agent > .cursor`; the
  array is what runs. `.claude/skills` is not a default root.
- `TODO(clarify)`: the vendor sources do not say how Qwen Code interprets one
  `allowedTools` entry. Apothem carries each entry as the source writes it,
  including pattern entries such as `Bash(git status *)`. The hooks page says
  permission rules accept Claude Code's `Bash`, `Read` and `Write` names, but no
  check has confirmed the pattern syntax or a mapping to Qwen Code's tool ids.
- `TODO(clarify)`: Qwen Code's `types.ts` documents a hyphenated
  `user-invocable` key where the source corpus writes `userInvocable`, and the
  Claude Code emission already renames it. This pin does not rename it for Qwen
  Code until the key has been checked against the vendor source.

## Hook Events

Pinned to the Qwen Code v0.26.0 source, retrieved 2026-10-24.

- Qwen Code defines 22 hook events (the `HookEventName` enum in
  `packages/core/src/hooks/types.ts`; the hooks page table lists the same 22):
  `PreToolUse`, `PostToolUse`, `PostToolUseFailure`, `PostToolBatch`,
  `Notification`, `UserPromptSubmit`, `UserPromptExpansion`, `SessionStart`,
  `Stop`, `MessageDisplay`, `SubagentStart`, `SubagentStop`, `PreCompact`,
  `PostCompact`, `SessionEnd`, `SessionDelete`, `PermissionRequest`,
  `PermissionDenied`, `StopFailure`, `TodoCreated`, `TodoCompleted`,
  `InstructionsLoaded`.
- Nineteen of the 22 share a name with a Claude Code event. `SessionDelete`,
  `TodoCreated` and `TodoCompleted` do not; Claude Code names the todo events
  `TaskCreated` and `TaskCompleted`.
- Apothem emits `SessionStart`, `PreToolUse`, `PreCompact`, `PostCompact` and
  `Stop`. All five are among the 22, so none is dead config, and none is one of
  the three Qwen Code-only names. A unit test fails when the materializer emits
  a name outside the 22.
- Claude Code compatibility: the hooks page accepts Claude Code tool names in a
  matcher (`"Bash"` and `"Write|Edit"` work unchanged) and sets
  `CLAUDE_PROJECT_DIR`. It does not state that the hook input and output JSON
  match Claude Code's, so this pin does not claim it.

## Discovery Targets

- None. No capability cell for this harness is discovery-pending.

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
(the manifest's `contextFileName` anchor), and `qwen-commands/apothem.md`, which
the manifest's `commands` key names as the extension's command directory. The
shared `commands/` directory keeps the Gemini CLI extension's TOML command; the
`commands` key keeps Qwen Code from reading that deprecated TOML file (the key
is read by `getExtensionCommandsPaths` in
<https://raw.githubusercontent.com/QwenLM/qwen-code/a011f66944768e05b432a10548ffa4576f1d8ef8/packages/cli/src/services/FileCommandLoader.ts>,
retrieved 2026-10-02; a Qwen Code build without the key falls back to
`commands/` and still finds the TOML command). Installing the extension *alone* — without running
`apothem install` — persists only what the vendor extension surface carries; the
full per-target cohort still requires the engine, which converts each Apothem
artifact to its Qwen-native shape (Markdown+YAML commands/agents, `.qwen/skills/`).

| Artifact class | Persists extension-alone? | Mechanism / limit |
|---|---|---|
| Context anchor (rules-as-text) | Yes | `QWEN.md` is loaded as session context by `context.fileName`; it now embeds the core engineering disciplines (Plans-Locality, Authority hygiene, Definitiveness, Production-ready, Plain-language) so those directives persist as context text. |
| Commands | Bootstrap only | The bundled `/apothem` command (`qwen-commands/apothem.md`, Markdown with a `description` frontmatter key) persists; it shells `npx @ahmed-g-gad/apothem`. The full converted command cohort (`~/.qwen/commands/`) requires `apothem install`, and the engine converts it to the Markdown+YAML shape. Qwen Code documents TOML commands as deprecated and shows a migration prompt when it finds one, so the Qwen extension no longer reads the Gemini TOML file. |
| Skills | No — requires `apothem install` | The extension manifest bundles no skills; `~/.qwen/skills/*/SKILL.md` lands only via the engine, with each `allowed-tools` string written as an `allowedTools` list. |
| Rules (as native primitive) | No — platform limit | Qwen Code has no native rules-directory primitive; Apothem rules persist as the `QWEN.md` context text above, or as the engine-installed `~/.qwen/.apothem/support/rules/` reference tree. |
| Hooks | No — requires `apothem install` | The adapter's materializer authors the native `settings.json` `hooks` block (SessionStart, PreToolUse, PreCompact, PostCompact, Stop, all among Qwen Code's 22 events); the extension manifest bundles none, so hooks land only via the engine run. Hook helper material lands under `~/.qwen/.apothem/support/hooks/`. |
| MCP servers | No — requires `apothem install` | The adapter's materializer projects the profile's MCP inventory into the native `settings.json` `mcpServers` block; the extension manifest authors no MCP entries, so they land only via the engine run. |
| Tools / settings | No — requires `apothem install` | `~/.qwen/settings.json` is materializer-rendered by the engine (context anchor, hooks, MCP); the extension manifest writes none of it. |

Bundle wiring status: the extension bundle persists the context anchor + the
`/apothem` bootstrap command. Embedding the full converted command, skill, and
sub-agent cohort into the extension package is a documented future enhancement —
the conversion logic lives in the engine (`markdown_commands` / `qwen_agents`
modes in `propagation-manifest.yaml`), so a build step that pre-renders those
into a bundled `commands/` + `.qwen/` tree would let the extension carry the
cohort without a post-install engine run.
