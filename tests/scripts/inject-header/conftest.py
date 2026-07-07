# SPDX-License-Identifier: MIT

"""Shared fixtures for the authorship-header injector test suite.

The injector script (``scripts/inject-header.py``) carries a hyphen in
its filename and cannot be imported as a module. Tests therefore invoke
it as a subprocess through the ``run_injector`` fixture defined here,
with the working directory set to the repository root so the script's
default fixture-resolution (``src/apothem/schemas/authorship-header.txt`` and
``src/apothem/schemas/header-exceptions.txt``) hits the real fixtures.
"""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

REPO_ROOT: Path = Path(__file__).resolve().parents[3]
INJECTOR_PATH: Path = REPO_ROOT / "scripts" / "inject-header.py"
FIXTURES_ROOT: Path = Path(__file__).parent / "fixtures"

InjectorRunner = Callable[..., "subprocess.CompletedProcess[str]"]


@pytest.fixture
def repo_root() -> Path:
    """Return the absolute path to the repository root."""
    return REPO_ROOT


@pytest.fixture
def fixtures_root() -> Path:
    """Return the absolute path to the test-fixtures root."""
    return FIXTURES_ROOT


@pytest.fixture
def run_injector() -> InjectorRunner:
    """Return a callable that invokes the injector via subprocess.

    The callable accepts the injector's CLI arguments as positional
    strings and returns the completed process. The working directory
    defaults to the repository root so the script's default fixture
    paths resolve correctly.
    """

    def _run(*args: str) -> subprocess.CompletedProcess[str]:
        cmd = [sys.executable, str(INJECTOR_PATH), *args]
        return subprocess.run(
            cmd,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

    return _run
