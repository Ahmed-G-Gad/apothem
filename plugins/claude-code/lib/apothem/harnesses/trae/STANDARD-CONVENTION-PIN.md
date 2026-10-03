<!-- SPDX-License-Identifier: MIT -->

# Trae Standard Convention Pin

## Snapshot

- Snapshot date: 2026-06-25
- Snapshot note: live re-verification against `docs.trae.ai` surfaced findings: (1) STALENESS — the pin framed Trae's agent surface as absent, but the vendor documents Agents (`docs.trae.ai/ide/agent`, create + manage); (2) skills live in BOTH `.trae/skills/` AND the cross-tool `.agents/skills/` (with `.trae/skills/` winning name collisions) — the pin cited only `.trae/skills/`; (3) `.trae/rules/` supports recursive subfolders up to three levels of nesting. The adapter's rules-only delivery remains a DELIBERATE posture. `.trae/rules/` + `project_rules.md`/`user_rules.md` anchors, AGENTS.md, and MCP (`.trae/mcp.json`, three transport types) all confirmed current. Previous 2026-06-09.
- Adapter source: `src/apothem/harnesses/trae/`
- Evidence level: adapter-local projection; no vendor-native UI claim is made here.

## Official Surface Refresh

- Refreshed live 2026-06-09 against the current Trae documentation
  (`docs.trae.ai`, https://docs.trae.ai/ide/rules). No authority-host move; no
  immutable version pin is exposed (mutable docs site), so every captured
  convention carries a no-immutable-source exception.
- Config-root note: the Trae workspace rules directory is `.trae/rules/`
  (project scope); global rules live under `~/.trae/user_rules`
  (`%userprofile%/.trae/user_rules` on Windows). Re-checked 2026-10-02 against
  https://docs.trae.ai/ide/rules, which no longer names a `project_rules.md`
  anchor. The adapter is project-scope and writes only a dedicated
  `<project>/.trae/rules/apothem-rules.md` file; it never clobbers other rule
  files in that directory or the global rules.
- Rule activation (re-checked 2026-10-02, same page): a project rule's
  application mode is carried by its frontmatter `alwaysApply` property
  (`true` for Always Apply), with `description` (intelligent apply) or `globs`
  (file-pattern apply) for the other modes. The template emits
  `alwaysApply: true` plus a `description`, as the first content in the file.
  `trigger` is a Windsurf key that Trae does not document.
- MCP is recognized: `.trae/mcp.json` is operator-owned; the adapter recognizes
  it but does not author entries. `capabilities.yml` `mcp_servers` and the
  shared capability matrix were set accordingly.
- Workspace rules are a `.trae/rules/*.md` directory of Markdown files, not a
  single file; `layered_context_surface` matches.
- The vendor documents skills (`.trae/skills/` plus the cross-tool
  `.agents/skills/`, with `.trae/skills/` winning name collisions), Agents
  (`docs.trae.ai/ide/agent`), and MCP (`.trae/mcp.json`, three transport types).
  The adapter delivers only the project rules file and authors none of those
  cohorts: a DELIBERATE rules-only posture, not a claim the surfaces are absent.
  Settings and status-lines remain undocumented as adapter-owned file surfaces.

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
ships. The adapter is project-scope rules-only: it writes a single merged rules
file at `<project>/.trae/rules/apothem-rules.md` (alongside, never clobbering,
the operator's other project rules or the `~/.trae/user_rules` global rules)
and authors no other cohort.
There is no standalone-installable bundle; every artifact requires the full
`apothem install --harness trae --project <path>` engine run.

| Artifact class | Persists standalone? | Mechanism / limit |
|---|---|---|
| Rules | No — requires `apothem install` | The merged `apothem-rules.md` (carrying the embedded behavioral mandates) is written only by the engine into the vendor-native `.trae/rules/` directory. Nothing persists before that run. |
| Commands / Skills / Agents | No — deliberate rules-only posture | Trae documents skills (`.trae/skills/` + `.agents/skills/`) and Agents (`docs.trae.ai/ide/agent`), but the adapter authors none of them (preserve-first rules-only delivery); these cohorts are not materialized for this harness by design. |
| Hooks / MCP / Settings | No — operator-owned / platform limit | `.trae/mcp.json` (MCP) is operator-owned; the adapter authors no entries. |

Platform limit: Trae ships no marketplace/extension channel, so a plugin-alone
story does not exist — the merged rules file via `apothem install` is the sole
persistence surface.
