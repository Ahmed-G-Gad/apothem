<!-- SPDX-License-Identifier: MIT -->

# GitHub Copilot Standard Convention Pin

## Snapshot

- Snapshot date: 2026-10-28
- Snapshot note (review): the tool aliases table of the custom-agents reference was re-read on 2026-10-28 for the `web` and `todo` cloud-agent notes and the `agent` alias. Previous 2026-10-27.
- Snapshot note (agents): the adapter now installs Apothem's agents as custom agent profiles in `<project>/.github/agents/`. The custom-agents reference and how-to pages, the CLI config-directory reference, the VS Code agent pages and the Copilot CLI changelog were read on 2026-10-27 (the changelog from its raw file, whole). Previous 2026-10-24.
- Snapshot note: the adapter now installs skills and command skills at the shared `~/.agents/skills/` and the rules and templates corpus at `~/.config/apothem/`. Refreshed against `docs.github.com/en/copilot`. Corrections: Copilot has user-defined commands (prompt files in `.github/prompts/*.prompt.md`, run as `/name` in Copilot Chat) and repository agent files (`.github/agents/*.agent.md`), and MCP can be configured in a custom agent profile as well as in repository settings, the IDE, and the Copilot CLI. Code review reads instructions from the pull request's head branch and no longer documents a fixed character cap. Previous 2026-06-25.
- Adapter source: `src/apothem/harnesses/github_copilot/`
- Evidence level: vendor-doc pinned (living docs; no-immutable-source exception). No vendor-native UI claim is made here.

## Official Surface Refresh

- Instructions: `.github/copilot-instructions.md` (repository-wide),
  `.github/instructions/*.instructions.md` (path-specific, `applyTo` glob), and
  agent instructions in `AGENTS.md` (the nearest in the tree wins) or a root
  `CLAUDE.md` / `GEMINI.md`. The adapter writes only
  `.github/copilot-instructions.md`. Zed also reads that file when no
  higher-priority instruction file exists, so the block is tool-neutral and the
  registry records Copilot as the file's owner.
- Code review: Copilot reads repository instructions, agent instructions, and
  skills from the pull request's head branch. GitHub's guidance is that shorter
  instruction files are more likely to be fully processed (about 1,000 lines at
  most), so the adapter puts the operator's profile section first in its block.
- Commands and agents: prompt files (`.github/prompts/*.prompt.md`) run as
  `/name` slash commands in Copilot Chat in VS Code, and custom agents are
  `.github/agents/*.agent.md` profiles. Skills (`.github/skills/<name>/SKILL.md`),
  hooks, and CLI plugins are also documented. The adapter authors no prompt
  file, hook, or plugin; it writes the agent profiles described next.
- Agent profiles (read 2026-10-27): the repository folder is
  `.github/agents/<name>.agent.md`; the CLI and VS Code also accept a plain `.md`.
  The user folder is `~/.copilot/agents/` (`$COPILOT_HOME/agents/` when that is
  set), and organization and enterprise agents live in the `agents/` folder of the
  `.github` or `.github-private` repository. The Copilot CLI also discovers the
  repository's `.claude/agents/` (changelog 1.0.62) and has not loaded `~/.claude/`
  agents since 1.0.36, so the Claude Code adapter's `~/.claude/agents/` does not
  reach Copilot (the registry records Copilot as no reader of it). A file name may
  hold only `.`, `-`, `_`, letters and digits, and the name without `.md` or
  `.agent.md` is the agent's id.
- Agent keys: `description` (required, the one key GitHub marks required), `name`
  (defaults to the file name), `target` (`vscode` or `github-copilot`; unset means
  both), `tools`, `model`, `disable-model-invocation`, `user-invocable`, `infer`
  (retired), and `mcp-servers` and `metadata` (neither used in VS Code or other IDE
  agents). Four keys the first reading missed: `include-custom-instructions` (CLI
  1.0.86), `model-policy` (1.0.83), `deferred-tool-loading` (1.0.52) and
  `reasoning-effort` (VS Code, Copilot harness). VS Code adds `argument-hint`,
  `agents`, `handoffs` and `hooks`; the cloud agent ignores `handoffs` and
  `argument-hint`. The CLI warns about an unknown key and still loads the file
  (changelog 0.0.415).
