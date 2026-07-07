# SPDX-License-Identifier: MIT

"""Self-tests for the smoke-install-grep validator."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Final

_REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[3]
_GREP_PATH: Final[Path] = (
    _REPO_ROOT / "src" / "apothem" / "conformity" / "smoke_install_grep.py"
)


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("smoke_install_grep", _GREP_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["smoke_install_grep"] = module
    spec.loader.exec_module(module)
    return module


_MOD: Final[ModuleType] = _load()


_GOOD_BASH = """#!/usr/bin/env bash
set -euo pipefail

# Usage: ./install.sh [--help]
if [[ "$1" == "--help" ]]; then
    echo "usage: scripts/installer/install.sh"
    exit 0
fi

command -v git >/dev/null 2>&1 || { echo "git required"; exit 1; }
"""


_GOOD_PS1 = """#Requires -Version 7.0
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

param([switch]$Help)

if ($Help) {
    Write-Host "Usage: scripts/installer/install.ps1 [-Help]"
    exit 0
}

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Error "git is required"
}
"""


_BAD_BASH_NO_STRICT = """#!/usr/bin/env bash
echo "starting"
"""


def _seed(root: Path, *, bash: str | None, ps1: str | None) -> None:
    (root / "scripts" / "installer").mkdir(parents=True, exist_ok=True)
    if bash is not None:
        (root / "scripts/installer/install.sh").write_text(bash, encoding="utf-8")
    if ps1 is not None:
        (root / "scripts/installer/install.ps1").write_text(ps1, encoding="utf-8")


def test_paired_scripts_pass(tmp_path: Path) -> None:
    _seed(tmp_path, bash=_GOOD_BASH, ps1=_GOOD_PS1)
    result = _MOD.check(tmp_path)
    assert result.passed, result.findings


def test_bash_absent_fails(tmp_path: Path) -> None:
    _seed(tmp_path, bash=None, ps1=_GOOD_PS1)
    result = _MOD.check(tmp_path)
    assert not result.passed
    assert any(
        "scripts/installer/install.sh absent" in f.detail for f in result.findings
    )


def test_ps1_absent_fails(tmp_path: Path) -> None:
    _seed(tmp_path, bash=_GOOD_BASH, ps1=None)
    result = _MOD.check(tmp_path)
    assert not result.passed
    assert any(
        "scripts/installer/install.ps1 absent" in f.detail for f in result.findings
    )


def test_bash_missing_strict_fails(tmp_path: Path) -> None:
    _seed(tmp_path, bash=_BAD_BASH_NO_STRICT, ps1=_GOOD_PS1)
    result = _MOD.check(tmp_path)
    assert not result.passed
    assert any("strict-mode preamble absent" in f.detail for f in result.findings)


def test_ps1_missing_strict_fails(tmp_path: Path) -> None:
    _seed(tmp_path, bash=_GOOD_BASH, ps1="param([switch]$Help)\n")
    result = _MOD.check(tmp_path)
    assert not result.passed
    assert any("strict-mode preamble absent" in f.detail for f in result.findings)


def test_real_repo_root_passes() -> None:
    result = _MOD.check(_REPO_ROOT)
    assert result.passed, [f.detail for f in result.findings]
