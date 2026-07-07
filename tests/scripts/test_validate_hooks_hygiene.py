# SPDX-License-Identifier: MIT

"""Unit tests for ``validate_hooks.validate_python_hygiene``.

Verifies the whitelist of approved shell stubs under the content root's
``hooks/`` directory:

1. An empty tree passes.
2. A tree containing only the approved stubs passes.
3. Any rogue ``.ps1`` or ``.sh`` file under ``hooks/`` fails with a clear
   diagnostic.
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPTS_DEV = _REPO_ROOT / "scripts" / "dev"
_LIB_DIR = _REPO_ROOT / "src" / "apothem" / "lib"
for _p in (_SCRIPTS_DEV, _LIB_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from reporter import Reporter  # noqa: E402
from validate_hooks import validate_python_hygiene  # noqa: E402

_APPROVED: tuple[str, ...] = (
    "find-python.ps1",
    "find-python.sh",
    "find-pwsh.ps1",
    "find-pwsh.sh",
    "bootstrap.ps1",
    "bootstrap.sh",
)


@pytest.fixture
def reporter() -> Reporter:
    """Return a Reporter writing to an in-memory stream."""
    return Reporter(stream=io.StringIO())


def _scaffold(root: Path) -> None:
    """Create the directories validate_python_hygiene scans."""
    (root / "hooks" / "lib").mkdir(parents=True)


def test_empty_tree_passes(tmp_path: Path, reporter: Reporter) -> None:
    _scaffold(tmp_path)

    validate_python_hygiene(tmp_path, reporter)

    assert reporter.failed == 0
    assert reporter.passed == 1


def test_approved_stubs_pass(tmp_path: Path, reporter: Reporter) -> None:
    _scaffold(tmp_path)
    lib = tmp_path / "hooks" / "lib"
    for name in _APPROVED:
        (lib / name).write_text("# stub\n", encoding="utf-8")

    validate_python_hygiene(tmp_path, reporter)

    assert reporter.failed == 0
    assert reporter.passed == 1


def test_rogue_shell_file_fails(tmp_path: Path, reporter: Reporter) -> None:
    _scaffold(tmp_path)
    rogue = tmp_path / "hooks" / "evil.sh"
    rogue.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")

    validate_python_hygiene(tmp_path, reporter)

    assert reporter.failed == 1
    assert any("evil.sh" in err for err in reporter.errors)


def test_rogue_powershell_in_hooks_lib_fails(
    tmp_path: Path, reporter: Reporter
) -> None:
    _scaffold(tmp_path)
    rogue = tmp_path / "hooks" / "lib" / "helper.ps1"
    rogue.write_text("Write-Host stub\n", encoding="utf-8")

    validate_python_hygiene(tmp_path, reporter)

    assert reporter.failed == 1
    assert any("helper.ps1" in err for err in reporter.errors)
