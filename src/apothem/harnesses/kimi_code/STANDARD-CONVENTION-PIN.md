<!-- SPDX-License-Identifier: MIT -->

# Kimi Code Standard Convention Pin

## Snapshot

- Snapshot date: 2026-10-24
- vendor-doc-url: <https://moonshotai.github.io/kimi-code/en/>
- snapshot-date: 2026-10-24
- Canonical docs host: `moonshotai.github.io/kimi-code/en/` (Kimi Code CLI,
  Moonshot). The earlier `moonshotai.github.io/kimi-cli` host documented the
  predecessor CLI and is no longer the authority for this adapter. The
  2026-10-24 refresh read the skills, agents, hooks and config-files pages at
  `www.kimi.com/code/docs/en/kimi-code-cli/` (see Vendor Sources); the refresh
  did not establish whether that host replaces the one above.
- canonical-filename: `AGENTS.md`
- canonical-schema: free-form Markdown agent instructions (the AGENTS.md
  convention); no frontmatter.
- Adapter source: `src/apothem/harnesses/kimi_code/`
- Evidence level: vendor-doc pinned (living docs, no version or commit
  surface; no-immutable-source exception). No vendor-native UI claim is made
  here.

## Official Surface Refresh

- Re-pinned 2026-10-24 for the native skills surface. Read that day on the
  vendor's English and Chinese pages (one vendor, one upstream):
  - Skills, project level: `.kimi-code/skills/` and `.agents/skills/`. The
    project root is the nearest directory containing `.git`, searching upward
    from the working directory, so `--project` must name the repository root
    for Kimi Code to find `<project>/.kimi-code/skills/`.
  - Skills, user level: `$KIMI_CODE_HOME/skills/` (default
    `~/.kimi-code/skills/`) and `~/.agents/skills/`. The Kimi-specific user
    directory moves with `KIMI_CODE_HOME`; `~/.agents/skills/` stays under the
    real OS home. A skill is a subdirectory of a skills directory whose main
    file is named `SKILL.md`.
  - Skills, priority (English page): the page scans four tiers and says "more
    specific scopes take higher priority": Project > User > Extra > Built-in.
    Extra directories come from `extra_skill_dirs` in `config.toml`. The page
    does not rank `.kimi-code/skills/` against `.agents/skills/` inside the
    project tier.
  - Skills, `SKILL.md` frontmatter (English page): `name` and `description`
    (both required in directory form; omitting either one makes parsing fail),
    `type` (`prompt` by default, `inline`, or `flow`; other values are
    skipped), `whenToUse` (also `when-to-use` and `when_to_use`),
    `disableModelInvocation` (also `disable-model-invocation` and
    `disable_model_invocation`), and `arguments`. The page states no rule for a
    key outside that list.
  - Agents, project level: `.kimi-code/agents/` and `.agents/agents/`; user
    level: `$KIMI_CODE_HOME/agents/` and `~/.agents/agents/`. Each directory is
    scanned recursively for `.md` files, and an agent file is "plain Markdown
    with a frontmatter block". Priority: explicit `--agent-file`, then project,
    extra, user, plugin, built-in.
  - Agents, frontmatter (English page): `name` (optional, kebab-case, defaults
    to the file name), `description` (required), `whenToUse`, `override`,
    `tools`, `disallowedTools` and `subagents`. `tools` and `disallowedTools`
    take a YAML list or a comma-separated string; built-in and user tool names
    match exactly and case-sensitively, MCP tools match as `mcp__<server>__*`
    globs, and a name no tool has is reported with a warning. Unknown fields
    are ignored, including those of other agent tools such as Claude Code's
    `model`, and the comma-separated `tools` form keeps Claude Code-style agent
    files loadable.
  - Hooks: all rules are `[[hooks]]` entries in `~/.kimi-code/config.toml`
    (`$KIMI_CODE_HOME/config.toml` when that variable is set). An entry takes
    exactly four fields: `event` (required), `matcher` (optional regular
    expression), `command` (required), `timeout` (optional, seconds, 1 to 600,
    default 30). An extra field makes the config file fail to load.
  - Facts below that this refresh did not re-read keep their 2026-10-03
    retrieval date under Vendor Sources.
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
  and `.agents/skills/` (`SKILL.md` folders). The adapter writes Apothem's
  skills, and its commands wrapped as skills, to `<project>/.kimi-code/skills/`
  (native). It never writes `.agents/skills/`: that folder is shared with other
  tools, so a write there would reach them too. Operator-authored skills with
  other names beside Apothem's in `.kimi-code/skills/` are kept on install,
  update and uninstall. A skill whose name matches an Apothem skill is
  replaced: install and update overwrite its directory (a file of the operator
  skill that Apothem's skill lacks is gone) and uninstall removes it, each after
  a timestamped copy under `~/.apothem/backups/`. The install prints no
  collision notice, and `tests/unit/test_kimi_code_native_skills.py` pins this
  behavior.
- Agents: `~/.kimi-code/agents/`, `.kimi-code/agents/`, `~/.agents/agents/` and
  `.agents/agents/`. The adapter authors none of them; Apothem's agents land in
  the support tree as reference material because the conversion has not been
  scoped: the `tools` entries in their frontmatter are Claude Code tool names,
  which have not been compared with the names Kimi Code matches (see Open
  Questions).
- Hooks: `[[hooks]]` in the user-scope `~/.kimi-code/config.toml`. The adapter
  writes no hooks (see Open Questions). Apothem's hook helpers land in the
  support tree.
- Tool permissions: `default_permission_mode` (`manual`, `yolo`, `auto`) and
  `[[permission.rules]]` entries in `config.toml`. Apothem does not yet project
  its universal-deny floor into them (see Discovery Targets).
- Support tree: the cohorts Apothem does not install natively (rules, agents,
  templates, hooks) land under the Apothem-owned
  `<project>/.kimi-code/.apothem/support/` subtree and are referenced from the
  `AGENTS.md` anchor. They are never written into `.kimi-code/agents/`,
  `.agents/` or other vendor-read directories.
- Migration: an install from before 2026-10-24 held skills at
  `<project>/.kimi-code/.apothem/support/skills/`. That path is in the
  manifest's `stale-sweep` list: an update removes it (after a backup) and
  writes the native directory, and an uninstall removes it too, so each skill is
  present once.
- Web fetch (`web_fetch` = **yes**): Kimi Code ships built-in `FetchURL`
  (returns a page's body text) and `WebSearch` tools, both auto-allowed, backed
  by the `moonshot_fetch` and `moonshot_search` services in `config.toml`.
- Model family: vendor-pinned and selected through the operator's own Kimi Code
  configuration; the adapter authors no model id.

## Vendor Sources

Retrieved 2026-10-24.

- <https://www.kimi.com/code/docs/en/kimi-code-cli/customization/skills.html>
  (skill directories, project and user level, `KIMI_CODE_HOME`)
- <https://www.kimi.com/code/docs/kimi-code-cli/customization/skills.html>
  (the same page, Chinese edition)
- <https://www.kimi.com/code/docs/en/kimi-code-cli/customization/agents.html>
  (agent file locations and format, priority order)
- <https://www.kimi.com/code/docs/kimi-code-cli/customization/agents>
  (the same page, Chinese edition)
- <https://www.kimi.com/code/docs/en/kimi-code-cli/customization/hooks.html>
  (`[[hooks]]` location and four-field schema)
- <https://www.kimi.com/code/docs/kimi-code-cli/customization/hooks.html>
  (the same page, Chinese edition)
- <https://www.kimi.com/code/docs/en/kimi-code-cli/configuration/config-files>
  (`config.toml` location, `hooks` as an `array<table>`)

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

## Open Questions

Each item below is a decision the vendor docs read on 2026-10-24 did not settle.
No Apothem behavior was changed on the strength of a guess; the item names what
stays as it is.

- TODO(clarify): how Kimi Code treats a `SKILL.md` frontmatter key outside the
  list the skills page documents (`name`, `description`, `type`, `whenToUse`,
  `disableModelInvocation`, `arguments`). The page states no rule for an unknown
  key. Apothem ships the source frontmatter unchanged, with no Kimi-specific
  translation. Every shipped skill and command-as-skill carries `name`,
  `description` (both required in directory form) and `disable-model-invocation`
  (a spelling the page accepts), so those three are read. The keys outside the
  documented list are `version`, `updated`, `archetype`, `userInvocable`,
  `argument-hint`, `portability` and `allowed-tools`; until the vendor states a
  rule for them, a key Kimi Code rejects would surface when it loads that skill,
  and a key it ignores changes behavior (a tool restriction that
  `allowed-tools` declares would not apply).
- TODO(clarify): whether to install Apothem's agents natively. The agents page
  documents the file format (see Official Surface Refresh), and says unknown
  fields are ignored and the comma-separated `tools` form stays loadable, so
  Apothem's agent files (frontmatter `name`, `version`, `updated`,
  `description`, `tools`, `disallowedTools`, `maxTurns`, `portability`) would
  load. They stay in the support tree because two points are unsettled: the
  `tools` and `disallowedTools` entries name Claude Code tools such as
  `WebFetch` and `TodoWrite`, and Kimi Code matches tool names case-sensitively
  and warns on a name no tool has, so the names need a comparison with Kimi
  Code's tool list first; and a project-level file in `.kimi-code/agents/` ranks
  above a same-name definition at the extra, user and plugin levels, so
  installing there can override a definition the project already uses. Install
  them natively once both are settled.
- TODO(clarify): hooks. Apothem writes no `[[hooks]]` entry. Three facts decide
  it. (1) The repository has no TOML read-merge-write with a surgical
  uninstall: the shared ownership merge reads and rewrites JSON and YAML, the
  plain-file uninstall deletes a file only when it equals the rendered
  template, the engine supports Python 3.10 where `tomllib` is absent, and no
  TOML writer is vendored. (2) `~/.kimi-code/config.toml` is user scope and
  moves with `KIMI_CODE_HOME`, while this adapter writes under `--project` and
  the install driver refuses a target outside the project root. (3) An entry
  allows exactly four fields and an extra one stops the config from loading, so
  there is no field to mark an entry as Apothem's; removal would have to match
  on the `command` text. Decide whether Apothem takes on a user-scope TOML
  surface before any hook is written.
- TODO(clarify): how Kimi Code ranks `<project>/.kimi-code/skills/` against
  `<project>/.agents/skills/` when both hold a skill of the same name. The
  skills page ranks the tiers (Project > User > Extra > Built-in), so the
  project-level copy this adapter writes takes precedence over a user-level copy
  of the same name, such as the `~/.agents/skills/` copy the Codex adapter
  writes. The page does not rank the two project folders against each other.

## Discovery Targets

- Discovery target: mcp_servers by 2026-12-31 — decide whether Apothem renders
  the profile's MCP inventory into `.kimi-code/mcp.json` or keeps naming it as
  operator-owned.
- Discovery target: tool_surface_restrictions by 2026-12-31 — decide how the
  universal-deny floor maps onto `[[permission.rules]]` in `config.toml`.

## Verification

Adapter output MUST produce an `AGENTS.md` managed block that Kimi Code reads as
project instructions, and MUST write each skill and each command-as-skill to
`<project>/.kimi-code/skills/<name>/SKILL.md`; deviations are findings per
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
native skills under `<project>/.kimi-code/skills/` and an Apothem support tree under
`<project>/.kimi-code/.apothem/support/`. There is no
standalone-installable bundle; every artifact requires the full
`apothem install --harness kimi-code --project <path>` engine run.

| Artifact class | Persists standalone? | Mechanism / limit |
|---|---|---|
| Context anchor (rules-as-text) | No — requires `apothem install` | `AGENTS.md` is written by the engine; nothing persists before that run. |
| Skills / Commands (as skills) | No — requires `apothem install` | Written by the engine to the native `<project>/.kimi-code/skills/`. |
| Rules / Agents / Templates / Hooks | No — deliberate posture | The support tree under the Apothem-owned subtree is engine-materialized as reference material. Kimi Code documents agent files (`.kimi-code/agents/`) and `[[hooks]]` in `~/.kimi-code/config.toml`; the adapter authors neither, for the reasons under Open Questions, not an absence-of-surface claim. |
| MCP servers | No — operator-owned | `.kimi-code/mcp.json` is operator-owned; the adapter authors no entries. |

## Bindings

- Established by ↑ `rules/harness-adapter-shape.md` §6.
- Cross-bound with ↔ `src/apothem/harnesses/kimi_code/__init__.py` (the adapter
  whose discovery walk this pin anchors).
