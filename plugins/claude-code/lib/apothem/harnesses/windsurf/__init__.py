# SPDX-License-Identifier: MIT

"""Apothem harness adapter for windsurf — project-scope install.

Materializes the apothem rules surface into the operator-supplied
project root at ``<project>/.devin/rules/apothem-rules.md`` — the
preferred workspace-rules surface per the vendor's current docs
(https://docs.devin.ai/desktop/cascade/workspace-rules). The windsurf
harness rebranded to Devin Desktop (OTA 2026-06-02); ``.devin/rules/``
now TAKES PRECEDENCE over the retained backward-compat fallback at
``.windsurf/rules/``, so Apothem writes the canonical target into
``.devin/rules/`` to avoid being silently shadowed. The harness slug stays
``windsurf``. The legacy single-file ``.windsurfrules`` user-scope target is
excluded; Windsurf / Devin workflows and memories are out of apothem's adapter
scope.

The adapter opts into the project-scope contract via
``requires_project = True``; the CLI rejects an install / update /
uninstall / verify invocation that omits ``--project <path>``. Delegates
install logic to :mod:`apothem.harnesses.windsurf.install`, which
consumes the canonical propagation manifest at
``src/apothem/lib/propagation-manifest.yaml``.
"""

from __future__ import annotations

from apothem.harnesses._shared.wrapper_factories import make_project_scope_adapter
from apothem.harnesses.windsurf.install import install as _install
from apothem.harnesses.windsurf.install import plan as _plan
from apothem.harnesses.windsurf.uninstall import RELATIVE_TARGET as _SENTINEL_RELATIVE
from apothem.harnesses.windsurf.uninstall import uninstall as _uninstall
from apothem.harnesses.windsurf.update import update as _update
from apothem.harnesses.windsurf.verify import verify as _verify

# The sentinel relative path used by ``output_path`` for display purposes only
# and joined onto ``--project`` by ``resolve_output_path``. Sourced from
# ``uninstall`` so the target path and the uninstall project-root derivation
# share one definition.

WindsurfAdapter = make_project_scope_adapter(
    "windsurf",
    error_label="windsurf",
    relative_target=_SENTINEL_RELATIVE,
    install_fn=_install,
    plan_fn=_plan,
    uninstall_fn=_uninstall,
    update_fn=_update,
    verify_fn=_verify,
    class_name="WindsurfAdapter",
)
