# SPDX-License-Identifier: MIT

"""Apothem harness adapter for antigravity — manifest-driven install.

Materializes the apothem convention surface into the Antigravity CLI
harness target. Antigravity reads ``~/.gemini/GEMINI.md`` as global
context and stores CLI customization under ``~/.gemini/antigravity-cli/``;
Apothem installs a named plugin at
``~/.gemini/antigravity-cli/plugins/apothem/`` for cohorts that should not
collide with Gemini CLI project-local files.

Delegates installation to
:mod:`apothem.harnesses.antigravity.install`, which consumes the
canonical manifest at ``src/apothem/lib/propagation-manifest.yaml``.
"""

from __future__ import annotations

from pathlib import Path

from apothem.harnesses._shared.wrapper_factories import make_user_scope_adapter
from apothem.harnesses.antigravity.install import install as _install
from apothem.harnesses.antigravity.install import plan as _plan
from apothem.harnesses.antigravity.uninstall import uninstall as _uninstall
from apothem.harnesses.antigravity.update import update as _update
from apothem.harnesses.antigravity.verify import verify as _verify

AntigravityAdapter = make_user_scope_adapter(
    "antigravity",
    target_factory=lambda: Path.home() / ".gemini/GEMINI.md",
    install_fn=_install,
    plan_fn=_plan,
    uninstall_fn=_uninstall,
    update_fn=_update,
    verify_fn=_verify,
    class_name="AntigravityAdapter",
)
