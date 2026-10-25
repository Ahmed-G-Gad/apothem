# SPDX-License-Identifier: MIT

"""Install logic for the cursor harness adapter.

Materializes the apothem Cursor rules surface into the operator-supplied
project root. Cursor's canonical user-facing rules surface is the
project-scope MDC ruleset at ``<project>/.cursor/rules/*.mdc`` (per
https://cursor.com/docs/rules). The legacy single-file
``~/.cursorrules`` target is excluded because Apothem targets the current
multi-file project rules surface.

The propagation contract is declared in the canonical manifest at
``src/apothem/lib/propagation-manifest.yaml`` under the ``cursor`` key
(a ``sentinel_merge`` operation targeting
``${PROJECT_ROOT}/.cursor/rules/apothem-rules.mdc``, preceded by the user-level entries that
install the skills in ``~/.agents/skills/`` and the rules and templates corpus in
``~/.config/apothem/``) and applied by the
shared driver at ``apothem.harnesses._shared.install_driver``. The
``${PROJECT_ROOT}`` placeholder is substituted with the operator-supplied
``--project <path>`` value the CLI threads through; absence of
``--project`` is rejected upstream at ``apothem.cli._materialize`` via the
``requires_project`` opt-in. The ``${USER_HOME}`` placeholder is the user home, and
the folders under it are shared with every other install that names them.
"""

from __future__ import annotations

from apothem.harnesses._shared.wrapper_factories import (
    make_project_scope_install,
    make_project_scope_plan,
)

# Manifest harness key for this adapter.
_HARNESS_NAME: str = "cursor"

install = make_project_scope_install(
    _HARNESS_NAME,
    error_message="cursor adapter requires --project <path>; CLI must thread it through",
)

plan = make_project_scope_plan(_HARNESS_NAME)
