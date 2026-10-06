# SPDX-License-Identifier: MIT

"""Apothem harness adapter for cursor — project-scope install.

Materializes the apothem rules surface into the operator-supplied
project root at ``<project>/.cursor/rules/apothem-rules.mdc`` — the
canonical Cursor rules surface per
https://cursor.com/docs/rules. The legacy single-file
``~/.cursorrules`` user-scope target is excluded because Apothem targets the
current project rules surface; Cursor does not offer a file-based user-global
rules surface.

The adapter opts into the project-scope contract via
``requires_project = True``; the CLI rejects an install / update /
uninstall / verify invocation that omits ``--project <path>``. Delegates
install logic to :mod:`apothem.harnesses.cursor.install`, which consumes
the canonical propagation manifest at
``src/apothem/lib/propagation-manifest.yaml``.
"""

from __future__ import annotations

from apothem.harnesses._shared.wrapper_factories import make_project_scope_adapter
from apothem.harnesses.cursor.install import install as _install
from apothem.harnesses.cursor.install import plan as _plan
from apothem.harnesses.cursor.uninstall import RELATIVE_TARGET as _SENTINEL_RELATIVE
from apothem.harnesses.cursor.uninstall import uninstall as _uninstall
from apothem.harnesses.cursor.update import update as _update
from apothem.harnesses.cursor.verify import verify as _verify

# The sentinel relative path used by ``output_path`` for display purposes only
# and joined onto ``--project`` by ``resolve_output_path``. Sourced from
# ``uninstall`` so the target path and the uninstall project-root derivation
# share one definition.

CursorAdapter = make_project_scope_adapter(
    "cursor",
    error_label="cursor",
    relative_target=_SENTINEL_RELATIVE,
    install_fn=_install,
    plan_fn=_plan,
    uninstall_fn=_uninstall,
    update_fn=_update,
    verify_fn=_verify,
    class_name="CursorAdapter",
)
