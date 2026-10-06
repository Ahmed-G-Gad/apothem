# SPDX-License-Identifier: MIT

"""Install logic for the trae harness adapter.

Materializes the apothem Trae rules surface into the operator-supplied
project root. Trae's canonical rules surface is the project-scope
Markdown format at ``<project>/.trae/rules/*.md`` (per
https://docs.trae.ai/ide/rules). The adapter writes a dedicated
``apothem-rules.md`` file whose frontmatter (``alwaysApply: true`` plus a
``description``) is the first content in the file; the operator's other rule
files and the global ``~/.trae/user_rules`` are never clobbered.

The propagation contract is declared in the canonical manifest at
``src/apothem/lib/propagation-manifest.yaml`` under the ``trae`` key
(a single ``sentinel_merge`` operation targeting
``${PROJECT_ROOT}/.trae/rules/apothem-rules.md``) and applied by the
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
_HARNESS_NAME: str = "trae"

install = make_project_scope_install(
    _HARNESS_NAME,
    error_message="trae adapter requires --project <path>; CLI must thread it through",
)

plan = make_project_scope_plan(_HARNESS_NAME)
