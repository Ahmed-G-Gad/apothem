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

The install also writes Apothem's agents into the project as Kiro custom agents,
one Markdown file each in ``<project>/.kiro/agents/`` (the ``kiro_agents`` mode),
per https://kiro.dev/docs/custom-agents/, retrieved 2026-10-27. Markdown agents
are the format IDE 1.0 and Kiro CLI V3 (``kiro-cli --v3``) read; no CLI 2.x JSON
profile is written, and the user folder ``~/.kiro/agents/`` is not.

Ahead of the project file the install also writes the user-level folders: the
skills and the commands wrapped as skills in ``~/.kiro/skills/``, and the rules and
templates corpus they cite in ``~/.config/apothem/``. Those folders sit in the
user home, not in the project, and every Apothem install that names one writes
the same bytes; the install ledger decides which uninstall removes it.

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
