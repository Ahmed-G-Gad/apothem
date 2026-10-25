<!-- SPDX-License-Identifier: MIT -->

# Trae Standard Convention Pin

## Snapshot

- Snapshot date: 2026-10-24
- Snapshot note (skills): the adapter now installs skills and command skills at Trae's own `~/.trae/skills/` and the rules and templates corpus at `~/.config/apothem/`. The skills claims were read on 2026-10-24 from the English page through a text-extraction proxy (the page does not render without a browser) and from the Chinese-edition page directly.
- Snapshot note: the docs site renders its text in the browser, so a plain text extractor sees no body, and its `llms.txt` and `.md` variants redirect to a landing page. The rules page's text ships as document JSON inside the page HTML; the rules claims below were read from that text on 2026-10-03. The skills, agents, and MCP claims carry over from the 2026-06-25 reading. Previous 2026-06-25.
- Adapter source: `src/apothem/harnesses/trae/`
- Evidence level: rules page text read 2026-10-03; skills, agents, and MCP pages last read 2026-06-25 (living docs; no-immutable-source exception). No vendor-native UI claim is made here.

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
- TODO(clarify): the Chinese edition (TRAE CN) documents `~/.trae-cn/skills/`,
  and its 2026-06-04 changelog entry (v3.3.63) says the CN and international
  global skill directories are compatible. The changelog was read through a
  summary, not directly. Until a probe on a CN install settles it, the adapter
  writes `~/.trae/skills/` only.
- The vendor also documents Agents (`docs.trae.ai/ide/agent`), `AGENTS.md`, and
  MCP (`.trae/mcp.json`, three transport types). The adapter authors none of
  those. The project `.trae/skills/` folder stays operator-owned.

## Vendor Sources

- <https://docs.trae.ai/ide/rules> (rules directories, activation, nesting;
  retrieved 2026-10-03)
- <https://docs.trae.ai/ide/skills> (skills; retrieved 2026-10-24, the folder the adapter writes)
- <https://docs.trae.ai/ide/agent> (agents; retrieved 2026-06-25)

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
skills at `~/.trae/skills/`, and the rules and templates corpus at
`~/.config/apothem/`, and authors no other cohort.
There is no standalone-installable bundle; every artifact requires the full
`apothem install --harness trae --project <path>` engine run.

| Artifact class | Persists standalone? | Mechanism / limit |
|---|---|---|
| Rules | No — requires `apothem install` | The merged `apothem-rules.md` (carrying the embedded behavioral mandates) is written only by the engine into the vendor-native `.trae/rules/` directory. Nothing persists before that run. |
| Skills and commands | No — requires `apothem install` | The engine writes them as skills to the user-level `~/.trae/skills/`. Nothing persists before that run. |
| Agents | No — adapter scope | Trae documents Agents (`docs.trae.ai/ide/agent`); the adapter authors none of them. |
| Hooks / MCP / Settings | No — operator-owned | `.trae/mcp.json` (MCP) is operator-owned; the adapter authors no entries. |

Apothem ships no Trae plugin or extension, so the files `apothem install` writes
are the sole persistence surface.
