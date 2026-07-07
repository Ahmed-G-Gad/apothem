# SPDX-License-Identifier: MIT

"""Apothem harness adapter for opencode.

Materializes ``~/.config/opencode/opencode.json`` per the opencode vendor
canonical schema at https://opencode.ai/docs/config/ and the adapter-local
``STANDARD-CONVENTION-PIN.md``. The POSIX-canonical path is uniform across
supported platforms. The install step also propagates commands, skills, and
subagents into OpenCode's native discovery directories and keeps unsupported
reference material under ``~/.config/opencode/.apothem/support/``.
Delegates install logic to :mod:`apothem.harnesses.opencode.install`, which
renders the native config via :mod:`apothem.harnesses.opencode.materializer`.
"""

from __future__ import annotations

from pathlib import Path

from apothem.harnesses._shared.wrapper_factories import make_native_config_adapter
from apothem.harnesses.opencode.install import install as _install
from apothem.harnesses.opencode.materializer import (
    materialize_native_config as materialize_native_config,
)
from apothem.harnesses.opencode.uninstall import uninstall as _uninstall
from apothem.harnesses.opencode.update import update as _update
from apothem.harnesses.opencode.verify import verify as _verify

OpenCodeAdapter = make_native_config_adapter(
    "opencode",
    target_factory=lambda: Path.home() / ".config/opencode/opencode.json",
    install_fn=_install,
    uninstall_fn=_uninstall,
    update_fn=_update,
    verify_fn=_verify,
    class_name="OpenCodeAdapter",
)
