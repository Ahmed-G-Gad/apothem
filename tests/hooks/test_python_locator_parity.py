# SPDX-License-Identifier: MIT

"""Cross-implementation parity for the three real-CPython locators.

The apothem hook machinery locates a real CPython >= 3.10 in three parallel
implementations that MUST agree on their shared constants — candidate
executable names, the interpreter byte-size floor, and the version floor:

* ``src/apothem/hooks/lib/find-python.sh`` — the POSIX-sh bootstrap locator.
* ``src/apothem/hooks/lib/find-python.ps1`` — its PowerShell counterpart.
* ``src/apothem/lib/python_resolver.py`` — the install-time Python resolver
  that wires ``${PYTHON_BIN}`` into hook commands.

Each carries its own hand-authored copy of the constants; nothing mechanically
pins them in step, so a bump to one (a new ``python3.15`` candidate, a raised
floor) can silently diverge from the others. This test reads all three sources
and asserts the shared constants match. It parses the two shell sources
textually and imports the Python module's constants directly — no subprocess,
no interpreter probe.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Final

from apothem.lib.python_resolver import (
    _CANDIDATE_NAMES,
    _MIN_INTERPRETER_BYTES,
    MIN_MAJOR,
    MIN_MINOR,
)

_REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[2]
_HOOKS_LIB: Final[Path] = _REPO_ROOT / "src" / "apothem" / "hooks" / "lib"
_FIND_PYTHON_SH: Final[Path] = _HOOKS_LIB / "find-python.sh"
_FIND_PYTHON_PS1: Final[Path] = _HOOKS_LIB / "find-python.ps1"


def _sh_candidate_names() -> tuple[str, ...]:
    """Extract the candidate list from find-python.sh's ``_frp_candidates=``."""
    text = _FIND_PYTHON_SH.read_text(encoding="utf-8")
    match = re.search(r'_frp_candidates="([^"]+)"', text)
    assert match is not None, "candidate list not found in find-python.sh"
    return tuple(match.group(1).split())


def _ps1_candidate_names() -> tuple[str, ...]:
    """Extract the candidate array from find-python.ps1's ``$candidates = @(...)``."""
    text = _FIND_PYTHON_PS1.read_text(encoding="utf-8")
    match = re.search(r"\$candidates\s*=\s*@\(([^)]+)\)", text)
    assert match is not None, "candidate array not found in find-python.ps1"
    return tuple(re.findall(r"'([^']+)'", match.group(1)))


def _sh_size_floor() -> int:
    """Extract the byte-size floor from find-python.sh's ``-lt 1024`` guard."""
    text = _FIND_PYTHON_SH.read_text(encoding="utf-8")
    match = re.search(r'"\$_frp_size"\s*-lt\s*(\d+)', text)
    assert match is not None, "size floor not found in find-python.sh"
    return int(match.group(1))


def _ps1_size_floor() -> int:
    """Extract the byte-size floor from find-python.ps1's ``.Length -lt 1024``."""
    text = _FIND_PYTHON_PS1.read_text(encoding="utf-8")
    match = re.search(r"\.Length\s*-lt\s*(\d+)", text)
    assert match is not None, "size floor not found in find-python.ps1"
    return int(match.group(1))


def _sh_version_floor() -> tuple[int, int]:
    """Extract the ``(major, minor)`` floor defaults from find-python.sh."""
    text = _FIND_PYTHON_SH.read_text(encoding="utf-8")
    major = re.search(r'_frp_min_major="\$\{1:-(\d+)\}"', text)
    minor = re.search(r'_frp_min_minor="\$\{2:-(\d+)\}"', text)
    assert major is not None, "major version-floor default not found in find-python.sh"
    assert minor is not None, "minor version-floor default not found in find-python.sh"
    return int(major.group(1)), int(minor.group(1))


def _ps1_version_floor() -> tuple[int, int]:
    """Extract the ``(MinMajor, MinMinor)`` param defaults from find-python.ps1."""
    text = _FIND_PYTHON_PS1.read_text(encoding="utf-8")
    major = re.search(r"\[int\]\$MinMajor\s*=\s*(\d+)", text)
    minor = re.search(r"\[int\]\$MinMinor\s*=\s*(\d+)", text)
    assert major is not None, "MinMajor default not found in find-python.ps1"
    assert minor is not None, "MinMinor default not found in find-python.ps1"
    return int(major.group(1)), int(minor.group(1))


def test_candidate_names_agree_across_all_three() -> None:
    """All three locators probe the identical candidate names in the same order."""
    sh_names = _sh_candidate_names()
    ps1_names = _ps1_candidate_names()
    py_names = tuple(_CANDIDATE_NAMES)

    assert sh_names == py_names, (
        f"find-python.sh candidate list {sh_names} diverges from "
        f"python_resolver._CANDIDATE_NAMES {py_names}"
    )
    assert ps1_names == py_names, (
        f"find-python.ps1 candidate list {ps1_names} diverges from "
        f"python_resolver._CANDIDATE_NAMES {py_names}"
    )


def test_size_floor_agrees_across_all_three() -> None:
    """All three locators reject sub-floor interpreter stubs at the same byte count."""
    assert _sh_size_floor() == _MIN_INTERPRETER_BYTES, (
        f"find-python.sh size floor {_sh_size_floor()} != "
        f"python_resolver._MIN_INTERPRETER_BYTES {_MIN_INTERPRETER_BYTES}"
    )
    assert _ps1_size_floor() == _MIN_INTERPRETER_BYTES, (
        f"find-python.ps1 size floor {_ps1_size_floor()} != "
        f"python_resolver._MIN_INTERPRETER_BYTES {_MIN_INTERPRETER_BYTES}"
    )


def test_version_floor_agrees_across_all_three() -> None:
    """All three locators enforce the same ``>= 3.10`` version floor."""
    py_floor = (MIN_MAJOR, MIN_MINOR)
    assert _sh_version_floor() == py_floor, (
        f"find-python.sh version floor {_sh_version_floor()} != "
        f"python_resolver floor {py_floor}"
    )
    assert _ps1_version_floor() == py_floor, (
        f"find-python.ps1 version floor {_ps1_version_floor()} != "
        f"python_resolver floor {py_floor}"
    )
