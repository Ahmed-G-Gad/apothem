# SPDX-License-Identifier: MIT

"""Apothem harness adapter for zed — project-scope install.

Materializes the apothem rules surface into the operator-supplied
project root at ``<project>/.rules`` — the canonical Zed project
agent-instruction file per https://zed.dev/docs/ai/instructions. Zed diverges
from the cohort's rules-directory shape: it auto-includes a single flat
project-root file (``.rules``, alongside the ``AGENTS.md`` / ``CLAUDE.md``
family) as agent instructions, with no dedicated per-tool rules
subdirectory. The adapter therefore writes a flat ``.rules`` file rather
than a dedicated ``apothem-rules.md`` inside a rules directory. The
global ``~/.config/zed/AGENTS.md`` surface and Zed's MCP context-server
block (``.zed/settings.json`` ``context_servers``) are out of apothem's
adapter scope.

The shared install driver backs up any pre-existing ``.rules`` file
before replace (timestamped copy under ``~/.apothem/backups/``), so an
operator's existing instruction file is preserved.

The adapter opts into the project-scope contract via
``requires_project = True``; the CLI rejects an install / update /
uninstall / verify invocation that omits ``--project <path>``. Delegates
install logic to :mod:`apothem.harnesses.zed.install`, which consumes the
canonical propagation manifest at
``src/apothem/lib/propagation-manifest.yaml``.
"""

from __future__ import annotations

from apothem.harnesses._shared.wrapper_factories import make_project_scope_adapter
from apothem.harnesses.zed.install import install as _install
from apothem.harnesses.zed.install import plan as _plan
from apothem.harnesses.zed.uninstall import RELATIVE_TARGET as _SENTINEL_RELATIVE
from apothem.harnesses.zed.uninstall import uninstall as _uninstall
from apothem.harnesses.zed.update import update as _update
from apothem.harnesses.zed.verify import verify as _verify

# The sentinel relative path used by ``output_path`` for display purposes only
# and joined onto ``--project`` by ``resolve_output_path``. Sourced from
# ``uninstall`` so the target path and the uninstall project-root derivation
# share one definition. Zed's flat-file divergence: the sentinel is the bare
# ``.rules`` dotfile at the project root, not a nested rules file.

ZedAdapter = make_project_scope_adapter(
    "zed",
    error_label="zed",
    relative_target=_SENTINEL_RELATIVE,
    install_fn=_install,
    plan_fn=_plan,
    uninstall_fn=_uninstall,
    update_fn=_update,
    verify_fn=_verify,
    class_name="ZedAdapter",
)
