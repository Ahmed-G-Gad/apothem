# SPDX-License-Identifier: MIT

"""Install logic for the gemini-cli harness adapter.

Materializes the apothem convention surface into the operator-supplied
project root. The gemini-cli adapter is project-scope only: user-scope
``~/.gemini/`` is reserved for the antigravity adapter, which owns
``~/.gemini/GEMINI.md``. The gemini-cli adapter avoids the shared
namespace by materialising under ``<project>/`` exclusively.

Vendor-canonical project-context surface is ``<project>/GEMINI.md``
(analogous to project CLAUDE.md per
https://github.com/google-gemini/gemini-cli/blob/main/docs/reference/configuration.md
commit 792654c). The apothem convention cohort propagates under
``<project>/.gemini/{commands,skills,agents}/`` plus
``<project>/.gemini/.apothem/support/rules/`` for Markdown rules and
``<project>/.gemini/.apothem/support/{templates,hooks}/`` for the template and
hook machinery — support material that Gemini CLI does not expose as a matching
native primitive.

The propagation contract is declared in the canonical manifest at
``src/apothem/lib/propagation-manifest.yaml`` under the ``gemini_cli``
key and applied by the shared driver at
``apothem.harnesses._shared.install_driver``. Drift between the
propagation contract and the on-disk install is impossible by
construction: the manifest IS the contract.
"""

from __future__ import annotations

from apothem.harnesses._shared.wrapper_factories import (
    make_project_scope_install,
    make_project_scope_plan,
)

# Manifest harness key for this adapter.
_HARNESS_NAME: str = "gemini_cli"

install = make_project_scope_install(
    _HARNESS_NAME,
    error_message="gemini_cli adapter requires --project <path>; CLI must thread it through",
)

plan = make_project_scope_plan(_HARNESS_NAME)
