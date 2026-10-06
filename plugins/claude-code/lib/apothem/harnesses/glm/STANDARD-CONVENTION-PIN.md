<!-- SPDX-License-Identifier: MIT -->

# GLM (Z.ai) Standard Convention Pin

## Snapshot

- Snapshot date: 2026-10-03
- Snapshot note: refreshed against the Z.ai Claude Code guide at `docs.z.ai/devpack/tool/claude`. The Anthropic-compatible base URL `https://api.z.ai/api/anthropic`, the `ANTHROPIC_AUTH_TOKEN` / `ANTHROPIC_BASE_URL` / `API_TIMEOUT_MS` variables, and the `ANTHROPIC_DEFAULT_OPUS_MODEL` / `ANTHROPIC_DEFAULT_SONNET_MODEL` / `ANTHROPIC_DEFAULT_HAIKU_MODEL` model mapping match the current page. The adapter pins no model id. Previous 2026-06-25.
- Adapter source: `src/apothem/harnesses/glm/`
- Evidence level: adapter-local projection; no vendor-native coding-tool UI claim is made here. GLM is a model backend, not a coding-agent tool.

## Official Surface Refresh

- Refreshed 2026-10-03 against the Z.ai documentation (`docs.z.ai`). No
  immutable version pin is exposed (mutable docs site), so every captured
  convention carries a no-immutable-source exception.
- GLM (Z.ai) is a **model backend**, not a first-party coding CLI. An
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

## Vendor Sources

Retrieved 2026-10-03.

- <https://docs.z.ai/devpack/tool/claude> (Anthropic-compatible setup and model mapping)

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

## Large-Codebase Practice Projection

- Layered context: not applicable — GLM is a backend endpoint, not an agent
  with a context hierarchy. The provider config file carries backend wiring
  only.
- LSP symbol navigation: not applicable — provided by the agent runtime the
  operator points at GLM, never by the backend.
- Hook learning capture: routed through the `persistent-conventions-vigilance`
  artifact-evolution cycle; the backend exposes no hook surface.

## Plugin-alone Persistence

GLM (Z.ai) exposes **no vendor plugin or extension install surface** that
Apothem ships. The adapter is project-scope and writes a single Apothem-owned
provider config file at `<project>/.apothem/providers/glm.toml`. There is no
standalone-installable bundle; the file is written only by the
`apothem install --harness glm --project <path>` engine run.

| Artifact class | Persists standalone? | Mechanism / limit |
|---|---|---|
| Provider config | No — requires `apothem install` | The `glm.toml` backend-provider file is written only by the engine into `<project>/.apothem/providers/`. Nothing persists before that run. |
| Commands / Skills / Agents / Rules / Hooks | No — platform limit | GLM is a model backend; it exposes no coding-agent primitive Apothem targets, so these cohorts are not materialized for this harness. |
| Auth / model mapping | Operator-owned | The auth token and model ids are operator placeholders; Apothem never writes a real secret or pins a version-volatile model id. |

GLM is a model backend with no plugin surface for Apothem to ship, so the
backend-provider file via `apothem install` is the sole persistence surface.
