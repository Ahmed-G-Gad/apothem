# SPDX-License-Identifier: MIT

"""A folder that tells ``Proj`` from ``proj``, for tests of case handling.

On Windows :func:`case_sensitive_folder` turns on per-folder case
sensitivity (as WSL sets it under ``/mnt/c``), which the folders made in it
inherit; elsewhere the file system must already be case sensitive. The test
is skipped when neither holds.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest


def case_sensitive_folder(folder: Path) -> None:
    """Make *folder* tell ``Probe`` from ``probe``, or skip the test."""
    folder.mkdir()
    if sys.platform == "win32":
        try:
            done = subprocess.run(
                ["fsutil", "file", "setCaseSensitiveInfo", str(folder), "enable"],
                capture_output=True,
                check=False,
            )
        except OSError:
            pytest.skip("fsutil is not available")
        if done.returncode != 0:
            pytest.skip("this host cannot turn on per-folder case sensitivity")
    (folder / "Probe").mkdir()
    if (folder / "probe").exists():
        pytest.skip("this file system does not tell names apart by case")
    (folder / "Probe").rmdir()
