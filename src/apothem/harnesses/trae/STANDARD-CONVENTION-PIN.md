<!-- SPDX-License-Identifier: MIT -->

# Trae Standard Convention Pin

## Snapshot

- Snapshot date: 2026-10-27
- Snapshot note (agents): the adapter now installs Apothem's agents as Trae subagents in `<project>/.trae/agents/`. The Subagents page (English, `updated_at` 2026-10-09; Chinese, 2026-10-22), the built-in Agent page and the changelog (2026-10-22) were read on 2026-10-27 from the document JSON the pages ship, the same method as the rules page. Previous 2026-10-24.
- Snapshot note (skills): the adapter now installs skills and command skills at Trae's own `~/.trae/skills/` and the rules and templates corpus at `~/.config/apothem/`. The skills claims were read on 2026-10-24 from the English page through a text-extraction proxy (the page does not render without a browser) and from the Chinese-edition page directly.
- Snapshot note: the docs site renders its text in the browser, so a plain text extractor sees no body, and its `llms.txt` and `.md` variants redirect to a landing page. The rules page's text ships as document JSON inside the page HTML; the rules claims below were read from that text on 2026-10-03. The MCP claims carry over from the 2026-06-25 reading. Previous 2026-06-25.
- Adapter source: `src/apothem/harnesses/trae/`
- Evidence level: rules page text read 2026-10-03; skills page read 2026-10-24; Subagents page and changelog read 2026-10-27; MCP page last read 2026-06-25 (living docs; no-immutable-source exception). The `Trae-AI/TRAE` repository lists no IDE source, so `docs.trae.ai` is the only primary source. No vendor-native UI claim is made here.

## Official Surface Refresh

- Config-root note: the Trae workspace rules directory is `.trae/rules/`
  (project scope); global rules live under `~/.trae/user_rules`
  (`%userprofile%/.trae/user_rules` on Windows), and the rules directory reads
  subfolders up to three levels deep. Re-checked 2026-10-02 and 2026-10-03
  against <https://docs.trae.ai/ide/rules>, which no longer names a
  `project_rules.md` anchor. The adapter is project-scope and writes only a dedicated
  `<project>/.trae/rules/apothem-rules.md` file; it never clobbers other rule
  files in that directory or the global rules.
- Rule activation (re-checked 2026-10-02 and 2026-10-03, same page): a project rule's
  application mode is carried by its frontmatter `alwaysApply` property
  (`true` for Always Apply), with `description` (intelligent apply) or `globs`
  (file-pattern apply) for the other modes. The template emits
  `alwaysApply: true` plus a `description`, as the first content in the file.
  `trigger` is a Windsurf key that Trae does not document. The page also
  documents a `scene: git_message` field for commit-message rules and imports
  a project's `AGENTS.md`, `CLAUDE.md`, and `CLAUDE.local.md`.
- MCP is recognized: `.trae/mcp.json` is operator-owned; the adapter recognizes
  it but does not author entries. `capabilities.yml` `mcp_servers` and the
  shared capability matrix were set accordingly.
- Workspace rules are a `.trae/rules/*.md` directory of Markdown files, not a
  single file; `layered_context_surface` matches.
- Skills (re-read 2026-10-24): project skills live in `.trae/skills/` and
  global skills in `~/.trae/skills/` (`%userprofile%/.trae/skills` on Windows),
  each defined by a `SKILL.md`. The cross-tool `.agents/skills/` folder is read
  only after the setting `Enable .agents Skills Directory` is switched on, and
  `.trae/skills/` wins a name collision; the English page documents
  `~/.agents/skills/` nowhere. The adapter therefore writes Apothem's skills,
  plus its commands wrapped as skills, to `~/.trae/skills/` and not to the
  cross-tool folder.
  TODO(clarify): the vendor docs do not say how Trae treats a `SKILL.md`
  frontmatter key it does not list. The shared emission sets `user-invocable`,
  `disable-model-invocation`, `allowed-tools`, `argument-hint`, and a
  `metadata` map; probe Trae with the full set before a release and, if it
  rejects extras, change `SHARED_TOPLEVEL_KEYS` in `install_driver_shared.py`.
- Skills user folder (re-read 2026-10-27): the English and the Chinese skills
  pages both give `~/.trae/skills` (`%userprofile%/.trae/skills` on Windows).
  The earlier note about a v3.3.63 changelog entry on CN and international
  skill directories is closed: neither changelog contains a 3.3.6x version.
- Agents (read 2026-10-27): a subagent is one Markdown file with YAML
  frontmatter (standard YAML, no BOM) and the system prompt as the body. The
  project folder is `{project_folder}/.trae/agents/<name>.md`, corroborated by
  the changelog entry for v3.5.67 (2026-06-17). A project subagent overrides a
  user subagent of the same name. The adapter writes the project folder only,
  one `<name>.md` per Apothem agent, and a same-named file you wrote there is
  backed up before it is replaced.
- Agent keys: `name` (required; starts with a letter, letters, digits and
  hyphens only, ends with a letter or digit, at most 50 characters) and
  `description` (required; it is the text Trae matches against the request, and
  a file without it cannot be parsed). `tools` and `disallowedTools` are
  comma-separated strings, not YAML lists; `disallowedTools` wins when a tool
  is in both, and an empty `tools` string disables every tool. Also documented
  are `model` (limited to TRAE's built-in model ids) and `mcpServers` (a YAML
  list of servers already configured in the IDE). The adapter writes `name`,
  `description`, `tools` and `disallowedTools` only. It writes no `model` (the
  subagent then uses the model chosen for the Agent in the chat box) and no
  `mcpServers`.
