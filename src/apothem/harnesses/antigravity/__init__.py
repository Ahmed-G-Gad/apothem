# SPDX-License-Identifier: MIT

"""Apothem harness adapter for antigravity — manifest-driven install.

Materializes the apothem convention surface into the Antigravity harness
target. Antigravity reads ``~/.gemini/GEMINI.md`` as global context and
loads plugins from ``~/.gemini/config/plugins/<name>/`` (current CLI
releases do, and the Antigravity App and IDE load the same folder); the CLI
keeps its own settings and cache under ``~/.gemini/antigravity-cli/``.
Apothem installs a named plugin at ``~/.gemini/config/plugins/apothem/`` for
cohorts that should not collide with Gemini CLI project-local files. An
install or update over an earlier install backs up and removes the plugin's
earlier folder, ``~/.gemini/antigravity-cli/plugins/apothem/``, whole; an
uninstall removes that earlier folder whole and Apothem's files from the
current one. ``~/.gemini/antigravity/`` is the Antigravity App's data
folder, so no install, update or uninstall touches it.

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
