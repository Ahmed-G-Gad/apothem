# SPDX-License-Identifier: MIT

"""The npm shim (``bin/apothem.mjs``) forwards to the engine on any Node floor.

Runs the shim with ``node`` against this checkout. ``APOTHEM_PYTHON`` points
the shim at the test interpreter so the probe is deterministic. Skipped when
``node`` is not on ``PATH``; the ``npm-shim`` CI workflow runs the same checks
on every supported Node major.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SHIM = _REPO_ROOT / "bin" / "apothem.mjs"
_NODE = shutil.which("node")

pytestmark = pytest.mark.skipif(_NODE is None, reason="node is not on PATH")


def _run(args: list[str], env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    assert _NODE is not None
    return subprocess.run(
        [_NODE, str(_SHIM), *args],
        capture_output=True,
        text=True,
        env=env,
        check=False,
        timeout=120,
    )


def _base_env(home: Path) -> dict[str, str]:
    env = {
        key: value
        for key, value in os.environ.items()
        if key not in {"PYTHONPATH", "CODEX_HOME", "XDG_CONFIG_HOME"}
    }
    env["HOME"] = str(home)
    env["USERPROFILE"] = str(home)
    env["APOTHEM_PYTHON"] = sys.executable
    return env


def test_shim_reports_the_engine_version(tmp_path: Path) -> None:
    """``node bin/apothem.mjs --version`` runs the bundled engine."""
    result = _run(["--version"], _base_env(tmp_path))
    assert result.returncode == 0, result.stderr
    assert "Apothem, version" in result.stdout


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX wrapper interpreter")
def test_shim_surfaces_the_engine_prerequisite_error(tmp_path: Path) -> None:
    """A Python without click and rich gets the engine's pip fix through the shim.

    The wrapper runs the test interpreter with ``-S`` (no site-packages), so
    neither prerequisite is importable while the vendored tree still is.
    """
    wrapper = tmp_path / "bare-python"
    wrapper.write_text(
        f'#!/bin/sh\nexec "{sys.executable}" -S "$@"\n', encoding="utf-8"
    )
    wrapper.chmod(0o755)
    env = _base_env(tmp_path)
    env["APOTHEM_PYTHON"] = str(wrapper)
    result = _run(["--version"], env)
    assert result.returncode == 1, result.stderr
    assert "Traceback" not in result.stderr
    assert "-m pip install" in result.stderr
    assert '"click==8.4.2"' in result.stderr