- Agent tools: the vocabulary is Bash, Edit, Glob, Grep, Read, Skill,
  TodoWrite, WebFetch, WebSearch, Write and LSP, plus
  `mcp__<server_name>__<tool_name>` together with `mcpServers`. This is not the
  hook matcher vocabulary (where Bash is RunCommand). The `tools` and
  `disallowedTools` fields carry a source tool only when its name is in that
  list, in the source order, so MultiEdit, NotebookEdit, PowerShell, Monitor,
  Agent, Artifact, TaskCreate and TaskUpdate are left out. A source with `tools`
  is never widened: an allowlist that loses every name is written as an empty
  string instead of being omitted.
- Feature gate: the English page says Settings > Beta > Subagents > Enable
  Subagents Directory must be on. The Chinese page, updated later, says the
  feature is usually on by default. Which applies to the current international
  build is unverified, so the docs page for this adapter names the switch.
- The Subagents page documents no read of `.claude/agents/`, `~/.claude/agents/`
  or `.agents/agents/`, and no turn-limit key, so `maxTurns` is not written.
- TODO(clarify): the Subagents page documents the user folder as
  `~/.trae-cn/agents/` (`%userprofile%/.trae-cn/agents/` on Windows), in both
  editions, while every other user path on the English site uses `~/.trae/`. Which
  of `~/.trae/agents/` and `~/.trae-cn/agents/` an international install reads is
  unverified, so the adapter writes no user-level agents folder.
- TODO(clarify): the docs do not say how Trae treats a frontmatter key it does
  not list, or an invalid `model` value.
- TODO(clarify): whether a `tools` entry that is not in the vocabulary (for
  example NotebookEdit) is ignored or rejected is unverified; the adapter leaves
  such names out.
- TODO(clarify): whether `.trae/agents/` applies to the Agent window of the
  merged "all-new TRAE" (v3.6.x) as it does to the IDE window; the Agent window
  pages carry no subagent text.
- The vendor also documents Agents created in the UI (`docs.trae.ai/ide/agent`,
  shared by link, no file surface), hooks (`hooks.json`, changelog v3.5.66),
  `AGENTS.md`, and MCP (`.trae/mcp.json`, three transport types). The adapter
  authors none of those. The project `.trae/skills/` folder stays
  operator-owned.

## Vendor Sources

- <https://docs.trae.ai/ide/rules> (rules directories, activation, nesting;
  retrieved 2026-10-03)
- <https://docs.trae.ai/ide/skills> (skills; retrieved 2026-10-24, the folder the adapter writes)
- <https://docs.trae.ai/ide/subagents> (subagent file format, keys, tool vocabulary, project and user folders; retrieved 2026-10-27, the folder the adapter writes agents to)
- <https://docs.trae.ai/ide/built-in-agent> (the built-in Agent invokes custom agents and Markdown subagents; retrieved 2026-10-27)
- <https://docs.trae.ai/ide/changelog> (v3.5.67 adds the `.trae/agents` directory and its switch; retrieved 2026-10-27)
- <https://docs.trae.ai/ide/agent> (agents created in the UI, no file surface; retrieved 2026-06-25)

## Discovery Targets

- Discovery target: mcp_servers by 2026-12-31 — re-read the Trae skills, agents,
  and MCP pages, confirm the claims above, and decide
  whether Apothem renders the profile's MCP inventory into `.trae/mcp.json` or
  keeps naming it as operator-owned.

## Recommended Postfix Rendering

- Status: supported as plain text.
- Mechanism: Apothem emits the literal ` (Recommended)` suffix in the option label. Trae rule templates preserve that suffix as authored.
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

Trae exposes **no vendor plugin or extension install surface** that Apothem
ships. The adapter writes a merged rules file at
`<project>/.trae/rules/apothem-rules.md` (alongside, never clobbering, the
operator's other project rules or the `~/.trae/user_rules` global rules), the
agents at `<project>/.trae/agents/`, the skills at `~/.trae/skills/`, and the
rules and templates corpus at `~/.config/apothem/`, and authors no other
cohort.
There is no standalone-installable bundle; every artifact requires the full
`apothem install --harness trae --project <path>` engine run.

| Artifact class | Persists standalone? | Mechanism / limit |
|---|---|---|
| Rules | No — requires `apothem install` | The merged `apothem-rules.md` (carrying the embedded behavioral mandates) is written only by the engine into the vendor-native `.trae/rules/` directory. Nothing persists before that run. |
| Skills and commands | No — requires `apothem install` | The engine writes them as skills to the user-level `~/.trae/skills/`. Nothing persists before that run. |
| Agents | No — requires `apothem install` | The engine writes them as subagents to the project's `.trae/agents/`. Nothing persists before that run. |
| Hooks / MCP / Settings | No — operator-owned | `.trae/mcp.json` (MCP) is operator-owned; the adapter authors no entries. Trae documents `hooks.json`; the adapter authors none. |

Apothem ships no Trae plugin or extension, so the files `apothem install` writes
are the sole persistence surface.
