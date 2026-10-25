<!-- SPDX-License-Identifier: MIT -->

# GitHub Copilot Standard Convention Pin

## Snapshot

- Snapshot date: 2026-10-24
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
  file, agent profile, hook, or plugin.
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
- <https://docs.github.com/en/copilot/how-tos/copilot-on-github/customize-copilot/customize-cloud-agent/create-custom-agents> (agent profiles)

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
`<project>/.github/copilot-instructions.md`, the skills at `~/.agents/skills/`, and
the rules and templates corpus at `~/.config/apothem/`, and authors no other cohort. There is no Apothem-distributable standalone bundle; every
artifact requires the full
`apothem install --harness github-copilot --project <path>` engine run.

| Artifact class | Persists standalone? | Mechanism / limit |
|---|---|---|
| Rules (instructions-as-text) | No — requires `apothem install` | The merged `copilot-instructions.md` (carrying the embedded behavioral mandates) is written only by the engine into the vendor-native `.github/` directory. Nothing persists before that run. |
| Skills and commands | No — requires `apothem install` | The engine writes them as skills to the user-level `~/.agents/skills/`, one copy shared by every project and every tool that reads that folder. Nothing persists before that run, and GitHub-hosted surfaces do not read it. |
| Agents / Hooks | No — Apothem ships no bundle | Copilot's `plugin.json`, prompt files (`.github/prompts/`), agent profiles (`.github/agents/`), and hooks accept these cohorts, but Apothem authors none of them. |
| MCP / Settings | No — operator-owned | MCP lives in repository settings, IDE configuration, the Copilot CLI, or a custom agent profile; the adapter authors no entries (`mcp_servers` stays `[]`). |

Platform note: the vendor plugin surface exists; the Apothem-distributable
plugin bundle does not. The files `apothem install` writes are the sole
persistence surface.
