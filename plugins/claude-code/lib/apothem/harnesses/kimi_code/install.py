# SPDX-License-Identifier: MIT

"""Install logic for the kimi-code harness adapter.

Materializes the apothem Kimi Code instruction surface into the
operator-supplied project root. Kimi Code's canonical instruction surface is
the project-root ``AGENTS.md`` file (per the vendor configuration docs at
https://moonshotai.github.io/kimi-cli/en/configuration/config-files.html);
project configuration lives under ``<project>/.kimi-code/``. The adapter
writes the apothem governance surface into ``AGENTS.md`` as a
sentinel-delimited managed block so operator prose is never clobbered, and
keeps non-native cohorts (rules, commands, skills, agents, templates, hooks)
under a single Apothem-owned support tree at
``<project>/.kimi-code/.apothem/support/`` — referenced
from the anchor.

The propagation contract is declared in the canonical manifest at
``src/apothem/lib/propagation-manifest.yaml`` under the ``kimi_code`` key
(a single operator-owned ``sentinel_merge`` operation targeting
``${PROJECT_ROOT}/AGENTS.md`` plus the apothem-owned support tree) and
applied by the shared driver at
``apothem.harnesses._shared.install_driver``. The ``${PROJECT_ROOT}``
placeholder is substituted with the operator-supplied ``--project <path>``
value the CLI threads through; absence of ``--project`` is rejected upstream
at ``apothem.cli._materialize`` via the ``requires_project`` opt-in.
"""

from __future__ import annotations

from apothem.harnesses._shared.wrapper_factories import (
    make_project_scope_install,
    make_project_scope_plan,
)

# Manifest harness key for this adapter.
_HARNESS_NAME: str = "kimi_code"

install = make_project_scope_install(
    _HARNESS_NAME,
    error_message="kimi_code adapter requires --project <path>; CLI must thread it through",
)

plan = make_project_scope_plan(_HARNESS_NAME)
