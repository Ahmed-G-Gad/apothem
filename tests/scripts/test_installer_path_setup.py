# SPDX-License-Identifier: MIT

"""Regression guards for the self-contained installer invocation model.

``scripts/installer/install.sh`` and ``install.ps1`` install apothem as a
per-harness plugin running on system Python with bundled dependencies. There is
no console-script launcher to place on PATH: the installer and the operator both
drive the CLI through ``python -m apothem`` (scoped with ``PYTHONPATH`` to the
bundled source), so install succeeds with no shell-profile or User-PATH edit.

These tests pin two invariants of that model:

1. The installer drives the CLI through ``-m apothem`` rather than a bare
   launcher, so its own calls succeed with no PATH entry.
2. The installer/uninstaller carry no managed-PATH block — there is no launcher
   on PATH to manage, so reintroducing a sentinel block or a ``sysconfig``
   scripts-dir PATH edit would be a regression toward the retired model.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT: Path = Path(__file__).resolve().parents[2]
INSTALLER: Path = REPO_ROOT / "scripts" / "installer"

# Sentinel markers and PATH-mutation idioms the retired managed-PATH model used.
# The self-contained installer carries none of them.
_RETIRED_PATH_MARKERS: tuple[str, ...] = (
    "# >>> apothem installer (managed PATH) >>>",
    "# <<< apothem installer (managed PATH) <<<",
    'sysconfig.get_path("scripts")',
    "SetEnvironmentVariable('Path'",
)


def _read(name: str) -> str:
    return (INSTALLER / name).read_text(encoding="utf-8")


@pytest.mark.parametrize("name", ["install.sh", "install.ps1"])
def test_installer_invokes_cli_path_independently(name: str) -> None:
    """The installer runs the ``apothem`` module itself, so its own calls
    succeed with no launcher on PATH.

    It starts the module through ``runpy`` from a ``-c`` program that drops the
    current folder from ``sys.path`` (with ``PYTHONSAFEPATH=1``), not through
    ``-m apothem``, which puts the current folder first on ``sys.path``.
    """
    content = _read(name)
    assert "runpy.run_module('apothem', run_name='__main__', alter_sys=True)" in content
    assert "PYTHONSAFEPATH" in content
    assert "-m apothem install" not in content
    assert "-m apothem verify" not in content


@pytest.mark.parametrize(
    "name", ["install.sh", "install.ps1", "uninstall.sh", "uninstall.ps1"]
)
def test_installer_carries_no_managed_path_block(name: str) -> None:
    """The self-contained installer/uninstaller manage no PATH entry — none of
    the retired managed-PATH markers or PATH-mutation idioms appears."""
    content = _read(name)
    for marker in _RETIRED_PATH_MARKERS:
        assert marker not in content, f"{name} carries retired PATH idiom: {marker}"


@pytest.mark.parametrize("name", ["install.sh", "update.sh", "uninstall.sh"])
def test_posix_scripts_start_no_module_with_dash_m(name: str) -> None:
    """The POSIX installer, updater and uninstaller start the engine and pip
    through ``runpy`` with ``PYTHONSAFEPATH=1``, never ``-m``, which puts the
    current folder first on ``sys.path``; nor do their banners suggest
    ``-m apothem``."""
    content = _read(name)
    assert "PYTHONSAFEPATH=1" in content
    assert "runpy.run_module('apothem', run_name='__main__', alter_sys=True)" in content
    for started in ('-m apothem "', "-m apothem <command>", "-m apothem quickstart"):
        assert started not in content, f"{name} starts {started!r}"
    assert "-m apothem uninstall" not in content
    assert "-m pip --version" not in content
    assert '-m pip install "$@"' not in content
