# SPDX-License-Identifier: MIT

"""The driver modules that entry points import directly load on their own.

The suite imports the driver package before anything else, so a cycle that
only bites when an entry point imports one module first goes unseen: the
plugin-tree assembler and the Claude Code adapter import the converters
directly, and the layout module is imported the same way. The driver's
internal modules are loaded through the package and are not listed. Each
module here is imported alone in a fresh interpreter.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parents[2] / "src"
_MODULES = (
    "apothem.harnesses._shared.install_driver",
    "apothem.harnesses._shared.install_driver_converters",
    "apothem.harnesses._shared.install_driver_layout",
    "apothem.lib.plugin_tree",
)


@pytest.mark.parametrize("module", _MODULES)
def test_module_imports_first(module: str) -> None:
    env = {**os.environ, "PYTHONPATH": str(_SRC)}
    completed = subprocess.run(
        [sys.executable, "-c", f"import {module}"],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
