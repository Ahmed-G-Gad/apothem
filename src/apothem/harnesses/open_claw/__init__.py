# SPDX-License-Identifier: MIT

"""Apothem harness adapter for open-claw.

Materializes ``~/.openclaw/openclaw.json`` from the shared profile:
OpenClaw's user-global configuration file. Delegates install logic to
:mod:`apothem.harnesses.open_claw.install`, which renders the native config
via :mod:`apothem.harnesses.open_claw.materializer`. The one config key Apothem
authors is ``skills.load.extraDirs``, which lists the support skills directory
so OpenClaw loads the installed skills after the agent's other skill sources.
OpenClaw's ``agents.defaults.skills`` allowlist and ``agents.entries.<id>.skills``
lists are the operator's, and MCP servers live in the ``mcp.servers`` block the
operator manages with the ``openclaw mcp`` CLI, so Apothem authors neither; the
shared cohorts (rules, agents, skills, hooks, templates) land as individual
files under ``~/.openclaw/.apothem/support/``. The profile's managed block goes
to ``~/.openclaw/apothem/rules/00-apothem-profile.md``, which OpenClaw does not
load, and into ``<workspace>/apothem/AGENTS.md`` in each agent workspace, which
it does: the install registers that path with OpenClaw's bundled
``bootstrap-extra-files`` hook (:mod:`apothem.harnesses.open_claw.rules_file`).
The block names the rule index under the support tree. The workspace's own
``AGENTS.md`` and the other bootstrap files stay the operator's.
"""

from __future__ import annotations

from pathlib import Path

from apothem.harnesses._shared.wrapper_factories import make_native_config_adapter
from apothem.harnesses.open_claw.install import install as _install
from apothem.harnesses.open_claw.materializer import (
    materialize_native_config as materialize_native_config,
)
from apothem.harnesses.open_claw.uninstall import uninstall as _uninstall
from apothem.harnesses.open_claw.update import update as _update
from apothem.harnesses.open_claw.verify import verify as _verify

OpenClawAdapter = make_native_config_adapter(
    "open-claw",
    target_factory=lambda: Path.home() / ".openclaw/openclaw.json",
    install_fn=_install,
    uninstall_fn=_uninstall,
    update_fn=_update,
    verify_fn=_verify,
    class_name="OpenClawAdapter",
)
