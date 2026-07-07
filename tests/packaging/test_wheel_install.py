# SPDX-License-Identifier: MIT

"""Clean-env built-wheel install + profile-validation smoke test (C5 / PK-4).

Builds the wheel, installs it into an isolated fresh venv with NO source tree on
the path, then validates a real profile end-to-end (loads the packaged profile
schema, runs the jsonschema validator with a FormatChecker, crawling the
draft-2020-12 meta-schema). This is the regression guard that the distributed
wheel is genuinely installable + functional from a clean environment — catching
missing packaged schema data, broken entry points, or unresolved deps that the
source-tree clean-install gate (which runs with the source on the path) cannot.

Note on C5 scope: a pip-installed wheel resolves ``import jsonschema`` to the
DECLARED ``jsonschema`` dependency (a real third-party package), not ``apothem._vendor``
(which is only used via the npx ``PYTHONPATH=[_vendor, src]`` path, off the
source tree — never the wheel). So validation here does not crash on missing
vendored data; vendored-data *completeness* in the artifact is guarded by
``test_wheel_payload`` (archive membership) instead. See PLAN-NOTES PK-4.D1.
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import venv
from pathlib import Path
from typing import Final

import pytest

REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[2]


def _isolated_env() -> dict[str, str]:
    """Return the parent env minus vars that would defeat venv isolation.

    Strips ``PYTHONPATH`` (the suite runs with ``PYTHONPATH=src``, which would
    leak the source tree into the venv subprocess), plus ``VIRTUAL_ENV`` /
    ``PYTHONHOME`` so the fresh venv's interpreter is the sole import root.
    """
    return {
        key: value
        for key, value in os.environ.items()
        if key not in {"PYTHONPATH", "VIRTUAL_ENV", "PYTHONHOME"}
    }


# pip failures that reflect the environment (no network, unreachable index),
# not a packaging defect. Anything else — a broken Requires-Dist, invalid
# metadata, a malformed wheel — must FAIL the test, not skip it.
_NETWORK_FAILURE_MARKERS: Final[tuple[str, ...]] = (
    "Could not fetch URL",
    "ReadTimeout",
    "No matching distribution found",
    "Temporary failure in name resolution",
    "Failed to establish a new connection",
    "Connection timed out",
    "ProxyError",
)


def _is_network_failure(stderr: str) -> bool:
    """True when pip's stderr indicates index unreachability, not a defect."""
    return any(marker in stderr for marker in _NETWORK_FAILURE_MARKERS)


# Validates a populated profile from the INSTALLED package — no PYTHONPATH=src.
# Loads the packaged profile schema and runs the jsonschema validator (the
# declared dependency when pip-installed) with a FormatChecker, forcing a
# draft-2020-12 meta-schema crawl through its specification data files.
_VALIDATE_SNIPPET: Final[str] = (
    "import apothem\n"
    "from apothem.lib.profile import validate_profile\n"
    "p = validate_profile({'identity': {'name': 'Wheel User', 'role': 'eng'},\n"
    "                      'preferences': {'language': 'python'}})\n"
    "assert p.identity.name == 'Wheel User'\n"
    "print('WHEEL_VALIDATE_OK')\n"
)


def _build_wheel(tmp_path: Path) -> Path:
    if importlib.util.find_spec("build") is None:
        pytest.skip("python build module unavailable on this host")
    out = tmp_path / "dist"
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "build",
            "--wheel",
            "--outdir",
            str(out),
            str(REPO_ROOT),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        pytest.fail(
            f"wheel build failed (exit {completed.returncode}): {completed.stderr[:800]}"
        )
    wheels = sorted(out.glob("*.whl"))
    if not wheels:
        pytest.fail("no wheel artifact produced")
    return wheels[0]


def _venv_python(venv_dir: Path) -> Path:
    if sys.platform == "win32":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def test_network_failure_markers_discriminate() -> None:
    """Index unreachability skips; a metadata defect must not match."""
    assert _is_network_failure(
        "WARNING: Retrying... Could not fetch URL https://index.invalid/simple/"
    )
    assert _is_network_failure(
        "ERROR: No matching distribution found for jsonschema>=4"
    )
    assert not _is_network_failure("ERROR: Wheel 'apothem' located at ... is invalid.")
    assert not _is_network_failure(
        "ERROR: Invalid requirement: 'jsonschema >=== 4' (from METADATA)"
    )


def test_built_wheel_installs_and_validates_a_profile(tmp_path: Path) -> None:
    wheel = _build_wheel(tmp_path)

    venv_dir = tmp_path / "venv"
    venv.create(venv_dir, with_pip=True)
    python = _venv_python(venv_dir)
    assert python.is_file(), f"venv python not found at {python}"

    env = _isolated_env()
    install = subprocess.run(
        [
            str(python),
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            str(wheel),
        ],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    if install.returncode != 0:
        # Only index unreachability is an environment condition worth a
        # skip; any other pip failure is a packaging defect and must fail.
        if _is_network_failure(install.stderr):
            pytest.skip(f"pip index unavailable: {install.stderr[:400]}")
        pytest.fail(
            f"pip install of the built wheel failed (exit {install.returncode}):\n"
            f"{install.stderr[:2000]}"
        )

    # Run the validation from a CWD with no source tree, under the isolated env,
    # so only the installed package is importable (not src/).
    result = subprocess.run(
        [str(python), "-c", _VALIDATE_SNIPPET],
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
        env=env,
        check=False,
    )
    assert result.returncode == 0, (
        "installed-wheel profile validation failed from a clean env — the wheel "
        "is not installable/functional (packaged schema data, entry points, or "
        f"deps):\nstdout: {result.stdout[:400]}\nstderr: {result.stderr[:800]}"
    )
    assert "WHEEL_VALIDATE_OK" in result.stdout
