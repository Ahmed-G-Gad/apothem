<!-- SPDX-License-Identifier: MIT -->

# GitHub Copilot Standard Convention Pin

## Snapshot

- Snapshot date: 2026-06-25
- Snapshot note: live re-verification against `docs.github.com` — `.github/copilot-instructions.md` (repo-wide) + `*.instructions.md` (path-specific `applyTo`, both-used-together) + the Copilot CLI `web_fetch` tool all confirmed current.
- Adapter source: `src/apothem/harnesses/github_copilot/`
- Evidence level: adapter-local projection; no vendor-native UI claim is made here.

## Official Surface Refresh

- Refreshed live 2026-05-31 against the current GitHub Copilot documentation
  (`docs.github.com`). No authority-host move; no immutable version pin is
  exposed (mutable docs site), so every captured convention carries a
  no-immutable-source exception.
- Instruction surface is broader than the single repo-wide file: the vendor
  recognizes `.github/copilot-instructions.md` (repo-wide),
  `.github/instructions/*.instructions.md` (`applyTo` glob, optional
  `excludeAgent`), `AGENTS.md` (nearest-in-tree wins), and root `CLAUDE.md` /
  `GEMINI.md`. The adapter delivers only the repo-wide
  `.github/copilot-instructions.md`; the other anchors are operator-owned and
  read-only.
- The vendor now documents skills (`.github/skills/<name>/SKILL.md`), hooks
  (`.github/hooks/*.json`), and CLI plugins (`plugin.json`). The adapter delivers
  only the instructions file and authors none of those cohorts (deliberate
  preserve-first posture).
- MCP is service / IDE state (`~/.copilot/mcp-config.json`), not a repo-writable
  file, so `capabilities.yml` `mcp_servers` stays `[]`. There is no user-defined
  custom-command creation surface (built-in slash commands only).

## Web-Fetch / Browser-Retrieval Surface

- Capability: `web_fetch` = **yes**. The backing dimension for
  `rules/source-accessibility.md` step 1 ("retrieve through the host's browser /
  fetch capability").
- Vendor-confirmed: GitHub Copilot CLI (the agent-invocable surface, distinct
  from the IDE extension) ships a `web_fetch` tool that retrieves URL content as
  markdown, gated by `--allow-url` / `--deny-url` permissions. This row reflects
  the Copilot CLI tool surface; the adapter itself materializes only
  `.github/copilot-instructions.md` and authors no tool config.
- Evidence: vendor-doc-url
  <https://docs.github.com/en/copilot/concepts/agents/copilot-cli/research>
  (+ `.../how-tos/copilot-cli/set-up-copilot-cli/configure-copilot-cli`);
  snapshot-id living docs; snapshot-date 2026-06-21.

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
Copilot plugin bundle** — the adapter is project-scope instructions-only, writing
a single merged file at `<project>/.github/copilot-instructions.md` and authoring
no other cohort. There is no Apothem-distributable standalone bundle; every
artifact requires the full
`apothem install --harness github-copilot --project <path>` engine run.

| Artifact class | Persists standalone? | Mechanism / limit |
|---|---|---|
| Rules (instructions-as-text) | No — requires `apothem install` | The merged `copilot-instructions.md` (carrying the embedded behavioral mandates) is written only by the engine into the vendor-native `.github/` directory. Nothing persists before that run. |
| Commands / Skills / Agents / Hooks | No — Apothem ships no bundle | Copilot's `plugin.json` / `.github/skills/` / `.github/hooks/` accept these cohorts, but Apothem authors no Copilot plugin; the instructions-only posture is deliberate. There is no user-defined custom-command creation surface (built-in slash commands only). |
| MCP / Settings | No — service/IDE state | MCP lives in `~/.copilot/mcp-config.json` (IDE/service state, not a repo-writable file); the adapter authors no entries (`mcp_servers` stays `[]`). |

Platform note: the vendor plugin surface exists; the Apothem-distributable
plugin bundle does not. The merged instructions file via `apothem install` is the
sole persistence surface.
