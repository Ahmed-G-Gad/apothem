# SPDX-License-Identifier: MIT

"""Install logic for the github-copilot harness adapter.

Materializes the apothem GitHub Copilot instructions surface into the
operator-supplied project root. The GA repo-wide instructions file is
``<project>/.github/copilot-instructions.md`` per
https://docs.github.com/en/copilot/customizing-copilot/adding-custom-instructions-for-github-copilot.
User-scope is unavailable — Copilot's user-level settings live in IDE
state (VS Code / JetBrains UI), not a file path the harness can write.

The propagation contract is declared in the canonical manifest at
``src/apothem/lib/propagation-manifest.yaml`` under the ``github_copilot``
key (a ``sentinel_merge`` operation targeting
``${PROJECT_ROOT}/.github/copilot-instructions.md``, preceded by the user-level entries that
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
_HARNESS_NAME: str = "github_copilot"

install = make_project_scope_install(
    _HARNESS_NAME,
    error_message=(
        "github_copilot adapter requires --project <path>; CLI must thread it through"
    ),
)

plan = make_project_scope_plan(_HARNESS_NAME)
