# SPDX-License-Identifier: MIT

"""Tests for the find-python POSIX locator's empty-PATH-segment hardening.

``src/apothem/hooks/lib/find-python.sh`` lists every executable matching a
candidate name across ``PATH`` (the ``type -ap`` analogue). Its internal
``_find_python_path_candidates`` walker SKIPS empty ``PATH`` segments rather
than resolving them to the current directory: the locator's result is
version-probed (executed) and wired into the hook command that runs on every
tool use, so an attacker-planted ``python`` in cwd must never be discoverable
through a doubled / leading / trailing ``:`` separator. The POSIX
empty-segment-to-cwd convention is the footgun this guard closes.

The walker is exercised via subprocess (sourcing the locator under bash),
mirroring ``tests/hooks/test_find_pwsh_locator.py``. The PowerShell sibling
``find-python.ps1`` delegates to ``Get-Command``, which never resolves an empty
PATH segment to cwd and never searches cwd implicitly, so it carries no
equivalent code path to harden or test.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from tests._shared.bash_resolver import SKIP_REASON, find_test_bash

REPO_ROOT = Path(__file__).resolve().parents[2]
LOCATOR_SH = REPO_ROOT / "src" / "apothem" / "hooks" / "lib" / "find-python.sh"

# Resolve a usable bash once at import time (on Windows a git-bash, never the
# WSL launcher), so subprocess finds it even when _list_candidates passes a
# restricted PATH env to the child.
_BASH: str | None = find_test_bash()


def _make_executable(directory: Path, name: str = "python3") -> Path:
    """Create a small executable named *name* in *directory*."""
    directory.mkdir(parents=True, exist_ok=True)
    binary = directory / name
    binary.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    binary.chmod(0o755)
    return binary


def _list_candidates(path_value: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    """Source find-python.sh and list ``python3`` candidates under *path_value*."""
    if _BASH is None:
        pytest.skip(SKIP_REASON)
    env = {"PATH": path_value}
    if "SYSTEMROOT" in os.environ:
        env["SYSTEMROOT"] = os.environ["SYSTEMROOT"]
    script = f". {LOCATOR_SH.as_posix()} && _find_python_path_candidates python3"
    return subprocess.run(
        [_BASH, "-c", script],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(cwd),
        check=False,
    )


def test_empty_segment_skipped_but_explicit_dot_honored(tmp_path: Path) -> None:
    """An empty PATH segment is skipped; an explicit '.' entry is still honored.

    The two halves form a self-validating contrast: the same cwd interpreter is
    discoverable through a non-empty ``.`` entry but NOT through an empty
    segment, proving only the cwd-from-empty-segment behavior changed.
    """
    _make_executable(tmp_path, "python3")

    # Control: an explicit "." entry resolves the cwd interpreter. This also
    # establishes that the host shell reports the cwd file as executable under
    # ``[ -x ]`` — the precondition the empty-segment contrast depends on.
    baseline = _list_candidates(".", cwd=tmp_path)
    if "python3" not in baseline.stdout:
        pytest.skip(
            "host shell does not report the cwd file as executable under [ -x ]; "
            "the empty-segment contrast is untestable here"
        )
    assert baseline.returncode == 0

    # The fix: a doubled (empty) PATH segment is SKIPPED, not resolved to cwd,
    # so the same cwd interpreter is not discovered through it. The two probe
    # directories do not exist, so the only would-be match is cwd via the empty
    # middle segment.
    hardened = _list_candidates("/nonexistent_a::/nonexistent_b", cwd=tmp_path)
    assert hardened.returncode == 0
    assert hardened.stdout.strip() == "", (
        "an empty PATH segment was resolved to cwd; the cwd interpreter must be "
        f"skipped (got: {hardened.stdout!r})"
    )
