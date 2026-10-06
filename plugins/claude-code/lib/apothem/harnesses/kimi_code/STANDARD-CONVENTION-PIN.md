<!-- SPDX-License-Identifier: MIT -->

# Kimi Code Standard Convention Pin

## Snapshot

- Snapshot date: 2026-10-03
- vendor-doc-url: <https://moonshotai.github.io/kimi-code/en/>
- snapshot-date: 2026-10-03
- Canonical docs host: `moonshotai.github.io/kimi-code/en/` (Kimi Code CLI,
  Moonshot). The earlier `moonshotai.github.io/kimi-cli` host documented the
  predecessor CLI and is no longer the authority for this adapter.
- canonical-filename: `AGENTS.md`
- canonical-schema: free-form Markdown agent instructions (the AGENTS.md
  convention); no frontmatter.
- Adapter source: `src/apothem/harnesses/kimi_code/`
- Evidence level: vendor-doc pinned (living docs, no version or commit
  surface; no-immutable-source exception). No vendor-native UI claim is made
  here.

## Official Surface Refresh

- Re-pinned 2026-10-03 to the Kimi Code docs at
  `moonshotai.github.io/kimi-code/en/`. This resolves the earlier open question
  about the `.kimi-code/` paths: the current docs place every Kimi Code surface
  under `.kimi-code/` (project) and `~/.kimi-code/` (user, relocatable with
  `KIMI_CODE_HOME`).
- Instructions: project instructions live in `AGENTS.md` or
  `.kimi-code/AGENTS.md` under the project tree; Kimi-specific global
  instructions live in `~/.kimi-code/AGENTS.md`, and cross-tool global
  instructions in `~/.agents/AGENTS.md`. The docs do not say which of the two
  project files wins when both exist, so the adapter keeps writing the
  project-root `AGENTS.md` managed block (operator prose outside the sentinels
  is preserved).
- Configuration: `~/.kimi-code/config.toml` (runtime settings) and
  `~/.kimi-code/tui.toml` (terminal UI). Operator-owned; the adapter writes
  neither.
- MCP: `mcp.json` at two levels, `~/.kimi-code/mcp.json` (user) and
  `.kimi-code/mcp.json` (project, overrides same-named user entries; stdio
  entries prompt through workspace trust). Operator-owned; the adapter names
  the project file and authors no entries.
- Skills: `~/.kimi-code/skills/`, `~/.agents/skills/`, `.kimi-code/skills/`,
  and `.agents/skills/` (`SKILL.md` folders). Agents: `~/.kimi-code/agents/`
  and `.kimi-code/agents/`. The adapter authors neither; Apothem's skills and
  agents land in the support tree as reference material (deliberate
  AGENTS.md-anchor posture).
- Tool permissions: `default_permission_mode` (`manual`, `yolo`, `auto`) and
  `[[permission.rules]]` entries in `config.toml`. Apothem does not yet project
  its universal-deny floor into them (see Discovery Targets).
- Support tree: non-native Markdown cohorts (rules, commands, skills, agents,
  templates, hooks) land under the Apothem-owned
  `<project>/.kimi-code/.apothem/support/` subtree and are referenced from the
  `AGENTS.md` anchor. They are never written into `.kimi-code/skills/`,
  `.kimi-code/agents/`, or other vendor-read directories.
- Web fetch (`web_fetch` = **yes**): Kimi Code ships built-in `FetchURL`
  (returns a page's body text) and `WebSearch` tools, both auto-allowed, backed
  by the `moonshot_fetch` and `moonshot_search` services in `config.toml`.
- Model family: vendor-pinned and selected through the operator's own Kimi Code
  configuration; the adapter authors no model id.

## Vendor Sources

Retrieved 2026-10-03.

- <https://moonshotai.github.io/kimi-code/en/> (docs home)
- <https://moonshotai.github.io/kimi-code/en/customization/agents> (instruction
  files, agent files, `SYSTEM.md`)
- <https://moonshotai.github.io/kimi-code/en/configuration/config-files>
  (`config.toml`, permissions, services)
- <https://moonshotai.github.io/kimi-code/en/customization/mcp> (`mcp.json`)
- <https://moonshotai.github.io/kimi-code/en/customization/skills> (skill
  directories)
- <https://moonshotai.github.io/kimi-code/en/reference/tools> (`FetchURL`,
  `WebSearch`)

## Discovery Targets

