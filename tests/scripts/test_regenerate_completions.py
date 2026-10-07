# SPDX-License-Identifier: MIT

"""``scripts/dev/regenerate-completions.{sh,ps1}`` reproduce the committed goldens.

``tests/unit/test_completion_goldens.py`` pins each golden to ``apothem
completion <shell>``. This module pins the scripts to the goldens. Each script
runs against a sandbox checkout: the script under ``scripts/dev/`` beside a copy
of ``src/apothem`` with its goldens deleted, so a run rewrites the sandbox and
never this checkout.

The scripts once resolved ``apothem`` from ``PATH`` first. The installer's shim
there puts the installed engine's ``src/`` first on ``PYTHONPATH``, so the
goldens came from the installed engine rather than the checkout. With an engine
predating the single-newline fix installed, both scripts wrote a trailing blank
line into every golden and still reported success. Here a stale ``apothem``
sits first on ``PATH`` and must never be consulted, and a broken entry point in
the sandbox must be the one that runs.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPTS = _REPO_ROOT / "scripts" / "dev"
_GOLDENS = _REPO_ROOT / "src" / "apothem" / "cli" / "completions"
_GOLDEN_NAMES = ("apothem.bash", "apothem.fish", "apothem.ps1", "apothem.zsh")
_STALE_OUTPUT = "# stale engine output"

_BASH = shutil.which("bash")
_PWSH = shutil.which("pwsh") or shutil.which("powershell")

_Runner = Callable[[Path, dict[str, str]], subprocess.CompletedProcess[str]]


def _run_sh(script: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    assert _BASH is not None
    return subprocess.run(
        [_BASH, str(script)],
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=180,
        check=False,
    )


def _run_ps1(script: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    assert _PWSH is not None
    return subprocess.run(
        [
            _PWSH,
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script),
        ],
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=180,
        check=False,
    )


_GENERATORS = [
    pytest.param(
        "regenerate-completions.sh",
        _run_sh,
        marks=pytest.mark.skipif(
            _BASH is None or os.name == "nt",
            reason="the .sh generator targets POSIX bash",
        ),
        id="sh",
    ),
    pytest.param(
        "regenerate-completions.ps1",
        _run_ps1,
        marks=pytest.mark.skipif(_PWSH is None, reason="no PowerShell on this host"),
        id="ps1",
    ),
]


def _sandbox(tmp_path: Path, script: str) -> tuple[Path, Path]:
    """Lay out a checkout holding *script*; return (script path, completions dir)."""
    root = tmp_path / "checkout"
    dev = root / "scripts" / "dev"
    dev.mkdir(parents=True)
    shutil.copy2(_SCRIPTS / script, dev / script)
    shutil.copytree(
        _REPO_ROOT / "src" / "apothem",
        root / "src" / "apothem",
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    out = root / "src" / "apothem" / "cli" / "completions"
    for golden in out.iterdir():
        golden.unlink()
    return dev / script, out


def _env(tmp_path: Path) -> dict[str, str]:
    """Pin the interpreter and put a stale ``apothem`` first on ``PATH``."""
    stale_bin = tmp_path / "stale-bin"
    stale_bin.mkdir()
    shim = stale_bin / "apothem"
    shim.write_text(f"#!/bin/sh\necho '{_STALE_OUTPUT}'\n", encoding="utf-8")
    shim.chmod(0o755)
    (stale_bin / "apothem.cmd").write_text(
        f"@echo {_STALE_OUTPUT}\r\n", encoding="utf-8"
    )
    env = dict(os.environ)
    env["PATH"] = str(stale_bin) + os.pathsep + env.get("PATH", "")
    env["APOTHEM_PYTHON"] = sys.executable
    # The script alone decides what is importable, and a leftover completion
    # trigger would turn `apothem completion` into a completion request.
    env.pop("PYTHONPATH", None)
    env.pop("_APOTHEM_COMPLETE", None)
    return env


@pytest.mark.parametrize(("script", "run"), _GENERATORS)
def test_regenerates_committed_goldens(
    tmp_path: Path, script: str, run: _Runner
) -> None:
    """Every golden comes back byte for byte, with ``PATH`` never consulted."""
    target, out = _sandbox(tmp_path, script)
    completed = run(target, _env(tmp_path))
    assert completed.returncode == 0, completed.stderr
    assert sorted(path.name for path in out.iterdir()) == sorted(_GOLDEN_NAMES)
    for name in _GOLDEN_NAMES:
        # .gitattributes checks *.ps1 out with CRLF; the index and the scripts
        # both use LF.
        expected = (_GOLDENS / name).read_bytes().replace(b"\r\n", b"\n")
        assert (out / name).read_bytes() == expected, name


@pytest.mark.parametrize(
    "entry_point", ["raise SystemExit(3)\n", ""], ids=["fails", "silent"]
)
@pytest.mark.parametrize(("script", "run"), _GENERATORS)
def test_failed_generation_keeps_existing_golden(
    tmp_path: Path, script: str, run: _Runner, entry_point: str
) -> None:
    """A generator that fails, or exits 0 printing nothing, writes no golden.

    The broken entry point lives only in the sandbox, so the refusal also shows
    that the checkout's ``src/`` comes first on ``PYTHONPATH``.
    """
    target, out = _sandbox(tmp_path, script)
    (out.parents[1] / "__main__.py").write_text(entry_point, encoding="utf-8")
    sentinel = out / "apothem.bash"
    sentinel.write_bytes(b"sentinel\n")
    completed = run(target, _env(tmp_path))
    assert completed.returncode != 0, completed.stdout
    assert sentinel.read_bytes() == b"sentinel\n"
    assert [path.name for path in out.iterdir()] == ["apothem.bash"]
