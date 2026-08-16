# SPDX-License-Identifier: MIT

"""Install logic for the antigravity harness adapter.

Installs the apothem convention surface into the Antigravity CLI harness
target. Antigravity reads ``~/.gemini/GEMINI.md`` as global context and
stores CLI customization under ``~/.gemini/antigravity-cli/``; Apothem
installs a named plugin at
``~/.gemini/antigravity-cli/plugins/apothem/`` for cohorts that should not
collide with Gemini CLI project-local files.

The adapter is user-scope: it propagates under the harness root resolved
as ``output_path.parent`` (``~/.gemini/``). Its propagation contract is
declared in the canonical manifest at
``src/apothem/lib/propagation-manifest.yaml`` under the ``antigravity``
key and applied by the shared driver at
``apothem.harnesses._shared.install_driver``. Drift between the
propagation contract and the on-disk install is impossible by
construction: the manifest IS the contract.
"""

from __future__ import annotations

from apothem.harnesses._shared.wrapper_factories import (
    make_plan_harness_root,
    make_user_scope_install,
)

# Manifest harness key for this adapter.
_HARNESS_NAME: str = "antigravity"

install = make_user_scope_install(_HARNESS_NAME)

plan = make_plan_harness_root(_HARNESS_NAME)
