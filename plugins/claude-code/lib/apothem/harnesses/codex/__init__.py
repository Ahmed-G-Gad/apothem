# SPDX-License-Identifier: MIT

"""Apothem harness adapter for codex — raw-propagation (no materializer).

Propagates the apothem convention surface into ``$CODEX_HOME`` (default
``~/.codex/``) per the canonical manifest at
``src/apothem/lib/propagation-manifest.yaml``.
Per the declared divergence at ``rules/harness-adapter-shape-schemas.md`` §2
("No materializer; …"), the codex adapter renders no standalone config file:
the AGENTS.md anchor instead receives the shared profile as a
sentinel-delimited Apothem managed block, preserving operator prose outside
the sentinels.
"""

from __future__ import annotations

import os
from pathlib import Path

from apothem.harnesses._shared.wrapper_factories import make_user_scope_adapter
from apothem.harnesses.codex.install import install as _install
from apothem.harnesses.codex.install import plan as _plan
from apothem.harnesses.codex.uninstall import uninstall as _uninstall
from apothem.harnesses.codex.update import update as _update
from apothem.harnesses.codex.verify import verify as _verify


def _codex_home() -> Path:
    """Return the Codex user configuration root."""
    configured = os.environ.get("CODEX_HOME")
    if configured:
        return Path(configured).expanduser()
    return Path.home() / ".codex"


CodexAdapter = make_user_scope_adapter(
    "codex",
    target_factory=lambda: _codex_home() / "AGENTS.md",
    install_fn=_install,
    plan_fn=_plan,
    uninstall_fn=_uninstall,
    update_fn=_update,
    verify_fn=_verify,
    class_name="CodexAdapter",
)
