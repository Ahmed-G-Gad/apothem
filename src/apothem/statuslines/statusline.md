<!-- SPDX-License-Identifier: MIT -->

# Statusline — Working Definition

> **Role.** The single conformity operating-posture statusline, emitted at the top of every harness session. Minimal, glanceable, cross-platform; surfaces the active plan suite's operating posture and documents the input it consumes and its degradation modes.

The renderer is [`render.py`](./render.py); the harness wires it in through the [`conformity.json`](./conformity.json) `type: command` snippet.

## Input Contract — JSON on stdin

The harness pipes a JSON object the renderer reads from stdin. The renderer consumes **one** field; every other field the harness reports (model, cost, duration, version) is ignored, because those session-context values are the harness's own native statusline territory.

| Field | Type | Description |
|-------|------|-------------|
| `workspace.project_dir` | string | Absolute path to the project root. Joined with `.apothem/plans/` to locate the project-local plans tree. |

The plans root resolves in this order:

1. `LLM_PLAN_SUITES_DIR` environment variable, when set — the operator override.
2. `<workspace.project_dir>/.apothem/plans/` from the stdin payload — the canonical project-local tree per the plans-locality discipline.
3. `<cwd>/.apothem/plans/` — the interactive fallback when no payload is supplied.

`.apothem/plans/` is the only tree the renderer reads. An operator holding a legacy `.plans/` tree upgrades it with `apothem migrate-workspace`; until then the statusline reports no active suite.

No harness configuration path is ever hardcoded; the renderer privileges no one harness. An absent payload or absent field degrades to the working-directory fallback, never to a harness-specific default.

## Output Contract — One Line on stdout

The renderer emits exactly one line to stdout, composed from the most-recently-touched plan suite under the resolved plans root:

```text
[<phase-pointer> | <sprint-goal> | <N> inquir(y|ies)]
```

1. The active phase / sub-phase pointer, read from the suite's `PROGRESS.md`.
2. The active phase's Sprint Goal sentence, read from its `PHASE.md` (truncated to a bounded width).
3. The count of unresolved `<USER-CONFIRM:…>` placeholders across the suite (`inquiry` / `inquiries` pluralized).

Segments that are absent are omitted; the inquiry count is always present. The rendering is plain text — no ANSI color codes, no decorative ASCII, no emojis — and is normalized to 7-bit ASCII so it renders identically across PowerShell, bash, and IDE harness terminals regardless of code-page. Glanceable, cross-platform, screen-reader-friendly.

### Example Render

```text
[03A-discovery | Ship the signed release. | 2 inquiries]
```

## Degradation Modes

- No plan suite under the resolved plans root → `[no active suite]`.
- Suite present but `PROGRESS.md` unparseable → the phase / goal segments are omitted; the inquiry count still renders.
- Sprint Goal absent in the active phase's `PHASE.md` → the goal segment is omitted.
- Any unexpected internal error → a single degraded marker `[statusline error: <ErrorClass>]`; the renderer never raises to stdout and never exits non-zero, so the harness statusline never breaks.
