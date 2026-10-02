# SPDX-License-Identifier: MIT

"""Clean-machine install gate.

Provisions an isolated, hermetic environment, runs the self-contained
one-shot installer (``scripts/installer/install.sh``) against the local
worktree as the explicit source (no clone, no network), and asserts a
working apothem: the claude-code harness config materializes under an
isolated ``HOME`` and adapter discovery resolves the full 17-harness cohort.

The test is hermetic: it never writes outside ``tmp_path`` and never touches
the operator's real ``~/.claude``. It is skipped gracefully when ``bash`` is
unavailable, since it exercises the POSIX shell installer.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from apothem.lib.harness_registry import SUPPORTED_HARNESS_COUNT

# Repository root: tests/integration/test_clean_machine_install.py -> repo root.
REPO_ROOT = Path(__file__).resolve().parents[2]
INSTALLER = REPO_ROOT / "scripts" / "installer" / "install.sh"
SRC_DIR = REPO_ROOT / "src"

# The claude-code adapter materializes a HOME-relative singleton config.
HARNESS_CONFIG_RELATIVE = Path(".claude") / "settings.json"

# The supported harness cohort size asserted by adapter discovery.
EXPECTED_ADAPTER_COUNT = SUPPORTED_HARNESS_COUNT

# Subprocess wall-clock ceiling for the hermetic install (no network).
INSTALL_TIMEOUT_SECONDS = 180

# A minimal, schema-valid shared profile the installer can consume directly.
MINIMAL_PROFILE = """\
identity:
  name: "Clean Machine Gate"
  role: "release engineer"
  email: "gate@example.invalid"
  website: "https://example.invalid"
  github: "clean-machine-gate"

preferences:
  language: "python"
  style: "concise"
  formatter: "ruff"
  test_framework: "pytest"

seriousness: PERSONAL_USE

rules:
  - "Keep generated harness output deterministic."
