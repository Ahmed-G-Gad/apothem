# SPDX-License-Identifier: MIT

"""Install logic for the windsurf harness adapter.

Materializes the apothem Windsurf rules surface into the operator-supplied
project root. The windsurf harness rebranded to Devin Desktop (OTA
2026-06-02); its preferred workspace-rules surface is now the project-scope
multi-file format at ``<project>/.devin/rules/*.md`` (per
https://docs.devin.ai/desktop/cascade/memories), which TAKES
PRECEDENCE over the retained backward-compat fallback at
``<project>/.windsurf/rules/*.md``. Apothem writes the canonical target into
``.devin/rules/`` to avoid being silently shadowed. The harness slug stays
``windsurf``. The legacy single-file ``.windsurfrules`` target is excluded.

The propagation contract is declared in the canonical manifest at
``src/apothem/lib/propagation-manifest.yaml`` under the ``windsurf`` key
(a single ``sentinel_merge`` operation targeting
``${PROJECT_ROOT}/.devin/rules/apothem-rules.md``) and applied by the
shared driver at ``apothem.harnesses._shared.install_driver``. The
``${PROJECT_ROOT}`` placeholder is substituted with the operator-supplied
``--project <path>`` value the CLI threads through; absence of
``--project`` is rejected upstream at ``apothem.cli._materialize`` via the
``requires_project`` opt-in.
"""

from __future__ import annotations

from apothem.harnesses._shared.wrapper_factories import (
    make_project_scope_install,
    make_project_scope_plan,
)

# Manifest harness key for this adapter.
_HARNESS_NAME: str = "windsurf"

install = make_project_scope_install(
    _HARNESS_NAME,
    error_message="windsurf adapter requires --project <path>; CLI must thread it through",
)

plan = make_project_scope_plan(_HARNESS_NAME)