- Discovery target: mcp_servers by 2026-12-31 — decide whether Apothem renders
  the profile's MCP inventory into `.kimi-code/mcp.json` or keeps naming it as
  operator-owned.
- Discovery target: tool_surface_restrictions by 2026-12-31 — decide how the
  universal-deny floor maps onto `[[permission.rules]]` in `config.toml`.

## Verification

Adapter output MUST produce an `AGENTS.md` managed block that Kimi Code reads as
project instructions; deviations are findings per
`rules/harness-adapter-shape.md` §4 Standard-Conformance.

## MCP Surface Projection

- Status: `.kimi-code/mcp.json` (project) and `~/.kimi-code/mcp.json` (user) are
  the documented MCP surfaces. Apothem names the project file in
  `capabilities.yml` and authors no entries.
- Boundary: the registry capability cell stays `discovery-pending` until the
  target above is resolved.

## Tool-Surface Restriction Projection

- Status: `discovery-pending`. The vendor surface is now identified
  (`default_permission_mode` and `[[permission.rules]]` in `config.toml`); the
  projection of the universal-deny floor (secrets paths, destructive shell ops,
  network-write to unsigned endpoints) into it is not yet built. The floor binds
  regardless per `rules/agent-capability-discipline.md` §5 and is named in
  `capabilities.yml` under `tool_surface_restrictions`.

## Recommended Postfix Rendering

- Status: supported as plain text.
- Mechanism: Apothem emits the literal ` (Recommended)` suffix in the option
  label. Kimi Code-facing prompts and fallback text preserve that suffix as
  authored.
- Boundary: this pin does not claim a harness-native recommended-option widget.
  It only pins the text-rendered convention used by
  `rules/interactive-questions.md`.

## Long Context and Compaction

- Status: profile-managed.
- Mechanism: Apothem keeps full-suite `/plan-execute` runs continuous by
  externalizing state to `.apothem/plans/`, compacting or restarting the harness session
  at phase boundaries as needed, and restoring via the Blind Bootstrap sequence.
- Boundary: this pin does not claim vendor-native autocompaction or a
  long-context size. It pins the adapter-local state handoff and
  compaction-restoration convention used by `rules/context-management.md`.

## Large-Codebase Practice Projection

- Layered context: declared in `capabilities.yml` under
  `layered_context_surface` — `AGENTS.md` plus the support tree; no vendor-native
  hierarchy is claimed beyond the adapter's documented file/template surface.
- LSP symbol navigation: `tracked-gap` until a vendor-ratified plugin or tool
  surface is pinned.
- Hook learning capture: routed through the `persistent-conventions-vigilance`
  artifact-evolution cycle; pass-class hooks stay silent and recurring findings
  become rule, skill, hook, or documentation updates.

## Refresh cadence

Re-verify against vendor reality every 90 days. On refresh, update the snapshot
date, the retrieval date under Vendor Sources, and any moved URL in the same
change-set, and emit a `[Pin — refreshed: kimi_code; …]` ledger entry per
`rules/disclosure-ledger.md`. A pin older than 90 days, or a discovery target
past its date, fails `scripts/dev/validate_harness_convention_pins.py`.

## Plugin-alone Persistence

Kimi Code exposes **no vendor plugin or extension install surface** that Apothem
ships. The adapter is project-scope: it writes the `AGENTS.md` managed block plus
an Apothem support tree under `<project>/.kimi-code/.apothem/support/`. There is no
standalone-installable bundle; every artifact requires the full
`apothem install --harness kimi-code --project <path>` engine run.

| Artifact class | Persists standalone? | Mechanism / limit |
|---|---|---|
| Context anchor (rules-as-text) | No — requires `apothem install` | `AGENTS.md` is written by the engine; nothing persists before that run. |
| Rules / Commands / Skills / Agents / Templates | No — deliberate posture | The support tree under the Apothem-owned subtree is engine-materialized as reference material. Kimi Code documents native skills (`.kimi-code/skills/`), agent files (`.kimi-code/agents/`), and slash commands; the adapter authors none of them (deliberate AGENTS.md-anchor posture), not an absence-of-surface claim. |
| MCP servers | No — operator-owned | `.kimi-code/mcp.json` is operator-owned; the adapter authors no entries. |

## Bindings

- Established by ↑ `rules/harness-adapter-shape.md` §6.
- Cross-bound with ↔ `src/apothem/harnesses/kimi_code/__init__.py` (the adapter
  whose discovery walk this pin anchors).
