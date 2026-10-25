<!-- SPDX-License-Identifier: MIT -->

# GLM (Z.ai) Standard Convention Pin

## Snapshot

- Snapshot date: 2026-10-24
- Snapshot note: refreshed against the Z.ai ZCode guide at `docs.z.ai/devpack/tool/zcode` and the Z.ai Claude Code guide at `docs.z.ai/devpack/tool/claude`. The 2026-10-24 refresh covered three facts only: ZCode is a first-party Z.ai coding tool, Z.ai's documentation calls it an "Agentic Development Environment", and the Claude Code guide's model mapping and compaction window disagree with other Z.ai statements (see Model Mapping Conflict). The 2026-10-03 refresh, against the same Claude Code guide, found the Anthropic-compatible base URL `https://api.z.ai/api/anthropic`, the `ANTHROPIC_AUTH_TOKEN` / `ANTHROPIC_BASE_URL` / `API_TIMEOUT_MS` variables, and the `ANTHROPIC_DEFAULT_OPUS_MODEL` / `ANTHROPIC_DEFAULT_SONNET_MODEL` / `ANTHROPIC_DEFAULT_HAIKU_MODEL` variable names on the page. The adapter pins no model id. Previous 2026-10-03.
- Adapter source: `src/apothem/harnesses/glm/`
- Evidence level: adapter-local projection; no vendor-native coding-tool UI claim is made here. The adapter configures GLM as a model backend. ZCode, Z.ai's first-party coding tool, is recorded as vendor context only and is not an adapter target.

## Official Surface Refresh

- Refreshed 2026-10-24 (ZCode and model mapping; see the Snapshot note) and
  2026-10-03 (the rest) against the Z.ai documentation (`docs.z.ai`). No
  immutable version pin is exposed (mutable docs site), so every captured
  convention carries a no-immutable-source exception.
- Z.ai ships a first-party coding tool, **ZCode**. Z.ai's ZCode guide calls it
  an "Agentic Development Environment", and its source is published in Z.ai's
  GitHub organization at `zai-org/ZCode` under the Apache-2.0 license. That
  repository's README calls it an "AI coding workspace", so the "Agentic
  Development Environment" wording comes from the documentation. This adapter
  does not configure ZCode. Every statement below that GLM is a model backend
  describes what this adapter configures, not ZCode.
- TODO(clarify): the 2026-10-24 refresh did not examine ZCode's own
  configuration surface (config format, paths, rules, skills, hooks, MCP
  servers), so this pin records none and the adapter targets none. Decide
  whether ZCode needs an adapter target once that surface is checked.
- Template text: the `glm.toml` template changed on 2026-10-24 (ZCode context
  and the mapping `TODO(clarify)`). The uninstall deletes an unedited file
  Apothem created when it equals the current template or matches a digest in the
  manifest entry's `earlier_digests` list, which holds the SHA-256 digest of each
  earlier shipped template (v1.0.1 to v1.1.0, and v1.2.0 to v1.2.2). A change to
  the template adds the previous digest in the same change-set.
- GLM (Z.ai) is configured here as a **model backend**. An
  Anthropic-compatible or OpenAI-compatible coding agent is pointed at GLM by
  setting backend environment variables.
- Anthropic-compatible backend: base URL `https://api.z.ai/api/anthropic`. An
  operator sets `ANTHROPIC_BASE_URL`, `ANTHROPIC_AUTH_TOKEN`, and optionally
  `API_TIMEOUT_MS`, and maps the agent's model roles with
  `ANTHROPIC_DEFAULT_OPUS_MODEL`, `ANTHROPIC_DEFAULT_SONNET_MODEL`, and
  `ANTHROPIC_DEFAULT_HAIKU_MODEL`.
- OpenAI-compatible backend: base URL `https://api.z.ai/api/coding/paas/v4`
  (recorded 2026-06-24; not on the Claude Code guide re-read on 2026-10-03).
- Canonical filename: `.apothem/providers/glm.toml`. The adapter is
  project-scope and writes only `<project>/.apothem/providers/glm.toml`, an
  Apothem-owned TOML provider file recording both compatibility surfaces, an
  auth-token placeholder (never a real secret), and the model-mapping
  placeholders. No GLM model id is pinned (model ids are version-volatile); the
  operator selects one from the current Z.ai catalog.
