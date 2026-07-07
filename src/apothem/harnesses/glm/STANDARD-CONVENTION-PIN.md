<!-- SPDX-License-Identifier: MIT -->

# GLM (Z.ai) Standard Convention Pin

## Snapshot

- Snapshot date: 2026-06-25
- Snapshot note: base URLs re-confirmed live against `docs.z.ai` — the Anthropic-compatible endpoint `https://api.z.ai/api/anthropic` (env `ANTHROPIC_BASE_URL` / `ANTHROPIC_AUTH_TOKEN` / `API_TIMEOUT_MS`) is an exact match to current docs; the no-pinned-model-id decision is vindicated (the catalog already advanced to GLM-5.2 / GLM-5-Turbo / GLM-4.7, which a hard-pinned id would have made stale). Previous 2026-06-24.
- Adapter source: `src/apothem/harnesses/glm/`
- Evidence level: adapter-local projection; no vendor-native coding-tool UI claim is made here. GLM is a model backend, not a coding-agent tool.

## Official Surface Refresh

- Refreshed live 2026-06-24 against the current Z.ai documentation
  (`docs.z.ai`). No authority-host move; no immutable version pin is exposed
  (mutable docs site), so every captured convention carries a
  no-immutable-source exception.
- GLM (Z.ai) is a **model backend**, not a first-party coding CLI. Z.ai ships
  no native GLM coding-agent tool. An Anthropic-compatible or OpenAI-compatible
  coding agent is pointed at GLM by setting backend environment variables.
- Anthropic-compatible backend: base URL `https://api.z.ai/api/anthropic`. An
  operator sets `ANTHROPIC_BASE_URL`, `ANTHROPIC_AUTH_TOKEN`, and
  (optionally) `API_TIMEOUT_MS` to route an Anthropic-compatible agent to GLM.
- OpenAI-compatible backend: base URL `https://api.z.ai/api/coding/paas/v4`.
- Canonical filename: `.apothem/providers/glm.toml`. The adapter is
  project-scope and writes only `<project>/.apothem/providers/glm.toml`, an
  Apothem-owned TOML provider file recording both compatibility surfaces, an
  auth-token placeholder (never a real secret), and operator-configurable
  model-mapping placeholders. No GLM model id is pinned (model ids are
  version-volatile); the operator selects one from the current Z.ai catalog.
- The adapter authors no coding-agent cohort (rules, commands, skills, agents,
  hooks): a model backend exposes none. Every capability is `unsupported`.

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

Platform limit: GLM ships no marketplace/extension channel, so a plugin-alone
story does not exist for this harness — the backend-provider file via
`apothem install` is the sole persistence surface.
