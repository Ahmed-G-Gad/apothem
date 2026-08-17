# SPDX-License-Identifier: MIT

"""Apothem harness adapter for codebuddy — project-scope install.

Materializes the apothem rules surface into the operator-supplied
project root at ``<project>/.codebuddy/rules/apothem-rules.md`` — the
canonical CodeBuddy rules surface per
https://www.codebuddy.ai/docs/ide/Rules. The adapter writes a dedicated
``apothem-rules.md`` file inside CodeBuddy's documented rules directory so
the operator's own rules files are never clobbered. The ``CODEBUDDY.md``
memory file and ``.codebuddy/settings.json`` permissions/MCP surface are
operator-owned and out of apothem's adapter scope.

The adapter opts into the project-scope contract via
``requires_project = True``; the CLI rejects an install / update /
uninstall / verify invocation that omits ``--project <path>``. Delegates
install logic to :mod:`apothem.harnesses.codebuddy.install`, which
consumes the canonical propagation manifest at
``src/apothem/lib/propagation-manifest.yaml``.
"""

from __future__ import annotations

from apothem.harnesses._shared.wrapper_factories import make_project_scope_adapter
from apothem.harnesses.codebuddy.install import install as _install
from apothem.harnesses.codebuddy.install import plan as _plan
from apothem.harnesses.codebuddy.uninstall import RELATIVE_TARGET as _SENTINEL_RELATIVE
from apothem.harnesses.codebuddy.uninstall import uninstall as _uninstall
from apothem.harnesses.codebuddy.update import update as _update
from apothem.harnesses.codebuddy.verify import verify as _verify

# The sentinel relative path used by ``output_path`` for display purposes only
# and joined onto ``--project`` by ``resolve_output_path``. Sourced from
# ``uninstall`` so the target path and the uninstall project-root derivation
# share one definition.

CodeBuddyAdapter = make_project_scope_adapter(
    "codebuddy",
    error_label="codebuddy",
    relative_target=_SENTINEL_RELATIVE,
    install_fn=_install,
    plan_fn=_plan,
    uninstall_fn=_uninstall,
    update_fn=_update,
    verify_fn=_verify,
    class_name="CodeBuddyAdapter",
)
