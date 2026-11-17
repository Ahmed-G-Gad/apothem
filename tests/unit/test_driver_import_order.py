# SPDX-License-Identifier: MIT

"""The driver modules that entry points import directly load on their own.

The suite imports the driver package before anything else, so a cycle that
only bites when an entry point imports one module first goes unseen: the
plugin-tree assembler and the Claude Code adapter import the converters
directly, and the layout module is imported the same way. Each module here
is imported alone in a fresh interpreter.

Every ``install_driver_*`` module is imported first too: the concern modules
read the ``install_driver`` shim's attributes inside the functions that need
them, never at import, so whichever module a program loads first, the shim
and its siblings load in a working order.
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


def test_each_install_driver_module_imports_first() -> None:
    shared = _SRC / "apothem" / "harnesses" / "_shared"
    modules = sorted(path.stem for path in shared.glob("install_driver_*.py"))
    assert modules
    env = {**os.environ, "PYTHONPATH": str(_SRC)}
    running = {
        name: subprocess.Popen(
            [sys.executable, "-c", f"import apothem.harnesses._shared.{name}"],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
        )
        for name in modules
    }

    failed = {}
    try:
        for name, process in running.items():
            _, stderr = process.communicate(timeout=120)
            if process.returncode != 0:
                failed[name] = stderr.strip().splitlines()[-1:]
    finally:
        # A hung import must not leave the other interpreters running.
        for process in running.values():
            if process.poll() is None:
                process.kill()
                process.communicate()

    assert failed == {}
