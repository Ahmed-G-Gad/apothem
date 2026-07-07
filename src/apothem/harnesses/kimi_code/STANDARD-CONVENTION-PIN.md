<!-- SPDX-License-Identifier: MIT -->

# Kimi Code Standard Convention Pin

## Snapshot

- Snapshot date: 2026-06-25
- vendor-doc-url: <https://moonshotai.github.io/kimi-cli/en/configuration/config-files.html>
- snapshot-date: 2026-06-25
- Canonical docs host: `moonshotai.github.io/kimi-cli` (source repo `MoonshotAI/kimi-cli`); the legacy `kimi-code` docs host mirror-resolves but risks link-rot.
- canonical-filename: `AGENTS.md`
- canonical-schema: the universal AGENTS.md open standard (Markdown agent-instructions file at the project root)
- Adapter source: `src/apothem/harnesses/kimi_code/`
- Evidence level: adapter-local projection; no vendor-native UI claim is made here.

## Official Surface Refresh

- Re-verified live 2026-06-25 against `github.com/MoonshotAI/kimi-cli` +
  `kimi-code`. Kimi Code (Moonshot) reads the project-root `AGENTS.md`
  instruction file (universal AGENTS.md convention; `/init` generates it,
  `KIMI_AGENTS_MD` consumes it) — CONFIRMED. FINDING (config-path discovery,
  flagged not rewritten): the pin declares `kimi-cli` the canonical source yet
  uses `<project>/.kimi-code/` project-scope paths, while the live kimi-cli docs
  show user-scope `~/.kimi/config.toml` + `~/.kimi/` for config / sessions / MCP
  and a conversational `/mcp-config` (`kimi mcp`) surface. The `kimi-code` vs
  `kimi-cli` product distinction makes the project-scope `.kimi-code/` path
  UNCERTAIN — it needs a targeted discovery pass against the actual `kimi-code`
  product before any path rewrite; flagged here rather than guessed (M5: never
  fabricate a path). The adapter authors no config / MCP entries, so no write is
  affected by the ambiguity.
- Canonical filename: `AGENTS.md` at the project root. The adapter is
  project-scope and writes the apothem governance surface into `AGENTS.md` as a
  sentinel-delimited managed block so operator prose outside the sentinels is
  never clobbered.
- Support tree: non-native Markdown cohorts (rules, commands, skills, agents)
  land under the Apothem-owned `<project>/.kimi-code/.apothem/support/` subtree, and the
  template and hook machinery under the shared working directory at
  `<project>/.kimi-code/.apothem/support/{templates,hooks}/`; both are referenced
  from the `AGENTS.md` anchor. They are never forced into vendor-reserved
  configuration directories.
- Model family: the Kimi Code model FAMILY is vendor-pinned and selected through
  the operator's own Kimi Code configuration; the adapter authors no model id
  and presets no model or effort preference.

## Verification

The vendor configuration surface at the pinned `vendor-doc-url` above was
verified against vendor reality on `snapshot-date`. Adapter materializer output
MUST produce an `AGENTS.md` managed block conforming to the universal AGENTS.md
convention; deviations are findings per
`rules/harness-adapter-shape.md` §4 Standard-Conformance.

## MCP Surface Projection

- Status: MCP is the recognized operator-owned surface at
  `<project>/.kimi-code/mcp.json`. Apothem names this surface in
  `capabilities.yml` but does not author MCP server entries; `.kimi-code/mcp.json`
  is operator-owned and outside the adapter's write surface.
- Boundary: the registry capability cell is `discovery-pending` — the pinned
  snapshot catalogs the config-materialization surfaces, not the vendor MCP
  schema, so Apothem claims only that the surface exists, not that it
  materializes entries.

## Tool-Surface Restriction Projection

- Status: `discovery-pending`. The Kimi Code tool-permission surface is not yet
  pinned against a vendor schema. The universal-deny floor (secrets paths,
  destructive shell ops, network-write to unsigned endpoints) binds regardless
  per `rules/agent-capability-discipline.md` §5 and is named in
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

Re-verify against vendor reality every 90 days. On refresh, update
`snapshot-date` (and `vendor-doc-url` if the authority host moves) in the same
change-set and emit a `[Pin — refreshed: kimi_code; …]` ledger entry per
`rules/disclosure-ledger.md`. A pin whose `snapshot-date` exceeds 90 days
against current vendor reality surfaces as a finding at the next adapter-touch
boundary per `rules/harness-adapter-shape.md` §6 stale-pin discipline.

## Plugin-alone Persistence

Kimi Code exposes **no vendor plugin or extension install surface** that Apothem
ships. The adapter is project-scope: it writes the `AGENTS.md` managed block plus
an Apothem support tree under `<project>/.kimi-code/.apothem/support/`. There is no
standalone-installable bundle; every artifact requires the full
`apothem install --harness kimi-code --project <path>` engine run.

| Artifact class | Persists standalone? | Mechanism / limit |
|---|---|---|
| Context anchor (rules-as-text) | No — requires `apothem install` | `AGENTS.md` is written by the engine; nothing persists before that run. |
| Rules / Commands / Skills / Agents / Templates | No — deliberate posture | The support tree under the Apothem-owned subtree is engine-materialized as reference material. NOTE: contrary to the prior framing, Kimi Code/CLI DOES document native skills (marketplace + GitHub install), built-in subagents (coder / explore / plan), slash commands (`/init`, `/plan`, `/mcp-config`), and agent specs — the adapter authors none of them (deliberate AGENTS.md-anchor posture), not an absence-of-surface claim. |
| MCP servers | No — operator-owned | `.kimi-code/mcp.json` is operator-owned; the adapter authors no entries. |

## Bindings

- Established by ↑ `rules/harness-adapter-shape.md` §6.
- Cross-bound with ↔ `src/apothem/harnesses/kimi_code/__init__.py` (the adapter
  whose discovery walk this pin anchors).
