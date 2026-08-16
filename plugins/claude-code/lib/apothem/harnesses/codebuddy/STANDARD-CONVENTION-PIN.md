<!-- SPDX-License-Identifier: MIT -->

# CodeBuddy Standard Convention Pin

## Snapshot

- Snapshot date: 2026-06-25
- Snapshot note: live re-verification against `www.codebuddy.ai/docs` surfaced a STALENESS CORRECTION — the vendor DOES document a fuller CodeBuddy Code CLI surface (Skills `/docs/cli/skills`, Sub-Agents `/docs/cli/sub-agents`, Slash Commands `/docs/cli/slash-commands`, Plugins `/docs/cli/plugins-reference`); the prior pin called these "undocumented". The adapter's rules-only delivery remains a DELIBERATE preserve-first posture, not an absence-of-surface claim. Rules (`.codebuddy/rules/*.md` auto-loaded as project memory; `alwaysApply` / `paths` frontmatter), `CODEBUDDY.md` (`/init`), and `.codebuddy/settings.json` (permissions + JSONC MCP) all confirmed current. Previous 2026-06-09.
- Adapter source: `src/apothem/harnesses/codebuddy/`
- Evidence level: adapter-local projection; no vendor-native UI claim is made here.

## Official Surface Refresh

- Refreshed live 2026-06-09 against the current CodeBuddy documentation
  (`www.codebuddy.ai/docs`). No authority-host move; no immutable version pin
  is exposed (mutable docs site), so every captured convention carries a
  no-immutable-source exception.
- Canonical filename: `.codebuddy/rules/apothem-rules.md`. CodeBuddy reads
  project rules from `.codebuddy/rules/*.md` (Markdown with optional YAML
  frontmatter: `alwaysApply`, `paths`, `enabled`) per
  https://www.codebuddy.ai/docs/ide/Rules. The adapter is project-scope and
  writes only `<project>/.codebuddy/rules/apothem-rules.md`, a dedicated file
  that never clobbers operator-authored rules.
- Memory file: `CODEBUDDY.md` at the project root is the operator-owned memory
  surface (https://www.codebuddy.ai/docs/cli/memory); the adapter does not
  author it.
- MCP and permissions: `.codebuddy/settings.json` is the project-scope
  settings surface (https://www.codebuddy.ai/docs/cli/settings) where MCP
  servers and permissions are declared. It is operator-owned; the adapter
  recognizes it but does not author entries. `capabilities.yml` `mcp_servers`
  and the shared capability matrix were refreshed accordingly.
- The vendor documents project rules, a project memory file, a settings
  surface, and a fuller CodeBuddy Code CLI surface (Skills, Sub-Agents, Slash
  Commands, Plugins — see the `/docs/cli/*` references above). The adapter
  delivers only the project rules file and authors none of those other surfaces:
  this is a DELIBERATE rules-only / preserve-first posture, not a claim that the
  surfaces are absent. Status-lines remain undocumented as an adapter-owned file
  surface.

## Recommended Postfix Rendering

- Status: supported as plain text.
- Mechanism: Apothem emits the literal ` (Recommended)` suffix in the option label. CodeBuddy rule templates preserve that suffix as authored.
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

CodeBuddy exposes **no vendor plugin or extension install surface** that Apothem
ships. The adapter is project-scope rules-only: it writes a single merged rules
file at `<project>/.codebuddy/rules/apothem-rules.md` and authors no other
cohort. There is no standalone-installable bundle; every artifact requires the
full `apothem install --harness codebuddy --project <path>` engine run.

| Artifact class | Persists standalone? | Mechanism / limit |
|---|---|---|
| Rules | No — requires `apothem install` | The merged `apothem-rules.md` (carrying the embedded behavioral mandates) is written only by the engine into the vendor-native `.codebuddy/rules/` directory. Nothing persists before that run. |
| Commands / Skills / Agents | No — deliberate rules-only posture | CodeBuddy DOES document CLI Skills / Sub-Agents / Slash Commands / Plugins, but the adapter authors none of them (preserve-first rules-only delivery); these cohorts are not materialized for this harness by design. |
| Hooks / MCP / Tools / Settings | No — operator-owned / platform limit | `.codebuddy/settings.json` (MCP + permissions) and `CODEBUDDY.md` memory are operator-owned; the adapter authors no entries. |

Platform limit: CodeBuddy ships no marketplace/extension channel, so a
plugin-alone story does not exist for this harness — the merged rules file via
`apothem install` is the sole persistence surface.
