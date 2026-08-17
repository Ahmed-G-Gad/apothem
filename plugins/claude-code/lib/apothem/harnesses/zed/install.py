# SPDX-License-Identifier: MIT

"""Install logic for the zed harness adapter.

Materializes the apothem Zed rules surface into the operator-supplied
project root. Zed's canonical agent-instruction surface is a single flat
project-root file at ``<project>/.rules`` (per
https://zed.dev/docs/ai/instructions) — a divergence from the cohort's
rules-directory shape: Zed auto-includes one flat ``.rules`` file
(alongside the ``AGENTS.md`` / ``CLAUDE.md`` family) rather than a
per-tool rules subdirectory. The global ``~/.config/zed/AGENTS.md``
target is excluded because Apothem targets the current project surface.

The propagation contract is declared in the canonical manifest at
``src/apothem/lib/propagation-manifest.yaml`` under the ``zed`` key
(a single ``sentinel_merge`` operation targeting
``${PROJECT_ROOT}/.rules``) and applied by the shared driver at
``apothem.harnesses._shared.install_driver``, which backs up any
pre-existing ``.rules`` before replace. The ``${PROJECT_ROOT}``
placeholder is substituted with the operator-supplied ``--project
<path>`` value the CLI threads through; absence of ``--project`` is
rejected upstream at ``apothem.cli._materialize`` via the
``requires_project`` opt-in.
"""

from __future__ import annotations

from apothem.harnesses._shared.wrapper_factories import (
    make_project_scope_install,
    make_project_scope_plan,
)

# Manifest harness key for this adapter.
_HARNESS_NAME: str = "zed"

install = make_project_scope_install(
    _HARNESS_NAME,
    error_message="zed adapter requires --project <path>; CLI must thread it through",
)

plan = make_project_scope_plan(_HARNESS_NAME)
