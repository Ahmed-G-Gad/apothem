# SPDX-License-Identifier: MIT

"""The npm shim (``bin/apothem.mjs``) forwards to the engine on any Node floor.

Runs the shim with ``node`` against this checkout. ``APOTHEM_PYTHON`` points
the shim at the test interpreter so the probe is deterministic. Skipped when
``node`` is not on ``PATH``; the ``npm-shim`` CI workflow runs the same checks
on every supported Node major.
"""

from __future__ import annotations

import json
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


def test_shim_dry_run_install_writes_nothing(tmp_path: Path) -> None:
    """A dry-run install through the shim on a clean HOME exits 0 and writes nothing."""
    home = tmp_path / "home"
    home.mkdir()
    result = _run(
        ["install", "--harness", "claude-code", "--dry-run", "--json"],
        _base_env(home),
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "dry_run"
    assert list(home.iterdir()) == []


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


def _plant_shadow_modules(folder: Path, marker: Path) -> None:
    """Fill ``folder`` with modules that write ``marker`` when imported or run."""
    body = f"from pathlib import Path\nPath({str(marker)!r}).write_text('ran')\n"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "click.py").write_text(body, encoding="utf-8")
    (folder / "rich").mkdir()
    (folder / "rich" / "__init__.py").write_text(body, encoding="utf-8")
    (folder / "apothem").mkdir()
    (folder / "apothem" / "__init__.py").write_text(body, encoding="utf-8")
    (folder / "apothem" / "__main__.py").write_text(body, encoding="utf-8")


@pytest.mark.parametrize("args", [["--version"], ["--help"]])
def test_shim_ignores_modules_in_the_current_folder(
    tmp_path: Path, args: list[str]
) -> None:
    """A ``click.py``, ``rich/`` or ``apothem/`` in the cwd never shadows the engine.

    Guards GHSA-4rh9-7m5x-94j9: Python puts the working directory first on
    ``sys.path`` for ``-c`` and ``-m``, so the shim must drop it on every start.
    """
    marker = tmp_path / "marker"
    work = tmp_path / "work"
    _plant_shadow_modules(work, marker)
    assert _NODE is not None
    env = _base_env(tmp_path)
    result = subprocess.run(
        [_NODE, str(_SHIM), *args],
        capture_output=True,
        text=True,
        env=env,
        cwd=work,
        check=False,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
    assert not marker.exists(), "a module from the current folder ran"
    assert "Apothem" in result.stdout + result.stderr


def test_shim_ignores_the_current_folder_even_with_pythonsafepath_off(
    tmp_path: Path,
) -> None:
    """A caller's ``PYTHONSAFEPATH=`` does not bring the current folder back."""
    marker = tmp_path / "marker"
    work = tmp_path / "work"
    _plant_shadow_modules(work, marker)
    assert _NODE is not None
    env = _base_env(tmp_path)
    env["PYTHONSAFEPATH"] = ""
    result = subprocess.run(
        [_NODE, str(_SHIM), "--version"],
        capture_output=True,
        text=True,
        env=env,
        cwd=work,
        check=False,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
    assert not marker.exists(), "a module from the current folder ran"


def test_shim_keeps_the_working_directory_and_arguments(tmp_path: Path) -> None:
    """Only ``sys.path`` changes: the engine still runs in the caller's folder."""
    work = tmp_path / "work"
    work.mkdir()
    assert _NODE is not None
    env = _base_env(tmp_path)
    result = subprocess.run(
        [
            _NODE,
            str(_SHIM),
            "install",
            "--harness",
            "claude-code",
            "--dry-run",
            "--json",
        ],
        capture_output=True,
        text=True,
        env=env,
        cwd=work,
        check=False,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["status"] == "dry_run"
    assert list(work.iterdir()) == []


@pytest.mark.parametrize(
    "entries",
    [
        ["", "/nonexistent"],
        ["/nonexistent", ""],
        ["."],
        ["relative/dir"],
    ],
)
def test_shim_drops_empty_and_relative_pythonpath_entries(
    tmp_path: Path, entries: list[str]
) -> None:
    """An empty or relative user ``PYTHONPATH`` entry never reaches Python.

    Python reads an empty entry as the current folder, so a ``sitecustomize.py``
    there would run at startup. The shim passes on only absolute entries.
    """
    marker = tmp_path / "marker"
    work = tmp_path / "work"
    _plant_shadow_modules(work, marker)
    body = f"from pathlib import Path\nPath({str(marker)!r}).write_text('ran')\n"
    for name in ("sitecustomize.py", "usercustomize.py", "json.py"):
        (work / name).write_text(body, encoding="utf-8")
    assert _NODE is not None
    env = _base_env(tmp_path)
    env["PYTHONPATH"] = os.pathsep.join(entries)
    result = subprocess.run(
        [_NODE, str(_SHIM), "--version"],
        capture_output=True,
        text=True,
        env=env,
        cwd=work,
        check=False,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
    assert not marker.exists(), "a module from the current folder ran"


@pytest.mark.skipif(sys.platform != "win32", reason="Windows path rule")
@pytest.mark.parametrize(
    "entry",
    ["\\lib", "C:rel", "C:", "/lib"],
    ids=["rooted", "drive-relative", "bare-drive", "forward-rooted"],
)
def test_shim_drops_rooted_and_drive_relative_entries_on_windows(
    tmp_path: Path, entry: str
) -> None:
    """A rooted or drive-relative entry still depends on the folder or drive."""
    marker = tmp_path / "marker"
    work = tmp_path / "work"
    _plant_shadow_modules(work, marker)
    body = f"from pathlib import Path\nPath({str(marker)!r}).write_text('ran')\n"
    (work / "sitecustomize.py").write_text(body, encoding="utf-8")
    assert _NODE is not None
    env = _base_env(tmp_path)
    env["PYTHONPATH"] = entry
    result = subprocess.run(
        [_NODE, str(_SHIM), "--version"],
        capture_output=True,
        text=True,
        env=env,
        cwd=work,
        check=False,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
    assert not marker.exists()


@pytest.mark.skipif(sys.platform != "win32", reason="Windows path rule")
@pytest.mark.parametrize("slash", ["\\", "/"], ids=["backslash", "slash"])
def test_shim_keeps_drive_path_entries_on_windows(tmp_path: Path, slash: str) -> None:
    """A drive path stays in the child's PYTHONPATH, written either way."""
    marker = tmp_path / "marker"
    lib = tmp_path / "userlib"
    lib.mkdir()
    body = f"from pathlib import Path\nPath({str(marker)!r}).write_text('ran')\n"
    (lib / "sitecustomize.py").write_text(body, encoding="utf-8")
    work = tmp_path / "work"
    work.mkdir()
    env = _base_env(tmp_path)
    env["PYTHONPATH"] = str(lib).replace("\\", slash)
    result = subprocess.run(
        [_NODE, str(_SHIM), "--version"],
        capture_output=True,
        text=True,
        env=env,
        cwd=work,
        check=False,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
    assert marker.exists(), "the kept entry was dropped"