- Agent tools: `tools` takes a list or a comma-separated string. Omitted or
  `["*"]` enables every tool, `[]` enables none, and an unrecognized name is ignored.
  There is no deny key. The names are case-insensitive aliases, each covering a
  group: `execute` (Bash, shell, powershell), `read` (Read, NotebookRead), `edit`
  (Edit, MultiEdit, Write, NotebookEdit), `search` (Grep, Glob), `agent`
  (custom-agent, Task), `web` (WebSearch, WebFetch) and `todo` (TodoWrite). MCP
  tools are written `server/tool` or `server/*`. The cloud agent does not honor
  `web` and `todo`; the `web` alias covers both WebSearch and WebFetch, so the
  three agents that search the web (citation-auditor, fact-checker,
  research-scout) can read and search files there but can neither search the web
  nor fetch pages. A source tool with a pattern, such as `Bash(git status)`, has
  no alias form: a patterned grant is left out (it is never widened to the whole
  tool's alias) and a patterned denial drops the alias of the whole tool.
- Agents the adapter writes: one `<name>.agent.md` per Apothem agent in
  `<project>/.github/agents/`, with `name`, `description` and `tools` as a flow
  list of aliases, for example `tools: ["read", "search", "execute"]`. Because
  Copilot has no deny key, the source `tools` minus `disallowedTools` is compiled
  into the allowlist: an alias is left out when the source denies any tool it
  covers (a grant of `Write` with `Edit` denied loses `edit`), a source tool with
  no alias (Monitor, an `mcp__` entry) is left out, and a grant that loses every
  alias is written as `tools: []`, never omitted. No `model`, `target`,
  `disable-model-invocation`, `user-invocable`, `mcp-servers`, `metadata` or VS Code
  key is written, nor `maxTurns`, `version`, `updated` or `portability`. A
  same-named `.agent.md` you wrote there is backed up before it is replaced. The
  adapter never writes `.agents/agents/`, `~/.copilot/agents/` or the Claude Code
  agents folder; `~/.copilot/agents/` is a possible user-level follow-up, because
  the adapter is project scope.
- Committed folder: `.github/agents/` is part of the repository. Teammates and the
  cloud coding agent read the same files, unlike the skills in
  `~/.agents/skills/`, which stay on the machine.
- TODO(clarify): whether Copilot prefers `.github/agents/` or `.claude/agents/`
  when both hold an agent of one name, and what it does when a folder holds both
  `x.md` and `x.agent.md`.
- TODO(clarify): how the cloud agent and VS Code treat a frontmatter key they do
  not list (the CLI warns), and whether the cloud agent reads only `.github/agents/`
  plus the organization and enterprise repositories.
- Skills: the agent-skills page lists `~/.agents/skills/` among the personal
  skill locations, so the adapter writes Apothem's skills, plus its commands
  wrapped as skills, to that one user-level copy shared with Codex, Cursor,
  Windsurf, and Zed. The folder is on the machine: the cloud agent and code review
  on GitHub run elsewhere and do not see it (the repository's own `.github/skills/`
  is what they read), so the instructions block carries the disciplines in full.
  TODO(clarify): the vendor docs do not say how Copilot treats a `SKILL.md`
  frontmatter key it does not list. The shared emission sets `user-invocable`,
  `disable-model-invocation`, `allowed-tools`, `argument-hint`, and a
  `metadata` map; probe Copilot with the full set before a release and, if it
  rejects extras, change `SHARED_TOPLEVEL_KEYS` in `install_driver_shared.py`.
- MCP: configured in repository settings for the cloud agent, in IDE
  configuration, in the Copilot CLI, or in a custom agent profile. The adapter
  authors no entries, so `capabilities.yml` `mcp_servers` stays `[]`.

## Web-Fetch / Browser-Retrieval Surface

- Capability: `web_fetch` = **yes**. The backing dimension for
  `rules/source-accessibility.md` step 1 ("retrieve through the host's browser /
  fetch capability").
- Vendor-confirmed: GitHub Copilot CLI (the agent-invocable surface, distinct
  from the IDE extension) ships a `web_fetch` tool that retrieves URL content.
  URL permissions apply to it: `--allow-url` pre-approves a domain and
  `--deny-url` denies one. This row reflects the Copilot CLI tool surface; the
  adapter itself materializes only `.github/copilot-instructions.md` and
  authors no tool config.
- Evidence: vendor-doc-url
  <https://docs.github.com/en/copilot/how-tos/copilot-cli/set-up-copilot-cli/configure-copilot-cli>;
  snapshot-id living docs; retrieved 2026-10-19. The page previously cited
  here moved and no longer names the tool or its URL permissions.

## Vendor Sources

Retrieved 2026-10-03 unless marked.

- <https://docs.github.com/en/copilot/how-tos/copilot-on-github/customize-copilot/add-custom-instructions/add-repository-instructions> (instruction files)
- <https://docs.github.com/en/copilot/tutorials/customize-code-review> (code review and instruction length)
- <https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/add-custom-instructions> (Copilot CLI instructions)
- <https://docs.github.com/en/copilot/concepts/customizations/agent-skills> (skills; the folder the adapter writes, retrieved 2026-10-25)
- <https://docs.github.com/en/copilot/tutorials/customization-library/prompt-files/your-first-prompt-file> (prompt files; retrieved 2026-10-02)
- <https://docs.github.com/en/copilot/how-tos/copilot-on-github/customize-copilot/customize-cloud-agent/create-custom-agents> (agent profiles in `.github/agents/`; retrieved 2026-10-27, the folder the adapter writes agents to)
- <https://docs.github.com/en/copilot/reference/custom-agents-configuration> (agent keys, `tools` and the tool aliases; retrieved 2026-10-27)
- <https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/create-custom-agents-for-cli> (CLI agent folders and ids; retrieved 2026-10-27)
- <https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-config-dir-reference> (`~/.copilot/agents/` and `COPILOT_HOME`; retrieved 2026-10-27)
- <https://raw.githubusercontent.com/github/copilot-cli/main/changelog.md> (custom agents 0.0.353, unknown keys warn 0.0.415, `~/.claude/` agents dropped 1.0.36, `.claude/agents` discovery 1.0.62; retrieved 2026-10-27)
- <https://code.visualstudio.com/docs/agent-customization/custom-agents> (VS Code agent folders; retrieved 2026-10-27)
- <https://code.visualstudio.com/docs/agents/reference/custom-agent-file-reference> (VS Code agent keys; retrieved 2026-10-27)

## Discovery Targets

- None. No capability cell for this harness is discovery-pending.

## Recommended Postfix Rendering

- Status: supported as plain text.
- Mechanism: Apothem emits the literal ` (Recommended)` suffix in the option label. GitHub Copilot instruction templates preserve that suffix as authored.
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

GitHub Copilot documents skills (`.github/skills/<name>/SKILL.md`), hooks
(`.github/hooks/*.json`), and CLI plugins (`plugin.json`), but **Apothem ships no
Copilot plugin bundle** — the adapter writes a merged file at
`<project>/.github/copilot-instructions.md`, the agents at
`<project>/.github/agents/`, the skills at `~/.agents/skills/`, and
the rules and templates corpus at `~/.config/apothem/`, and authors no other cohort. There is no Apothem-distributable standalone bundle; every
artifact requires the full
`apothem install --harness github-copilot --project <path>` engine run.

| Artifact class | Persists standalone? | Mechanism / limit |
|---|---|---|
| Rules (instructions-as-text) | No — requires `apothem install` | The merged `copilot-instructions.md` (carrying the embedded behavioral mandates) is written only by the engine into the vendor-native `.github/` directory. Nothing persists before that run. |
| Skills and commands | No — requires `apothem install` | The engine writes them as skills to the user-level `~/.agents/skills/`, one copy shared by every project and every tool that reads that folder. Nothing persists before that run, and GitHub-hosted surfaces do not read it. |
| Agents | No — requires `apothem install` | The engine writes them as custom agent profiles to the project's `.github/agents/`. Nothing persists before that run. |
| Hooks | No — Apothem ships no bundle | Copilot's `plugin.json`, prompt files (`.github/prompts/`), and hooks accept these cohorts, but Apothem authors none of them. |
| MCP / Settings | No — operator-owned | MCP lives in repository settings, IDE configuration, the Copilot CLI, or a custom agent profile; the adapter authors no entries (`mcp_servers` stays `[]`). |

Platform note: the vendor plugin surface exists; the Apothem-distributable
plugin bundle does not. The files `apothem install` writes are the sole
persistence surface.
