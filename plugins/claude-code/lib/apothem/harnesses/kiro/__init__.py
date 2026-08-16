# SPDX-License-Identifier: MIT

"""Apothem harness adapter for kiro — project-scope install.

Materializes the apothem rules surface into the operator-supplied
project root at ``<project>/.kiro/steering/apothem-rules.md`` — a
dedicated Apothem steering file inside Kiro's documented steering
directory per https://kiro.dev/docs/steering/. Kiro's foundation
steering files (``product.md``, ``tech.md``, ``structure.md``) are
operator-authored; the adapter writes only its own ``apothem-rules.md``
steering file and never clobbers them. Kiro specs
(``.kiro/specs/``) and agent hooks are out of apothem's adapter scope.

The adapter opts into the project-scope contract via
``requires_project = True``; the CLI rejects an install / update /
uninstall / verify invocation that omits ``--project <path>``. Delegates
install logic to :mod:`apothem.harnesses.kiro.install`, which
consumes the canonical propagation manifest at
``src/apothem/lib/propagation-manifest.yaml``.
"""

from __future__ import annotations

from apothem.harnesses._shared.wrapper_factories import make_project_scope_adapter
from apothem.harnesses.kiro.install import install as _install
from apothem.harnesses.kiro.install import plan as _plan
from apothem.harnesses.kiro.uninstall import RELATIVE_TARGET as _SENTINEL_RELATIVE
from apothem.harnesses.kiro.uninstall import uninstall as _uninstall
from apothem.harnesses.kiro.update import update as _update
from apothem.harnesses.kiro.verify import verify as _verify

# The sentinel relative path used by ``output_path`` for display purposes only
# and joined onto ``--project`` by ``resolve_output_path``. Sourced from
# ``uninstall`` so the target path and the uninstall project-root derivation
# share one definition.

KiroAdapter = make_project_scope_adapter(
    "kiro",
    error_label="kiro",
    relative_target=_SENTINEL_RELATIVE,
    install_fn=_install,
    plan_fn=_plan,
    uninstall_fn=_uninstall,
    update_fn=_update,
    verify_fn=_verify,
    class_name="KiroAdapter",
)
