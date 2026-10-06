# SPDX-License-Identifier: MIT

"""The POSIX installers colour only a terminal, and honour NO_COLOR.

The ``bold``/``info``/``ok``/``warn``/``die`` helpers in ``install.sh``,
``update.sh`` and ``uninstall.sh`` used to hard-code ANSI escapes, so CI logs,
redirected files and screen readers got raw escape sequences. Each script is
run on a path that prints its banner and then fails fast (``APOTHEM_SOURCE``
points at an empty directory), so nothing is installed or removed.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

_INSTALLER_DIR = Path(__file__).resolve().parents[2] / "scripts" / "installer"
_SCRIPTS = ("install.sh", "update.sh", "uninstall.sh")
_ESC = "\x1b["

pytestmark = pytest.mark.skipif(
    sys.platform == "win32" or shutil.which("sh") is None,
    reason="POSIX installers need sh and a pty",
)


def _env(tmp_path: Path, *, no_color: bool) -> dict[str, str]:
    empty = tmp_path / "not-a-source"
    empty.mkdir(exist_ok=True)
    env = {
        key: value
        for key, value in os.environ.items()
        if key not in {"NO_COLOR", "PYTHONPATH", "APOTHEM_AUTO_INSTALL_DEPS"}
    }
    env.update(
        HOME=str(tmp_path / "home"),
        APOTHEM_HOME=str(tmp_path / "home" / ".apothem"),
        APOTHEM_SOURCE=str(empty),
    )
    if no_color:
        env["NO_COLOR"] = "1"
    return env


def _run_piped(script: str, env: dict[str, str]) -> str:
    result = subprocess.run(
        ["sh", str(_INSTALLER_DIR / script), "--yes"],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
        check=False,
    )
    assert result.returncode != 0, result.stdout + result.stderr
    return result.stdout + result.stderr


def _run_on_terminal(script: str, env: dict[str, str]) -> str:
    import pty

    leader, follower = pty.openpty()
    try:
        process = subprocess.Popen(
            ["sh", str(_INSTALLER_DIR / script), "--yes"],
            stdin=subprocess.DEVNULL,
            stdout=follower,
            stderr=follower,
            env=env,
        )
    finally:
        os.close(follower)
    chunks: list[bytes] = []
    try:
        while True:
            try:
                chunk = os.read(leader, 4096)
            except OSError:
                break
            if not chunk:
                break
            chunks.append(chunk)
    finally:
        os.close(leader)
    process.wait(timeout=120)
    return b"".join(chunks).decode("utf-8", "replace")


@pytest.mark.parametrize("script", _SCRIPTS)
def test_redirected_output_has_no_escape_sequences(tmp_path: Path, script: str) -> None:
    output = _run_piped(script, _env(tmp_path, no_color=False))
    assert output.strip()
    assert _ESC not in output, output


@pytest.mark.parametrize("script", _SCRIPTS)
def test_terminal_output_keeps_colour(tmp_path: Path, script: str) -> None:
    output = _run_on_terminal(script, _env(tmp_path, no_color=False))
    assert _ESC in output, output


@pytest.mark.parametrize("script", _SCRIPTS)
def test_no_color_disables_colour_on_a_terminal(tmp_path: Path, script: str) -> None:
    output = _run_on_terminal(script, _env(tmp_path, no_color=True))
    assert output.strip()
    assert _ESC not in output, output
