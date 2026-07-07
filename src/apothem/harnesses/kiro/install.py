# SPDX-License-Identifier: MIT

"""Install logic for the kiro harness adapter.

Materializes the apothem Kiro steering surface into the operator-supplied
project root. Kiro's canonical steering surface is the project-scope
Markdown format at ``<project>/.kiro/steering/*.md`` (per
https://kiro.dev/docs/steering/). The adapter writes a dedicated
``apothem-rules.md`` steering file and never clobbers Kiro's
operator-authored foundation files (``product.md``, ``tech.md``,
``structure.md``).

The propagation contract is declared in the canonical manifest at
``src/apothem/lib/propagation-manifest.yaml`` under the ``kiro`` key
(a single ``sentinel_merge`` operation targeting
``${PROJECT_ROOT}/.kiro/steering/apothem-rules.md``) and applied by the
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
_HARNESS_NAME: str = "kiro"

install = make_project_scope_install(
    _HARNESS_NAME,
    error_message="kiro adapter requires --project <path>; CLI must thread it through",
)

plan = make_project_scope_plan(_HARNESS_NAME)
