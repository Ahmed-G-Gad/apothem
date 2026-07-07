# SPDX-License-Identifier: MIT

"""Install logic for the codebuddy harness adapter.

Materializes the apothem CodeBuddy rules surface into the operator-supplied
project root. CodeBuddy's canonical rules surface is the project-scope
multi-file format at ``<project>/.codebuddy/rules/*.md`` (per
https://www.codebuddy.ai/docs/ide/Rules). The adapter writes a dedicated
``apothem-rules.md`` file so the operator's own rules files are never
clobbered. The ``CODEBUDDY.md`` memory file and ``.codebuddy/settings.json``
permissions/MCP surface are operator-owned and out of apothem's adapter
scope.

The propagation contract is declared in the canonical manifest at
``src/apothem/lib/propagation-manifest.yaml`` under the ``codebuddy`` key
(a single operator-owned ``sentinel_merge`` operation targeting
``${PROJECT_ROOT}/.codebuddy/rules/apothem-rules.md``) and applied by the
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
_HARNESS_NAME: str = "codebuddy"

install = make_project_scope_install(
    _HARNESS_NAME,
    error_message="codebuddy adapter requires --project <path>; CLI must thread it through",
)

plan = make_project_scope_plan(_HARNESS_NAME)
