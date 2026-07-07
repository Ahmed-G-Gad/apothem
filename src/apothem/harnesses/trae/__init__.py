# SPDX-License-Identifier: MIT

"""Apothem harness adapter for trae — project-scope install.

Materializes the apothem rules surface into the operator-supplied
project root at ``<project>/.trae/rules/apothem-rules.md`` — a dedicated
apothem rules file inside Trae's documented ``.trae/rules/`` directory per
https://docs.trae.ai/ide/rules. The vendor anchors ``project_rules.md`` and
``user_rules.md`` are never clobbered: Apothem writes only its own
``apothem-rules.md`` file alongside them. Trae's MCP surface
(``.trae/mcp.json``) and skill surface (``.trae/skills/``) are operator-owned
and out of apothem's adapter scope.

The adapter opts into the project-scope contract via
``requires_project = True``; the CLI rejects an install / update /
uninstall / verify invocation that omits ``--project <path>``. Delegates
install logic to :mod:`apothem.harnesses.trae.install`, which
consumes the canonical propagation manifest at
``src/apothem/lib/propagation-manifest.yaml``.
"""

from __future__ import annotations

from apothem.harnesses._shared.wrapper_factories import make_project_scope_adapter
from apothem.harnesses.trae.install import install as _install
from apothem.harnesses.trae.install import plan as _plan
from apothem.harnesses.trae.uninstall import RELATIVE_TARGET as _SENTINEL_RELATIVE
from apothem.harnesses.trae.uninstall import uninstall as _uninstall
from apothem.harnesses.trae.update import update as _update
from apothem.harnesses.trae.verify import verify as _verify

# The sentinel relative path used by ``output_path`` for display purposes only
# and joined onto ``--project`` by ``resolve_output_path``. Sourced from
# ``uninstall`` so the target path and the uninstall project-root derivation
# share one definition.

TraeAdapter = make_project_scope_adapter(
    "trae",
    error_label="trae",
    relative_target=_SENTINEL_RELATIVE,
    install_fn=_install,
    plan_fn=_plan,
    uninstall_fn=_uninstall,
    update_fn=_update,
    verify_fn=_verify,
    class_name="TraeAdapter",
)
