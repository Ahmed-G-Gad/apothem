# SPDX-License-Identifier: MIT

"""The POSIX installer's inline interpreter probe skips Microsoft Store shims.

``scripts/installer/install.sh`` reuses the ``find-python.sh`` locator when it
runs from a source tree. Run from anywhere else (the ``curl ... | sh`` form, or
a copy outside the checkout), the script probes the bare interpreter names on
``PATH`` itself. That fallback must not execute a candidate that resolves under
a ``WindowsApps`` directory: the Store launcher alias opens the Store page
instead of Python. ``install.ps1`` and the npm shim reject the same alias.

Each case runs a copy of ``install.sh`` placed outside the source tree, so the
locator is absent and the fallback is the only probe that runs. The stub
interpreters append to a sentinel file every time they are executed, so a stub
the fallback runs is visible even when the run then fails.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT: Path = Path(__file__).resolve().parents[2]
INSTALL_SH: Path = REPO_ROOT / "scripts" / "installer" / "install.sh"
SH: str = shutil.which("sh") or "sh"

# The names the inline probe tries, in order.
PROBE_NAMES: tuple[str, ...] = (
    "python3",
    "python",
    "python3.14",
    "python3.13",
    "python3.12",
    "python3.11",
    "python3.10",
)
NO_PYTHON: str = "No Python >= 3.10 found in PATH"

pytestmark = pytest.mark.skipif(
    shutil.which("sh") is None,
    reason="runs the POSIX install.sh under sh",
)


def _write_stub_dir(directory: Path, sentinel: Path) -> None:
    """Write a stub for every probed name into *directory*.

    Each stub appends a line to *sentinel* when it runs, then runs the interpreter
    executing this test, so it passes the version probe. A fallback that runs the
    stub therefore accepts it and records the run.
    """
    directory.mkdir(parents=True)
    real = Path(sys.executable).as_posix()
    body = (
        f'#!/bin/sh\nprintf "ran\\n" >> "{sentinel.as_posix()}"\nexec "{real}" "$@"\n'
    )
    for name in PROBE_NAMES:
        stub = directory / name
        stub.write_text(body, encoding="utf-8", newline="\n")
        stub.chmod(0o755)


def _run_copied_installer(
    tmp_path: Path, path_dirs: tuple[Path, ...]
) -> subprocess.CompletedProcess[str]:
    """Run a copy of install.sh outside the source tree, with *path_dirs* first on PATH."""
    # A copy outside the checkout has no ../../src/apothem/hooks/lib/find-python.sh
    # beside it, so the inline fallback is the probe that runs.
    installer = tmp_path / "outside" / "scripts" / "installer"
    installer.mkdir(parents=True)
    script = installer / "install.sh"
    shutil.copyfile(INSTALL_SH, script)

    home = tmp_path / "home"
    source = tmp_path / "empty-source"
    home.mkdir()
    source.mkdir()

    # APOTHEM_SOURCE names an empty directory. install.sh checks it after the
    # Python prerequisite, so a run that clears the probe ends quickly there.
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith("APOTHEM_") and key not in {"PYTHONPATH", "NO_COLOR"}
    }
    env.update(
        PATH=os.pathsep.join(
            [*(str(d) for d in path_dirs), os.environ.get("PATH", "")]
        ),
        HOME=str(home),
        APOTHEM_HOME=str(home / ".apothem"),
        APOTHEM_BIN_DIR=str(home / "bin"),
        APOTHEM_SOURCE=str(source),
        NO_COLOR="1",
    )
    return subprocess.run(
        [SH, str(script)],
        env=env,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
        check=False,
    )


def test_inline_probe_does_not_execute_a_windowsapps_candidate(tmp_path: Path) -> None:
    """A candidate under a WindowsApps directory is skipped before it runs.

    The stub would pass the version probe, so without the skip the probe would
    run it, record the run, and accept it. With the skip, nothing runs and the
    installer stops at the missing-Python message.
    """
    sentinel = tmp_path / "ran.log"
    shim_dir = tmp_path / "Microsoft" / "WindowsApps"
    _write_stub_dir(shim_dir, sentinel)

    result = _run_copied_installer(tmp_path, (shim_dir,))

    assert not sentinel.exists(), "the inline probe executed a WindowsApps candidate"
    assert result.returncode != 0
    assert NO_PYTHON in result.stderr


def test_inline_probe_accepts_the_same_stub_outside_windowsapps(tmp_path: Path) -> None:
    """The same stub is accepted once its directory is not a WindowsApps one.

    This case shows the skip is by path. A probe that dropped every candidate
    would also pass the case above.
    """
    sentinel = tmp_path / "ran.log"
    bin_dir = tmp_path / "Other" / "bin"
    _write_stub_dir(bin_dir, sentinel)

    result = _run_copied_installer(tmp_path, (bin_dir,))

    assert sentinel.exists(), "the inline probe did not run the stub"
    assert NO_PYTHON not in result.stderr
    assert "python3 (" in result.stdout
