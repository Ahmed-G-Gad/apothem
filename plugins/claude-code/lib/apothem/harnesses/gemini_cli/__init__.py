# SPDX-License-Identifier: MIT

"""Apothem harness adapter for gemini-cli — project-scope install.

Materializes the apothem rules + convention cohort into the operator-
supplied project root at ``<project>/GEMINI.md`` (vendor-canonical
project-context anchor) plus
``<project>/.gemini/{commands,skills,agents}/`` and
``<project>/.gemini/.apothem/support/`` per the
gemini-cli configuration discovery contract at
https://google-gemini.github.io/gemini-cli/docs/.

The gemini-cli adapter is project-scope only: user-scope ``~/.gemini/``
is reserved for the antigravity adapter, which owns
``~/.gemini/GEMINI.md`` as its anchor. The gemini-cli adapter avoids the
shared namespace by materialising under ``<project>/`` exclusively.

The adapter opts into the project-scope contract via
``requires_project = True``; the CLI rejects an install / update /
uninstall / verify invocation that omits ``--project <path>``. Delegates
install logic to :mod:`apothem.harnesses.gemini_cli.install`, which
consumes the canonical propagation manifest at
``src/apothem/lib/propagation-manifest.yaml``.
"""

from __future__ import annotations

from apothem.harnesses._shared.wrapper_factories import make_project_scope_adapter
from apothem.harnesses.gemini_cli.install import install as _install
from apothem.harnesses.gemini_cli.install import plan as _plan
from apothem.harnesses.gemini_cli.uninstall import RELATIVE_TARGET as _SENTINEL_RELATIVE
from apothem.harnesses.gemini_cli.uninstall import uninstall as _uninstall
from apothem.harnesses.gemini_cli.update import update as _update
from apothem.harnesses.gemini_cli.verify import verify as _verify

# The sentinel relative path used by ``output_path`` for display purposes only
# and joined onto ``--project`` by ``resolve_output_path``. Sourced from
# ``uninstall`` so the target path and the uninstall project-root derivation
# share one definition.

GeminiCliAdapter = make_project_scope_adapter(
    "gemini-cli",
    error_label="gemini_cli",
    relative_target=_SENTINEL_RELATIVE,
    install_fn=_install,
    plan_fn=_plan,
    uninstall_fn=_uninstall,
    update_fn=_update,
    verify_fn=_verify,
    class_name="GeminiCliAdapter",
)
