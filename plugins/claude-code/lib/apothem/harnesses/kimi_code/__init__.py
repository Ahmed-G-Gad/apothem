# SPDX-License-Identifier: MIT

"""Apothem harness adapter for kimi_code — project-scope install.

Materializes the apothem instruction surface into the operator-supplied
project root at ``<project>/AGENTS.md`` — the canonical Kimi Code CLI
instruction file per the vendor configuration docs
(https://moonshotai.github.io/kimi-cli/en/configuration/config-files.html,
snapshot-date 2026-06-24). Kimi Code (Moonshot) reads project-root
``AGENTS.md`` as its agent-instructions surface following the universal
AGENTS.md convention; project configuration lives under
``<project>/.kimi-code/``.

The adapter writes the apothem governance surface into ``AGENTS.md`` as a
sentinel-delimited managed block (operator prose outside the sentinels is
preserved — identical to how the user-scope codex adapter handles its
``AGENTS.md``, but project-scoped via ``${PROJECT_ROOT}``). Non-native
cohorts (rules, commands, skills, agents, templates, hooks) land under a
single Apothem-owned support tree at
``<project>/.kimi-code/.apothem/support/`` — referenced
from the instruction anchor. The ``.kimi-code/mcp.json`` MCP surface is
operator-owned and out of apothem's adapter scope; the model FAMILY and
its configuration are vendor-pinned, not adapter-authored.

The adapter opts into the project-scope contract via
``requires_project = True``; the CLI rejects an install / update /
uninstall / verify invocation that omits ``--project <path>``. Delegates
install logic to :mod:`apothem.harnesses.kimi_code.install`, which consumes
the canonical propagation manifest at
``src/apothem/lib/propagation-manifest.yaml``.
"""

from __future__ import annotations

from apothem.harnesses._shared.wrapper_factories import make_project_scope_adapter
from apothem.harnesses.kimi_code.install import install as _install
from apothem.harnesses.kimi_code.install import plan as _plan
from apothem.harnesses.kimi_code.uninstall import RELATIVE_TARGET as _SENTINEL_RELATIVE
from apothem.harnesses.kimi_code.uninstall import uninstall as _uninstall
from apothem.harnesses.kimi_code.update import update as _update
from apothem.harnesses.kimi_code.verify import verify as _verify

# Sentinel relative path used by ``output_path`` for display purposes only; the
# real target is resolved per-install via ``resolve_output_path(project)`` once
# the operator supplies ``--project <path>``. Imported from ``uninstall`` so the
# target path and the uninstall project-root derivation cannot drift apart.

KimiCodeAdapter = make_project_scope_adapter(
    "kimi-code",
    error_label="kimi_code",
    relative_target=_SENTINEL_RELATIVE,
    install_fn=_install,
    plan_fn=_plan,
    uninstall_fn=_uninstall,
    update_fn=_update,
    verify_fn=_verify,
    class_name="KimiCodeAdapter",
)
