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
    """The installer drives apothem via ``-m apothem`` so its own calls succeed
    with no launcher on PATH."""
    content = _read(name)
    assert "-m apothem install" in content
    assert "-m apothem verify" in content


@pytest.mark.parametrize(
    "name", ["install.sh", "install.ps1", "uninstall.sh", "uninstall.ps1"]
)
def test_installer_carries_no_managed_path_block(name: str) -> None:
    """The self-contained installer/uninstaller manage no PATH entry — none of
    the retired managed-PATH markers or PATH-mutation idioms appears."""
    content = _read(name)
    for marker in _RETIRED_PATH_MARKERS:
        assert marker not in content, f"{name} carries retired PATH idiom: {marker}"
