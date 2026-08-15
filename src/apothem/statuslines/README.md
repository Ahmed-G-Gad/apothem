<!-- SPDX-License-Identifier: MIT -->

# statuslines

> **Role.** The conformity operating-posture statusline — a single renderer that surfaces the ecosystem's operating posture (active phase pointer, sprint goal, unresolved-inquiry count) in the harness statusline.

## Files

| File | Purpose |
|------|---------|
| `render.py` | The statusline renderer. Reads the harness statusline JSON on stdin (only `workspace.project_dir`), locates the project-local `.apothem/plans/` tree, and emits `[<phase> \| <sprint-goal> \| <N> inquiries]`. |
| `conformity.json` | The harness statusline-config snippet — a `type: command` entry whose command invokes `render.py` through the `${HARNESS_ROOT}` token. It wires the renderer into the harness statusline hook; `render.py` never reads it. |
| `statusline.md` | Reference documentation for the renderer's input contract, output shape, and degradation modes. |
| `__init__.py` | Package marker. |

## Operating in this folder

- **`render.py` is the single renderer.** There is one statusline product, and the harness exposes one statusline slot. Changing the rendered output means editing `render.py` and updating `statusline.md` + this README in the same change-set.
- **Harness-agnostic, project-local paths.** The plans root resolves from the `LLM_PLAN_SUITES_DIR` operator override, then the stdin payload's `workspace.project_dir` joined with `.apothem/plans/`, then the working directory's `.apothem/plans/`. That tree is the only one read: an operator holding a legacy `.plans/` tree upgrades it with `apothem migrate-workspace`, and until then the statusline reports no active suite. No harness config path is ever hardcoded — privilege no one harness.
- **Changing the wiring:** edit `conformity.json` (the `type: command` snippet the installer ships). The harness pipes its statusline JSON to the command's stdin; the renderer consumes only `workspace.project_dir`.
- Python follows the repo coding conventions (3.10+ syntax, `pathlib.Path`, strict-scoped typing).
- Validate a change with `python -m apothem.conformity.gate --all .`, `python -m pytest tests/unit/test_statuslines_render.py`, and `python -m ruff check`; the renderer is in CLI/harness-adjacent scope, so run the scoped `mypy` where it applies.

## Related

- [`conformity/`](../conformity/) — the conformity validators whose posture this statusline surfaces.