"""


pytestmark = pytest.mark.skipif(
    shutil.which("bash") is None or sys.platform == "win32",
    reason=(
        "clean-machine install gate exercises the POSIX install.sh; skipped on "
        "Windows (install.ps1 is the Windows path, and `bash` there resolves to "
        "the WSL launcher, not git-bash) and when bash is absent from PATH"
    ),
)


def _interpreter_bin_dir(scratch: Path) -> Path:
    """Return a directory whose ``python`` is the interpreter running the tests.

    The installer has no interpreter override: it takes the first qualifying
    ``python`` / ``python3`` on ``PATH``. Left alone, that is whatever the host
    put first, which may lack the click and rich prerequisites the suite's own
    interpreter has, so the gate would fail for a reason unrelated to the code.
    A virtual environment's ``bin`` already holds a ``python`` that keeps the
    environment active, so it is used as is. Otherwise a ``python`` symlink to
    ``sys.executable`` is placed in a scratch directory (a symlink outside a
    virtual environment loses nothing).
    """
    interpreter = Path(sys.executable)
    if (interpreter.parent / "python").is_file():
        return interpreter.parent
    shim_dir = scratch / "python-bin"
    shim_dir.mkdir(exist_ok=True)
    for name in ("python", "python3"):
        (shim_dir / name).symlink_to(interpreter)
    return shim_dir


def _isolated_env(
    home: Path, profile: Path, apothem_home: Path, interpreter_dir: Path
) -> dict[str, str]:
    """Build a hermetic environment dict for the installer subprocess.

    The real ``HOME`` / ``USERPROFILE`` are redirected to a tmp subdir so the
    materialized harness config lands in isolation. ``APOTHEM_SOURCE`` points
    at the local worktree so the installer uses it directly with no clone and
    no network. ``PYTHONPATH`` is stripped so the installer's own
    ``PYTHONPATH=$SOURCE/src`` is what is exercised. ``interpreter_dir`` leads
    ``PATH`` so the installer resolves the interpreter running this suite, not
    the host's first ``python``.
    """
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    env["PATH"] = f"{interpreter_dir}{os.pathsep}{env.get('PATH', '')}"
    env["HOME"] = str(home)
    env["USERPROFILE"] = str(home)  # Windows HOME resolution
    env["APOTHEM_SOURCE"] = str(REPO_ROOT)
    env["APOTHEM_HOME"] = str(apothem_home)
    env["APOTHEM_HARNESS"] = "claude-code"
    env["APOTHEM_PROFILE"] = str(profile)
    # Let verify run as part of the gate (do not set APOTHEM_SKIP_VERIFY).
    return env


def test_clean_machine_install_materializes_and_discovers(tmp_path: Path) -> None:
    """The self-contained installer materializes claude-code config and
    discovery works.

    Arrange an isolated HOME + minimal profile, act by running the installer
    against the local worktree source, and assert: exit zero, the harness
    config exists under the isolated HOME, and adapter discovery against the
    same source tree resolves the full 17-harness cohort.
    """
    # Arrange.
    assert INSTALLER.is_file(), f"installer missing: {INSTALLER}"
    home = tmp_path / "home"
    home.mkdir()
    apothem_home = tmp_path / "apothem-home"
    profile = tmp_path / "profile.yaml"
    profile.write_text(MINIMAL_PROFILE, encoding="utf-8")
    env = _isolated_env(home, profile, apothem_home, _interpreter_bin_dir(tmp_path))

    # Act.
    result = subprocess.run(
        ["bash", str(INSTALLER)],
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=INSTALL_TIMEOUT_SECONDS,
    )

    # Assert: installer exited clean.
    assert result.returncode == 0, (
        "installer exited non-zero "
        f"(code {result.returncode})\n"
        f"--- stdout ---\n{result.stdout}\n"
        f"--- stderr ---\n{result.stderr}"
    )

    # Assert: harness config materialized under the isolated HOME.
    materialized = home / HARNESS_CONFIG_RELATIVE
    assert materialized.is_file(), (
        f"expected materialized config at {materialized}\n"
        f"--- stdout ---\n{result.stdout}\n"
        f"--- stderr ---\n{result.stderr}"
    )

    # Assert: hermeticity — nothing landed in the operator's real HOME.
    assert str(REPO_ROOT) not in str(materialized.resolve())

    # Assert: adapter discovery resolves the full cohort against this source.
    discovery_env = dict(env)
    discovery_env["PYTHONPATH"] = str(SRC_DIR)
    probe = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from apothem.lib.harness_registry import "
                "discover_adapters, SUPPORTED_HARNESS_COUNT;"
                "from pathlib import Path; import apothem;"
                "root = Path(apothem.__file__).resolve().parent;"
                "n = len(discover_adapters(root));"
                "print(n, SUPPORTED_HARNESS_COUNT)"
            ),
        ],
        cwd=str(REPO_ROOT),
        env=discovery_env,
        capture_output=True,
        text=True,
        timeout=INSTALL_TIMEOUT_SECONDS,
    )
    assert probe.returncode == 0, (
        "adapter discovery probe failed\n"
        f"--- stdout ---\n{probe.stdout}\n"
        f"--- stderr ---\n{probe.stderr}"
    )
    discovered_count = int(probe.stdout.split()[0])
    assert discovered_count == EXPECTED_ADAPTER_COUNT, (
        f"expected {EXPECTED_ADAPTER_COUNT} adapters, "
        f"discovered {discovered_count}: {probe.stdout.strip()}"
    )


def test_clean_machine_install_without_a_profile_needs_one_run(
    tmp_path: Path,
) -> None:
    """A first run with no profile creates it, installs, and verifies.

    The installer used to stop after copying the example profile, exit 0,
    and install nothing until it ran a second time. One run must now leave
    the harness installed and ``verify`` at exit 0.
    """
    home = tmp_path / "home"
    home.mkdir()
    profile = home / ".config" / "apothem" / "profile.yaml"
    env = _isolated_env(home, profile, tmp_path / "apothem-home")

    result = subprocess.run(
        ["bash", str(INSTALLER)],
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=INSTALL_TIMEOUT_SECONDS,
    )

    output = f"--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"
    assert result.returncode == 0, output
    assert profile.is_file(), output
    assert (home / HARNESS_CONFIG_RELATIVE).is_file(), output
    assert "re-run this installer" not in result.stdout, output

    verify_env = dict(env)
    verify_env["PYTHONPATH"] = str(SRC_DIR)
    verify = subprocess.run(
        [sys.executable, "-m", "apothem", "verify", "--harness", "claude-code"],
        cwd=str(tmp_path),
        env=verify_env,
        capture_output=True,
        text=True,
        timeout=INSTALL_TIMEOUT_SECONDS,
    )
    assert verify.returncode == 0, verify.stdout + verify.stderr


def test_clean_machine_dry_run_without_a_profile_writes_nothing(
    tmp_path: Path,
) -> None:
    """``--dry-run`` with no profile previews with the example and writes nothing."""
    home = tmp_path / "home"
    home.mkdir()
    profile = home / ".config" / "apothem" / "profile.yaml"
    env = _isolated_env(home, profile, tmp_path / "apothem-home")

    result = subprocess.run(
        ["bash", str(INSTALLER), "--dry-run"],
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=INSTALL_TIMEOUT_SECONDS,
    )

    output = f"--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"
    assert result.returncode == 0, output
    assert list(home.iterdir()) == [], output
