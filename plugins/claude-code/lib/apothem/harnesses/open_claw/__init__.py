# SPDX-License-Identifier: MIT

"""Apothem harness adapter for open-claw.

Materializes ``~/.openclaw/openclaw.json`` from the shared profile:
OpenClaw's user-global configuration file. Delegates install logic to
:mod:`apothem.harnesses.open_claw.install`, which renders the native config
via :mod:`apothem.harnesses.open_claw.materializer`. The one config key Apothem
authors is ``skills.load.extraDirs``, which lists the support skills directory
so OpenClaw loads the installed skills at the lowest precedence. OpenClaw's
``agents.defaults.skills`` is a name allowlist the operator owns and MCP is a
CLI surface, so Apothem authors neither; the shared cohorts (rules, agents,
skills, hooks, templates) land as individual files under
``~/.openclaw/.apothem/support/``. No single profile document is projected —
OpenClaw auto-loads no instruction file, so the operator wires the other
cohorts in through the vendor's own mechanisms.
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
