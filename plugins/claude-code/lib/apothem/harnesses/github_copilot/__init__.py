# SPDX-License-Identifier: MIT

"""Apothem harness adapter for github-copilot — project-scope install.

Materializes the apothem Copilot instructions surface into the operator-
supplied project root at ``<project>/.github/copilot-instructions.md``,
the GA repo-wide instructions surface per
https://docs.github.com/en/copilot/customizing-copilot/adding-custom-instructions-for-github-copilot.
User-scope is unavailable — Copilot's user-level settings live in IDE
state (VS Code / JetBrains UI), not a file path the harness can write.

The adapter opts into the project-scope contract via
``requires_project = True``; the CLI rejects an install / update /
uninstall / verify invocation that omits ``--project <path>``. Delegates
install logic to :mod:`apothem.harnesses.github_copilot.install`, which
consumes the canonical propagation manifest at
``src/apothem/lib/propagation-manifest.yaml``.
"""

from __future__ import annotations

from apothem.harnesses._shared.wrapper_factories import make_project_scope_adapter
from apothem.harnesses.github_copilot.install import install as _install
from apothem.harnesses.github_copilot.install import plan as _plan
from apothem.harnesses.github_copilot.uninstall import (
    RELATIVE_TARGET as _SENTINEL_RELATIVE,
)
from apothem.harnesses.github_copilot.uninstall import uninstall as _uninstall
from apothem.harnesses.github_copilot.update import update as _update
from apothem.harnesses.github_copilot.verify import verify as _verify

# The sentinel relative path used by ``output_path`` for display purposes only
# and joined onto ``--project`` by ``resolve_output_path``. Sourced from
# ``uninstall`` so the target path and the uninstall project-root derivation
# share one definition.

GitHubCopilotAdapter = make_project_scope_adapter(
    "github-copilot",
    error_label="github_copilot",
    relative_target=_SENTINEL_RELATIVE,
    install_fn=_install,
    plan_fn=_plan,
    uninstall_fn=_uninstall,
    update_fn=_update,
    verify_fn=_verify,
    class_name="GitHubCopilotAdapter",
)