- The adapter authors no coding-agent cohort (rules, commands, skills, agents,
  hooks): a model backend exposes none. Every capability is `unsupported`.

## Model Mapping Conflict

Z.ai's statements about the Anthropic-compatible role-to-model mapping and the
compaction window disagree. The pin records all three and claims none:

- The manual `settings.json` example on `docs.z.ai/devpack/tool/claude` maps
  opus and sonnet to `glm-5.3[1m]` and haiku to `glm-5.3-flash[1m]`, and sets
  `CLAUDE_CODE_AUTO_COMPACT_WINDOW` to `1000000`. This is the only place on the
  page that carries those model ids and that value.
- The same page's default mapping lists `GLM-5.3-Flash` for all three roles
  (opus, sonnet, haiku).
- Z.ai's `@z_ai/coding-helper` 0.1.1 (npm, published 2026-08-27) defaults to
  `glm-5.3-flash`, appends `[1m]` to all three roles, and writes the
  compaction window from its model registry, which holds 1048576 for both
  `glm-5.3` and `glm-5.3-flash`.

Z.ai's Chinese-language page for the same guide repeats the first two
statements; it is the same vendor, not an independent source. The template
keeps the `<GLM_MODEL_ID>` placeholders and carries a `TODO(clarify)` comment
above them, and the operator decides which mapping to use.

## Vendor Sources

Retrieved 2026-10-24.

- <https://docs.z.ai/devpack/tool/claude> (Anthropic-compatible setup and model mapping)
- <https://docs.z.ai/devpack/tool/zcode> (ZCode, Z.ai's first-party coding tool)
- <https://github.com/zai-org/ZCode> (ZCode source repository)

## Discovery Targets

- None. No capability cell for this harness is discovery-pending.

## Recommended Postfix Rendering

- Status: not applicable.
- Mechanism: GLM is a model backend, not a coding-agent tool with an
  option-rendering surface. Apothem renders no recommended-option label here.
- Boundary: this pin claims no harness-native recommended-option widget; the
  backend exposes no agent UI surface to render one.

## Long Context and Compaction

- Status: profile-managed.
- Mechanism: long-context and compaction are properties of the coding agent
  the operator points at GLM, not of the backend. Apothem's context-management
  discipline lives in the agent harness, not in this backend provider file.
- Boundary: this pin claims no vendor-native autocompaction or long-context
  size for the backend itself.
- Compaction-window values: Z.ai's own statements differ (1000000 in the
  Claude Code guide's manual example, 1048576 from `@z_ai/coding-helper`).
  The pin records both and claims neither; see Model Mapping Conflict.

## Large-Codebase Practice Projection

- Layered context: not applicable — GLM is a backend endpoint, not an agent
  with a context hierarchy. The provider config file carries backend wiring
  only.
- LSP symbol navigation: not applicable — provided by the agent runtime the
  operator points at GLM, never by the backend.
- Hook learning capture: routed through the `persistent-conventions-vigilance`
  artifact-evolution cycle; the backend exposes no hook surface.

## Plugin-alone Persistence

The GLM backend exposes **no vendor plugin or extension install surface** that
Apothem ships; ZCode's was not examined (see the `TODO(clarify)` above). The adapter is project-scope and writes a single Apothem-owned
provider config file at `<project>/.apothem/providers/glm.toml`. There is no
standalone-installable bundle; the file is written only by the
`apothem install --harness glm --project <path>` engine run.

| Artifact class | Persists standalone? | Mechanism / limit |
|---|---|---|
| Provider config | No — requires `apothem install` | The `glm.toml` backend-provider file is written only by the engine into `<project>/.apothem/providers/`. Nothing persists before that run. |
| Commands / Skills / Agents / Rules / Hooks | No — platform limit | The GLM backend exposes no coding-agent primitive Apothem targets, and ZCode's primitives were not examined (see the `TODO(clarify)` above), so these cohorts are not materialized for this harness. |
| Auth / model mapping | Operator-owned | The auth token and model ids are operator placeholders; Apothem never writes a real secret or pins a version-volatile model id. |

The GLM backend has no plugin surface for Apothem to ship, so the
backend-provider file via `apothem install` is the sole persistence surface.
